from __future__ import annotations

import csv
import json
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .scoring import safe_for_review


PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>YottaFlex | Supportive retention review</title>
<style>
:root{font-family:Inter,ui-sans-serif,system-ui,"Segoe UI",sans-serif;color:#142b3b;background:#f4f7fa;font-synthesis:none}*{box-sizing:border-box}body{margin:0}.wrap{max-width:1180px;margin:auto;padding:30px 22px 56px}.top{display:flex;justify-content:space-between;gap:16px;align-items:center}.brand{font-size:13px;letter-spacing:.13em;color:#526c7c;font-weight:700}.pill{border:1px solid #b4d8ce;background:#e4f5ef;border-radius:999px;padding:7px 12px;color:#20614f;font-size:12px;font-weight:700}.hero{margin:28px 0 22px}.hero h1{margin:0;font-size:34px;letter-spacing:-.035em}.hero p{color:#586e7c;max-width:760px;line-height:1.6}.notice{background:#fff8e7;border:1px solid #f0d99d;color:#654e14;padding:13px 15px;border-radius:10px;font-size:13px;line-height:1.5}.cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:18px 0}.card,.panel{background:white;border:1px solid #e3eaf0;border-radius:12px;padding:18px;box-shadow:0 2px 8px #18354a08}.label{font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:#6a7f8d}.value{font-size:27px;font-weight:750;margin-top:7px}.sub{font-size:12px;color:#738795;margin-top:3px}.panel{padding:20px;margin-top:14px}.panel h2{font-size:18px;margin:0 0 14px}.toolbar{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:14px}input,select{font:inherit;border:1px solid #cbd6de;border-radius:8px;padding:9px 11px;background:white;color:#1c3444}input{min-width:230px;flex:1}table{border-collapse:collapse;width:100%;font-size:13px}th{text-align:left;color:#657b89;font-size:11px;text-transform:uppercase;letter-spacing:.07em;padding:10px 8px;border-bottom:1px solid #e4ebef}td{padding:12px 8px;border-bottom:1px solid #edf1f4;vertical-align:top}.band{font-weight:700}.priority{color:#9a3f28}.monitor{color:#936d0a}.no_signal{color:#39745e}.why{max-width:480px;line-height:1.45;color:#405766}.confidence{font-size:11px;color:#627986}.footer{font-size:12px;color:#778b98;margin-top:18px;line-height:1.5}.metricline{display:flex;gap:24px;flex-wrap:wrap;color:#425a69;font-size:13px}.metricline strong{color:#16384c}.downloads a{display:inline-block;margin-right:14px;color:#176c86;text-decoration:none;font-weight:600}.empty{padding:28px;text-align:center;color:#728793}@media(max-width:760px){.cards{grid-template-columns:repeat(2,1fr)}.hero h1{font-size:27px}table{min-width:760px}.scroll{overflow:auto}}
</style></head><body><main class="wrap"><div class="top"><div class="brand">YOTTAFLEX · PEOPLE ANALYTICS</div><div class="pill">SYNTHETIC DATA · LOCAL DEMO</div></div>
<section class="hero"><h1>Supportive retention review</h1><p>Use explainable, time-bounded signals to help HR partners and managers plan thoughtful check-ins. Scores describe patterns in synthetic data; people make every decision.</p></section>
<div class="notice"><strong>Human review required.</strong> This is a supportive conversation aid only. Do not use it to make hiring, compensation, promotion, performance, or termination decisions. Missing survey responses are treated as unknown, never as negative feedback.</div>
<section class="cards"><div class="card"><div class="label">Synthetic employees</div><div class="value" id="employees">—</div><div class="sub">Included in the cohort</div></div><div class="card"><div class="label">Priority conversations</div><div class="value" id="priority">—</div><div class="sub">Rule threshold ≥ 60</div></div><div class="card"><div class="label">Monitor signals</div><div class="value" id="monitor">—</div><div class="sub">Rule threshold 40–59</div></div><div class="card"><div class="label">Survey missingness</div><div class="value" id="missing">—</div><div class="sub">Responses marked unknown</div></div></section>
<section class="panel"><h2>Temporal evaluation</h2><div class="metricline" id="metrics">Loading evaluation…</div><div class="footer">Held-out cohort scored using history through 2026-06-30 and compared with simulated voluntary exits from 2026-07 through 2026-12. Synthetic metrics are for workflow demonstration, not model validation.</div></section>
<section class="panel"><h2>Review queue</h2><div class="toolbar"><input id="q" placeholder="Search synthetic employee ID or explanation"><select id="band"><option value="">All priority bands</option><option value="priority">Priority</option><option value="monitor">Monitor</option><option value="no_signal">No signal</option></select><select id="confidence"><option value="">All confidence levels</option><option>high</option><option>medium</option><option>low</option></select></div><div class="scroll"><table><thead><tr><th>Employee</th><th>Band</th><th>Signal</th><th>Confidence</th><th>Explainable factors</th><th>Next step</th></tr></thead><tbody id="rows"></tbody></table></div><div id="empty" class="empty" hidden>No matching records.</div></section>
<section class="panel downloads"><h2>Artifacts</h2><a href="/files/evaluation_metrics.json">Evaluation metrics</a><a href="/files/validation_summary.json">Validation report</a><a href="/files/ground_truth.json">Separate ground truth</a><a href="/files/feature_manifest.json">Feature cutoff manifest</a></section><div class="footer">This demo contains no real employee records. Synthetic IDs are not identities. Review local setup and data dictionary in the project README.</div></main>
<script>
let records=[];const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function render(){const q=document.querySelector('#q').value.toLowerCase(),b=document.querySelector('#band').value,c=document.querySelector('#confidence').value;const rows=records.filter(r=>(!b||r.priority_band===b)&&(!c||r.confidence===c)&&(!q||(r.employee_id+' '+r.explanation).toLowerCase().includes(q))).slice(0,250);document.querySelector('#rows').innerHTML=rows.map(r=>`<tr><td><strong>${esc(r.employee_id)}</strong></td><td class="band ${esc(r.priority_band)}">${esc(r.priority_band.replace('_',' '))}</td><td>${esc(r.risk_score)}/100</td><td class="confidence">${esc(r.confidence)}</td><td class="why">${esc(r.explanation)}</td><td>Manager or HR partner to review context and offer a voluntary check-in</td></tr>`).join('');document.querySelector('#empty').hidden=rows.length>0}
Promise.all([fetch('/api/summary').then(r=>r.json()),fetch('/api/candidates').then(r=>r.json()),fetch('/api/metrics').then(r=>r.json())]).then(([s,c,m])=>{records=c;document.querySelector('#employees').textContent=s.employees.toLocaleString();document.querySelector('#priority').textContent=s.priority.toLocaleString();document.querySelector('#monitor').textContent=s.monitor.toLocaleString();document.querySelector('#missing').textContent=s.missing_survey_rate+'%';document.querySelector('#metrics').innerHTML=`Holdout: <strong>${m.held_out_employee_count}</strong> · prevalence: <strong>${m.holdout_prevalence??'—'}</strong> · ROC AUC: <strong>${m.roc_auc??'—'}</strong> · precision @ top 20%: <strong>${m.precision_at_top_20pct??'—'}</strong> · lift: <strong>${m.lift_at_top_20pct??'—'}</strong>`;render()});['q','band','confidence'].forEach(id=>document.querySelector('#'+id).addEventListener(id==='q'?'input':'change',render));
</script></body></html>'''


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def handler_for(data_dir: Path):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            parsed = urlparse(self.path)
            route = parsed.path
            if route == "/": return self.send_body(PAGE.encode(), "text/html; charset=utf-8")
            if route.startswith("/files/"):
                name = route.split("/", 2)[-1]
                if name not in {"evaluation_metrics.json", "validation_summary.json", "ground_truth.json", "feature_manifest.json"}:
                    return self.send_error(404)
                target = data_dir / name
                if not target.exists(): return self.send_error(404)
                return self.send_body(target.read_bytes(), "application/json; charset=utf-8")
            if route == "/api/candidates":
                rows = [r for r in load_csv(data_dir / "risk_scores.csv") if safe_for_review(r)]
                for r in rows: r["risk_score"] = int(r["risk_score"])
                return self.send_json(rows)
            if route == "/api/summary":
                scores = load_csv(data_dir / "risk_scores.csv")
                surveys = load_csv(data_dir / "engagement_surveys.csv")
                bands = Counter(s["priority_band"] for s in scores)
                total = len(surveys); missing = sum(s["response_status"] == "missing" for s in surveys)
                return self.send_json({"employees": len(scores), "priority": bands["priority"], "monitor": bands["monitor"], "missing_survey_rate": round(100*missing/total, 1) if total else 0})
            if route == "/api/metrics":
                target = data_dir / "evaluation_metrics.json"
                return self.send_body(target.read_bytes(), "application/json; charset=utf-8") if target.exists() else self.send_error(404)
            return self.send_error(404)

        def send_json(self, value):
            return self.send_body(json.dumps(value).encode(), "application/json; charset=utf-8")

        def send_body(self, body: bytes, content_type: str):
            self.send_response(200); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store"); self.end_headers(); self.wfile.write(body)

        def log_message(self, fmt, *args):
            print(f"{self.client_address[0]} - {fmt % args}")
    return Handler


def serve(data_dir: Path, host: str = "127.0.0.1", port: int = 8000) -> None:
    data_dir = data_dir.resolve()
    if not (data_dir / "risk_scores.csv").exists():
        raise SystemExit(f"No generated dataset at {data_dir}; run: python -m yottaflex generate --size starter")
    server = ThreadingHTTPServer((host, port), handler_for(data_dir))
    print(f"Local review dashboard: http://{host}:{port} (Ctrl+C to stop)")
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
