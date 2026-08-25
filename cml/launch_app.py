"""CML Launch Script — starts PBI CLI Chat server on CDSW_APP_PORT."""

import os
import sys
import subprocess
import shutil

# Detect working directory (Cloudera uses /home/cdsw)
workdir = os.environ.get("WORKDIR", os.getcwd())
if workdir not in sys.path:
    sys.path.insert(0, workdir)

port = os.environ.get("CDSW_APP_PORT", "5174")
os.environ["CLOUD_MODE"] = "true"

print(f"[CML] Working directory: {workdir}")
print(f"[CML] Starting PBI CLI Chat on port {port}...")
print(f"[CML] Cloud mode: {os.environ.get('CLOUD_MODE', 'false')}")

# Change to working directory
os.chdir(workdir)

# Install/update the bundled Power BI skills for the same user that runs the app.
pbi_cli = shutil.which("pbi-cli")
if pbi_cli:
    result = subprocess.run(
        [pbi_cli, "skills", "install", "--yes"],
        capture_output=True,
        text=True,
        timeout=90,
    )
    if result.returncode == 0:
        print("[CML] Power BI skills ready")
    else:
        print(f"[CML] Warning: skills installation failed: {result.stderr[:500]}")
else:
    print("[CML] Warning: pbi-cli not found; verify requirements installation")

# Run the server
subprocess.run([
    sys.executable, "server.py",
    f"--port={port}",
])
