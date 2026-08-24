# Análisis: pbir.tools

## Información General
- **Repositorio**: maxanatsko/pbir.tools
- **Versión actual**: v0.9.20 (publicado: 22/05/2026)
- **Stars**: 200 ⭐
- **Forks**: 18
- **Licencia**: Other
- **Última actualización**: 27/05/2026

## ¿Qué es pbir.tools?

Es una **herramienta CLI** (Command Line Interface) especializada en trabajar con archivos **PBIR** (Power BI Report Project format) - el nuevo formato de proyecto de Power BI que usa archivos de texto plano en lugar de .pbix binario.

## Funcionalidades Principales (v0.9.20)

### Nuevas características:
1. **Code signing** - Binarios firmados digitalmente (Windows y macOS)
2. **Page conformance** (`pbir pages conform`)
   - Fuerza propiedades de formato visual (título, fondo, bordes)
   - Aplica defaults del tema
   - Preview con `--dry-run`
   - Output JSON
   - Modo idempotente

3. **Field where-used** (`pbir fields where-used`)
   - Encuentra todos los visuales y filtros que usan un campo
   - Búsqueda exacta y por substring

### Bug Fixes importantes:
- Card visuals: formato condicional de color de fuente
- Traversal de páginas por directory path (no display name)
- Reparación automática de links de grupos visuales
- Validación mejorada (orphan groups, stale interactions)
- Splash animado reemplazado por estático en Windows

## Comparación con tu aplicación actual

### Tu app (PBI CLI Chat)
| Característica | Tu App | pbir.tools |
|---|---|---|
| **Interfaz** | Web UI + Chat AI | CLI |
| **Enfoque** | Modelos semánticos (TMDL) | Reportes (PBIR) |
| **DAX** | ✅ Queries, medidas | ❌ |
| **Modelado** | ✅ Tablas, relaciones | ❌ |
| **Visuales** | ⚠️ Básico (via pbi-cli) | ✅ Avanzado |
| **Páginas** | ⚠️ Básico | ✅ Avanzado |
| **Temas** | ⚠️ Básico | ✅ Conformance |
| **AI Assistant** | ✅ Claude integration | ❌ |
| **Detección auto** | ✅ Nombre de archivo | ❌ |

## Recomendación

### ✅ **INTEGRAR** - No crear app separada

**Razones:**
1. **Complementario**: pbir.tools es fuerte en visuales/páginas, tu app en modelado/DAX
2. **Misma audiencia**: usuarios que trabajan con Power BI
3. **Sinergia**: Tu chat AI puede ejecutar comandos de pbir.tools
4. **Mejor UX**: Una sola interfaz para todo

### Cómo integrar:

```python
# En tu server.py, agregar wrapper para pbir.tools
def execute_pbir_command(command: str) -> dict:
    """Execute pbir.tools commands"""
    result = subprocess.run(
        f"pbir {command}",
        capture_output=True,
        text=True,
        shell=True
    )
    return {"output": result.stdout, "error": result.stderr}

# Agregar endpoint
@app.route("/api/pbir", methods=["POST"])
def handle_pbir():
    command = request.json.get("command")
    return execute_pbir_command(command)
```

### Funcionalidades que agregarías:

1. **Visual Management**
   - `pbir visuals list` - Listar todos los visuales
   - `pbir visuals cf` - Aplicar conditional formatting
   - `pbir visuals bind` - Bind data a visuales

2. **Page Management** 
   - `pbir pages conform` - Aplicar formato consistente
   - `pbir pages list` - Listar páginas

3. **Field Analysis**
   - `pbir fields where-used` - Ver dónde se usa un campo
   - `pbir tree` - Árbol de dependencias

4. **Validation**
   - `pbir validate` - Validar estructura PBIR

### Beneficios de la integración:

✅ Tu chat AI puede hacer: "Aplicá conditional formatting a todos los card visuals"
✅ Validación automática antes de commits
✅ Análisis de impacto: "¿Qué visuales usan la medida X?"
✅ Conformance automática de temas
✅ Mejor experiencia de usuario (GUI + AI en lugar de CLI)

## Próximos pasos sugeridos:

1. ⬇️ Descargar `pbir.exe` del último release
2. 🧪 Probarlo en tu proyecto PBIR actual
3. 🔌 Agregar wrapper en tu `server.py`
4. 🎨 Agregar botones en el frontend para funciones comunes
5. 🤖 Entrenar a Claude para usar pbir.tools commands

¿Querés que te ayude a implementar la integración?
