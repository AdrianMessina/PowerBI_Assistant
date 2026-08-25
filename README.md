# PowerBI Assistant

Interfaz web conversacional para analizar Power BI mediante Microsoft Foundry
o Claude CLI y `pbi-cli`. Incluye respuestas en streaming, estados de ejecución
y métricas de latencia.

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
proyecto en Cloudera. Nunca deben agregarse al repositorio. `pbi-cli`, sus
skills y el SDK de Anthropic se instalan desde `requirements.txt`. En Cloudera,
la aplicación usa Foundry directamente y no necesita Node ni Claude CLI.

Para Microsoft Foundry, la aplicación hereda estas variables:

```text
CLAUDE_CODE_USE_FOUNDRY=1
ANTHROPIC_FOUNDRY_BASE_URL=https://<resource>.services.ai.azure.com/anthropic
ANTHROPIC_FOUNDRY_API_KEY=<secret>
ANTHROPIC_MODEL=<deployment-name>
ANTHROPIC_DEFAULT_SONNET_MODEL=<deployment-name>
```

Más información en [README_CLOUDERA.md](README_CLOUDERA.md).

## Uso de PBIP en Cloudera

Cloudera trabaja en modo offline con el proyecto PBIP; no intenta conectarse
al Power BI Desktop de la PC del usuario. Desde **Configurar**, se debe subir un
ZIP que conserve junta la estructura exportada por Power BI Desktop:

```text
MiReporte.pbip
MiReporte.Report/
MiReporte.SemanticModel/
```

El `.pbip` solo es un descriptor y no sirve aislado. El servidor descomprime el
ZIP, valida que existan los artifacts referenciados y recién entonces lo marca
como proyecto activo. Los proyectos cargados quedan en `uploads/`, fuera de Git.

Con un PBIP activo, **Configurar → Exportar informe KPI HTML** analiza los
metadatos del modelo y genera:

- KPI existentes y KPI de negocio propuestos.
- Medidas y cálculos DAX con su fundamento y fuentes utilizadas.
- Hallazgos, limitaciones y recomendaciones ejecutivas.
- Un HTML autocontenido con logo de YPF, buscador, filtros, copia de DAX,
  descarga del análisis en JSON e impresión a PDF.

El informe no inventa resultados: cuando el PBIP aporta estructura pero no los
datos ejecutados, identifica el valor como `Requiere ejecución sobre datos`.

## Métricas de uso

La aplicación conserva eventos en `logs/usage_YYYYMMDD.jsonl` dentro del
proyecto de Cloudera. Registra usuario, PBIP, conversación, mensajes, latencia,
tokens de entrada/salida informados por Foundry y una estimación del contexto
PBIP al cargarlo. Cada usuario ve sus propias métricas; los usuarios de
`admin_users` y `PROJECT_OWNER` ven el consolidado global y por proyecto.

## Archivos que no se publican

- `.env` y configuraciones locales.
- Credenciales o tokens.
- Logs y estadísticas de uso.
- Reportes cargados en `uploads/`.
- Cachés y entornos virtuales.
