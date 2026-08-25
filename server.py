"""
PBI CLI Chat — Web server
Serves the chat UI and proxies messages to Claude CLI (with pbi-cli skills).
Supports both local and cloud (Cloudera AI Workbench) deployment.
"""

import http.server
import json
import subprocess
import os
import sys
import threading
import webbrowser
import time
import signal
import tempfile
import argparse
import uuid
import io
import zipfile
import stat
from pathlib import Path

from usage_logger import ChatLogger
from business_report import (
    build_business_prompt,
    collect_pbip_context,
    inspect_pbip_project,
    parse_business_analysis,
    render_business_html,
)

# ─── Environment Detection ──────────────────────────────────────────────
def is_cloud():
    """Detect if running in Cloudera AI Workbench."""
    return os.environ.get("CLOUD_MODE", "").lower() == "true" or \
           os.environ.get("CDSW_APP_PORT") is not None

def load_env():
    """Load .env file if exists."""
    env_path = Path(BASE_DIR) / ".env"
    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, val = line.split('=', 1)
                    os.environ.setdefault(key.strip(), val.strip())

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
CONFIG_LOCAL_FILE = os.path.join(BASE_DIR, "config.local.json")

# Load environment variables
load_env()

CLOUD_MODE = is_cloud()
PORT = int(os.environ.get("CDSW_APP_PORT", os.environ.get("PORT", "5174")))
PROJECT_DIR = os.path.abspath(os.environ.get(
    "PBI_PROJECT_DIR",
    BASE_DIR if CLOUD_MODE else os.path.dirname(BASE_DIR),
))

# ─── Usage logger (singleton) ──────────────────────────────────────────────
chat_logger = ChatLogger()

# ─── Tone system prompts ────────────────────────────────────────────────────
TONE_PROMPTS = {
    "porteno": (
        "INSTRUCCION OBLIGATORIA DE IDIOMA Y TONO: "
        "Responde SIEMPRE en espanol rioplatense (porteno). "
        "Usa voseo en todo momento (vos, tenes, podes, fijate, hacelo). "
        "Se relajado y cercano, como un colega de laburo. "
        "Evita el tuteo (tu, tienes, puedes) y el ustedeo. "
        "Usa expresiones naturales del habla portena cuando corresponda. "
        "Nunca cambies a ingles salvo para nombres de comandos o codigo.\n\n"
    ),
    "formal": (
        "INSTRUCCION OBLIGATORIA DE IDIOMA Y TONO: "
        "Responde SIEMPRE en espanol formal y profesional. "
        "Usa usted en todo momento. "
        "Mantene un tono tecnico, preciso y respetuoso. "
        "Nunca cambies a ingles salvo para nombres de comandos o codigo.\n\n"
    ),
    "neutral": (
        "INSTRUCCION OBLIGATORIA DE IDIOMA Y TONO: "
        "Responde SIEMPRE en espanol neutro, claro y directo. "
        "Usa un tono profesional pero accesible. "
        "Se conciso y ve al grano. "
        "Nunca cambies a ingles salvo para nombres de comandos o codigo.\n\n"
    ),
}

# ─── Find Claude CLI ────────────────────────────────────────────────────────
import shutil

CLAUDE_PATH = None
CLAUDE_AVAILABLE = False

# Try to find Claude CLI
for candidate in filter(None, [
    os.environ.get("CLAUDE_CLI_PATH"),
    os.path.expanduser("~/OneDrive - YPF/Claude tests/node-v22.19.0-win-x64/claude.cmd"),
    "claude.cmd",
    "claude",
    "/usr/local/bin/claude",
    "/usr/bin/claude",
    os.path.expanduser("~/.local/bin/claude"),
]):
    if os.path.isfile(candidate):
        CLAUDE_PATH = candidate
        CLAUDE_AVAILABLE = True
        break
    found = shutil.which(candidate)
    if found:
        CLAUDE_PATH = found
        CLAUDE_AVAILABLE = True
        break

if CLAUDE_AVAILABLE:
    print(f"[OK] Claude CLI: {CLAUDE_PATH}")
else:
    print("[INFO] Claude CLI no encontrado; comprobando proveedor Foundry.")

# Direct Microsoft Foundry provider for environments without Claude CLI.
FOUNDRY_AVAILABLE = False
AnthropicFoundry = None
if os.environ.get("ANTHROPIC_FOUNDRY_BASE_URL") and os.environ.get("ANTHROPIC_FOUNDRY_API_KEY"):
    try:
        from anthropic import AnthropicFoundry as _AnthropicFoundry
        AnthropicFoundry = _AnthropicFoundry
        FOUNDRY_AVAILABLE = True
        print("[OK] Microsoft Foundry SDK configurado")
    except ImportError as e:
        print(f"[WARN] SDK de Anthropic no disponible: {e}")

if not CLAUDE_AVAILABLE and not FOUNDRY_AVAILABLE:
    print("[WARN] No hay un proveedor de IA configurado.")

FOUNDRY_SESSIONS = {}
FOUNDRY_SESSIONS_LOCK = threading.Lock()
POWER_BI_SKILLS = (
    "power-bi-custom-visuals", "power-bi-dax", "power-bi-deployment",
    "power-bi-diagnostics", "power-bi-docs", "power-bi-filters",
    "power-bi-modeling", "power-bi-pages", "power-bi-partitions",
    "power-bi-report", "power-bi-security", "power-bi-themes",
    "power-bi-visuals",
)


def serialize_foundry_content_block(block):
    """Return only fields accepted by the Messages API on a later turn.

    SDK response models can contain response-only fields such as
    ``parsed_output``. Replaying model_dump() verbatim makes Foundry reject the
    second request with HTTP 400.
    """
    raw = block if isinstance(block, dict) else block.model_dump(mode="json")
    block_type = raw.get("type")
    allowed_fields = {
        "text": ("type", "text"),
        "tool_use": ("type", "id", "name", "input"),
        "tool_result": ("type", "tool_use_id", "content", "is_error"),
    }
    fields = allowed_fields.get(block_type)
    if not fields:
        return None
    return {key: raw[key] for key in fields if key in raw}


def sanitize_foundry_messages(messages):
    """Sanitize persisted conversation history before sending it to Foundry."""
    clean = []
    for message in messages:
        if not isinstance(message, dict) or message.get("role") not in ("user", "assistant"):
            continue
        content = message.get("content")
        if isinstance(content, str):
            clean.append({"role": message["role"], "content": content})
            continue
        if isinstance(content, list):
            blocks = [serialize_foundry_content_block(block) for block in content]
            blocks = [block for block in blocks if block]
            if blocks:
                clean.append({"role": message["role"], "content": blocks})
    return clean


def add_message_usage(accumulator, message):
    """Accumulate provider-reported token usage from an Anthropic message."""
    usage = getattr(message, "usage", None)
    if not usage:
        return
    for key in (
        "input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"
    ):
        value = getattr(usage, key, 0) or 0
        accumulator[key] = accumulator.get(key, 0) + int(value)
    accumulator["source"] = "provider"
    accumulator["total_tokens"] = sum(
        int(accumulator.get(key) or 0) for key in (
            "input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"
        )
    )

print(f"[OK] Proyecto: {PROJECT_DIR}")
print(f"[OK] Modo: {'CLOUD' if CLOUD_MODE else 'LOCAL'}")

