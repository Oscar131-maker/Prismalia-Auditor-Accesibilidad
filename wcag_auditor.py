import asyncio
import json
import os
import time
import pandas as pd
from datetime import datetime
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright, Page
from slugify import slugify

class WCAGAuditor:
    def __init__(self, start_url: str, crawl_deep: bool = True, max_pages: int = 50):
        self.start_url = start_url
        self.domain = urlparse(start_url).netloc
        self.crawl_deep = crawl_deep
        self.max_pages = max_pages
        self.visited_urls = set()
        self.urls_to_audit = set()
        self.results_dir = f"audit_report_{slugify(self.domain)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Ensure results directory exists
        if not os.path.exists(self.results_dir):
            os.makedirs(self.results_dir)
            os.makedirs(os.path.join(self.results_dir, "screenshots"))

    async def initialize_browser(self, p):
        browser = await p.chromium.launch(headless=True)
        return browser

    async def crawl(self):
        """Phase 1: Deep Crawl to obtain URLs"""
        print(f"--- INICIANDO CRAWL EN: {self.start_url} ---")
        async with async_playwright() as p:
            browser = await self.initialize_browser(p)
            context = await browser.new_context()
            page = await context.new_page()

            queue = [self.start_url]
            while queue and len(self.visited_urls) < self.max_pages:
                url = queue.pop(0)
                if url in self.visited_urls or not url.startswith("http"):
                    continue

                print(f"Rastreando: {url}")
                try:
                    await page.goto(url, wait_until="networkidle", timeout=30000)
                    self.visited_urls.add(url)
                    
                    # Extract internal links
                    hrefs = await page.eval_on_selector_all("a[href]", "elements => elements.map(e => e.href)")
                    for href in hrefs:
                        full_url = urljoin(url, href)
                        parsed_href = urlparse(full_url)
                        
                        # Only same domain and not visited
                        if parsed_href.netloc == self.domain and full_url not in self.visited_urls:
                            if full_url not in queue:
                                queue.append(full_url)
                except Exception as e:
                    print(f"Error rastreando {url}: {e}")

            await browser.close()
        
        # Save to Excel
        df = pd.DataFrame(list(self.visited_urls), columns=["URL"])
        excel_path = os.path.join(self.results_dir, "urls_crawled.xlsx")
        df.to_excel(excel_path, index=False)
        print(f"--- CRAWL FINALIZADO: {len(self.visited_urls)} URLs encontradas. Guardadas en {excel_path} ---")
        return list(self.visited_urls)

    async def run_audit(self, urls: list):
        """Phase 2: Audit each URL according to Principle 1-4"""
        print(f"--- INICIANDO AUDITORIA DE {len(urls)} URLs ---")
        async with async_playwright() as p:
            browser = await self.initialize_browser(p)
            
            for i, url in enumerate(urls):
                print(f"[{i+1}/{len(urls)}] Auditando: {url}")
                # We create a new context per page to avoid state contamination
                context = await browser.new_context(
                    viewport={'width': 1280, 'height': 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
                )
                page = await context.new_page()
                
                try:
                    page_data = await self.audit_single_page(page, url)
                    
                    # Save individual JSON report
                    file_name = f"report_{slugify(urlparse(url).path or 'home')}_{i}.json"
                    with open(os.path.join(self.results_dir, file_name), "w", encoding="utf-8") as f:
                        json.dump(page_data, f, indent=2, ensure_ascii=False)
                        
                except Exception as e:
                    print(f"Error auditando {url}: {e}")
                finally:
                    await context.close()

            await browser.close()

    async def audit_single_page(self, page: Page, url: str):
        # 1. Navigate and wait
        await page.goto(url, wait_until="networkidle")
        
        # 2. Capture full page screenshot
        screenshot_name = f"full_{slugify(urlparse(url).path or 'home')}.png"
        screenshot_path = os.path.join(self.results_dir, "screenshots", screenshot_name)
        await page.screenshot(full_page=True, path=screenshot_path)
        
        # 3. Get Accessibility Tree (Aria Snapshot for Playwright 1.57+)
        try:
            aom = await page.locator("html").aria_snapshot()
        except:
            aom = "No se pudo obtener el Aria Snapshot (requiere Playwright 1.49+)"
        
        # 4. Extract Data for Principles
        p1 = await self.collect_principle_1(page, screenshot_path)
        p2 = await self.collect_principle_2(page)
        p3 = await self.collect_principle_3(page)
        p4 = await self.collect_principle_4(page, aom)
        
        return {
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "screenshot_path": screenshot_path,
            "principio_1": p1,
            "principio_2": p2,
            "principio_3": p3,
            "principio_4": p4
        }

    async def collect_principle_1(self, page: Page, screenshot_path: str):
        """Principio 1: Perceptibilidad"""
        # Pauta 1.1: Texto Alternativo
        elements_1_1 = await page.evaluate("""() => {
            const selectors = ['img', 'svg', 'canvas', 'area', 'input[type="image"]', '[role="img"]'];
            const found = [];
            selectors.forEach(sel => {
                document.querySelectorAll(sel).forEach(el => {
                    found.push({
                        tipo_elemento: el.tagName.toLowerCase(),
                        outer_html: el.outerHTML,
                        atributos_accesibilidad: {
                            alt: el.getAttribute('alt'),
                            aria_label: el.getAttribute('aria-label'),
                            aria_labelledby: el.getAttribute('aria-labelledby'),
                            role: el.getAttribute('role')
                        },
                        // Contexto visual simple
                        texto_adyacente: (el.previousElementSibling?.innerText || '') + ' | ' + (el.nextElementSibling?.innerText || '')
                    });
                });
            });
            return found;
        }""")

        # Pauta 1.3: Adaptable
        adaptable_data = await page.evaluate("""() => {
            const headers = Array.from(document.querySelectorAll('h1, h2, h3, h4, h5, h6')).map(h => ({
                nivel: h.tagName,
                texto: h.innerText,
                outer_html: h.outerHTML
            }));
            
            const tables = Array.from(document.querySelectorAll('table')).map(t => ({
                outer_html_tabla: t.outerHTML,
                headers_detectados: Array.from(t.querySelectorAll('th')).map(th => ({
                    texto: th.innerText,
                    scope: th.getAttribute('scope'),
                    id: th.id
                }))
            }));
            
            const forms = Array.from(document.querySelectorAll('input, select, textarea')).map(i => {
                const label = document.querySelector(`label[for="${i.id}"]`) || i.closest('label');
                return {
                    id_input: i.id,
                    tipo_input: i.getAttribute('type'),
                    autocomplete: i.getAttribute('autocomplete'),
                    label_asociado: {
                        texto_label: label ? label.innerText : null,
                        metodo_asociacion: i.id && document.querySelector(`label[for="${i.id}"]`) ? 'explícito' : (i.closest('label') ? 'implícito' : 'ninguno'),
                        html_label: label ? label.outerHTML : null
                    }
                };
            });
            
            return { jerarquia_encabezados: headers, tablas_datos: tables, formularios: forms };
        }""")

        # Pauta 1.4: Distinguible (Color & Reflow)
        # Mobile simulate for reflow
        distinguible_data = await page.evaluate("""async () => {
            const textNodes = [];
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
            let node;
            while(node = walker.nextNode()) {
                if (node.parentElement && node.textContent.trim().length > 0) {
                    const style = window.getComputedStyle(node.parentElement);
                    textNodes.push({
                        texto_interno: node.textContent.trim().substring(0, 100),
                        html_nodo: node.parentElement.tagName,
                        estilos_computados: {
                            color_texto: style.color,
                            color_fondo: style.backgroundColor,
                            font_size_px: style.fontSize,
                            font_weight: style.fontWeight
                        }
                    });
                }
                if (textNodes.length > 50) break; // Limit for LLM context
            }
            return { nodos_texto_contraste: textNodes };
        }""")

        return {
            "pauta_1_1": elements_1_1,
            "pauta_1_3": adaptable_data,
            "pauta_1_4": distinguible_data
        }

    async def collect_principle_2(self, page: Page):
        """Principio 2: Operabilidad"""
        # 2.1 Teclado & 2.2 Tiempo & 2.4 Navegación
        # Inyectar MutationObserver
        await page.evaluate("""() => {
            window.mutations = [];
            const observer = new MutationObserver((mutations) => {
                mutations.forEach((m) => {
                    window.mutations.push({
                        type: m.type,
                        target: m.target.outerHTML?.substring(0, 100)
                    });
                });
            });
            observer.observe(document.body, { childList: true, subtree: true, attributes: true });
        }""")

        # Tab Walk (Simulated partially)
        tab_sequence = []
        for i in range(10): # First 10 tabs
            await page.keyboard.press("Tab")
            active = await page.evaluate("""() => {
                const el = document.activeElement;
                return {
                    outer_html: el.outerHTML,
                    es_visible: el.offsetWidth > 0 && el.offsetHeight > 0
                };
            }""")
            tab_sequence.append(active)
            if i > 0 and tab_sequence[i]['outer_html'] == tab_sequence[0]['outer_html']:
                break # Looped back

        # Pauta 2.5: Modalidades de entrada (WCAG 2.2 Target Size)
        target_sizes = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('a, button, input[type="submit"], [role="button"]')).map(el => {
                const rect = el.getBoundingClientRect();
                return {
                    outer_html: el.outerHTML.substring(0, 100),
                    ancho_px: rect.width,
                    alto_px: rect.height,
                    texto_visible: el.innerText || el.value,
                    nombre_accesible: el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') // Basic
                };
            });
        }""")

        return {
            "pauta_2_1_y_2_4": { "secuencia_tabulacion": tab_sequence },
            "pauta_2_2": { "mutaciones_detectadas": await page.evaluate("window.mutations.slice(0, 20)") },
            "pauta_2_5": { "dimensiones_objetivos": target_sizes }
        }

    async def collect_principle_3(self, page: Page):
        """Principio 3: Comprensibilidad"""
        data = await page.evaluate("""() => {
            const htmlLang = document.documentElement.lang;
            const langChanges = Array.from(document.querySelectorAll('[lang]')).map(el => ({
                outer_html: el.outerHTML.substring(0, 100),
                lang: el.lang
            }));
            
            return {
                pauta_3_1: {
                    idioma_global: htmlLang,
                    cambios_idioma: langChanges
                }
            };
        }""")
        
        # Pauta 3.3: Asistencia entrada
        forms_assist = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('input')).map(i => ({
                id_input: i.id,
                placeholder: i.placeholder,
                descripcion_accesible: i.getAttribute('aria-describedby'),
                requerido: i.required || i.getAttribute('aria-required') === 'true'
            }));
        }""")
        data["pauta_3_3"] = { "instrucciones_y_etiquetas": forms_assist }
        
        return data

    async def collect_principle_4(self, page: Page, aom: dict):
        """Principio 4: Robustez"""
        custom_controls = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('div[role], span[role], [tabindex]')).map(el => ({
                outer_html: el.outerHTML.substring(0, 200),
                rol_semantico: el.getAttribute('role'),
                tabindex: el.getAttribute('tabindex')
            }));
        }""")
        
        iframes = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('iframe')).map(f => ({
                outer_html: f.outerHTML,
                title: f.title
            }));
        }""")

        return {
            "pauta_4_1": {
                "controles_personalizados": custom_controls,
                "iframes": iframes,
                "accessibility_tree_sample": aom
            }
        }

async def main():
    # URL de ejemplo, el usuario puede cambiarla
    TARGET_URL = "https://www.google.com" 
    
    auditor = WCAGAuditor(TARGET_URL, max_pages=5)
    
    # 1. Crawl
    urls = await auditor.crawl()
    
    # 2. Audit
    await auditor.run_audit(urls)
    
    print(f"\n✅ Auditoría completa. Resultados en el directorio: {auditor.results_dir}")

if __name__ == "__main__":
    asyncio.run(main())
