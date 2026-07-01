import json
import os
from datetime import datetime
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright
from slugify import slugify
from .models import Analysis, PageReport
from .database import SessionLocal
from .gemini_service import GeminiService
from .logger import logger

class WCAGAuditor:
    def __init__(self, analysis_id: int):
        self.analysis_id = analysis_id
        self.gemini = GeminiService()

    def run_full_analysis(self, start_url: str, max_pages: int):
        """
        Versión Sincrónica robusta para Windows.
        """
        db = SessionLocal()
        try:
            logger.info(f"Iniciando análisis completo para: {start_url} (ID: {self.analysis_id})")
            analysis = db.query(Analysis).filter(Analysis.id == self.analysis_id).first()
            if not analysis:
                logger.error(f"No se encontró el objeto de análisis con ID {self.analysis_id}")
                return
            
            analysis.status = "processing"
            db.commit()

            domain = urlparse(start_url).netloc
            visited_urls = set()
            pages_to_audit = []

            # Phase 1: Crawl
            logger.info(f"Fase 1: Rastreando dominio {domain}...")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context()
                page = context.new_page()

                queue = [start_url]
                while queue and len(visited_urls) < max_pages:
                    url = queue.pop(0)
                    if url in visited_urls or not url.startswith("http"):
                        continue

                    try:
                        logger.info(f"Rastreando: {url}")
                        page.goto(url, wait_until="networkidle", timeout=30000)
                        visited_urls.add(url)
                        pages_to_audit.append(url)
                        
                        hrefs = page.eval_on_selector_all("a[href]", "elements => elements.map(e => e.href)")
                        for href in hrefs:
                            full_url = urljoin(url, href)
                            parsed_href = urlparse(full_url)
                            if parsed_href.netloc == domain and full_url not in visited_urls:
                                if full_url not in queue:
                                    queue.append(full_url)
                    except Exception as e:
                        logger.warning(f"Error rastreando {url}: {e}")
                        continue

                browser.close()

            # Phase 2: Audit & Gemini
            logger.info(f"Fase 2: Auditando {len(pages_to_audit)} páginas encontradas.")
            all_summaries = []
            total_cost = 0.0
            
            # Precios Gemini 1.5 Flash / Lite (con base en la imagen proporcionada)
            PRICE_INPUT_1M = 0.25
            PRICE_OUTPUT_1M = 1.50

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                for i, url in enumerate(pages_to_audit):
                    logger.info(f"[{i+1}/{len(pages_to_audit)}] Auditando: {url}")
                    context = browser.new_context(viewport={'width': 1280, 'height': 800})
                    page = context.new_page()
                    try:
                        raw_data = self.audit_single_page(page, url)
                        
                        logger.info(f"Enviando datos a Gemini para {url}...")
                        # Now calling synchronously
                        result = self.gemini.generate_page_analysis(raw_data)
                        gemini_analysis = result.get("data", {})
                        usage = result.get("usage", {})
                        
                        # Cálculo de costo
                        prompt_tokens = usage.get("prompt_tokens", 0)
                        candidates_tokens = usage.get("candidates_tokens", 0)
                        cost = (prompt_tokens * PRICE_INPUT_1M / 1_000_000) + (candidates_tokens * PRICE_OUTPUT_1M / 1_000_000)
                        total_cost += cost
                        
                        logger.info(f"Costo consulta URL ({url}): ${cost:.6f} USD (Tokens: {prompt_tokens} in / {candidates_tokens} out)")
                        
                        report = PageReport(
                            analysis_id=self.analysis_id,
                            url=url,
                            issues=raw_data,
                            errors_count=0,
                            warnings_count=0,
                            notices_count=0,
                        )
                        db.add(report)
                        db.commit()
                        all_summaries.append({"url": url, "summary": gemini_analysis.get("summary")})
                        logger.info(f"Reporte IA completado para {url}")
                    except Exception as e:
                        logger.error(f"Error auditando {url}: {e}")
                    finally:
                        context.close()
                browser.close()

            # Phase 3: Global Summary
            logger.info("Fase 3: Generando resumen ejecutivo global...")
            result_global = self.gemini.generate_global_summary(all_summaries)
            global_summary = result_global.get("text")
            usage_global = result_global.get("usage", {})
            
            # Costo resumen global
            prompt_tokens_g = usage_global.get("prompt_tokens", 0)
            candidates_tokens_g = usage_global.get("candidates_tokens", 0)
            cost_global = (prompt_tokens_g * PRICE_INPUT_1M / 1_000_000) + (candidates_tokens_g * PRICE_OUTPUT_1M / 1_000_000)
            total_cost += cost_global
            
            logger.info(f"Costo Resumen Global: ${cost_global:.6f} USD (Tokens: {prompt_tokens_g} in / {candidates_tokens_g} out)")
            logger.info(f"COSTO TOTAL DEL ANÁLISIS: ${total_cost:.6f} USD")

            analysis.global_summary = global_summary
            analysis.status = "completed"
            db.commit()
            logger.info(f"Análisis {self.analysis_id} completado con éxito.")

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.critical(f"Fallo crítico en el proceso de análisis: {e}\n{error_details}")
            analysis = db.query(Analysis).filter(Analysis.id == self.analysis_id).first()
            if analysis:
                analysis.status = "failed"
                db.commit()
        finally:
            db.close()

    def audit_single_page(self, page, url: str):
        page.goto(url, wait_until="networkidle")
        
        try:
            aom = page.locator("html").aria_snapshot()
        except:
            aom = "N/A"
        
        p1 = page.evaluate("""() => {
            const imgs = Array.from(document.querySelectorAll('img')).map(el => ({ alt: el.alt, src: el.src.substring(0, 50) }));
            const headers = Array.from(document.querySelectorAll('h1, h2, h3')).map(h => ({ level: h.tagName, text: h.innerText }));
            return { images: imgs, headers: headers };
        }""")
        
        p2 = page.evaluate("""() => {
            const buttons = Array.from(document.querySelectorAll('button, a[role="button"]')).map(b => ({ text: b.innerText, accessible_name: b.getAttribute('aria-label') }));
            return { interactables: buttons };
        }""")

        return {
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "p1": p1,
            "p2": p2,
            "aria_snapshot": aom[:2000]
        }