# ─── Configuration helpers ──────────────────────────────────────────────────
def load_config():
    """Load public defaults, overridden by the ignored local config."""
    config = {"pbip_project_path": None, "search_directories": []}
    for config_path in (CONFIG_FILE, CONFIG_LOCAL_FILE):
        try:
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config.update(json.load(f))
        except Exception as e:
            print(f"[WARN] No se pudo leer {os.path.basename(config_path)}: {e}")
    return config

def save_config(config):
    """Save machine-specific configuration outside version control."""
    try:
        with open(CONFIG_LOCAL_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[ERROR] No se pudo guardar config.json: {e}")
        return False

def validate_pbip_project(pbip_path):
    """Validate that a .pbip file and its referenced project artifacts exist."""
    pbip_path = Path(pbip_path)
    if not pbip_path.is_file() or pbip_path.suffix.lower() != ".pbip":
        return False, ["No es un archivo .pbip valido."]
    try:
        data = json.loads(pbip_path.read_text(encoding="utf-8-sig"))
    except Exception as e:
        return False, [f"No se pudo leer el PBIP: {e}"]

    referenced_paths = []
    for artifact in data.get("artifacts", []):
        if not isinstance(artifact, dict):
            continue
        for artifact_data in artifact.values():
            if isinstance(artifact_data, dict) and artifact_data.get("path"):
                referenced_paths.append(artifact_data["path"])
    if not referenced_paths:
        return False, ["El PBIP no declara artifacts."]

    missing = []
    for relative_path in referenced_paths:
        artifact_path = (pbip_path.parent / relative_path).resolve()
        if not artifact_path.exists():
            missing.append(relative_path)
    if missing:
        return False, [f"Falta el artifact: {path}" for path in missing]
    return True, []

def get_pbip_search_paths():
    """Get list of directories to search for .pbip files.
    Priority:
    1. PBIP_PROJECT_PATH env var (if file exists)
    2. pbip_project_path from config.json (if file exists)
    3. search_directories from config.json
    4. PROJECT_DIR (default fallback)
    """
    paths = []

    # 1. Check environment variable
    env_path = os.environ.get("PBIP_PROJECT_PATH")
    if env_path and os.path.exists(env_path):
        paths.append(env_path)

    # 2. Check config file
    config = load_config()
    config_path = config.get("pbip_project_path")
    if config_path and os.path.exists(config_path):
        paths.append(config_path)

    # 3. Add search directories from config
    for dir_path in config.get("search_directories", []):
        if os.path.isdir(dir_path):
            paths.append(dir_path)

    # 4. Default fallback
    if PROJECT_DIR not in paths:
        paths.append(PROJECT_DIR)

    return paths


# ─── Stream-JSON parser ─────────────────────────────────────────────────────
def parse_stream_json(output):
    """Parse stream-json output from Claude CLI.
    Returns (response_text, session_id)."""
    text_parts = []
    session_id = None

    for line in output.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            # Extract session ID from any event that has it
            if event.get("session_id") and not session_id:
                session_id = event["session_id"]
            # Extract text from assistant messages
            if event.get("type") == "assistant":
                msg = event.get("message", {})
                for block in msg.get("content", []):
                    if block.get("type") == "text":
                        text_parts.append(block["text"])
            # Extract from result events
            if event.get("type") == "result":
                result_text = event.get("result", "")
                if result_text and result_text not in text_parts:
                    text_parts.append(result_text)
        except json.JSONDecodeError:
            continue

    return "\n".join(text_parts), session_id


class ChatHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def _request_username(self):
        """Resolve the authenticated user forwarded by Cloudera's proxy."""
        for header in (
            "X-Forwarded-User", "X-Authenticated-User", "X-CDSW-User",
            "X-Cloudera-User", "Remote-User", "X-Forwarded-Email",
        ):
            value = self.headers.get(header)
            if value:
                return value.split(",", 1)[0].strip().lower()
        for env_name in ("CDSW_USER", "CDSW_PROJECT_USER", "PROJECT_OWNER", "USERNAME", "USER"):
            value = os.environ.get(env_name)
            if value:
                return value.strip().lower()
        return "unknown"

    def _active_project_name(self):
        configured_pbip = load_config().get("pbip_project_path")
        if configured_pbip and validate_pbip_project(configured_pbip)[0]:
            return Path(configured_pbip).stem
        return None

    def do_POST(self):
        if self.path == "/api/chat/stream":
            self._handle_chat_stream()
        elif self.path == "/api/chat":
            self._handle_chat()
        elif self.path == "/api/pbi":
            self._handle_pbi()
        elif self.path == "/api/set-pbip-path":
            self._handle_set_pbip_path()
        elif self.path == "/api/switch-connection":
            self._handle_switch_connection()
        elif self.path == "/api/upload-pbip":
            self._handle_upload_pbip()
        elif self.path == "/api/export-business-report":
            self._handle_export_business_report()
        elif self.path == "/api/discover-pbip":
            self._handle_discover_pbip()
        else:
            self.send_error(404)

    def do_GET(self):
        if self.path == "/" or self.path == "":
            self.path = "/index.html"
        elif self.path == "/api/status":
            self._handle_status()
            return
        elif self.path == "/api/auth":
            self._handle_auth()
            return
        elif self.path == "/api/usage-stats":
            self._handle_usage_stats()
            return
        elif self.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        super().do_GET()

    def guess_type(self, path):
        """Ensure HTML is served with UTF-8 charset."""
        mime = super().guess_type(path)
        if mime == "text/html":
            return "text/html; charset=utf-8"
        return mime

    def end_headers(self):
        """Prevent stale UI assets after a Cloudera redeployment."""
        if self.command == "GET" and not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.send_header("Pragma", "no-cache")
            self.send_header("Expires", "0")
        super().end_headers()

    def _handle_status(self):
        """Return granular status: pbi-cli installed, PBI connected, report found."""
        status = {
            "pbi_installed": False,
            "pbi_connected": False,
            "connection_name": None,
            "report_found": False,
            "report_path": None,
        }

        # 1. Check pbi-cli is installed
        try:
            r = subprocess.run(
                "pbi --version",
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=10,
                cwd=PROJECT_DIR, shell=True,
            )
            if r.returncode == 0 and r.stdout.strip():
                status["pbi_installed"] = True
                status["pbi_version"] = r.stdout.strip()
        except Exception:
            pass

        # 2. Check active PBI Desktop connection(s)
        try:
            # Get last active connection
            r = subprocess.run(
                "pbi --json connections last",
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=10,
                cwd=PROJECT_DIR, shell=True,
            )
            if r.returncode == 0 and r.stdout.strip():
                data = json.loads(r.stdout)
                if data.get("name"):
                    status["pbi_connected"] = True
                    status["connection_name"] = data["name"]
                    status["connection_port"] = data.get("port")

                    # Try to get the report name from Power BI Desktop window title
                    try:
                        # Get window title from PBIDesktop.exe process
                        # Use cp850 encoding which is the default for Spanish Windows console
                        window_title_cmd = subprocess.run(
                            ['tasklist', '/FI', 'IMAGENAME eq PBIDesktop.exe', '/V', '/FO', 'CSV'],
                            capture_output=True, text=True, encoding="cp850",
                            errors="replace", timeout=5,
                        )
                        if window_title_cmd.returncode == 0 and window_title_cmd.stdout.strip():
                            import csv
                            from io import StringIO

                            # Parse CSV output
                            csv_reader = csv.DictReader(StringIO(window_title_cmd.stdout))
                            for row in csv_reader:
                                # Try to get window title using various column name variations
                                window_title = ""
                                for key in row.keys():
                                    if "tulo" in key.lower() and "ventana" in key.lower():  # Matches "Título de ventana"
                                        window_title = row[key].strip()
                                        break
                                if not window_title:  # Fallback for English
                                    window_title = row.get("Window Title", "").strip()

                                # Skip processes without window title or with system titles
                                if window_title and window_title not in ["N/A", "No aplicable", ""]:
                                    # Remove " - Power BI Desktop" suffix if present
                                    if " - Power BI Desktop" in window_title:
                                        window_title = window_title.replace(" - Power BI Desktop", "")
                                    # Remove "*" (unsaved changes indicator) if present
                                    window_title = window_title.replace("*", "").strip()

                                    if window_title:
                                        status["report_found"] = True
                                        status["report_name"] = window_title
                                        status["report_source"] = "window_title"
                                        print(f"[DEBUG] Detected file name from window: {window_title}")
                                        break
                    except Exception as e:
                        # Log error for debugging
                        print(f"[DEBUG] Error getting window title: {e}")
                        import traceback
                        traceback.print_exc()
                        pass

                    # Fallback: try to get the database name from the active connection
                    if not status["report_found"]:
                        try:
                            db_list = subprocess.run(
                                "pbi --json database list",
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=10,
                                cwd=PROJECT_DIR, shell=True,
                            )
                            if db_list.returncode == 0 and db_list.stdout.strip():
                                db_data = json.loads(db_list.stdout)
                                # database list returns an array of databases
                                # For Power BI Desktop, typically there's only one database
                                if isinstance(db_data, list) and len(db_data) > 0:
                                    # Get the first database name (usually the report name)
                                    db_name = db_data[0].get("name") or db_data[0].get("Name")
                                    if db_name:
                                        status["report_found"] = True
                                        status["report_name"] = db_name
                                        status["report_source"] = "database_name"
                        except Exception:
                            pass
        except Exception:
            pass

        # Get all available connections
        try:
            r = subprocess.run(
                "pbi --json connections list",
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=10,
                cwd=PROJECT_DIR, shell=True,
            )
            if r.returncode == 0 and r.stdout.strip():
                connections_data = json.loads(r.stdout)
                if isinstance(connections_data, list):
                    status["all_connections"] = connections_data
                    status["multiple_connections"] = len(connections_data) > 1
        except Exception:
            pass

        # 3. Check for PBIR report project in configured paths (only if not found from active connection)
        if not status["report_found"]:
            try:
                from pathlib import Path
                search_paths = get_pbip_search_paths()

                for search_path in search_paths:
                    search_path_obj = Path(search_path)

                    # If it's a direct .pbip file
                    if search_path_obj.is_file() and search_path_obj.suffix.lower() == ".pbip":
                        complete, issues = validate_pbip_project(search_path_obj)
                        if complete:
                            status["report_found"] = True
                            status["report_path"] = str(search_path_obj)
                            status["report_name"] = search_path_obj.stem
                            status["report_source"] = "pbip_project"
                            break
                        status["pbip_incomplete"] = True
                        status["pbip_issues"] = issues

                    # If it's a directory, search for *.Report or *.pbip
                    if search_path_obj.is_dir():
                        # Look for *.Report/definition/report.json
                        for p in search_path_obj.rglob("*.Report"):
                            defn = p / "definition" / "report.json"
                            if defn.exists():
                                status["report_found"] = True
                                status["report_path"] = str(p)
                                status["report_name"] = p.parent.name if p.parent != search_path_obj else p.name
                                status["report_source"] = "pbip_folder"
                                break

                        # Look for *.pbip files
                        if not status["report_found"]:
                            for p in search_path_obj.glob("*.pbip"):
                                status["report_found"] = True
                                status["report_path"] = str(p)
                                status["report_name"] = p.stem
                                status["report_source"] = "pbip_file"
                                break

                    if status["report_found"]:
                        break

                # If no PBIP found, suggest conversion
                if not status["report_found"] and status["pbi_connected"]:
                    status["suggest_conversion"] = True
                    status["search_paths"] = [str(p) for p in search_paths[:3]]  # Show first 3
            except Exception as e:
                status["error"] = str(e)
                pass

        self._json_response(status)

    def _handle_chat(self):
        """Send user message to Claude CLI with session persistence."""
        # Check if Claude CLI is available
        if not CLAUDE_AVAILABLE:
            self._json_response({
                "response": "⚠️ **Claude CLI no está configurado**\n\n"
                           "Para habilitar el chat con Claude AI:\n\n"
                           "1. Instalar Claude CLI en el entorno\n"
                           "2. O configurar variable de entorno `CLAUDE_CLI_PATH`\n\n"
                           "Mientras tanto, puedes usar las funcionalidades de análisis masivo de PBIP.",
                "session_id": None,
            })
            return

        body = self._read_body()
        user_msg = body.get("message", "")
        tone = body.get("tone", "porteno")
        session_id = body.get("session_id")  # None on first message

        if not user_msg:
            self._json_response({"error": "Mensaje vacio"}, status=400)
            return

        temp_files = []
        try:
            # Write user message to temp file (stdin redirection)
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="utf-8"
            ) as f:
                f.write(user_msg)
                user_temp = f.name
                temp_files.append(user_temp)

            # Build command based on whether we have a session
            base_flags = '--print --verbose --output-format stream-json --dangerously-skip-permissions'

            if session_id:
                # RESUME existing conversation — Claude already has full context
                cmd = f'"{CLAUDE_PATH}" --resume {session_id} {base_flags} < "{user_temp}"'
            else:
                # NEW conversation — include tone as system prompt
                tone_instruction = TONE_PROMPTS.get(tone, TONE_PROMPTS["porteno"])
                system_prompt = (
                    tone_instruction +
                    "\nEl usuario tiene Power BI Desktop abierto con un modelo/reporte. "
                    "Esta usando pbi-cli.\n\n"
                    "RESTRICCION CRITICA: Solo podes responder consultas relacionadas con Power BI, "
                    "modelos semanticos, DAX, reportes, visualizaciones, datos y analisis de reportes. "
                    "Si el usuario pregunta algo que NO tiene relacion con Power BI o analisis de datos, "
                    "responde amablemente que solo podes ayudar con temas de Power BI y reportes."
                )
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".txt", delete=False, encoding="utf-8"
                ) as f:
                    f.write(system_prompt)
                    system_temp = f.name
                    temp_files.append(system_temp)

                cmd = f'"{CLAUDE_PATH}" {base_flags} --append-system-prompt-file "{system_temp}" < "{user_temp}"'

            print(f"[CHAT] session={session_id or 'NEW'} msg={user_msg[:60]}...")
            start_time = time.time()

            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=PROJECT_DIR,
                timeout=300,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )

            # Debug: log raw output for troubleshooting
            if result.returncode != 0:
                print(f"[CHAT] CLI exit code: {result.returncode}")
            if result.stderr:
                print(f"[CHAT] stderr: {result.stderr[:300]}")
            raw_len = len(result.stdout or '')
            print(f"[CHAT] raw stdout: {raw_len} chars")
            if raw_len < 500:
                print(f"[CHAT] stdout preview: {result.stdout[:500]}")

            # Parse stream-json to extract text and session_id
            response_text, new_session_id = parse_stream_json(result.stdout)

            # Fallback: if stream-json parsing failed, try raw stdout
            if not response_text:
                response_text = result.stdout.strip()
            if not response_text and result.stderr:
                response_text = f"Error: {result.stderr.strip()}"

            duration_ms = int((time.time() - start_time) * 1000)
            print(f"[CHAT] session={new_session_id or session_id} response={len(response_text or '')} chars ({duration_ms}ms)")

            # Log usage event
            chat_logger.log_chat(
                user_msg=user_msg,
                response_len=len(response_text or ''),
                duration_ms=duration_ms,
                tone=tone,
                cli_session=new_session_id or session_id,
                username=self._request_username(),
                project=self._active_project_name(),
            )

            self._json_response({
                "response": response_text or "Sin respuesta.",
                "session_id": new_session_id or session_id,
            })

        except subprocess.TimeoutExpired:
            self._json_response({"response": "La consulta tardo mas de 5 minutos. Intenta con algo mas especifico o dividila en pasos."})
        except Exception as e:
            self._json_response({"error": str(e)}, status=500)
        finally:
            for f in temp_files:
                try:
                    os.unlink(f)
                except OSError:
                    pass

    def _handle_chat_stream(self):
        """Stream Claude CLI output to the browser as Server-Sent Events."""
        request_started = time.perf_counter()
        if not CLAUDE_AVAILABLE:
            if FOUNDRY_AVAILABLE:
                self._handle_foundry_stream(request_started)
                return
            self._json_response({"error": "Claude CLI no esta configurado"}, status=503)
            return

        body = self._read_body()
        user_msg = body.get("message", "")
        tone = body.get("tone", "porteno")
        session_id = body.get("session_id")
        if not user_msg:
            self._json_response({"error": "Mensaje vacio"}, status=400)
            return

        temp_files = []
        process = None
        timed_out = threading.Event()

        def send_event(event_type, **data):
            payload = json.dumps({"type": event_type, **data}, ensure_ascii=False)
            self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
            self.wfile.flush()

        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="utf-8"
            ) as f:
                f.write(user_msg)
                user_temp = f.name
                temp_files.append(user_temp)

            base_flags = (
                "--print --verbose --output-format stream-json "
                "--include-partial-messages --dangerously-skip-permissions"
            )
            if session_id:
                cmd = f'"{CLAUDE_PATH}" --resume {session_id} {base_flags} < "{user_temp}"'
            else:
                tone_instruction = TONE_PROMPTS.get(tone, TONE_PROMPTS["porteno"])
                system_prompt = (
                    tone_instruction
                    + "\nEl usuario tiene Power BI Desktop abierto con un modelo/reporte. "
                    "Esta usando pbi-cli.\n\n"
                    "RESTRICCION CRITICA: Solo podes responder consultas relacionadas con Power BI, "
                    "modelos semanticos, DAX, reportes, visualizaciones, datos y analisis de reportes. "
                    "Si el usuario pregunta algo que NO tiene relacion con Power BI o analisis de datos, "
                    "responde amablemente que solo podes ayudar con temas de Power BI y reportes."
                )
                with tempfile.NamedTemporaryFile(
                    mode="w", suffix=".txt", delete=False, encoding="utf-8"
                ) as f:
                    f.write(system_prompt)
                    system_temp = f.name
                    temp_files.append(system_temp)
                cmd = f'"{CLAUDE_PATH}" {base_flags} --append-system-prompt-file "{system_temp}" < "{user_temp}"'

            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-transform")
            # The response has no Content-Length; closing it after `done` is
            # how HTTP/1.0 clients and proxies detect the end of the stream.
            self.send_header("Connection", "close")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            self.close_connection = True
            send_event("start", session_id=session_id)
            send_event("status", message="Iniciando asistente...")

            print(f"[CHAT STREAM] session={session_id or 'NEW'} msg={user_msg[:60]}...")
            start_time = time.time()
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=PROJECT_DIR,
                bufsize=1,
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            cli_start_ms = int((time.perf_counter() - request_started) * 1000)
            send_event("status", message="Analizando la consulta...")

            stderr_parts = []
            stderr_thread = threading.Thread(
                target=lambda: stderr_parts.extend(process.stderr.readlines()), daemon=True
            )
            stderr_thread.start()

            def stop_on_timeout():
                timed_out.set()
                if process.poll() is None:
                    process.kill()

            timer = threading.Timer(300, stop_on_timeout)
            timer.daemon = True
            timer.start()

            response_parts = []
            fallback_text = ""
            new_session_id = session_id
            emitted_deltas = False
            first_event_ms = None
            first_token_ms = None

            for raw_line in process.stdout:
                try:
                    event = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                elapsed_ms = int((time.perf_counter() - request_started) * 1000)
                if first_event_ms is None:
                    first_event_ms = elapsed_ms

                if event.get("session_id"):
                    new_session_id = event["session_id"]

                if event.get("type") == "stream_event":
                    inner = event.get("event", {})
                    delta = inner.get("delta", {})
                    if inner.get("type") == "content_block_delta" and delta.get("type") == "text_delta":
                        text_delta = delta.get("text", "")
                        if text_delta:
                            if first_token_ms is None:
                                first_token_ms = elapsed_ms
                            emitted_deltas = True
                            response_parts.append(text_delta)
                            send_event("delta", text=text_delta, session_id=new_session_id)
                    elif inner.get("type") == "content_block_start":
                        block = inner.get("content_block", {})
                        if block.get("type") == "tool_use":
                            tool_name = block.get("name", "herramienta")
                            send_event(
                                "status",
                                message=f"Consultando Power BI ({tool_name})...",
                                tool=tool_name,
                            )
                elif event.get("type") == "assistant":
                    blocks = event.get("message", {}).get("content", [])
                    tool_blocks = [block for block in blocks if block.get("type") == "tool_use"]
                    if tool_blocks:
                        tool_name = tool_blocks[-1].get("name", "herramienta")
                        send_event(
                            "status",
                            message=f"Consultando Power BI ({tool_name})...",
                            tool=tool_name,
                        )
                    assistant_text = "".join(
                        block.get("text", "") for block in blocks if block.get("type") == "text"
                    )
                    if assistant_text:
                        fallback_text = assistant_text
                elif event.get("type") == "result" and event.get("result"):
                    fallback_text = event["result"]

            process.wait()
            timer.cancel()
            stderr_thread.join(timeout=1)

            if timed_out.is_set():
                send_event("error", error="La consulta tardo mas de 5 minutos.")
                return
            if process.returncode != 0:
                error_text = "".join(stderr_parts).strip() or f"Claude CLI finalizo con codigo {process.returncode}"
                send_event("error", error=error_text[:1000])
                return
            if not emitted_deltas and fallback_text:
                first_token_ms = int((time.perf_counter() - request_started) * 1000)
                response_parts.append(fallback_text)
                send_event("delta", text=fallback_text, session_id=new_session_id)

            response_text = "".join(response_parts)
            duration_ms = int((time.time() - start_time) * 1000)
            total_ms = int((time.perf_counter() - request_started) * 1000)
            latency = {
                "cli_start_ms": cli_start_ms,
                "first_event_ms": first_event_ms,
                "first_token_ms": first_token_ms,
                "total_ms": total_ms,
            }
            chat_logger.log_chat(
                user_msg=user_msg,
                response_len=len(response_text),
                duration_ms=duration_ms,
                tone=tone,
                cli_session=new_session_id,
                latency=latency,
                username=self._request_username(),
                project=self._active_project_name(),
            )
            print(f"[CHAT STREAM] session={new_session_id} response={len(response_text)} chars ({duration_ms}ms)")
            send_event("done", session_id=new_session_id, latency=latency)

        except (BrokenPipeError, ConnectionResetError):
            if process and process.poll() is None:
                process.kill()
            print("[CHAT STREAM] browser disconnected")
        except Exception as e:
            try:
                send_event("error", error=str(e))
            except (BrokenPipeError, ConnectionResetError):
                pass
        finally:
            if process and process.poll() is None:
                process.kill()
            for f in temp_files:
                try:
                    os.unlink(f)
                except OSError:
                    pass

    def _handle_foundry_stream(self, request_started):
        """Stream responses from Microsoft Foundry using the Anthropic SDK."""
        body = self._read_body()
        user_msg = body.get("message", "")
        tone = body.get("tone", "porteno")
        session_id = body.get("session_id") or str(uuid.uuid4())
        if not user_msg:
            self._json_response({"error": "Mensaje vacio"}, status=400)
            return

        def send_event(event_type, **data):
            payload = json.dumps({"type": event_type, **data}, ensure_ascii=False)
            self.wfile.write(f"data: {payload}\n\n".encode("utf-8"))
            self.wfile.flush()

        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-transform")
            self.send_header("Connection", "close")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()
            self.close_connection = True
            send_event("start", session_id=session_id)
            send_event("status", message="Conectando con Foundry...")

            with FOUNDRY_SESSIONS_LOCK:
                messages = sanitize_foundry_messages(FOUNDRY_SESSIONS.get(session_id, []))
            messages.append({"role": "user", "content": user_msg})

            system_prompt = (
                TONE_PROMPTS.get(tone, TONE_PROMPTS["porteno"])
                + "Sos un asistente especializado exclusivamente en Power BI, modelos semanticos, "
                "DAX, PBIP, reportes y analisis de datos. Si una consulta no esta relacionada, "
                "explica amablemente esa limitacion. Estas ejecutandote en Cloudera sobre Linux. "
                "No podes acceder al Power BI Desktop de la PC del usuario; trabaja con archivos "
                "disponibles en el directorio del proyecto. En modo PBIP offline, usa primero "
                "inspect_active_pbip para estadisticas, tablas, medidas, relaciones y archivos. "
                "No intentes comandos de conexion a Power BI Desktop, database o DAX execute. "
                "Usa read_powerbi_skill y run_pbi_cli solamente para operaciones de archivo que la "
                "skill confirme como compatibles con PBIP offline. No narres cada intento: llama a "
                "la herramienta directamente y entrega una respuesta consolidada. Si una herramienta "
                "falla, no pruebes variantes repetitivas; explica la limitacion y continua con la "
                "evidencia disponible. Pedi un archivo PBIP si el analisis requiere uno y no esta disponible. "
                "Si el usuario pide un informe ejecutivo, KPI o HTML, recordale que puede generarlo "
                "desde Configurar > Exportar informe KPI HTML con el PBIP activo."
            )
            config = load_config()
            configured_pbip = config.get("pbip_project_path")
            if configured_pbip:
                complete, issues = validate_pbip_project(configured_pbip)
                if complete:
                    system_prompt += (
                        f"\n\nPROYECTO PBIP ACTIVO: {configured_pbip}\n"
                        f"Directorio del proyecto: {Path(configured_pbip).parent}\n"
                        "Este archivo ya fue seleccionado por el usuario. No vuelvas a pedir su nombre o ruta. "
                        "Usalo directamente en las herramientas y explica que el modo es offline."
                    )
                else:
                    system_prompt += "\n\nNo hay un proyecto PBIP completo disponible: " + "; ".join(issues)
            tools = [
                {
                    "name": "inspect_active_pbip",
                    "description": (
                        "Inspecciona directamente el PBIP activo en modo offline. Devuelve estadisticas, "
                        "tablas, medidas, relaciones, paginas, visuales, advertencias y metadatos TMDL. "
                        "Es la herramienta principal para salud, documentacion y analisis del modelo en Cloudera."
                    ),
                    "input_schema": {"type": "object", "properties": {}},
                },
                {
                    "name": "read_powerbi_skill",
                    "description": "Lee las instrucciones instaladas de una skill especializada de Power BI.",
                    "input_schema": {
                        "type": "object",
                        "properties": {"name": {"type": "string", "enum": list(POWER_BI_SKILLS)}},
                        "required": ["name"],
                    },
                },
                {
                    "name": "run_pbi_cli",
                    "description": "Ejecuta pbi-cli de forma segura. Envia solamente los argumentos posteriores a pbi.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "arguments": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Ejemplo: [\"--json\", \"report\", \"info\", \"archivo.Report\"]",
                            }
                        },
                        "required": ["arguments"],
                    },
                },
            ]

            client = AnthropicFoundry(
                api_key=os.environ["ANTHROPIC_FOUNDRY_API_KEY"],
                base_url=os.environ["ANTHROPIC_FOUNDRY_BASE_URL"],
            )
            model = os.environ.get("ANTHROPIC_MODEL") or os.environ.get("ANTHROPIC_DEFAULT_SONNET_MODEL")
            provider_start_ms = int((time.perf_counter() - request_started) * 1000)
            first_event_ms = None
            first_token_ms = None
            response_parts = []
            tool_call_counts = {}
            tool_error_count = 0
            token_usage = {}
            send_event("status", message="Analizando la consulta...")

            for _ in range(8):
                round_parts = []
                with client.messages.stream(
                    model=model,
                    max_tokens=4096,
                    system=system_prompt,
                    messages=messages,
                    tools=tools,
                    timeout=300,
                ) as stream:
                    for text_delta in stream.text_stream:
                        elapsed_ms = int((time.perf_counter() - request_started) * 1000)
                        if first_event_ms is None:
                            first_event_ms = elapsed_ms
                        if first_token_ms is None:
                            first_token_ms = elapsed_ms
                        round_parts.append(text_delta)
                        response_parts.append(text_delta)
                        send_event("delta", text=text_delta, session_id=session_id)
                    final_message = stream.get_final_message()
                add_message_usage(token_usage, final_message)

                if first_event_ms is None:
                    first_event_ms = int((time.perf_counter() - request_started) * 1000)
                assistant_content = [
                    serialize_foundry_content_block(block) for block in final_message.content
                ]
                assistant_content = [block for block in assistant_content if block]
                messages.append({"role": "assistant", "content": assistant_content})
                tool_uses = [block for block in final_message.content if block.type == "tool_use"]
                if not tool_uses:
                    # Defensive fallback for SDKs that produced a final text block without text_stream deltas.
                    if not round_parts:
                        fallback = "".join(
                            block.text for block in final_message.content if block.type == "text"
                        )
                        if fallback:
                            if first_token_ms is None:
                                first_token_ms = int((time.perf_counter() - request_started) * 1000)
                            response_parts.append(fallback)
                            send_event("delta", text=fallback, session_id=session_id)
                    break

                tool_results = []
                for tool_use in tool_uses:
                    send_event(
                        "status",
                        message=f"Consultando Power BI ({tool_use.name})...",
                        tool=tool_use.name,
                    )
                    signature = tool_use.name + ":" + json.dumps(tool_use.input, sort_keys=True, ensure_ascii=False)
                    tool_call_counts[signature] = tool_call_counts.get(signature, 0) + 1
                    if tool_call_counts[signature] > 1:
                        result_text = (
                            "Esta misma herramienta ya fue ejecutada con estos argumentos. "
                            "No la repitas: responde ahora con la evidencia disponible."
                        )
                        is_error = True
                    else:
                        result_text, is_error = self._execute_foundry_tool(tool_use.name, tool_use.input)
                    if is_error:
                        tool_error_count += 1
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": result_text,
                        "is_error": is_error,
                    })
                messages.append({"role": "user", "content": tool_results})
                send_event("status", message="Interpretando resultados...")
                if tool_error_count >= 2:
                    # Stop an unproductive tool loop and force a useful explanation.
                    final_response = client.messages.create(
                        model=model,
                        max_tokens=4096,
                        system=system_prompt,
                        messages=messages,
                        timeout=300,
                    )
                    add_message_usage(token_usage, final_response)
                    final_content = [
                        serialize_foundry_content_block(block) for block in final_response.content
                    ]
                    final_content = [block for block in final_content if block]
                    messages.append({"role": "assistant", "content": final_content})
                    final_text = "".join(
                        block.get("text", "") for block in final_content if block.get("type") == "text"
                    )
                    if final_text:
                        if first_token_ms is None:
                            first_token_ms = int((time.perf_counter() - request_started) * 1000)
                        response_parts.append(final_text)
                        send_event("delta", text=final_text, session_id=session_id)
                    break
            else:
                fallback = (
                    "No pude completar todas las operaciones solicitadas dentro del límite seguro. "
                    "El PBIP permanece cargado; probá pedir un análisis más específico."
                )
                response_parts.append(fallback)
                send_event("delta", text=fallback, session_id=session_id)

            # Keep bounded in-memory conversation context for direct SDK sessions.
            with FOUNDRY_SESSIONS_LOCK:
                FOUNDRY_SESSIONS[session_id] = sanitize_foundry_messages(messages[-60:])

            total_ms = int((time.perf_counter() - request_started) * 1000)
            latency = {
                "cli_start_ms": provider_start_ms,
                "first_event_ms": first_event_ms,
                "first_token_ms": first_token_ms,
                "total_ms": total_ms,
            }
            response_text = "".join(response_parts)
            chat_logger.log_chat(
                user_msg=user_msg,
                response_len=len(response_text),
                duration_ms=total_ms,
                tone=tone,
                cli_session=session_id,
                latency=latency,
                username=self._request_username(),
                project=self._active_project_name(),
                token_usage=token_usage or None,
            )
            print(f"[CHAT FOUNDRY] session={session_id} response={len(response_text)} chars ({total_ms}ms)")
            send_event("done", session_id=session_id, latency=latency, usage=token_usage)

        except (BrokenPipeError, ConnectionResetError):
            print("[CHAT FOUNDRY] browser disconnected")
        except Exception as e:
            print(f"[CHAT FOUNDRY] error: {e}")
            try:
                send_event("error", error=str(e))
            except (BrokenPipeError, ConnectionResetError):
                pass

    def _execute_foundry_tool(self, name, tool_input):
        """Execute the small, allow-listed tool surface exposed to Foundry."""
        if name == "inspect_active_pbip":
            configured_pbip = load_config().get("pbip_project_path")
            complete, issues = validate_pbip_project(configured_pbip) if configured_pbip else (False, [])
            if not complete:
                detail = " ".join(issues) if issues else "No hay un proyecto PBIP activo."
                return detail, True
            try:
                inventory = inspect_pbip_project(configured_pbip)
                return json.dumps(inventory, ensure_ascii=False), False
            except OSError as e:
                return f"No se pudo inspeccionar el PBIP: {e}", True

        if name == "read_powerbi_skill":
            skill_name = str(tool_input.get("name", ""))
            if skill_name not in POWER_BI_SKILLS:
                return "Skill no permitida.", True
            skill_path = Path.home() / ".claude" / "skills" / skill_name / "SKILL.md"
            if not skill_path.is_file():
                return f"La skill {skill_name} no esta instalada.", True
            return skill_path.read_text(encoding="utf-8", errors="replace")[:50000], False

        if name == "run_pbi_cli":
            arguments = tool_input.get("arguments", [])
            if not isinstance(arguments, list) or not all(isinstance(arg, str) for arg in arguments):
                return "arguments debe ser una lista de textos.", True
            if len(arguments) > 100 or any(len(arg) > 10000 for arg in arguments):
                return "Argumentos fuera de los limites permitidos.", True
            pbi_path = shutil.which("pbi") or shutil.which("pbi-cli")
            if not pbi_path:
                return "pbi-cli no esta disponible en PATH.", True
            try:
                result = subprocess.run(
                    [pbi_path, *arguments],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    cwd=PROJECT_DIR,
                    timeout=180,
                    env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                )
                output = (result.stdout or "")
                if result.stderr:
                    output += ("\n" if output else "") + result.stderr
                output = output.strip() or f"Comando finalizado con codigo {result.returncode}, sin salida."
                return output[:50000], result.returncode != 0
            except subprocess.TimeoutExpired:
                return "El comando pbi-cli supero los 180 segundos.", True

        return f"Herramienta desconocida: {name}", True

    def _handle_pbi(self):
        """Execute a pbi command directly."""
        body = self._read_body()
        command = body.get("command", "")
        if not command:
            self._json_response({"error": "Comando vacio"}, status=400)
            return

        try:
            safe_cmd = command.replace('"', '\\"')
            result = subprocess.run(
                f'pbi --json {safe_cmd}',
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=60,
                cwd=PROJECT_DIR, shell=True,
            )
            try:
                data = json.loads(result.stdout)
            except json.JSONDecodeError:
                data = result.stdout.strip()
            self._json_response({"result": data})
        except Exception as e:
            self._json_response({"error": str(e)}, status=500)

    def _handle_set_pbip_path(self):
        """Configure the PBIP project path."""
        body = self._read_body()
        pbip_path = body.get("path", "").strip()

        if not pbip_path:
            self._json_response({"error": "Path vacio"}, status=400)
            return

        # Validate path
        from pathlib import Path
        path_obj = Path(pbip_path)

        # Check if it's a file or directory
        if not path_obj.exists():
            self._json_response({
                "error": f"La ruta no existe: {pbip_path}",
                "success": False
            }, status=400)
            return

        # Load current config
        config = load_config()

        # If it's a .pbip file, set as direct path
        if path_obj.is_file() and path_obj.suffix == ".pbip":
            config["pbip_project_path"] = str(path_obj)
            if save_config(config):
                self._json_response({
                    "success": True,
                    "message": f"Ruta PBIP configurada: {path_obj.name}",
                    "path": str(path_obj)
                })
            else:
                self._json_response({"error": "No se pudo guardar la configuracion"}, status=500)

        # If it's a directory, add to search directories
        elif path_obj.is_dir():
            if "search_directories" not in config:
                config["search_directories"] = []
            if str(path_obj) not in config["search_directories"]:
                config["search_directories"].insert(0, str(path_obj))
            if save_config(config):
                self._json_response({
                    "success": True,
                    "message": f"Directorio agregado a busqueda: {path_obj.name}",
                    "path": str(path_obj)
                })
            else:
                self._json_response({"error": "No se pudo guardar la configuracion"}, status=500)

        else:
            self._json_response({
                "error": "Debe ser un archivo .pbip o un directorio",
                "success": False
            }, status=400)

    def _handle_upload_pbip(self):
        """Upload a complete PBIP project ZIP (or validate a standalone PBIP)."""
        content_type = self.headers.get('Content-Type', '')
        if 'multipart/form-data' not in content_type:
            self._json_response({"error": "Content-Type debe ser multipart/form-data"}, status=400)
            return

        # Extract boundary from content-type
        boundary = None
        for part in content_type.split(';'):
            part = part.strip()
            if part.startswith('boundary='):
                boundary = part.split('=', 1)[1].strip('"')
                break

        if not boundary:
            self._json_response({"error": "No se encontro boundary en Content-Type"}, status=400)
            return

        # Read raw body with a configurable limit because multipart parsing is in-memory.
        length = int(self.headers.get('Content-Length', 0))
        max_upload_bytes = int(os.environ.get("MAX_PBIP_UPLOAD_MB", "500")) * 1024 * 1024
        if length <= 0 or length > max_upload_bytes:
            self._json_response({
                "error": f"El archivo supera el limite de {max_upload_bytes // (1024 * 1024)} MB"
            }, status=413)
            return
        body = self.rfile.read(length)

        # Parse multipart to find file
        boundary_bytes = boundary.encode()
        parts = body.split(b'--' + boundary_bytes)

        filename = None
        file_data = None

        for part in parts:
            if b'filename="' in part:
                # Extract filename
                header_end = part.find(b'\r\n\r\n')
                if header_end == -1:
                    continue
                header_section = part[:header_end].decode('utf-8', errors='replace')
                # Find filename in Content-Disposition
                for line in header_section.split('\r\n'):
                    if 'filename="' in line:
                        start = line.index('filename="') + 10
                        end = line.index('"', start)
                        filename = line[start:end]
                        break
                # Extract file content (skip headers + \r\n\r\n)
                file_data = part[header_end + 4:]
                # Remove trailing \r\n
                if file_data.endswith(b'\r\n'):
                    file_data = file_data[:-2]
                break

        if not filename or not file_data:
            self._json_response({"error": "No se encontro archivo en el upload"}, status=400)
            return

        filename = Path(filename).name
        lower_filename = filename.lower()
        if not (lower_filename.endswith('.zip') or lower_filename.endswith('.pbip')):
            self._json_response({
                "error": f"Subi un ZIP del proyecto PBIP completo (recibido: {filename})"
            }, status=400)
            return

        uploads_dir = Path(BASE_DIR) / "uploads"
        uploads_dir.mkdir(parents=True, exist_ok=True)
        safe_stem = "".join(c if c.isalnum() or c in "-_" else "_" for c in Path(filename).stem)[:80]
        package_dir = uploads_dir / f"{safe_stem}-{uuid.uuid4().hex[:8]}"

        try:
            if lower_filename.endswith('.zip'):
                with zipfile.ZipFile(io.BytesIO(file_data)) as archive:
                    members = archive.infolist()
                    if len(members) > 20000:
                        raise ValueError("El ZIP contiene demasiados archivos.")
                    total_size = sum(member.file_size for member in members)
                    if total_size > 2 * 1024 * 1024 * 1024:
                        raise ValueError("El contenido descomprimido supera 2 GB.")
                    package_dir.mkdir(parents=True, exist_ok=False)
                    package_root = package_dir.resolve()
                    for member in members:
                        member_mode = member.external_attr >> 16
                        if stat.S_ISLNK(member_mode):
                            raise ValueError("El ZIP contiene enlaces simbolicos no permitidos.")
                        target = (package_dir / member.filename).resolve()
                        if target != package_root and package_root not in target.parents:
                            raise ValueError("El ZIP contiene una ruta no permitida.")
                        if member.is_dir():
                            target.mkdir(parents=True, exist_ok=True)
                        else:
                            target.parent.mkdir(parents=True, exist_ok=True)
                            with archive.open(member) as source, open(target, "wb") as destination:
                                shutil.copyfileobj(source, destination)
                pbip_files = sorted(
                    (p for p in package_dir.rglob("*") if p.is_file() and p.suffix.lower() == ".pbip"),
                    key=lambda p: len(p.parts),
                )
                if len(pbip_files) != 1:
                    raise ValueError(
                        f"El ZIP debe contener exactamente un archivo .pbip (encontrados: {len(pbip_files)})."
                    )
                pbip_path = pbip_files[0]
            else:
                package_dir.mkdir(parents=True, exist_ok=False)
                pbip_path = package_dir / filename
                pbip_path.write_bytes(file_data)

            complete, issues = validate_pbip_project(pbip_path)
            if not complete:
                raise ValueError(
                    "Proyecto PBIP incompleto. Subi un ZIP que incluya el .pbip y sus carpetas .Report/"
                    ".SemanticModel. " + " ".join(issues)
                )
        except (zipfile.BadZipFile, ValueError, OSError) as e:
            # package_dir is always a newly-created UUID child of uploads_dir.
            # Remove an invalid/partial upload without touching existing projects.
            try:
                uploads_root = uploads_dir.resolve()
                failed_package = package_dir.resolve()
                if uploads_root in failed_package.parents and failed_package.exists():
                    shutil.rmtree(failed_package)
            except OSError:
                pass
            self._json_response({"error": str(e)}, status=400)
            return

        # Update config
        config = load_config()
        config["pbip_project_path"] = str(pbip_path)
        if save_config(config):
            pbip_context, metadata_files = collect_pbip_context(pbip_path)
            chat_logger.log_event('pbip_uploaded', {
                'filename': filename,
                'size': len(file_data),
                'project': pbip_path.stem,
                'metadata_files': metadata_files,
                'estimated_context_tokens': max(1, (len(pbip_context) + 3) // 4),
            }, username=self._request_username())
            self._json_response({
                "success": True,
                "message": f"Proyecto PBIP listo: {pbip_path.stem}",
                "path": str(pbip_path),
            })
        else:
            self._json_response({"error": "No se pudo guardar la configuracion"}, status=500)

    def _handle_export_business_report(self):
        """Generate and download a self-contained KPI report from PBIP metadata."""
        if not FOUNDRY_AVAILABLE:
            self._json_response({"error": "Microsoft Foundry no esta configurado"}, status=503)
            return

        body = self._read_body()
        objective = str(body.get("objective", "")).strip()[:1000]
        configured_pbip = load_config().get("pbip_project_path")
        complete, issues = validate_pbip_project(configured_pbip) if configured_pbip else (False, [])
        if not complete:
            detail = " ".join(issues) if issues else "No hay un proyecto PBIP activo."
            self._json_response({
                "error": "Primero subi el ZIP completo del proyecto PBIP. " + detail
            }, status=400)
            return

        try:
            context, file_count = collect_pbip_context(configured_pbip)
            if not context.strip():
                self._json_response({"error": "El PBIP no contiene metadatos de texto analizables."}, status=400)
                return

            pbip_path = Path(configured_pbip)
            prompt = build_business_prompt(pbip_path.stem, objective, context)
            client = AnthropicFoundry(
                api_key=os.environ["ANTHROPIC_FOUNDRY_API_KEY"],
                base_url=os.environ["ANTHROPIC_FOUNDRY_BASE_URL"],
            )
            model = os.environ.get("ANTHROPIC_MODEL") or os.environ.get("ANTHROPIC_DEFAULT_SONNET_MODEL")
            response = client.messages.create(
                model=model,
                max_tokens=8000,
                system=(
                    "Sos un analista senior de Power BI y performance de negocio. "
                    "Tu salida debe ser JSON valido y no debe inventar resultados numericos."
                ),
                messages=[{"role": "user", "content": prompt}],
            )
            raw_text = "".join(
                getattr(block, "text", "")
                for block in response.content
                if getattr(block, "type", "") == "text"
            )
            analysis = parse_business_analysis(raw_text)
            export_usage = {}
            add_message_usage(export_usage, response)
            report_html = render_business_html(
                analysis,
                project_name=pbip_path.stem,
                objective=objective,
                logo_path=Path(BASE_DIR) / "logo_ypf.png",
            ).encode("utf-8")
            safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in pbip_path.stem)[:80]
            filename = f"Informe_KPI_{safe_name}.html"
            chat_logger.log_event("business_report_exported", {
                "project": pbip_path.stem,
                "metadata_files": file_count,
                "kpis": len(analysis.get("kpis", [])),
                "tokens": export_usage,
            }, username=self._request_username())
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Content-Length", str(len(report_html)))
            self.end_headers()
            self.wfile.write(report_html)
        except (ValueError, json.JSONDecodeError) as e:
            self._json_response({"error": str(e)}, status=502)
        except Exception as e:
            print(f"[BUSINESS REPORT] error: {e}")
            self._json_response({"error": f"No se pudo generar el informe: {e}"}, status=500)

    def _handle_switch_connection(self):
        """Switch active Power BI connection by port."""
        body = self._read_body()
        port = body.get("port", "")

        if not port:
            self._json_response({"error": "Puerto no especificado"}, status=400)
            return

        try:
            r = subprocess.run(
                f"pbi connect -d localhost:{port}",
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=15,
                cwd=PROJECT_DIR, shell=True,
            )
            if r.returncode == 0:
                self._json_response({
                    "success": True,
                    "message": f"Conectado a localhost:{port}"
                })
            else:
                self._json_response({
                    "error": r.stderr.strip() or "Error al conectar"
                }, status=500)
        except Exception as e:
            self._json_response({"error": str(e)}, status=500)

    def _handle_discover_pbip(self):
        """Discover all .pbip files in configured search paths."""
        body = self._read_body()
        custom_paths = body.get("search_paths", [])

        # Get search paths from config or use custom ones
        if custom_paths:
            search_paths = custom_paths
        else:
            search_paths = get_pbip_search_paths()

        discovered = []
        seen_paths = set()

        try:
            from pathlib import Path
            import datetime

            for search_path_str in search_paths:
                search_path = Path(search_path_str)

                if not search_path.exists():
                    continue

                # If it's a direct .pbip file
                if search_path.is_file() and search_path.suffix == ".pbip":
                    if str(search_path) not in seen_paths:
                        discovered.append(self._extract_pbip_metadata(search_path))
                        seen_paths.add(str(search_path))
                    continue

                # If it's a directory, search recursively for .pbip files
                if search_path.is_dir():
                    for pbip_file in search_path.rglob("*.pbip"):
                        if str(pbip_file) not in seen_paths:
                            discovered.append(self._extract_pbip_metadata(pbip_file))
                            seen_paths.add(str(pbip_file))

            # Sort by modification time (most recent first)
            discovered.sort(key=lambda x: x["modified"], reverse=True)

            self._json_response({
                "success": True,
                "count": len(discovered),
                "files": discovered,
                "search_paths": [str(p) for p in search_paths],
            })

        except Exception as e:
            self._json_response({"error": str(e), "success": False}, status=500)

    def _extract_pbip_metadata(self, pbip_path):
        """Extract metadata from a .pbip file."""
        import datetime
        stat = pbip_path.stat()

        return {
            "name": pbip_path.stem,
            "path": str(pbip_path),
            "size": stat.st_size,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "modified": stat.st_mtime,
            "modified_str": datetime.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            "parent_dir": pbip_path.parent.name,
        }

    def _handle_auth(self):
        """Check if current Windows user is authorized."""
        config = load_config()
        username = self._request_username()
        whitelist = [u.strip().lower() for u in config.get('whitelist', []) if u.strip()]
        admin_users = [u.strip().lower() for u in config.get('admin_users', []) if u.strip()]
        project_owner = os.environ.get('PROJECT_OWNER', '').strip().lower()

        # Empty whitelist = everyone authorized
        authorized = not whitelist or username in whitelist
        is_admin = username in admin_users or bool(project_owner and username == project_owner)

        self._json_response({
            'user': username,
            'authorized': authorized,
            'is_admin': is_admin,
        })

    def _handle_usage_stats(self):
        """Return global stats to admins and personal stats to other users."""
        config = load_config()
        username = self._request_username()
        admin_users = [u.strip().lower() for u in config.get('admin_users', []) if u.strip()]
        project_owner = os.environ.get('PROJECT_OWNER', '').strip().lower()
        is_admin = username in admin_users or bool(project_owner and username == project_owner)
        stats = chat_logger.get_stats(username=None if is_admin else username)
        stats['scope'] = 'global' if is_admin else 'user'
        stats['current_user'] = username
        self._json_response(stats)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        return json.loads(raw) if raw else {}

    def _json_response(self, data, status=200):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", len(payload))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        try:
            first = str(args[0]) if args else ""
            if "/api/" in first:
                super().log_message(format, *args)
        except Exception:
            pass


