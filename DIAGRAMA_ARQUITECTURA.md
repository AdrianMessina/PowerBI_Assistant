# PBI Assistant - Diagramas de Arquitectura

## 🎨 Diagrama 1: Vista General del Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                         USUARIO FINAL                           │
│                    (No técnico - YPF)                           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ Browser (Chrome/Edge)
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│                    FRONTEND (index.html)                        │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────────────┐     │
│  │  Welcome    │  │  Chat Area   │  │  Config Banner    │     │
│  │  Screen     │  │  Messages    │  │  Status Display   │     │
│  │  Feature    │  │  Input Box   │  │  Tone Selector    │     │
│  │  Cards      │  │  Markdown    │  │  Auth Check       │     │
│  └─────────────┘  └──────────────┘  └───────────────────┘     │
│                                                                  │
│  JavaScript: sendMessage() → fetch('/api/chat')                │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ HTTP REST API
                         │ (JSON request/response)
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│                   BACKEND (server.py)                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  REST Endpoints                                          │  │
│  │  • POST /api/chat        → Proxy a Claude CLI          │  │
│  │  • GET  /api/status      → Verifica pbi-cli + PBI      │  │
│  │  • POST /api/set-pbip    → Configura archivo PBIP      │  │
│  │  • GET  /api/auth        → Whitelist check             │  │
│  │  • GET  /api/usage-stats → Métricas (admin)            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  Python: subprocess.run("claude --resume {session_id}")         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ subprocess + stdin redirect
                         │ (temp files para mensaje y tono)
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│                  CLAUDE CLI (Local Binary)                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Session Manager                                         │  │
│  │  • Mantiene contexto de conversación                    │  │
│  │  • --resume {session_id} para persistencia              │  │
│  │  • --append-system-prompt-file para tone injection      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Skills Engine (13 skills de pbi-cli)                   │  │
│  │  ✅ power-bi-dax         → Queries y medidas DAX       │  │
│  │  ✅ power-bi-modeling    → Tablas, columnas, relaciones│  │
│  │  ✅ power-bi-report      → Scaffold de reportes PBIR   │  │
│  │  ✅ power-bi-visuals     → Crear/modificar visuales    │  │
│  │  ✅ power-bi-diagnostics → Health checks y tracing     │  │
│  │  ✅ ... (+ 8 skills más)                               │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  Output: stream-json → {"type": "assistant", "message": {...}} │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ subprocess.run("pbi --json ...")
                         │ Ejecuta comandos según skill
                         ↓
┌─────────────────────────────────────────────────────────────────┐
│                    PBI-CLI (Rust Binary)                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Dual-layer architecture:                                │  │
│  │                                                          │  │
│  │  [Semantic Model Layer]      [Report Layer]             │  │
│  │  • Requiere PBI Desktop      • Trabaja offline          │  │
│  │  • TCP → Analysis Services   • Lee/escribe .pbip JSON   │  │
│  │  • DAX queries               • Modifica visuals         │  │
│  │  • Metadata operations       • Themes, pages, filters   │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────┬───────────────────────────────────────────┬────────────┘
         │                                           │
         │ TCP (auto-detect port)                    │ File I/O
         ↓                                           ↓
