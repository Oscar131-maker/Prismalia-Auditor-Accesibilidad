import asyncio
import os
import uuid
import sys
from datetime import datetime
from playwright.async_api import async_playwright
from backend.services.dom_extractor import DOMExtractor
from backend.services.llm_evaluator import LLMEvaluator

# Fix para subprocesos de Playwright en Windows
if sys.platform == 'win32':
    try:
        if not isinstance(asyncio.get_event_loop_policy(), asyncio.WindowsProactorEventLoopPolicy):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except:
        pass

class AuditPipeline:
    def __init__(self, target_url: str, max_pages: int = 5):
        self.target_url = target_url
        self.max_pages = max_pages
        self.run_id = str(uuid.uuid4())
        self.results_dir = f"audits/run_{self.run_id}"
        os.makedirs(f"{self.results_dir}/screenshots", exist_ok=True)
        self.llm_evaluator = LLMEvaluator()

    async def run(self):
        """Ejecuta el pipeline completo: Crawl -> Extracción -> Evaluación -> Reporte."""
        print(f"--- Iniciando Auditoría {self.run_id} en {self.target_url} ---")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            )
            
            # Phase 1: Crawl (simplificado para este pipeline)
            urls = await self._crawl(context)
            
            page_results = []
            for i, url in enumerate(urls):
                print(f"[{i+1}/{len(urls)}] Procesando: {url}")
                page = await context.new_page()
                try:
                    # Phase 2: Extracción Determinista
                    result = await self._process_page(page, url)
                    page_results.append(result)
                except Exception as e:
                    print(f"Error procesando {url}: {e}")
                finally:
                    await page.close()

            await browser.close()
            
            # Phase 4: Consolidación y Guardado (En base de datos o JSON local por ahora)
            report_path = f"{self.results_dir}/full_report.json"
            with open(report_path, "w", encoding="utf-8") as f:
                import json
                json.dump(page_results, f, indent=2, ensure_ascii=False)
            
            print(f"--- Auditoría Finalizada: {report_path} ---")
            return page_results

    async def _crawl(self, context):
        """Rastreo básico de enlaces internos."""
        page = await context.new_page()
        await page.goto(self.target_url, wait_until="networkidle")
        hrefs = await page.eval_on_selector_all("a[href]", "elements => elements.map(e => e.href)")
        from urllib.parse import urljoin, urlparse
        domain = urlparse(self.target_url).netloc
        
        valid_urls = {self.target_url}
        for href in hrefs:
            full_url = urljoin(self.target_url, href)
            if urlparse(full_url).netloc == domain and len(valid_urls) < self.max_pages:
                valid_urls.add(full_url)
        
        await page.close()
        return list(valid_urls)

    async def _process_page(self, page, url):
        """Ejecuta extracción y evaluación de una sola página."""
        extractor = DOMExtractor(page)
        
        # 1. Navegación
        await page.goto(url, wait_until="networkidle")
        
        # 2. Captura Normal
        screenshot_name = f"{uuid.uuid4()}.png"
        screenshot_path = f"{self.results_dir}/screenshots/{screenshot_name}"
        await page.screenshot(full_page=True, path=screenshot_path)
        
        # 3. Captura Sin CSS (Criterio 11)
        await page.evaluate("""() => {
            const styles = document.querySelectorAll('style, link[rel="stylesheet"]');
            styles.forEach(s => s.remove());
            const allElements = document.querySelectorAll('*');
            allElements.forEach(el => el.removeAttribute('style'));
        }""")
        screenshot_no_css_name = f"{uuid.uuid4()}_no_css.png"
        screenshot_no_css_path = f"{self.results_dir}/screenshots/{screenshot_no_css_name}"
        await page.screenshot(full_page=True, path=screenshot_no_css_path)
        
        # 4. Datos del DOM
        dom_data = await extractor.extract_all_criteria(url)
        
        # 5. Evaluación Heurística (Gemini)
        eval_result = await self.llm_evaluator.evaluate_page(
            dom_data, 
            screenshot_path, 
            screenshot_no_css_path
        )
        
        return {
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "dom_data": dom_data,
            "llm_evaluation": eval_result,
            "screenshots": {
                "normal": screenshot_path,
                "no_css": screenshot_no_css_path
            }
        }

if __name__ == "__main__":
    # Test simple
    async def main():
        pipeline = AuditPipeline("https://www.google.com", max_pages=1)
        await pipeline.run()
    asyncio.run(main())