class ThreadedHTTPServer(http.server.HTTPServer):
    """Handle each request in a separate thread so long-running API calls
    don't block the browser from loading static files."""
    from socketserver import ThreadingMixIn
    allow_reuse_address = True

    def process_request(self, request, client_address):
        t = threading.Thread(target=self._handle, args=(request, client_address))
        t.daemon = True
        t.start()

    def _handle(self, request, client_address):
        try:
            self.finish_request(request, client_address)
        except Exception:
            self.handle_error(request, client_address)
        finally:
            self.shutdown_request(request)


def main():
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="PBI CLI Chat Server")
    parser.add_argument("--port", type=int, default=PORT, help=f"Port to run on (default: {PORT})")
    args = parser.parse_args()

    port = args.port
    bind_address = "127.0.0.1" if CLOUD_MODE else "127.0.0.1"

    server = ThreadedHTTPServer((bind_address, port), ChatHandler)

    mode_label = "CLOUD" if CLOUD_MODE else "LOCAL"
    print(f"\n{'='*50}")
    print(f"  PBI CLI Chat [{mode_label}] — http://localhost:{port}")
    print(f"{'='*50}")

    if not CLOUD_MODE:
        print(f"  Abriendo navegador...")
        print(f"  Ctrl+C para detener\n")

        # Open browser after a short delay (local mode only)
        def open_browser():
            time.sleep(1)
            webbrowser.open(f"http://localhost:{port}")

        threading.Thread(target=open_browser, daemon=True).start()
    else:
        print(f"  Modo Cloud: accede via Cloudera AI Workbench")
        print(f"  Ctrl+C para detener\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Detenido]")
        server.shutdown()


if __name__ == "__main__":
    main()
