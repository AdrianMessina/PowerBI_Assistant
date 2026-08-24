# ✅ Checklist de Deployment - Cloudera AI Workbench

## Pre-Deployment

- [x] `.project-metadata.yaml` creado y configurado
- [x] `requirements.txt` con todas las dependencias
- [x] `cml/launch_app.py` script de inicio
- [x] `.gitignore` configurado
- [x] `.env.example` documentado
- [x] Detección de ambiente cloud/local en `server.py`
- [x] Soporte para `--port` en servidor
- [x] README_CLOUDERA.md con instrucciones completas

## Archivos Críticos

```
✅ .project-metadata.yaml  → Config de Cloudera
✅ requirements.txt        → Dependencias Python
✅ cml/launch_app.py      → Script de inicio
✅ server.py              → Backend (con detección cloud)
✅ index.html             → Frontend
✅ usage_logger.py        → Logging
✅ config.json            → Configuración runtime
```

## Verificaciones Pre-Upload

### 1. Verificar estructura de archivos
```bash
cd "C:\Users\SE46958\1 - Claude - Proyecto viz\PBI CLi 2.0\pbi-cli\web"
ls -la
```

Debe contener:
- `.project-metadata.yaml` ✓
- `requirements.txt` ✓
- `cml/launch_app.py` ✓
- `server.py` ✓
- `index.html` ✓
- `.gitignore` ✓

### 2. Limpiar archivos innecesarios
```bash
# Eliminar cache Python
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

# Eliminar logs locales (se crearán en cloud)
rm -rf logs/

# Eliminar uploads locales
rm -rf uploads/

# Eliminar .env local (usar .env.example)
rm -f .env
```

### 3. Crear archivo ZIP para upload
```bash
# Opción A: Desde Git Bash / Linux
cd "C:\Users\SE46958\1 - Claude - Proyecto viz\PBI CLi 2.0\pbi-cli"
zip -r pbi-cli-chat.zip web/ -x "*.pyc" -x "*__pycache__*" -x "*/logs/*" -x "*/uploads/*" -x "*/.env"

# Opción B: Desde PowerShell
Compress-Archive -Path "web\*" -DestinationPath "pbi-cli-chat.zip" -Force
```

## Deployment Steps

### 🔵 Opción 1: Upload Manual (Más Rápido)

1. **Comprimir proyecto**
   - Ejecutar script de creación de ZIP (arriba)
   - Verificar que `pbi-cli-chat.zip` se creó

2. **Subir a Cloudera**
   - Ir a: https://ml-1b92dce9-f6e.apdazrus.yu7q-bef3.a2.cloudera.site/applications
   - Click: **+ New Application**
   - Seleccionar: **Upload Project**
   - Arrastrar: `pbi-cli-chat.zip`
   - Cloudera detectará automáticamente `.project-metadata.yaml`

3. **Configurar (Automático)**
   - Cloudera leerá `.project-metadata.yaml`
   - Asignará: Python 3.11, 2 CPU, 4GB RAM
   - Variables de entorno: `CLOUD_MODE=true`

4. **Lanzar**
   - Click: **Start Application**
   - Esperar ~2-3 min (instalación de dependencias)
   - Acceder via URL generada

### 🟢 Opción 2: Git Push (Más Profesional)

1. **Inicializar Git (si no existe)**
   ```bash
   cd "C:\Users\SE46958\1 - Claude - Proyecto viz\PBI CLi 2.0\pbi-cli\web"
   git init
   git add .
   git commit -m "feat: PBI CLI Chat - Initial deployment"
   ```

2. **Push a repositorio corporativo**
   ```bash
   git remote add origin <URL_REPO_YPF>
   git push -u origin main
   ```

3. **Importar en Cloudera**
   - **New Project** > **Git**
   - URL del repositorio
   - Branch: `main`
   - Cloudera clonará y detectará config

## Post-Deployment

### ✅ Verificaciones Inmediatas

1. **Aplicación arrancó correctamente**
   - Estado: ✅ Running (verde)
   - No hay errores en Logs

2. **Verificar endpoint de salud**
   ```bash
   curl https://<tu-app-url>/api/status
   # Debe retornar JSON con status
   ```

3. **Verificar UI**
   - Abrir URL de la app en navegador
   - Header visible con "PBI CLI Chat"
   - Status badge muestra "Verificando..."

4. **Verificar Claude CLI**
   - Logs deben mostrar: `[OK] Claude CLI: <ruta>`
   - Si no: seguir instrucciones de troubleshooting

### 🔧 Configuración Adicional (Opcional)

#### Agregar directorios de búsqueda PBIP

En la UI de la app:
1. Click en status badge
2. Click en "⚙️ Configurar"
3. Pegar ruta: `/home/cdsw/reportes` (ejemplo)
4. Guardar

O via API:
```bash
curl -X POST https://<app-url>/api/set-pbip-path \
  -H "Content-Type: application/json" \
  -d '{"path": "/home/cdsw/reportes"}'
```

#### Configurar logging PostgreSQL (opcional)

Si quieres usar PostgreSQL en vez de SQLite:

1. **Project Settings** > **Environment Variables**
   ```
   LOG_BACKEND=postgres
   LOG_POSTGRES_HOST=<host>
   LOG_POSTGRES_DB=pbi_cli_logs
   LOG_POSTGRES_USER=<user>
   LOG_POSTGRES_PASSWORD=<password>
   ```

2. Instalar driver:
   ```bash
   pip install psycopg2-binary
   ```

## Testing Inicial

### Test 1: Chat Básico
1. Abrir app en navegador
2. Escribir: "Hola, ¿cómo estás?"
3. Enviar
4. Debe responder en tono porteño

### Test 2: Status Check
1. Click en status badge (esquina superior derecha)
2. Verificar 3 pasos:
   - ✅ CLI instalado
   - ⚠️ Conectado (esperado si no hay Power BI Desktop)
   - ⚠️ PBIP (esperado si no hay archivos)

### Test 3: API Discovery (Nuevo)
```bash
curl -X POST https://<app-url>/api/discover-pbip \
  -H "Content-Type: application/json" \
  -d '{"search_paths": ["/home/cdsw"]}'
```

Debe retornar:
```json
{
  "success": true,
  "count": 0,
  "files": [],
  "search_paths": ["/home/cdsw"]
}
```

## 🎯 Próximos Pasos (Post-Deployment)

Una vez que la app esté corriendo en Cloudera:

1. ✅ **Deployment exitoso** ← ESTAMOS AQUÍ
2. 🚧 Agregar switch Modo Normal/Masivo en UI
3. 🚧 Implementar panel de selección múltiple
4. 🚧 Integrar operaciones batch (analyze, fix, layout)
5. 🚧 Integrar módulos YPF BI Monitor
6. 🚧 Integrar módulos Power BI Fixer
7. 🚧 Testing de operaciones masivas

## 📞 Contacto

¿Problemas durante el deployment?
- **Slack:** #powerbi-automation
- **Email:** Data Analytics Team
- **Docs:** README_CLOUDERA.md

---

**Status:** ✅ Listo para deployment  
**Última revisión:** Mayo 2026
