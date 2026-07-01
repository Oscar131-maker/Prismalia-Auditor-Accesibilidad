from fastapi import FastAPI, BackgroundTasks, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import Optional
import os
import asyncio
import sys
import json
import subprocess
import urllib.request
import xml.etree.ElementTree as ET

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from . import models
from .database import engine, get_db
from .criteria import map_issues_to_criteria, group_by_section, SECTION_ORDER
from .services.dom_checker import run_dom_checks
from .logger import get_audit_logger, get_logs, get_analysis_ids, load_logs_from_file
from .services.wp_fingerprint import get_wp_fingerprint, summarize_for_prompt
from .services.fix_advisor import get_fix_advice

app = FastAPI(title="Pa11y Accessibility Auditor")

AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD", "admin123")
PA11Y_RUNNER = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pa11y_runner.js")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

async def verify_token(authorization: Optional[str] = Header(None)):
    if authorization != f"Bearer {AUTH_PASSWORD}":
        raise HTTPException(status_code=401, detail="No autorizado")

@app.post("/login")
async def login(data: dict):
    if data.get("password") == AUTH_PASSWORD:
        return {"token": AUTH_PASSWORD}
    raise HTTPException(status_code=401, detail="Contraseña incorrecta")


NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Pa11yAuditor/1.0)"}


def _fetch_xml(url: str):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=12) as resp:
        return ET.fromstring(resp.read())


def _is_sitemap_index(root) -> bool:
    tag = root.tag.lower()
    return "sitemapindex" in tag


def _extract_page_urls(root) -> list[str]:
    """Extract <loc> entries from a regular sitemap (not an index)."""
    return [el.text.strip() for el in root.findall(".//sm:loc", NS) if el.text and el.text.strip()]


def _extract_sub_sitemaps(root) -> list[str]:
    """Extract child sitemap <loc> entries from a sitemapindex."""
    return [el.text.strip() for el in root.findall(".//sm:sitemap/sm:loc", NS) if el.text and el.text.strip()]


def fetch_sitemap_urls(base_url: str, limit: int) -> list[str]:
    base = base_url.rstrip("/")
    candidates = [
        f"{base}/sitemap.xml",
        f"{base}/sitemap_index.xml",
        f"{base}/sitemap",
    ]

    for sitemap_url in candidates:
        try:
            root = _fetch_xml(sitemap_url)
        except Exception:
            continue

        if _is_sitemap_index(root):
            # It's an index: fetch every child sitemap and collect real page URLs
            sub_sitemaps = _extract_sub_sitemaps(root)
            page_urls: list[str] = []
            for sub_url in sub_sitemaps:
                try:
                    sub_root = _fetch_xml(sub_url)
                    page_urls.extend(_extract_page_urls(sub_root))
                except Exception:
                    continue
                if len(page_urls) >= limit:
                    break
            if page_urls:
                return page_urls[:limit]
        else:
            # It's a regular sitemap: URLs are directly inside
            page_urls = _extract_page_urls(root)
            if page_urls:
                return page_urls[:limit]

    # Fallback: audit just the root URL
    return [base_url]


PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))

def run_pa11y(urls: list[str]) -> list[dict]:
    payload = json.dumps({"urls": urls, "standard": "WCAG2AA", "timeout": 60000})
    result = subprocess.run(
        ["node", PA11Y_RUNNER, payload],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
        cwd=PROJECT_ROOT,
    )
    stdout = (result.stdout or "").strip()
    if not stdout:
        stderr_hint = (result.stderr or "")[:800]
        raise RuntimeError(
            f"pa11y no produjo salida (returncode={result.returncode}). "
            f"stderr: {stderr_hint}"
        )
    return json.loads(stdout)


