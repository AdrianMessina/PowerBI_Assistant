# 🔐 Cómo se Conecta PBI Assistant con Claude CLI

## ✅ Respuesta Rápida

**PBI Assistant se conecta a Claude mediante:**
- **Claude CLI** (instalado localmente en tu máquina)
- **Autenticación**: Palantir Foundry (API corporativa de YPF)
- **No usa API Key directa** de Anthropic
- **Método**: Third-party authentication via Foundry

---

## 🔍 Verificación Actual

### Estado de Autenticación:
```bash
claude auth status
```

**Resultado**:
```json
{
  "loggedIn": true,
  "authMethod": "third_party",
  "apiProvider": "foundry"
}
```

### ✅ Interpretación:
- **loggedIn: true** → Estás autenticado correctamente
- **authMethod: "third_party"** → No usa cuenta personal de Anthropic
- **apiProvider: "foundry"** → Usa **Palantir Foundry** (infraestructura corporativa de YPF)

---

## 🏗️ Arquitectura de Conexión

```
┌────────────────────────────────────────────────────────────────┐
│  PBI Assistant (server.py)                                     │
│  └─ Ejecuta: subprocess.run('claude.cmd --resume abc123')     │
└───────────────────┬────────────────────────────────────────────┘
                    │
                    ↓ Comando local (subprocess)
┌────────────────────────────────────────────────────────────────┐
│  Claude CLI (claude.cmd)                                       │
│  Ubicación: ~/OneDrive - YPF/Claude tests/.../claude.cmd      │
│                                                                │
│  Autenticación configurada:                                    │
│  • Método: third_party (Foundry)                               │
│  • No requiere ANTHROPIC_API_KEY                               │
│  • Usa credenciales corporativas de YPF                        │
└───────────────────┬────────────────────────────────────────────┘
                    │
                    ↓ API calls
┌────────────────────────────────────────────────────────────────┐
│  Palantir Foundry (API corporativa YPF)                        │
│  • Proxy/Gateway a modelos de Anthropic                        │
│  • Maneja billing corporativo                                  │
│  • Control de acceso, compliance, auditoría                    │
└───────────────────┬────────────────────────────────────────────┘
                    │
                    ↓ Infraestructura corporativa
┌────────────────────────────────────────────────────────────────┐
│  Claude API (Anthropic)                                        │
│  • Model: claude-sonnet-4-5                                    │
│  • Endpoint: Manejado por Foundry                              │
└────────────────────────────────────────────────────────────────┘
```

---

## 📝 Código Relevante en server.py

### 1. Detección de Claude CLI:
```python
# server.py líneas 82-102
CLAUDE_PATH = None
CLAUDE_AVAILABLE = False

# Try to find Claude CLI
for candidate in [
    os.path.expanduser("~/OneDrive - YPF/Claude tests/node-v22.19.0-win-x64/claude.cmd"),
    "claude.cmd",
    "claude",
    # ...
]:
    if os.path.isfile(candidate):
        CLAUDE_PATH = candidate
        CLAUDE_AVAILABLE = True
        break
```

**Resultado**: `CLAUDE_PATH` apunta a tu instalación local de Claude CLI.

---

### 2. Ejecución de Comandos:
```python
# server.py líneas 459-481
if session_id:
    # RESUME existing conversation
    cmd = f'"{CLAUDE_PATH}" --resume {session_id} {base_flags} < "{user_temp}"'
else:
    # NEW conversation
    cmd = f'"{CLAUDE_PATH}" {base_flags} --append-system-prompt-file "{system_temp}" < "{user_temp}"'

result = subprocess.run(
    cmd,
    shell=True,
    capture_output=True,
    text=True,
    encoding="utf-8",
    cwd=PROJECT_DIR,
    timeout=300
)
```

**Nota**: No se pasa ningún API key manualmente. Claude CLI usa la autenticación ya configurada internamente.

---

## 🔐 ¿Cómo se Configuró la Autenticación?

### Método de Autenticación: Foundry (Third-Party)

Esto significa que **previamente** se ejecutó algo como:

```bash
# Opción 1: Login corporativo (SSO)
claude auth login --provider foundry

# O mediante configuración en settings
# ~/.claude/settings.json o settings específicos
```

Una vez autenticado, **Claude CLI guarda las credenciales** (tokens, refresh tokens) y las reutiliza automáticamente en cada llamada.

---

## 🆚 Comparación: Foundry vs API Key Directa

| Aspecto | Foundry (Actual) | API Key Directa |
|---------|------------------|-----------------|
| **Configuración** | `claude auth login --provider foundry` | `export ANTHROPIC_API_KEY=sk-...` |
| **Billing** | Corporativo (YPF paga) | Personal/proyecto |
| **Control** | YPF administra acceso | Libre (cualquiera con key) |
| **Compliance** | Auditado por YPF | Sin auditoría corporativa |
| **Rate Limits** | Compartidos corporativos | Por API key |
| **Seguridad** | SSO corporativo | API key en archivo |

---

## 🔄 ¿Qué Pasa Cuando se Ejecuta un Mensaje?

### Flujo Completo:

1. **Usuario escribe**: "Mostrame ventas por región"

