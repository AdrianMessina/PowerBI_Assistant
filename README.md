# PowerBI Assistant

Interfaz web conversacional para analizar Power BI mediante Claude CLI y
`pbi-cli`. Incluye respuestas en streaming, estados de ejecución y métricas de
latencia.

## Ejecución local

Requisitos:

- Python 3.10 o superior.
- Claude CLI instalado y autenticado.
- `pbi-cli` disponible en `PATH`.

```bash
python -m pip install -r requirements.txt
python server.py
```

La aplicación queda disponible en `http://localhost:5174`.

La configuración específica de cada equipo se guarda en
`config.local.json`, que no se publica en Git. `config.json` contiene solamente
valores iniciales seguros.

## Cloudera AI Workbench

El proyecto incluye `.project-metadata.yaml` y `cml/launch_app.py`. La
aplicación usa el puerto entregado por `CDSW_APP_PORT`.

Variables principales:

```text
CLOUD_MODE=true
PBI_PROJECT_DIR=/home/cdsw
CLAUDE_CLI_PATH=/ruta/al/binario/claude
```

Las credenciales del LLM deben configurarse como secretos o variables del
proyecto en Cloudera. Nunca deben agregarse al repositorio. `pbi-cli` y sus
skills se instalan desde `requirements.txt`; Claude CLI debe estar disponible
en el runtime.

Para Microsoft Foundry, la aplicación hereda estas variables:

```text
CLAUDE_CODE_USE_FOUNDRY=1
ANTHROPIC_FOUNDRY_BASE_URL=https://<resource>.services.ai.azure.com/anthropic
ANTHROPIC_FOUNDRY_API_KEY=<secret>
ANTHROPIC_MODEL=<deployment-name>
ANTHROPIC_DEFAULT_SONNET_MODEL=<deployment-name>
```

Más información en [README_CLOUDERA.md](README_CLOUDERA.md).

## Archivos que no se publican

- `.env` y configuraciones locales.
- Credenciales o tokens.
- Logs y estadísticas de uso.
- Reportes cargados en `uploads/`.
- Cachés y entornos virtuales.