def run_dom_checks_for_urls(urls: list[str], analysis_id: int | None = None) -> dict[str, list[dict]]:
    """Ejecuta los checks DOM con Playwright sync para cada URL. Devuelve {url: [issues]}."""
    import time
    from playwright.sync_api import sync_playwright
    log = get_audit_logger(analysis_id) if analysis_id else get_audit_logger("global")
    results: dict[str, list[dict]] = {}
    log.info("dom-checker iniciado", phase="dom-checker", total_urls=len(urls))
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for url in urls:
            issues: list[dict] = []
            t0 = time.monotonic()
            try:
                page = browser.new_page()
                log.info("navegando a página", phase="dom-checker", url=url)
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(500)
                issues = run_dom_checks(page)
                dur = int((time.monotonic() - t0) * 1000)
                errors   = sum(1 for i in issues if i["type"] == "error")
                warnings = sum(1 for i in issues if i["type"] == "warning")
                notices  = sum(1 for i in issues if i["type"] == "notice")
                log.info(
                    "dom-checker completado",
                    phase="dom-checker", url=url,
                    duration_ms=dur, total_issues=len(issues),
                    errors=errors, warnings=warnings, notices=notices,
                )
            except Exception as exc:
                dur = int((time.monotonic() - t0) * 1000)
                log.error(
                    f"dom-checker falló: {exc}",
                    phase="dom-checker", url=url, duration_ms=dur, exc=str(exc),
                )
                issues = [{
                    "type": "notice",
                    "code": "dom-checker-error",
                    "message": f"Error al ejecutar checks DOM: {exc}",
                    "selector": "", "context": "", "runner": "dom-checker"
                }]
            finally:
                try:
                    page.close()
                except Exception:
                    pass
            results[url] = issues
        browser.close()
    log.info("dom-checker finalizado", phase="dom-checker", total_urls=len(urls))
    return results


