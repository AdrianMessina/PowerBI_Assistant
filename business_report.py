"""Build an executive KPI report from PBIP metadata."""

import base64
import html
import json
import re
from datetime import datetime
from pathlib import Path


TEXT_EXTENSIONS = {".tmdl", ".dax", ".json", ".pbir", ".pbism", ".pbiqviz", ".txt"}
SKIP_PARTS = {".git", ".pbi", "cache", "uploads"}


def collect_pbip_context(pbip_path, max_chars=140_000, max_file_chars=30_000):
    """Collect bounded, text-only model/report metadata from a validated PBIP."""
    pbip_path = Path(pbip_path).resolve()
    root = pbip_path.parent
    candidates = [pbip_path]
    candidates.extend(
        path for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in TEXT_EXTENSIONS
        and not any(part.lower() in SKIP_PARTS for part in path.relative_to(root).parts)
    )
    priority = {".tmdl": 0, ".dax": 1, ".pbism": 2, ".pbir": 3, ".json": 4}
    candidates = sorted(set(candidates), key=lambda p: (priority.get(p.suffix.lower(), 9), str(p)))

    sections = []
    used = 0
    for path in candidates:
        if used >= max_chars:
            break
        try:
            text = path.read_text(encoding="utf-8-sig", errors="replace")
        except OSError:
            continue
        # Avoid forwarding credentials accidentally embedded in connection metadata.
        text = re.sub(
            r"(?im)(password|pwd|access[_-]?token|api[_-]?key|client[_-]?secret)(\s*[:=]\s*)[^\s,;\"']+",
            r"\1\2[REDACTED]",
            text,
        )
        remaining = max_chars - used
        text = text[: min(max_file_chars, remaining)]
        relative = path.relative_to(root).as_posix()
        section = f"\n--- ARCHIVO: {relative} ---\n{text}"
        sections.append(section)
        used += len(section)
    return "".join(sections), len(candidates)


def build_business_prompt(project_name, objective, context):
    objective = (objective or "Diagnóstico ejecutivo general del negocio").strip()[:1000]
    return f"""
Analizá los metadatos del proyecto Power BI `{project_name}` y prepará un informe ejecutivo de KPI.

Objetivo de negocio indicado por el usuario: {objective}

Reglas obligatorias:
- Basate solamente en tablas, columnas, medidas, relaciones y páginas visibles en los metadatos.
- No inventes valores numéricos ni afirmes haber ejecutado consultas sobre datos.
- Diferenciá cada KPI o cálculo como `existing` si ya existe claramente en el modelo, o `proposed` si lo proponés.
- Para KPI sin valor calculable desde metadatos, usa exactamente `Requiere ejecución sobre datos` en `value`.
- Proponé DAX válido y útil para el negocio cuando haya campos suficientes. Si no los hay, dejá `dax` vacío y explicá el dato faltante.
- Los targets deben ser criterios sugeridos, nunca resultados observados, salvo que estén explícitos en el modelo.
- Redactá en español profesional, claro y accionable.
- Entregá únicamente JSON válido, sin Markdown ni comentarios.

Esquema JSON requerido:
{{
  "report_title": "string",
  "subtitle": "string",
  "executive_summary": "string",
  "kpis": [
    {{
      "name": "string",
      "category": "Comercial|Operaciones|Finanzas|Clientes|Calidad|Otro",
      "status": "existing|proposed",
      "value": "string",
      "format": "string",
      "business_question": "string",
      "description": "string",
      "dax": "string",
      "target": "string",
      "source": "tabla/medida/columna usada",
      "rationale": "string"
    }}
  ],
  "calculations": [
    {{"name":"string", "status":"existing|proposed", "dax":"string", "explanation":"string"}}
  ],
  "insights": ["string"],
  "recommendations": ["string"],
  "limitations": ["string"]
}}

Generá entre 6 y 12 KPI relevantes y hasta 10 cálculos. Metadatos PBIP:
{context}
""".strip()


