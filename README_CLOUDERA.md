# PBI CLI Chat - Deployment en Cloudera AI Workbench

Interfaz conversacional con Claude AI + pbi-cli para Power BI, con capacidades de análisis masivo.

## 📋 Pre-requisitos

- Acceso a Cloudera AI Workbench
- Python 3.11+
- Acceso corporativo a Microsoft Foundry

## 🚀 Deployment en Cloudera

### Opción 1: Subir como New Project

1. **Comprimir el proyecto**
   ```bash
   # Desde el directorio web/
   zip -r pbi-cli-chat.zip . -x "*.pyc" -x "__pycache__/*" -x "logs/*" -x "uploads/*" -x ".env"
   ```

2. **Crear proyecto en Cloudera**
   - Ir a **Projects** > **New Project**
   - Seleccionar **Upload** 
   - Subir el archivo `pbi-cli-chat.zip`
   - El nombre del proyecto será: **PBI CLI Chat**

3. **Cloudera detectará automáticamente `.project-metadata.yaml`** y configurará:
   - Runtime: Python 3.11
   - Recursos: 2 CPU, 4GB RAM
   - Variables de entorno: `CLOUD_MODE=true`

### Opción 2: Git Push (Recomendado)

Si tienes un repositorio Git:

```bash
# Inicializar repo (si no existe)
git init
git add .
git commit -m "Initial commit - PBI CLI Chat"

# Push a tu repositorio corporativo
git remote add origin <TU_REPO_URL>
git push -u origin main
```

Luego en Cloudera:
- **New Project** > **Git**
- Pegar URL del repositorio
- Cloudera clonará y detectará `.project-metadata.yaml`

## ⚙️ Configuración Post-Deployment

### 1. Instalar Dependencias

Cloudera instalará automáticamente las dependencias de `requirements.txt`. Si necesitas instalar manualmente:

```bash
pip install -r requirements.txt
```

### 2. Configurar Variables de Entorno (Opcional)

Editar en Cloudera AI Workbench:
- **Project Settings** > **Advanced** > **Environment Variables**

Variables disponibles:
```
CLOUD_MODE=true
LOG_BACKEND=sqlite
LOG_SQLITE_PATH=/home/cdsw/pbi_cli_logs/usage.db
BATCH_MAX_WORKERS=4
ENABLE_MASS_MODE=true
```

### 3. Proveedor de IA

En Cloudera, el servidor usa el SDK de Anthropic con Microsoft Foundry. No se
necesita instalar Node ni Claude CLI. Claude CLI continúa siendo compatible
para la ejecución local.

### 4. Configurar Microsoft Foundry

La aplicación no necesita un login interactivo si el proyecto recibe las
credenciales mediante el almacén de secretos de Cloudera. Configurar:

```text
CLAUDE_CODE_USE_FOUNDRY=1
ANTHROPIC_FOUNDRY_BASE_URL=https://<resource>.services.ai.azure.com/anthropic
ANTHROPIC_FOUNDRY_API_KEY=<secret>
ANTHROPIC_MODEL=<deployment-name>
ANTHROPIC_DEFAULT_SONNET_MODEL=<deployment-name>
```

`ANTHROPIC_FOUNDRY_API_KEY` debe marcarse como secreto. No copiar archivos de
credenciales desde Windows ni publicar sus valores en GitHub.

Verificar desde una sesión de Workbench:

```bash
python -c "import anthropic; print(anthropic.__version__, hasattr(anthropic, 'AnthropicFoundry'))"
```

## 🎯 Lanzar la Aplicación

### Desde Cloudera UI (Recomendado)

1. Ir a **Applications** tab
2. Click en **New Application**
3. Cloudera detectará automáticamente la configuración desde `.project-metadata.yaml`
4. La app se lanzará en el puerto asignado por `CDSW_APP_PORT`
5. Acceder via la URL generada por Cloudera

### Desde Terminal (Desarrollo)

```bash
# Iniciar en modo cloud
export CLOUD_MODE=true
python server.py --port=8080
```

## 📁 Estructura del Proyecto

```
web/
├── .project-metadata.yaml    # Config de Cloudera
├── server.py                 # Backend HTTP + Foundry/Claude CLI
├── index.html                # Frontend UI
├── usage_logger.py           # Sistema de logging
├── requirements.txt          # Dependencias Python
├── config.json              # Config de rutas PBIP
├── .env.example             # Template de variables
├── .gitignore               # Exclusiones Git
├── cml/
│   └── launch_app.py        # Script de inicio CML
└── README_CLOUDERA.md       # Este archivo
```

## 🔧 Troubleshooting

### La aplicación no arranca

1. **Verificar logs en Cloudera:**
   - Applications tab > Tu app > Logs

2. **Verificar dependencias:**
   ```bash
   pip list | grep -E "pyyaml|requests|pandas|plotly"
   ```

3. **Verificar puerto:**
   ```bash
   echo $CDSW_APP_PORT
   # Debería mostrar un número (ej: 8090)
   ```

### Proveedor Foundry no disponible

Verificar que `anthropic` esté instalado y que las variables
`ANTHROPIC_FOUNDRY_BASE_URL`, `ANTHROPIC_FOUNDRY_API_KEY` y `ANTHROPIC_MODEL`
estén configuradas en el proyecto. Reiniciar la sesión o aplicación después de
modificar variables.

### Errores de permisos

Si aparecen errores de permisos en `/home/cdsw`:

```bash
# Crear directorio de logs
mkdir -p /home/cdsw/pbi_cli_logs
chmod 755 /home/cdsw/pbi_cli_logs
```

## 🎨 Características Actuales

### Modo Normal (Implementado)
- ✅ Chat conversacional con Claude AI
- ✅ Integración con pbi-cli skills
- ✅ Selector de tono (Porteño/Formal/Neutral)
- ✅ Detección automática de PBIP
- ✅ Upload de archivos .pbip
- ✅ Múltiples conexiones Power BI Desktop
- ✅ Sistema de logging de uso

### Modo Masivo (En Desarrollo)
- 🚧 Switch Normal/Masivo en UI
- 🚧 Detección de múltiples PBIP (API lista)
- 🚧 Selector múltiple de reportes
- 🚧 Operaciones batch (analyze, fix, layout)
- 🚧 Integración YPF BI Monitor
- 🚧 Integración Power BI Fixer

## 📞 Soporte

Para soporte técnico:
- **Email:** Data Analytics Team
- **Slack:** #powerbi-automation
- **Docs:** [Confluence - Power BI Tools]

## 🔄 Actualizaciones

Para actualizar la aplicación en Cloudera:

### Via Git:
```bash
git pull origin main
# Reiniciar la aplicación desde Cloudera UI
```

### Via Upload:
1. Exportar nueva versión como ZIP
2. En Cloudera: Project Settings > Replace Files
3. Subir nuevo ZIP
4. Reiniciar aplicación

## 📊 Monitoring

Cloudera proporciona métricas automáticas:
- **CPU/Memory usage**: Applications tab > Metrics
- **Logs**: Applications tab > Logs  
- **Usage analytics**: `/api/usage-stats` (admin only)

---

**Versión:** 2.0  
**Última actualización:** Mayo 2026  
**Autor:** YPF Data Analytics Team