async def audit_task(analysis_id: int, url: str, limit: int):
    import time
    log = get_audit_logger(analysis_id)
    db = next(get_db())
    t_total = time.monotonic()
    try:
        log.info("auditoría iniciada", phase="init", url=url, limit=limit)
        analysis = db.query(models.Analysis).filter(models.Analysis.id == analysis_id).first()
        analysis.status = "processing"
        db.commit()

        # ── Fase: sitemap ──────────────────────────────────────────────────────
        log.info("buscando URLs en sitemap", phase="sitemap", url=url)
        t0 = time.monotonic()
        urls = fetch_sitemap_urls(url, limit)
        log.info(
            f"sitemap resuelto: {len(urls)} páginas encontradas",
            phase="sitemap", url=url,
            duration_ms=int((time.monotonic() - t0) * 1000),
            pages=urls,
        )
        analysis.total_urls = len(urls)
        db.commit()

        # ── Fase: pa11y ────────────────────────────────────────────────────────
        log.info("iniciando análisis pa11y", phase="pa11y", total_urls=len(urls))
        t0 = time.monotonic()
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, run_pa11y, urls)
        pa11y_dur = int((time.monotonic() - t0) * 1000)
        log.info(
            f"pa11y completado: {len(results)} páginas procesadas",
            phase="pa11y", duration_ms=pa11y_dur,
        )
        for res in results:
            page_issues = res.get("issues", [])
            if res.get("error"):
                log.warning(
                    f"pa11y error en página: {res.get('error')}",
                    phase="pa11y", url=res.get("url"),
                )
            else:
                log.info(
                    f"pa11y: {len(page_issues)} issues detectados",
                    phase="pa11y", url=res.get("url"),
                    errors=sum(1 for i in page_issues if i.get("type") == "error"),
                    warnings=sum(1 for i in page_issues if i.get("type") == "warning"),
                    notices=sum(1 for i in page_issues if i.get("type") == "notice"),
                )

        # ── Fase: dom-checker ─────────────────────────────────────────────────
        log.info("iniciando dom-checker (Playwright)", phase="dom-checker", total_urls=len(urls))
        t0 = time.monotonic()
        dom_results = await loop.run_in_executor(
            None, lambda: run_dom_checks_for_urls(urls, analysis_id)
        )
        log.info(
            "dom-checker completado para todas las páginas",
            phase="dom-checker",
            duration_ms=int((time.monotonic() - t0) * 1000),
        )

        # ── Fase: WP fingerprint ──────────────────────────────────────────────
        log.info("detectando entorno WordPress", phase="wp-fingerprint", url=url)
        t0 = time.monotonic()
        fp_data = get_wp_fingerprint(url)
        theme_str, plugins_str = summarize_for_prompt(fp_data)
        log.info(
            f"wp-fingerprint completado: WP={fp_data.get('is_wordpress')}, "
            f"tema={theme_str[:60]}, plugins={len(fp_data.get('plugins', []))}",
            phase="wp-fingerprint",
            duration_ms=int((time.monotonic() - t0) * 1000),
        )

        # ── Fase: LLM fix-advice (pre-generate for all unique error issues) ──
        log.info("pre-generando instrucciones IA para errores", phase="fix-advice-batch")
        t0 = time.monotonic()

        # Collect all unique error issues across pages (deduplicate by code)
        all_error_issues = []
        for res in results:
            pa11y_issues = res.get("issues", [])
            dom_issues = dom_results.get(res["url"], [])
            for issue in pa11y_issues + dom_issues:
                if issue.get("type") == "error":
                    all_error_issues.append(issue)

        # Deduplicate by code (keep first occurrence for each code)
        seen_codes = set()
        unique_issues = []
        for issue in all_error_issues:
            code = issue.get("code", "")
            if code and code not in seen_codes:
                seen_codes.add(code)
                unique_issues.append(issue)
            elif not code:
                unique_issues.append(issue)

        log.info(
            f"fix-advice: {len(unique_issues)} issues únicos de {len(all_error_issues)} totales",
            phase="fix-advice-batch",
        )

        # Generate advice for each unique issue (sync, one by one to avoid rate limits)
        from .services.fix_advisor import build_prompt, _run_gemini_sync
        advice_cache = {}  # code -> advice text
        for idx, issue in enumerate(unique_issues[:30]):  # cap at 30 to avoid excessive API usage
            code = issue.get("code", f"unknown-{idx}")
            try:
                prompt = build_prompt(
                    issue_code=code,
                    issue_message=issue.get("message", ""),
                    issue_context=(issue.get("context", "") or "")[:2000],
                    issue_selector=issue.get("selector", ""),
                    theme_str=theme_str,
                    plugins_str=plugins_str,
                )
                log.info(
                    f"fix-advice [{idx+1}/{len(unique_issues[:30])}] consultando Gemini para {code[:60]}",
                    phase="fix-advice-batch",
                )
                advice = _run_gemini_sync(prompt)
                advice_cache[code] = advice
                log.info(
                    f"fix-advice [{idx+1}] recibido ({len(advice)} chars)",
                    phase="fix-advice-batch",
                )
            except Exception as e:
                log.error(f"fix-advice error para {code}: {e}", phase="fix-advice-batch")
                advice_cache[code] = f"Error al consultar la IA: {e}"

        log.info(
            f"fix-advice batch completado: {len(advice_cache)} respuestas en "
            f"{int((time.monotonic() - t0) * 1000)}ms",
            phase="fix-advice-batch",
        )

        # ── Fase: guardar resultados ───────────────────────────────────────────
        log.info("guardando resultados en base de datos", phase="db")
        total_errors = total_warnings = total_notices = 0
        for res in results:
            page_url = res["url"]
            pa11y_issues = res.get("issues", [])
            dom_issues = dom_results.get(page_url, [])
            all_issues = pa11y_issues + dom_issues

            # Inject pre-generated fix advice into each error issue
            for issue in all_issues:
                code = issue.get("code", "")
                if code in advice_cache:
                    issue["fix_advice"] = advice_cache[code]

            errors = sum(1 for i in all_issues if i.get("type") == "error")
            warnings = sum(1 for i in all_issues if i.get("type") == "warning")
            notices = sum(1 for i in all_issues if i.get("type") == "notice")
            total_errors += errors
            total_warnings += warnings
            total_notices += notices
            report = models.PageReport(
                analysis_id=analysis_id,
                url=page_url,
                status=res.get("status", "ok"),
                error_msg=res.get("error"),
                issues=all_issues,
                errors_count=errors,
                warnings_count=warnings,
                notices_count=notices,
                page_title=res.get("documentTitle", "") or "",
            )
            db.add(report)

        analysis.status = "completed"
        analysis.total_errors = total_errors
        analysis.total_warnings = total_warnings
        analysis.total_notices = total_notices
        analysis.wp_fingerprint = fp_data
        db.commit()

        total_dur = int((time.monotonic() - t_total) * 1000)
        log.info(
            "auditoría completada",
            phase="done",
            duration_ms=total_dur,
            total_errors=total_errors,
            total_warnings=total_warnings,
            total_notices=total_notices,
        )
    except Exception as e:
        log.error(f"error fatal en auditoría: {e}", phase="error", exc=str(e))
        try:
            db.rollback()
            analysis = db.query(models.Analysis).filter(models.Analysis.id == analysis_id).first()
            if analysis:
                analysis.status = "failed"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@app.post("/analyze")
async def start_analysis(
    url: str,
    limit: int = 10,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
    auth: None = Depends(verify_token),
):
    from urllib.parse import urlparse
    parsed = urlparse(url)
    name = parsed.netloc or url
    db_analysis = models.Analysis(main_url=url, name=name, status="pending", max_pages=limit)
    db.add(db_analysis)
    db.commit()
    db.refresh(db_analysis)
    background_tasks.add_task(audit_task, db_analysis.id, url, limit)
    return {"id": db_analysis.id, "status": "pending"}