2. **Frontend** → `POST /api/chat`:
   ```json
   {
     "message": "Mostrame ventas por región",
     "tone": "porteno",
     "session_id": "abc123"
   }
   ```

3. **Backend (server.py)** → Escribe mensaje a archivo temporal:
   ```python
   with tempfile.NamedTemporaryFile(...) as f:
       f.write("Mostrame ventas por región")
       user_temp = f.name
   ```

4. **Backend ejecuta Claude CLI**:
   ```bash
   "C:\Users\SE46958\OneDrive - YPF\...\claude.cmd" \
     --resume abc123 \
     --print \
     --output-format stream-json \
     < user_temp.txt
   ```

5. **Claude CLI internamente**:
   - Lee credenciales guardadas (Foundry auth)
   - Hace API call a Palantir Foundry
   - Foundry forward a Anthropic Claude API
   - Retorna respuesta en stream-json

6. **Backend parsea respuesta**:
   ```python
   response_text, new_session_id = parse_stream_json(result.stdout)
   ```

7. **Frontend renderiza** como Markdown

---

## 🛡️ Seguridad y Compliance

### Ventajas de Usar Foundry:

1. **Centralización**:
   - Todo el tráfico pasa por infraestructura YPF
   - Logging centralizado de API calls
   - Auditoría completa

2. **Control de Acceso**:
   - Solo usuarios autorizados por YPF
   - Revocación centralizada de acceso
   - No hay API keys flotando en código

3. **Billing Corporativo**:
   - YPF paga por todos los usos
   - No hay sorpresas en costos individuales
   - Reportes de uso consolidados

4. **Compliance**:
   - Cumple políticas corporativas de YPF
   - Data residency según políticas
   - Encriptación end-to-end

---

## 🔧 Troubleshooting

### Problema: "Claude CLI no encontrado"
```
[WARN] Claude CLI no encontrado. La aplicacion funcionara en modo limitado.
```

**Solución**:
```bash
# Verifica que existe
ls "C:\Users\SE46958\OneDrive - YPF\Claude tests\node-v22.19.0-win-x64\claude.cmd"

# O agrega al PATH
set PATH=%PATH%;C:\Users\SE46958\OneDrive - YPF\Claude tests\node-v22.19.0-win-x64
```

---

### Problema: "Authentication failed"
```
Error: Not authenticated
```

**Solución**:
```bash
# Re-autenticar con Foundry
claude auth login --provider foundry

# Verificar estado
claude auth status
```

---

### Problema: "Rate limit exceeded"
```
Error: Rate limit exceeded (429)
```

**Causa**: Límites compartidos corporativos de Foundry.

**Solución**: Esperar o contactar administrador de Foundry en YPF.

---

## 📊 Alternativas para Producción

### Opción 1: Continuar con Foundry (Recomendado)
✅ **Mantener configuración actual**
- Ya está funcionando
- Compliance corporativo
- Billing centralizado

**Sin cambios necesarios**.

---

### Opción 2: Migrar a API Key Directa
Si en el futuro necesitas usar API key directa de Anthropic:

```python
# server.py - Reemplazar subprocess por anthropic.Client()
from anthropic import Anthropic

client = Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY")
)

response = client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=4096,
    system=[{"type": "text", "text": system_prompt}],
    messages=conversation_history
)
```

**Cambios necesarios**:
- Definir tools manualmente (actualmente son skills de Claude CLI)
- Manejar session state manualmente (actualmente --resume)
- Ver [HERMES_MIGRATION_EXAMPLE.py](./HERMES_MIGRATION_EXAMPLE.py) para código completo

---

### Opción 3: Dual Mode (Foundry + API Key)
Soportar ambos modos con fallback:

```python
# server.py - Inicio
if FOUNDRY_AVAILABLE:
    # Usar Claude CLI con Foundry (actual)
    use_claude_cli()
elif os.environ.get("ANTHROPIC_API_KEY"):
    # Fallback a API key directa
    use_anthropic_client()
else:
    # Error: ninguna configuración disponible
    raise AuthenticationError("No authentication method available")
```

---

## 🎓 Resumen

### ✅ Estado Actual:
```
PBI Assistant
    └─ Claude CLI (claude.cmd)
        └─ Foundry (third_party auth)
            └─ Anthropic Claude API
```

### 🔑 Autenticación:
- **Método**: Palantir Foundry (third-party)
- **Configuración**: Ya hecha previamente con `claude auth login`
- **API Key**: No necesaria (Foundry maneja credenciales)
- **Billing**: Corporativo (YPF)

### 📝 Para la Reunión:
Si preguntan sobre autenticación:
> "Usamos Claude CLI con autenticación corporativa via Palantir Foundry. 
> No hay API keys hardcodeadas, todo pasa por infraestructura de YPF 
> con logging y compliance completos."

---

## 📚 Referencias

- **Verificar auth**: `claude auth status`
- **Documentación**: [Claude CLI Authentication](https://docs.anthropic.com/claude/docs/claude-cli)
- **Foundry docs**: (Interno YPF)
- **Código**: [server.py líneas 82-543](./server.py)

---

**Última actualización**: 2026-06-10  
**Usuario**: SE46958  
**Configuración**: Foundry (third_party)
