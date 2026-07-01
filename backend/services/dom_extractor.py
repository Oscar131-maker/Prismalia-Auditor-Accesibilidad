import asyncio
import os
from playwright.async_api import Page, Locator
import json

class DOMExtractor:
    def __init__(self, page: Page):
        self.page = page

    async def extract_all_criteria(self, url: str):
        """Ejecuta todas las subrutinas de extracción y devuelve un JSON estructurado."""
        results = {
            "url": url,
            "images_and_icons": await self.subroutine_images_and_icons(),
            "semantics": await self.subroutine_semantics(),
            "forms": await self.subroutine_forms(),
            "visual_responsive": await self.subroutine_visual_responsive(),
            "operability": await self.subroutine_operability()
        }
        return results

    async def subroutine_images_and_icons(self):
        """Criterios 1, 3, 4: Imágenes, Íconos y Logotipo."""
        return await self.page.evaluate("""() => {
            const results = {
                images: [],
                icons: [],
                logo: null
            };

            // 1. Extraer imágenes y roles
            const imgElements = document.querySelectorAll('img, svg, [role="img"]');
            imgElements.forEach(el => {
                const rect = el.getBoundingClientRect();
                const data = {
                    tag: el.tagName.toLowerCase(),
                    alt: el.getAttribute('alt'),
                    aria_label: el.getAttribute('aria-label'),
                    title: el.getAttribute('title'),
                    role: el.getAttribute('role'),
                    src: el.src || el.getAttribute('xlink:href'),
                    outerHTML: el.outerHTML.substring(0, 300),
                    is_visible: rect.width > 0 && rect.height > 0
                };

                // Criterio 3: Detección heurística de íconos
                const isIcon = el.tagName.toLowerCase() === 'svg' || 
                               el.classList.contains('icon') || 
                               el.classList.contains('fa') || 
                               (rect.width > 0 && rect.width < 50 && rect.height < 50);
                
                if (isIcon) {
                    results.icons.push(data);
                } else {
                    results.images.push(data);
                }

                // Criterio 4: Buscar logotipo (en header o por clase/id común)
                const isLogo = el.closest('header') && (
                    el.id.toLowerCase().includes('logo') || 
                    el.className.toString().toLowerCase().includes('logo') ||
                    (el.src && el.src.toLowerCase().includes('logo'))
                );
                if (isLogo && !results.logo) {
                    const link = el.closest('a');
                    results.logo = {
                        has_link: !!link,
                        link_href: link ? link.href : null,
                        points_to_home: link ? (link.pathname === '/' || link.pathname === '/index.html') : false
                    };
                }
            });

            return results;
        }""")

    async def subroutine_semantics(self):
        """Criterios 7, 8, 9, 10: H1, Falsos Encabezados, Listas, Tablas."""
        return await self.page.evaluate("""() => {
            const h1s = Array.from(document.querySelectorAll('h1'));
            
            // Criterio 8: Falsos encabezados (div/span que parecen títulos)
            const fauxHeadings = [];
            const possibleFaux = document.querySelectorAll('div, span, p');
            possibleFaux.forEach(el => {
                const style = window.getComputedStyle(el);
                const fontSize = parseFloat(style.fontSize);
                const fontWeight = style.fontWeight;
                const className = el.className.toString().toLowerCase();
                
                if ((fontSize > 20 || fontWeight === 'bold' || fontWeight > 600) && 
                    (className.includes('title') || className.includes('heading') || className.includes('header')) &&
                    el.innerText.trim().length > 0 && el.innerText.trim().length < 100) {
                    fauxHeadings.push({
                        tag: el.tagName.toLowerCase(),
                        text: el.innerText.trim(),
                        fontSize: style.fontSize,
                        fontWeight: style.fontWeight,
                        outerHTML: el.outerHTML.substring(0, 200)
                    });
                }
            });

            // Criterio 9: Listas visuales (saltos de línea o viñetas sin ul/li)
            // Esto es complejo, enviamos fragmentos sospechosos para análisis LLM después.

            // Criterio 10: Tablas y sus headers
            const tables = Array.from(document.querySelectorAll('table')).map(t => ({
                has_th: t.querySelectorAll('th').length > 0,
                rowCount: t.rows.length,
                outerHTML: t.outerHTML.substring(0, 300)
            }));

            return {
                h1_count: h1s.length,
                h1_texts: h1s.map(h => h.innerText.trim()),
                faux_headings: fauxHeadings,
                tables: tables
            };
        }""")

    async def subroutine_forms(self):
        """Criterio 19: Inputs, Labels y Placeholders."""
        return await self.page.evaluate("""() => {
            const inputs = Array.from(document.querySelectorAll('input, textarea, select'));
            return inputs.map(i => {
                const label = document.querySelector(`label[for="${i.id}"]`) || i.closest('label');
                return {
                    type: i.type || i.tagName.toLowerCase(),
                    id: i.id,
                    placeholder: i.placeholder,
                    has_label: !!label,
                    label_text: label ? label.innerText.trim() : null,
                    aria_label: i.getAttribute('aria-label'),
                    aria_labelledby: i.getAttribute('aria-labelledby'),
                    only_placeholder: !!i.placeholder && !label && !i.getAttribute('aria-label')
                };
            });
        }""")

    async def subroutine_visual_responsive(self):
        """Criterio 15, 16, 17: Contraste, Zoom, Reflow."""
        # Nota: Zoom y Reflow requieren cambiar el viewport de la página antes.
        # Por ahora extraemos colores para contraste.
        return await self.page.evaluate("""() => {
            const interactive = document.querySelectorAll('a, button, input[type="submit"]');
            const contrastSamples = Array.from(interactive).slice(0, 15).map(el => {
                const style = window.getComputedStyle(el);
                return {
                    tag: el.tagName.toLowerCase(),
                    text: el.innerText.trim(),
                    color: style.color,
                    backgroundColor: style.backgroundColor,
                    fontSize: style.fontSize
                };
            });
            return { contrast_samples: contrastSamples };
        }""")

    async def check_reflow(self):
        """Criterio 17: Simular 320px para detectar scroll horizontal."""
        original_size = self.page.viewport_size
        await self.page.set_viewport_size({"width": 320, "height": 800})
        await asyncio.sleep(0.5)
        
        has_horizontal_scroll = await self.page.evaluate("""() => {
            return document.documentElement.scrollWidth > window.innerWidth;
        }""")
        
        await self.page.set_viewport_size(original_size)
        return {"has_horizontal_scroll_320px": has_horizontal_scroll}

    async def subroutine_operability(self):
        """Criterio 18: Interactividad (Escape key simple check)."""
        # Esta prueba es dinámica y requiere simulación de disparadores. 
        # Por ahora registramos elementos con tabIndex o roles interactivos.
        return await self.page.evaluate("""() => {
            const interactive = document.querySelectorAll('[tabindex], [role="button"], [role="menuitem"]');
            return {
                custom_interactive_count: interactive.length,
                samples: Array.from(interactive).slice(0, 5).map(el => el.outerHTML.substring(0, 200))
            };
        }""")