@app.get("/history")
async def get_history(db: Session = Depends(get_db), auth: None = Depends(verify_token)):
    items = db.query(models.Analysis).order_by(models.Analysis.created_at.desc()).all()
    return [
        {
            "id": a.id,
            "name": a.name,
            "main_url": a.main_url,
            "status": a.status,
            "created_at": a.created_at.isoformat(),
            "total_urls": a.total_urls,
            "total_errors": a.total_errors,
            "total_warnings": a.total_warnings,
            "total_notices": a.total_notices,
            "max_pages": a.max_pages or 10,
        }
        for a in items
    ]


@app.get("/analysis/{id}")
async def get_analysis(id: int, db: Session = Depends(get_db), auth: None = Depends(verify_token)):
    analysis = db.query(models.Analysis).filter(models.Analysis.id == id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Not found")
    reports = db.query(models.PageReport).filter(models.PageReport.analysis_id == id).all()
    return {
        "analysis": {
            "id": analysis.id,
            "name": analysis.name,
            "main_url": analysis.main_url,
            "status": analysis.status,
            "created_at": analysis.created_at.isoformat(),
            "total_urls": analysis.total_urls,
            "total_errors": analysis.total_errors,
            "total_warnings": analysis.total_warnings,
            "total_notices": analysis.total_notices,
        },
        "reports": [
            {
                "id": r.id,
                "url": r.url,
                "page_title": r.page_title or "",
                "status": r.status,
                "error_msg": r.error_msg,
                "issues": r.issues or [],
                "errors_count": r.errors_count,
                "warnings_count": r.warnings_count,
                "notices_count": r.notices_count,
            }
            for r in reports
        ],
    }


@app.get("/analysis/{id}/criteria")
async def get_analysis_criteria(id: int, db: Session = Depends(get_db), auth: None = Depends(verify_token)):
    analysis = db.query(models.Analysis).filter(models.Analysis.id == id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Not found")
    reports = db.query(models.PageReport).filter(models.PageReport.analysis_id == id).all()

    pages = []
    for r in reports:
        criteria_list = map_issues_to_criteria(r.issues or [])
        sections = group_by_section(criteria_list)
        pages.append({
            "id": r.id,
            "url": r.url,
            "status": r.status,
            "error_msg": r.error_msg,
            "errors_count": r.errors_count,
            "warnings_count": r.warnings_count,
            "notices_count": r.notices_count,
            "page_title": r.page_title or "",
            "sections": {
                section: [
                    {
                        "id": c["id"],
                        "label": c["label"],
                        "manual": c["manual"],
                        "status": c["status"],
                        "issues": c["issues"],
                    }
                    for c in criteria
                ]
                for section, criteria in sections.items()
            },
        })

    return {
        "analysis": {
            "id": analysis.id,
            "name": analysis.name,
            "main_url": analysis.main_url,
            "status": analysis.status,
            "created_at": analysis.created_at.isoformat(),
            "total_urls": analysis.total_urls,
            "total_errors": analysis.total_errors,
            "total_warnings": analysis.total_warnings,
            "total_notices": analysis.total_notices,
            "max_pages": analysis.max_pages or 10,
        },
        "section_order": SECTION_ORDER,
        "pages": pages,
    }


@app.patch("/analysis/{analysis_id}/issue")
async def toggle_issue_resolved(
    analysis_id: int,
    report_id: int,
    issue_index: int,
    resolved: bool = True,
    db: Session = Depends(get_db),
    auth: None = Depends(verify_token),
):
    """Mark/unmark a single issue as resolved and recalculate counters."""
    report = db.query(models.PageReport).filter(
        models.PageReport.id == report_id,
        models.PageReport.analysis_id == analysis_id,
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    issues = list(report.issues or [])
    if issue_index < 0 or issue_index >= len(issues):
        raise HTTPException(status_code=400, detail="Invalid issue index")

    issues[issue_index]["resolved"] = resolved
    report.issues = issues
    # Force SQLAlchemy to detect JSON mutation
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(report, "issues")

    # Recalculate page-level counts (only count non-resolved)
    active = [i for i in issues if not i.get("resolved")]
    report.errors_count = sum(1 for i in active if i.get("type") == "error")
    report.warnings_count = sum(1 for i in active if i.get("type") == "warning")
    report.notices_count = sum(1 for i in active if i.get("type") == "notice")

    # Recalculate analysis-level totals
    all_reports = db.query(models.PageReport).filter(
        models.PageReport.analysis_id == analysis_id
    ).all()
    analysis = db.query(models.Analysis).filter(models.Analysis.id == analysis_id).first()
    total_e = total_w = total_n = 0
    for r in all_reports:
        if r.id == report_id:
            total_e += report.errors_count
            total_w += report.warnings_count
            total_n += report.notices_count
        else:
            total_e += r.errors_count or 0
            total_w += r.warnings_count or 0
            total_n += r.notices_count or 0
    analysis.total_errors = total_e
    analysis.total_warnings = total_w
    analysis.total_notices = total_n
    db.commit()

    return {
        "status": "ok",
        "errors": analysis.total_errors,
        "warnings": analysis.total_warnings,
        "notices": analysis.total_notices,
    }


@app.delete("/analysis/{id}")
async def delete_analysis(id: int, db: Session = Depends(get_db), auth: None = Depends(verify_token)):
    analysis = db.query(models.Analysis).filter(models.Analysis.id == id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Not found")
    db.delete(analysis)
    db.commit()
    return {"status": "deleted"}


@app.put("/analysis/{id}")
async def update_analysis_name(id: int, name: str, db: Session = Depends(get_db), auth: None = Depends(verify_token)):
    analysis = db.query(models.Analysis).filter(models.Analysis.id == id).first()
    if not analysis:
        raise HTTPException(status_code=404, detail="Not found")
    analysis.name = name
    db.commit()
    return {"status": "updated"}


@app.get("/logs")
async def get_all_logs(
    level: str | None = None,
    phase: str | None = None,
    limit: int = 200,
    auth: None = Depends(verify_token),
):
    """Devuelve los últimos logs globales (todas las auditorías)."""
    return {
        "logs": get_logs(analysis_id=None, level=level, phase=phase, limit=limit),
        "analysis_ids": get_analysis_ids(),
    }


@app.get("/logs/{analysis_id}")
async def get_analysis_logs(
    analysis_id: int,
    level: str | None = None,
    phase: str | None = None,
    limit: int = 500,
    from_disk: bool = False,
    auth: None = Depends(verify_token),
):
    """
    Devuelve logs de una auditoría específica.
    - from_disk=true: carga desde el archivo (útil tras reinicio del servidor)
    """
    if from_disk:
        logs = load_logs_from_file(analysis_id)
        if level:
            logs = [e for e in logs if e.get("level", "").upper() == level.upper()]
        if phase:
            logs = [e for e in logs if e.get("phase", "").lower() == phase.lower()]
        return {"logs": list(reversed(logs[-limit:])), "source": "disk"}

    return {
        "logs": get_logs(analysis_id=analysis_id, level=level, phase=phase, limit=limit),
        "source": "memory",
    }


@app.get("/fix-advice")
async def fix_advice(
    site_url: str,
    issue_code: str = "",
    issue_message: str = "",
    issue_context: str = "",
    issue_selector: str = "",
    analysis_id: int = 0,
    auth: None = Depends(verify_token),
):
    """Construye el contexto WP del sitio y llama a Gemini para instrucciones de corrección."""
    log = get_audit_logger(analysis_id) if analysis_id else get_audit_logger("global")

    log.info(
        "fix-advice solicitado",
        phase="fix-advice",
        site_url=site_url,
        issue_code=issue_code,
    )

    # 1. WP fingerprint (cached per domain, runs in thread)
    loop = asyncio.get_event_loop()
    fp_data = await loop.run_in_executor(None, get_wp_fingerprint, site_url)
    theme_str, plugins_str = summarize_for_prompt(fp_data)

    log.info(
        f"fix-advice: fingerprint completado (WP={fp_data.get('is_wordpress')}, "
        f"tema={theme_str[:60]}, plugins={len(fp_data.get('plugins', []))})",
        phase="fix-advice",
    )

    # 2. Gemini advice
    advice = await get_fix_advice(
        issue_code=issue_code,
        issue_message=issue_message,
        issue_context=issue_context,
        issue_selector=issue_selector,
        theme_str=theme_str,
        plugins_str=plugins_str,
        log=log,
    )

    return {"advice": advice, "wp": {"theme": fp_data.get("theme"), "plugins_count": len(fp_data.get("plugins", []))}}


app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