┌───────────────────────┐              ┌──────────────────────────┐
│  Power BI Desktop     │              │  Archivos .pbip          │
│  Analysis Services    │              │  ├── *.Report/           │
│  (Puerto dinámico)    │              │  │   └── report.json     │
│  ┌─────────────────┐  │              │  └── *.SemanticModel/   │
│  │ Modelo Semántico│  │              │      └── definition/     │
│  │ • Tablas        │  │              │          ├── model.tmd   │
│  │ • Medidas       │  │              │          └── tables/*.tmd│
│  │ • Relaciones    │  │              └──────────────────────────┘
│  │ • RLS           │  │
│  └─────────────────┘  │
└───────────────────────┘
```

---

## 🔄 Diagrama 2: Flujo de un Mensaje de Chat

```
┌─────────────────────────────────────────────────────────────────────┐
│ PASO 1: Usuario escribe mensaje                                    │
│ ┌───────────────────────────────────────────────────────┐           │
│ │ "Mostrame los top 10 productos por ventas"          │ [Enviar] │
│ └───────────────────────────────────────────────────────┘           │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────────┐
│ PASO 2: Frontend prepara request                                   │
│ {                                                                   │
│   "message": "Mostrame los top 10 productos por ventas",           │
│   "tone": "porteno",                                                │
│   "session_id": "abc123"  // null si es primera consulta           │
│ }                                                                   │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         │ POST /api/chat
                         ↓
┌─────────────────────────────────────────────────────────────────────┐
│ PASO 3: Backend (server.py) procesa                                │
│                                                                     │
│ if session_id exists:                                               │
│   cmd = "claude --resume abc123 < mensaje.txt"                     │
│ else:                                                               │
│   1. Crea tone_prompt.txt:                                          │
│      "INSTRUCCION: Responde en voseo, se relajado..."              │
│   2. cmd = "claude --append-system-prompt-file tone.txt < msg.txt" │
│                                                                     │
│ subprocess.run(cmd, capture_output=True)                            │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         │ stdin: mensaje del usuario
                         ↓
┌─────────────────────────────────────────────────────────────────────┐
│ PASO 4: Claude CLI procesa (con contexto completo de sesión)       │
│                                                                     │
│ System Prompt:                                                      │
│ • Tone instruction (porteno)                                        │
│ • "Solo responder consultas de Power BI"                            │
│ • Skills disponibles: power-bi-*                                    │
│                                                                     │
│ Claude Reasoning:                                                   │
│ 1. Usuario pide "top 10 productos por ventas"                      │
│ 2. Esto es una consulta DAX → Invocar skill power-bi-dax           │
│ 3. Necesito ejecutar: pbi dax execute -e "EVALUATE..."             │
│ 4. Construir query DAX con TOPN()                                   │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         │ Skill invoca subprocess
                         ↓
┌─────────────────────────────────────────────────────────────────────┐
│ PASO 5: pbi-cli ejecuta comando                                    │
│                                                                     │
│ $ pbi --json dax execute -e "                                       │
│     EVALUATE                                                        │
│     TOPN(                                                           │
│       10,                                                           │
│       SUMMARIZE(                                                    │
│         Products,                                                   │
│         Products[ProductName],                                      │
│         'Sales', SUM(Sales[Amount])                                 │
│       ),                                                            │
│       [Sales],                                                      │
│       DESC                                                          │
│     )                                                               │
│   "                                                                 │
│                                                                     │
│ → Conecta a localhost:XXXXX (puerto de Analysis Services)          │
│ → Ejecuta query DAX contra modelo activo                            │
│ → Retorna JSON con resultados                                       │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         │ stdout: JSON results
                         ↓
┌─────────────────────────────────────────────────────────────────────┐
│ PASO 6: Claude CLI formatea respuesta (en español porteño)         │
│                                                                     │
│ "Acá tenés el top 10 de productos por ventas:                      │
│                                                                     │
│ | Producto         | Ventas       |                                │
│ |------------------|--------------|                                │
│ | Mountain Bike    | $1,234,567   |                                │
│ | Road Bike        | $987,654     |                                │
│ | Helmet           | $456,789     |                                │
│ | ...                             |                                │
│                                                                     │
│ ¿Necesitás algo más?"                                               │
│                                                                     │
│ Output stream-json:                                                 │
│ {"type": "assistant", "message": {"content": [...]}}               │
│ {"type": "result", "result": "...", "session_id": "abc123"}        │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         │ stdout parseado por server.py
                         ↓
┌─────────────────────────────────────────────────────────────────────┐
│ PASO 7: Backend extrae y retorna JSON                              │
│ {                                                                   │
│   "response": "Acá tenés el top 10...",                             │
│   "session_id": "abc123"                                            │
│ }                                                                   │
│                                                                     │
│ + Log event:                                                        │
│   chat_logger.log_chat(msg, response_len, duration_ms, tone, ...)  │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         │ HTTP 200 OK
                         ↓
┌─────────────────────────────────────────────────────────────────────┐
│ PASO 8: Frontend renderiza respuesta                               │
│                                                                     │
│ [PBAI] Acá tenés el top 10 de productos por ventas:                │
│                                                                     │
│        | Producto      | Ventas       |                            │
│        |---------------|--------------|                            │
│        | Mountain Bike | $1,234,567   |                            │
│        | Road Bike     | $987,654     |                            │
│        | ...                           |                            │
│                                                                     │
│        ¿Necesitás algo más?                                         │
│                                                                     │
│ [Usuario] _                                                         │
└─────────────────────────────────────────────────────────────────────┘

Total time: ~2-5 segundos (depende de complejidad de query)
```

---

## 🏗️ Diagrama 3: Arquitectura de Archivos

```
pbi-cli/
├── web/                                    ← Tu aplicación web
│   ├── index.html                          ← Frontend completo (1941 líneas)
│   ├── server.py                           ← Backend API (920 líneas)
│   ├── usage_logger.py                     ← Sistema de métricas
│   ├── requirements.txt                    ← Dependencias Python
│   ├── config.json                         ← Configuración runtime
│   │   ├── pbip_project_path               ← Path a archivo .pbip
│   │   ├── search_directories              ← Directorios de búsqueda
│   │   ├── whitelist                       ← Usuarios autorizados
│   │   └── admin_users                     ← Admins con métricas
│   ├── .env                                ← Variables de entorno (no versionado)
│   ├── logs/                               ← Logs de uso
│   │   └── usage_20260610.jsonl            ← Log diario
│   ├── uploads/                            ← Archivos .pbip subidos
│   ├── logo_ypf.png                        ← Branding
│   └── cml/                                ← Configs Cloudera
│       └── deployment.yaml
│
├── src/                                    ← pbi-cli Rust source
│   └── pbi_cli/
│       ├── commands/
│       ├── dlls/
│       └── ...
│
└── ~/.claude/                              ← Claude CLI config (user home)
    ├── skills/
    │   ├── power-bi-dax.md
    │   ├── power-bi-modeling.md
    │   ├── power-bi-report.md
    │   └── ... (13 skills)
    └── sessions/
        └── abc123.json                     ← Session state persistida
```

---

## 🎯 Diagrama 4: Feature Cards → Comandos pbi-cli

```
┌─────────────────────────────────────────────────────────────────────┐
│ FRONTEND: Feature Card Clicked                                     │
│ ┌─────────────────────────────────────────────────────────────┐    │
│ │ [📊 Top productos por ventas]                              │    │
│ │ Ejecuta una query DAX para ver los productos con más ingresos │  │
│ └─────────────────────────────────────────────────────────────┘    │
│                                                                     │
│ → Autocompleta input: "Mostrame los top 10 productos por ventas"   │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────────┐
│ CLAUDE CLI: Interpreta intención                                   │
│ "El usuario quiere ejecutar una consulta DAX agregada"             │
│ → Skill: power-bi-dax                                               │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────────┐
│ PBI-CLI: Comando ejecutado                                         │
│ $ pbi --json dax execute -e "                                       │
│     EVALUATE                                                        │
│     TOPN(10, SUMMARIZE(...), [Sales], DESC)                         │
│   "                                                                 │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ Otro ejemplo: Crear Medida                                         │
├─────────────────────────────────────────────────────────────────────┤
│ [Feature Card]                                                      │
│ "Crear medida DAX" → "Creame una medida YTD de ventas"             │
│           ↓                                                         │
│ [Claude CLI]                                                        │
│ Skill: power-bi-modeling                                            │
│           ↓                                                         │
│ [pbi-cli]                                                           │
│ $ pbi measure create \                                              │
│     -t Sales \                                                      │
│     -n "Sales YTD" \                                                │
│     -e "TOTALYTD(SUM(Sales[Amount]), Calendar[Date])"              │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ Otro ejemplo: Agregar Visual                                       │
├─────────────────────────────────────────────────────────────────────┤
│ [Feature Card]                                                      │
│ "Agregar visuales" → "Agrega un grafico de barras de ventas"       │
│           ↓                                                         │
│ [Claude CLI]                                                        │
│ Skill: power-bi-visuals                                             │
│           ↓                                                         │
│ [pbi-cli]                                                           │
│ $ pbi visual add \                                                  │
│     --type barChart \                                               │
│     --page "Sales Dashboard" \                                      │
│     --x "Products[Category]" \                                      │
│     --y "Sales[Amount]"                                             │
│           ↓                                                         │
│ [Filesystem]                                                        │
│ Modifica: MiReporte.Report/definition/pages/Sales_Dashboard.json   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🔐 Diagrama 5: Sistema de Autenticación y Métricas

```
┌─────────────────────────────────────────────────────────────────────┐
│ Usuario abre http://localhost:5174                                  │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Frontend: checkAuth()                                               │
│ GET /api/auth                                                       │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Backend: _handle_auth()                                             │
│ username = os.environ.get('USERNAME').lower()  # 'se46958'          │
│ config = load_config()                                              │
│ whitelist = config.get('whitelist', [])                             │
│ admin_users = config.get('admin_users', [])                         │
│                                                                     │
│ authorized = username in whitelist OR whitelist is empty            │
│ is_admin = username in admin_users                                  │
│                                                                     │
│ return {                                                            │
│   'user': username,                                                 │
│   'authorized': authorized,                                         │
│   'is_admin': is_admin                                              │
│ }                                                                   │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Frontend: Renderiza según auth status                              │
│                                                                     │
│ if (!data.authorized):                                              │
│   document.getElementById('accessDenied').style.display = 'flex'    │
│   // Muestra overlay: "Acceso restringido"                          │
│                                                                     │
│ if (data.is_admin):                                                 │
│   // Muestra badge: "👑 se46958"                                    │
│   // Habilita panel de métricas en config banner                    │
│   loadMetrics()                                                     │
│ else:                                                               │
│   // Muestra badge: "👤 se46958"                                    │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ Panel de Métricas (solo admin)                                     │
│ ┌─────────────────────────────────────────────────────────────────┐ │
│ │ 📊 Métricas de uso                                              │ │
│ ├─────────────────────────────────────────────────────────────────┤ │
│ │ [KPIs]                                                          │ │
│ │ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │ │
│ │ │   450    │ │    23    │ │     8    │ │   1250   │          │ │
│ │ │ Mensajes │ │ Sesiones │ │ Usuarios │ │  Eventos │          │ │
│ │ └──────────┘ └──────────┘ └──────────┘ └──────────┘          │ │
│ │                                                                 │ │
│ │ [Actividad últimos 14 días - Gráfico de barras]                │ │
│ │ ████ ███ ████ ██ ███ ████ █████ ████ ███ ████ ███ ████ ███  │ │
│ │                                                                 │ │
│ │ [Últimos eventos]                                               │ │
│ │ Fecha            Usuario  Evento                                │ │
│ │ 2026-06-10 14:23 se46958  chat_message                         │ │
│ │ 2026-06-10 14:18 user1    pbip_uploaded                        │ │
│ │ 2026-06-10 13:45 se46958  chat_message                         │ │
│ │                                                                 │ │
│ │ [Exportar CSV]                                                  │ │
│ └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘

Backend: GET /api/usage-stats
  → Verifica admin_users
  → Lee todos los logs/usage_*.jsonl
  → Agrega estadísticas
  → Retorna JSON
```

---

## 🚀 Diagrama 6: Deployment en Cloudera AI Workbench

```
┌─────────────────────────────────────────────────────────────────────┐
│ ENTORNO LOCAL (Desarrollo)                                         │
│                                                                     │
│ Developer machine:                                                  │
│   pbi-cli/web/                                                      │
│   $ python server.py                                                │
│   → Detecta CLOUD_MODE=false                                        │
│   → Bind: 127.0.0.1:5174                                            │
│   → Auto-abre: http://localhost:5174                                │
│   → Claude CLI path: ~/OneDrive/.../claude.cmd                      │
└─────────────────────────────────────────────────────────────────────┘

                         VS

┌─────────────────────────────────────────────────────────────────────┐
│ ENTORNO CLOUD (Producción)                                         │
│                                                                     │
│ Cloudera AI Workbench:                                              │
│   .env:                                                             │
│     CLOUD_MODE=true                                                 │
│     CDSW_APP_PORT=8080                                              │
│     PBIP_PROJECT_PATH=/data/reportes/ventas.pbip                    │
│                                                                     │
│   cml/deployment.yaml:                                              │
│     runtime: Python 3.10                                            │
│     cpu: 2                                                          │
│     memory: 4Gi                                                     │
│     script: python web/server.py                                    │
│                                                                     │
│   $ python server.py                                                │
│   → Detecta CLOUD_MODE=true                                         │
│   → Bind: 0.0.0.0:8080                                              │
│   → NO abre browser                                                 │
│   → URL: https://cdsw.ypf.com/projects/pbi-assistant/              │
│   → Claude CLI path: /usr/local/bin/claude                          │
│                                                                     │
│   Proxy inverso:                                                    │
│   Nginx/HAProxy → Cloudera → server.py:8080                        │
└─────────────────────────────────────────────────────────────────────┘

prepare_deployment.bat:
  1. Verifica pbi-cli instalado
  2. Verifica Claude CLI instalado
  3. Crea .env si no existe
  4. Valida config.json
  5. Copia archivos a staging/
  6. Genera requirements.txt
  7. Crea cml/deployment.yaml
  8. README con instrucciones de deploy
```

---

## 🔄 Diagrama 7: Comparación con Hermes Agent

```
┌─────────────────────────────────────────────────────────────────────┐
│ ARQUITECTURA ACTUAL (PBI Assistant)                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ Frontend (HTML/JS)                                                  │
│      ↕ HTTP REST                                                    │
│ Backend (Python server.py)                                          │
│      ↕ subprocess + stdin                                           │
│ Claude CLI (with skills)                                            │
│      ↕ subprocess                                                   │
│ pbi-cli (Rust)                                                      │
│      ↕ TCP / File I/O                                               │
│ Power BI Desktop / .pbip files                                      │
│                                                                     │
│ Ventajas:                                                           │
│ ✅ Session management automático (--resume)                         │
│ ✅ Skills predefinidos (no config)                                  │
│ ✅ Debugging simple (stdout legible)                                │
│                                                                     │
│ Desventajas:                                                        │
│ ❌ Requiere Claude CLI instalado                                    │
│ ❌ Subprocess overhead                                              │
│ ❌ No control granular de prompts                                   │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ MIGRACIÓN A HERMES AGENT                                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ Hermes UI (o Frontend existente embebido)                           │
│      ↕ Hermes Protocol                                              │
│ Hermes Agent SDK (Python)                                           │
│      ↕ anthropic.Client() direct API                                │
│ Claude API (Sonnet 4.5)                                             │
│      ↕ Function calling (custom tools)                              │
│ pbi-cli wrapper (Python functions)                                  │
│      ↕ subprocess                                                   │
│ pbi-cli (Rust)                                                      │
│      ↕ TCP / File I/O                                               │
│ Power BI Desktop / .pbip files                                      │
│                                                                     │
│ Cambios necesarios:                                                 │
│ 1. Reemplazar server.py → Hermes Agent SDK                          │
│ 2. Convertir skills → Hermes tools                                  │
│    Example:                                                         │
│    @tool                                                            │
│    def execute_dax_query(query: str) -> dict:                       │
│        result = subprocess.run(["pbi", "dax", "execute", "-e", query]) │
│        return json.loads(result.stdout)                             │
│                                                                     │
│ 3. Session state → Redis/DynamoDB                                   │
│    (Hermes SDK puede proveer esto)                                  │
│                                                                     │
│ 4. Tone prompts → System messages                                   │
│    client.messages.create(                                          │
│        model="claude-sonnet-4-5",                                   │
│        system=[{                                                    │
│            "type": "text",                                          │
│            "text": TONE_PROMPTS[tone]                               │
│        }],                                                          │
│        messages=[...]                                               │
│    )                                                                │
│                                                                     │
│ Ventajas:                                                           │
│ ✅ No requiere Claude CLI                                           │
│ ✅ Control total de prompts y tools                                 │
│ ✅ Mejor integración con ecosistema Hermes                          │
│ ✅ Métricas nativas de Hermes                                       │
│                                                                     │
│ Desventajas:                                                        │
│ ❌ Más código a escribir (tools config)                             │
│ ❌ Session management manual                                        │
│ ❌ Debugging más complejo (API responses)                           │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ OPCIÓN HÍBRIDA: Coexistencia                                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│ Hermes Agent (Orchestrator)                                         │
│      │                                                              │
│      ├── Sub-agent: PBI Assistant (actual, via HTTP)                │
│      │    → POST http://localhost:5174/api/chat                     │
│      │                                                              │
│      ├── Sub-agent: SQL Analyst                                     │
│      └── Sub-agent: Excel Helper                                    │
│                                                                     │
│ Usuario: "Analiza ventas de Power BI y exporta a Excel"            │
│    ↓                                                                │
│ Hermes decide: "Necesito PBI Assistant + Excel Helper"             │
│    ↓                                                                │
│ Hermes llama PBI Assistant → Obtiene datos                          │
│ Hermes llama Excel Helper → Genera XLSX                             │
│ Hermes retorna: "Análisis completo + archivo Excel"                │
│                                                                     │
│ Ventajas:                                                           │
│ ✅ Sin reescribir código existente                                  │
│ ✅ Hermes orquesta multi-dominio                                    │
│ ✅ PBI Assistant sigue funcionando standalone                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📝 Diagrama 8: Estructura de Session State

```
┌─────────────────────────────────────────────────────────────────────┐
│ Claude CLI Session (--resume abc123)                               │
├─────────────────────────────────────────────────────────────────────┤
│ ~/.claude/sessions/abc123.json                                      │
│ {                                                                   │
│   "session_id": "abc123",                                           │
│   "created_at": "2026-06-10T14:00:00Z",                             │
│   "last_accessed": "2026-06-10T14:23:15Z",                          │
│   "system_prompts": [                                               │
│     {                                                               │
│       "type": "text",                                               │
│       "text": "INSTRUCCION: Responde en voseo..."                   │
│     }                                                               │
│   ],                                                                │
│   "messages": [                                                     │
│     {                                                               │
│       "role": "user",                                               │
│       "content": "Mostrame ventas por region"                       │
│     },                                                              │
│     {                                                               │
│       "role": "assistant",                                          │
│       "content": "Aca tenes las ventas por region:\n\n| Region..."  │
│     },                                                              │
│     {                                                               │
│       "role": "user",                                               │
│       "content": "Ahora mostrame solo la region Norte"             │
│     },                                                              │
│     {                                                               │
│       "role": "assistant",                                          │
│       "content": "Claro! Filtrando solo Norte:\n\n..."             │
│     }                                                               │
│   ],                                                                │
│   "context": {                                                      │
│     "working_directory": "C:\\Reportes\\",                          │
│     "pbi_connection": "localhost:12345",                            │
│     "model_name": "Ventas 2024"                                     │
│   }                                                                 │
│ }                                                                   │
└─────────────────────────────────────────────────────────────────────┘

Cuando usuario envía nuevo mensaje:
  1. Frontend envía: {message, session_id: "abc123"}
  2. Backend ejecuta: claude --resume abc123 < new_message.txt
  3. Claude CLI:
     - Lee abc123.json
     - Carga todo el historial en memoria
     - Procesa nuevo mensaje con contexto completo
     - Actualiza abc123.json con nueva interacción
  4. Backend retorna respuesta + mismo session_id

Si session_id es null (primera consulta):
  1. Backend ejecuta: claude --append-system-prompt-file tone.txt
  2. Claude CLI:
     - Crea nuevo session_id (ej: "xyz789")
     - Guarda xyz789.json con system prompts + primer mensaje
  3. Backend retorna respuesta + nuevo session_id
  4. Frontend almacena xyz789 para próximas consultas
```

---

**Fin de los diagramas. Estos complementan el RESUMEN_EJECUTIVO_REUNION.md**