def parse_business_analysis(raw_text):
    """Parse a model JSON response, tolerating a fenced response."""
    text = (raw_text or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("La IA no devolvió un informe JSON válido.")
    data = json.loads(text[start:end + 1])
    if not isinstance(data, dict) or not isinstance(data.get("kpis"), list):
        raise ValueError("El informe generado no contiene una lista de KPI válida.")
    data["kpis"] = [item for item in data["kpis"] if isinstance(item, dict)]
    if not data["kpis"]:
        raise ValueError("El informe generado no contiene KPI utilizables.")
    for key in ("calculations", "insights", "recommendations", "limitations"):
        if not isinstance(data.get(key), list):
            data[key] = []
    data["calculations"] = [item for item in data["calculations"] if isinstance(item, dict)]
    return data


def _e(value):
    return html.escape(str(value or ""), quote=True)


def _logo_data_uri(logo_path):
    path = Path(logo_path)
    if not path.is_file():
        return ""
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def render_business_html(analysis, project_name, objective, logo_path):
    """Render a self-contained, interactive and safely escaped HTML report."""
    kpis = analysis.get("kpis", [])
    calculations = analysis.get("calculations", [])
    categories = sorted({_e(item.get("category", "Otro")) for item in kpis})
    logo_uri = _logo_data_uri(logo_path)
    created = datetime.now().astimezone().strftime("%d/%m/%Y %H:%M")

    category_options = "".join(f'<option value="{cat}">{cat}</option>' for cat in categories)
    kpi_cards = []
    for index, item in enumerate(kpis):
        status = "existing" if item.get("status") == "existing" else "proposed"
        status_label = "Existente" if status == "existing" else "Propuesto"
        searchable = " ".join(str(item.get(key, "")) for key in (
            "name", "category", "description", "business_question", "source"
        )).lower()
        dax = _e(item.get("dax") or "No disponible con los metadatos actuales")
        kpi_cards.append(f"""
        <article class="kpi-card" data-category="{_e(item.get('category', 'Otro'))}"
                 data-status="{status}" data-search="{_e(searchable)}">
          <div class="card-top"><span class="category">{_e(item.get('category', 'Otro'))}</span>
            <span class="status {status}">{status_label}</span></div>
          <h3>{_e(item.get('name'))}</h3>
          <div class="value">{_e(item.get('value', 'Requiere ejecución sobre datos'))}</div>
          <p>{_e(item.get('description'))}</p>
          <dl><dt>Pregunta de negocio</dt><dd>{_e(item.get('business_question'))}</dd>
              <dt>Fuente</dt><dd>{_e(item.get('source'))}</dd>
              <dt>Formato</dt><dd>{_e(item.get('format'))}</dd>
              <dt>Objetivo sugerido</dt><dd>{_e(item.get('target'))}</dd></dl>
          <details><summary>Ver cálculo DAX y fundamento</summary>
            <div class="code-head"><span>DAX</span><button onclick="copyDax({index}, this)">Copiar</button></div>
            <pre id="dax-{index}">{dax}</pre><p class="rationale">{_e(item.get('rationale'))}</p>
          </details>
        </article>""")

    calc_cards = "".join(f"""
      <article class="calc"><div><strong>{_e(item.get('name'))}</strong>
      <span class="status {'existing' if item.get('status') == 'existing' else 'proposed'}">
      {'Existente' if item.get('status') == 'existing' else 'Propuesto'}</span></div>
      <p>{_e(item.get('explanation'))}</p><pre>{_e(item.get('dax'))}</pre></article>
    """ for item in calculations)

    def list_items(name):
        return "".join(f"<li>{_e(value)}</li>" for value in analysis.get(name, [])) or "<li>Sin observaciones.</li>"

    embedded_json = (json.dumps(analysis, ensure_ascii=False)
                     .replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e"))
    return f"""<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(analysis.get('report_title', 'Informe ejecutivo KPI'))}</title>
<style>
:root{{--yellow:#f2c811;--blue:#0066b3;--navy:#101522;--panel:#182033;--text:#eef2f8;--muted:#a7b1c2;--line:#2b3549}}
*{{box-sizing:border-box}} body{{margin:0;background:#0b0f18;color:var(--text);font:15px/1.5 Arial,sans-serif}}
header{{background:linear-gradient(125deg,#111827,#17243b);border-bottom:3px solid var(--yellow);padding:24px 5vw;display:flex;gap:24px;align-items:center}}
header img{{width:92px;max-height:62px;object-fit:contain;background:white;border-radius:6px;padding:7px}} h1{{margin:0;font-size:clamp(24px,4vw,42px)}}
.sub{{color:var(--muted)}} main{{max-width:1440px;margin:auto;padding:28px 5vw 60px}} .summary{{background:var(--panel);border-left:5px solid var(--yellow);padding:20px;border-radius:10px;margin-bottom:24px}}
.toolbar{{position:sticky;top:0;z-index:4;display:flex;gap:10px;flex-wrap:wrap;padding:14px;background:#0b0f18eF;border-bottom:1px solid var(--line)}}
input,select,button{{border:1px solid var(--line);background:#131a29;color:var(--text);padding:10px 12px;border-radius:8px}} input{{flex:1;min-width:220px}} button{{cursor:pointer}} button:hover{{border-color:var(--yellow)}}
.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin:20px 0}} .stat{{background:var(--panel);padding:16px;border-radius:10px}} .stat b{{font-size:26px;color:var(--yellow);display:block}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px}} .kpi-card,.calc{{background:var(--panel);border:1px solid var(--line);padding:18px;border-radius:12px}} .kpi-card:hover{{transform:translateY(-2px);border-color:#53617a}}
.card-top{{display:flex;justify-content:space-between}} .category,.status{{font-size:12px;padding:3px 8px;border-radius:12px;background:#253049}} .existing{{color:#70e19c}} .proposed{{color:#ffd75e}}
h2{{margin-top:34px}} h3{{font-size:20px;margin:15px 0 4px}} .value{{color:var(--yellow);font-size:18px;font-weight:bold}} dl{{display:grid;grid-template-columns:130px 1fr;gap:5px 10px}} dt{{color:var(--muted)}} dd{{margin:0}}
details{{border-top:1px solid var(--line);margin-top:14px;padding-top:12px}} summary{{cursor:pointer;color:#8fcaff}} pre{{white-space:pre-wrap;overflow:auto;background:#0d121d;padding:12px;border-radius:8px;color:#d8e7ff}}
.code-head{{display:flex;justify-content:space-between;align-items:center;margin-top:10px}} .rationale{{color:var(--muted)}} .columns{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:18px}}
footer{{color:var(--muted);text-align:center;border-top:1px solid var(--line);padding:22px}} .hidden{{display:none!important}}
@media print{{body{{background:white;color:#111}} .toolbar,button{{display:none}} .kpi-card,.calc,.summary,.stat{{break-inside:avoid;background:white;border-color:#bbb}} pre{{background:#f3f3f3;color:#111}}}}
</style></head><body>
<header>{f'<img src="{logo_uri}" alt="YPF">' if logo_uri else '<strong>YPF</strong>'}<div><h1>{_e(analysis.get('report_title', 'Informe ejecutivo KPI'))}</h1><div class="sub">{_e(analysis.get('subtitle'))}<br>Proyecto: {_e(project_name)} · Generado: {created}</div></div></header>
<main><section class="summary"><strong>Resumen ejecutivo</strong><p>{_e(analysis.get('executive_summary'))}</p><small>Objetivo: {_e(objective or 'Diagnóstico ejecutivo general')}</small></section>
<div class="stats"><div class="stat"><b>{len(kpis)}</b>KPI identificados</div><div class="stat"><b>{sum(1 for x in kpis if x.get('status') == 'existing')}</b>Existentes</div><div class="stat"><b>{sum(1 for x in kpis if x.get('status') != 'existing')}</b>Propuestos</div></div>
<div class="toolbar"><input id="search" placeholder="Buscar KPI, fuente o concepto..." oninput="filterCards()"><select id="category" onchange="filterCards()"><option value="">Todas las categorías</option>{category_options}</select><select id="status" onchange="filterCards()"><option value="">Todos</option><option value="existing">Existentes</option><option value="proposed">Propuestos</option></select><button onclick="window.print()">Imprimir / PDF</button><button onclick="downloadJson()">Descargar JSON</button></div>
<h2>KPI de negocio</h2><section class="grid" id="kpis">{''.join(kpi_cards)}</section>
<h2>Cálculos y medidas</h2><section class="grid">{calc_cards or '<p>Sin cálculos adicionales.</p>'}</section>
<section class="columns"><div><h2>Hallazgos</h2><ul>{list_items('insights')}</ul></div><div><h2>Recomendaciones</h2><ul>{list_items('recommendations')}</ul></div><div><h2>Limitaciones</h2><ul>{list_items('limitations')}<li>Los valores reales requieren ejecutar las medidas sobre el modelo y sus fuentes de datos.</li></ul></div></section>
</main><footer>Power BI Assistant · Informe PBIP offline · Identidad visual YPF</footer>
<script id="report-data" type="application/json">{embedded_json}</script><script>
function filterCards(){{const q=document.getElementById('search').value.toLowerCase(),c=document.getElementById('category').value,s=document.getElementById('status').value;document.querySelectorAll('.kpi-card').forEach(x=>x.classList.toggle('hidden',!!((q&&!x.dataset.search.includes(q))||(c&&x.dataset.category!==c)||(s&&x.dataset.status!==s))))}}
function copyDax(i,b){{navigator.clipboard.writeText(document.getElementById('dax-'+i).textContent).then(()=>{{const old=b.textContent;b.textContent='Copiado';setTimeout(()=>b.textContent=old,1200)}})}}
function downloadJson(){{const text=document.getElementById('report-data').textContent,blob=new Blob([text],{{type:'application/json'}}),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='informe-kpi.json';a.click();URL.revokeObjectURL(a.href)}}
</script></body></html>"""
