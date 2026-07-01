"""
dom_checker.py
Checks automáticos de criterios de accesibilidad que pa11y no puede detectar.
Usa Playwright (sync) para inspeccionar el DOM de cada página.

Cada check retorna una lista de dicts compatibles con el formato de issue de pa11y:
    {
        "type":     "error" | "warning" | "notice",
        "code":     str,          # slug del criterio
        "message":  str,          # descripción en español
        "selector": str,          # selector CSS del elemento afectado (o "")
        "context":  str,          # fragmento HTML del elemento (o "")
        "runner":   "dom-checker"
    }
"""

from __future__ import annotations
from playwright.sync_api import Page


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _outer(page: Page, selector: str) -> str:
    """Devuelve el outerHTML del primer elemento que coincide (truncado)."""
    try:
        el = page.query_selector(selector)
        if el:
            html = el.evaluate("el => el.outerHTML")
            return (html or "")[:200]
    except Exception:
        pass
    return ""


def _make(code: str, msg: str, sel: str = "", ctx: str = "", level: str = "error") -> dict:
    return {
        "type":    level,
        "code":    code,
        "message": msg,
        "selector": sel,
        "context":  ctx,
        "runner":  "dom-checker",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Checks individuales
# ─────────────────────────────────────────────────────────────────────────────

def check_logo_home_link(page: Page) -> list[dict]:
    """
    logo-home-link: El logotipo debe tener un enlace a la página de inicio.
    Busca <img> o <svg> dentro de <a> en <header> cuyo href sea "/" o la raíz del dominio.
    """
    issues = []
    found = page.evaluate("""() => {
        const header = document.querySelector('header, [role="banner"]');
        if (!header) return { hasHeader: false, hasLogoLink: false };
        const logoLink = header.querySelector(
            'a img, a svg, a [class*="logo"], a [class*="brand"], [class*="logo"] a, [class*="brand"] a'
        );
        if (!logoLink) return { hasHeader: true, hasLogoLink: false };
        const anchor = logoLink.closest('a') || logoLink.querySelector('a');
        if (!anchor) return { hasHeader: true, hasLogoLink: false };
        const href = (anchor.getAttribute('href') || '').trim();
        const isHome = href === '/' || href === '' || /^https?:\/\/[^/]+\/?$/.test(href);
        return { hasHeader: true, hasLogoLink: isHome };
    }""")

    if not found.get("hasHeader"):
        issues.append(_make(
            "logo-home-link",
            "No se encontró un elemento <header> o landmark banner en la página.",
            "", "", "warning"
        ))
    elif not found.get("hasLogoLink"):
        issues.append(_make(
            "logo-home-link",
            "El logotipo no está envuelto en un enlace que apunte a la página de inicio (href='/').",
            "header a:has(img), header a:has(svg)", "", "error"
        ))
    return issues


def check_single_h1(page: Page) -> list[dict]:
    """
    single-h1: Debe existir exactamente un <h1> por página.
    """
    issues = []
    h1s = page.query_selector_all("h1")
    count = len(h1s)
    if count == 0:
        issues.append(_make(
            "single-h1",
            "La página no tiene ningún elemento <h1>. Cada página debe tener exactamente uno.",
            "h1", "", "error"
        ))
    elif count > 1:
        for i, el in enumerate(h1s[1:], 2):
            ctx = (el.evaluate("el => el.outerHTML") or "")[:200]
            issues.append(_make(
                "single-h1",
                f"Se encontraron {count} elementos <h1> en la página. Solo debe existir uno (este es el #{i}).",
                "h1", ctx, "error"
            ))
    return issues


def check_heading_hierarchy(page: Page) -> list[dict]:
    """
    heading-hierarchy: Los encabezados no deben saltarse niveles (H1→H3 sin H2, etc.).
    """
    issues = []
    headings = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('h1,h2,h3,h4,h5,h6')).map(el => ({
            level: parseInt(el.tagName[1]),
            text: el.innerText.trim().slice(0, 80),
            html: el.outerHTML.slice(0, 200)
        }));
    }""")
    prev = 0
    for h in headings:
        lvl = h["level"]
        if prev > 0 and lvl > prev + 1:
            issues.append(_make(
                "heading-hierarchy",
                f"Salto de nivel de encabezado: de H{prev} a H{lvl}. Los encabezados deben seguir un orden sin saltos.",
                f"h{lvl}", h["html"], "error"
            ))
        prev = lvl
    return issues


def check_semantic_landmarks(page: Page) -> list[dict]:
    """
    semantic-landmarks: La página debe usar elementos semánticos (header, nav, main, footer).
    """
    issues = []
    result = page.evaluate("""() => {
        const check = (sel, role) => {
            return !!(document.querySelector(sel) || document.querySelector('[role="' + role + '"]'));
        };
        return {
            header: check('header', 'banner'),
            nav:    check('nav', 'navigation'),
            main:   check('main', 'main'),
            footer: check('footer', 'contentinfo'),
        };
    }""")
    mapping = {
        "header": ("<header>", "banner"),
        "nav":    ("<nav>", "navigation"),
        "main":   ("<main>", "main"),
        "footer": ("<footer>", "contentinfo"),
    }
    for key, (tag, role) in mapping.items():
        if not result.get(key):
            issues.append(_make(
                "semantic-landmarks",
                f"No se encontró el elemento semántico {tag} (ni role=\"{role}\"). "
                f"Úsalo para estructurar correctamente las regiones de la página.",
                tag, "", "warning"
            ))
    return issues


def check_placeholder_no_label(page: Page) -> list[dict]:
    """
    placeholder-no-label: Inputs con placeholder pero sin <label> visible asociada.
    """
    issues = []
    results = page.evaluate("""() => {
        const inputs = Array.from(document.querySelectorAll(
            'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"]):not([type="image"]), textarea'
        ));
        return inputs.map(el => {
            const id = el.id;
            const hasLabel = id
                ? !!document.querySelector('label[for="' + id + '"]')
                : !!el.closest('label');
            const hasAria = !!(el.getAttribute('aria-label') || el.getAttribute('aria-labelledby'));
            const hasPlaceholder = !!el.getAttribute('placeholder');
            const hasTitle = !!el.getAttribute('title');
            return {
                hasProblem: hasPlaceholder && !hasLabel && !hasAria && !hasTitle,
                placeholder: el.getAttribute('placeholder') || '',
                html: el.outerHTML.slice(0, 200)
            };
        }).filter(r => r.hasProblem);
    }""")
    for r in results:
        issues.append(_make(
            "placeholder-no-label",
            f"El campo con placeholder \"{r['placeholder']}\" no tiene etiqueta visible (<label>), "
            "aria-label ni aria-labelledby. El placeholder desaparece al escribir y no es suficiente como etiqueta.",
            "input, textarea", r["html"], "error"
        ))
    return issues


def check_new_window_warning(page: Page) -> list[dict]:
    """
    new-window-warning: Los enlaces que abren nueva pestaña deben indicarlo.
    """
    issues = []
    results = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('a[target="_blank"]')).map(el => {
            const text = (el.innerText || el.getAttribute('aria-label') || '').toLowerCase();
            const title = (el.getAttribute('title') || '').toLowerCase();
            const warns = ['nueva ventana','nueva pestaña','new window','new tab','_blank','opens in'];
            const hasWarning = warns.some(w => text.includes(w) || title.includes(w));
            return { hasWarning, html: el.outerHTML.slice(0, 200), text: el.innerText.trim().slice(0, 60) };
        }).filter(r => !r.hasWarning);
    }""")
    for r in results:
        issues.append(_make(
            "new-window-warning",
            f"El enlace \"{r['text'] or '(sin texto)'}\" abre en nueva pestaña (target=\"_blank\") "
            "pero no lo indica en su texto, aria-label ni title.",
            'a[target="_blank"]', r["html"], "warning"
        ))
    return issues


def check_reflow_320(page: Page) -> list[dict]:
    """
    reflow-320: Con viewport de 320px no debe aparecer scroll horizontal.
    """
    issues = []
    original = page.viewport_size
    try:
        page.set_viewport_size({"width": 320, "height": 568})
        page.wait_for_timeout(400)
        overflow = page.evaluate("""() => {
            return document.documentElement.scrollWidth > document.documentElement.clientWidth;
        }""")
        if overflow:
            issues.append(_make(
                "reflow-320",
                "Con un viewport de 320px aparece scroll horizontal innecesario. "
                "El contenido debe adaptarse sin necesidad de desplazamiento horizontal (WCAG 1.4.10 Reflow).",
                "body", "", "error"
            ))
    finally:
        if original:
            page.set_viewport_size(original)
    return issues


def check_focus_visible(page: Page) -> list[dict]:
    """
    focus-visible: Detecta elementos interactivos con outline:none o outline:0 en su CSS,
    lo cual elimina el indicador de foco visible.
    """
    issues = []
    results = page.evaluate("""() => {
        const interactive = Array.from(document.querySelectorAll(
            'a[href], button, input, select, textarea, [tabindex]:not([tabindex="-1"])'
        ));
        return interactive.slice(0, 100).map(el => {
            const style = window.getComputedStyle(el);
            const outline = style.outlineStyle;
            const outlineWidth = parseFloat(style.outlineWidth);
            const noOutline = outline === 'none' || outlineWidth === 0;
            return { noOutline, html: el.outerHTML.slice(0, 150) };
        }).filter(r => r.noOutline).slice(0, 10);
    }""")
    for r in results:
        issues.append(_make(
            "focus-visible",
            "Este elemento interactivo tiene outline:none o outline-width:0. "
            "El indicador de foco debe ser visible para usuarios que navegan con teclado.",
            "a[href], button, input, [tabindex]", r["html"], "warning"
        ))
    return issues


def check_accordion_aria_expanded(page: Page) -> list[dict]:
    """
    accordion-state: Botones de acordeón/tab sin aria-expanded.
    """
    issues = []
    results = page.evaluate("""() => {
        const candidates = Array.from(document.querySelectorAll(
            'button, [role="button"], [role="tab"]'
        ));
        return candidates.filter(el => {
            const controls = el.getAttribute('aria-controls');
            const expanded = el.getAttribute('aria-expanded');
            return controls && expanded === null;
        }).slice(0, 20).map(el => ({
            html: el.outerHTML.slice(0, 200)
        }));
    }""")
    for r in results:
        issues.append(_make(
            "accordion-state",
            "Este botón controla un elemento expandible (aria-controls) pero no tiene "
            "aria-expanded. Los acordeones, tabs y desplegables deben anunciar su estado.",
            "button[aria-controls]", r["html"], "error"
        ))
    return issues


def check_lang_attribute(page: Page) -> list[dict]:
    """
    lang-attr: El elemento <html> debe tener el atributo lang definido y válido.
    """
    issues = []
    result = page.evaluate("""() => {
        const lang = document.documentElement.getAttribute('lang') || '';
        return { lang: lang.trim() };
    }""")
    lang = result.get("lang", "")
    if not lang:
        issues.append(_make(
            "lang-attr",
            "El elemento <html> no tiene atributo lang. Añade lang=\"es\" (o el idioma correspondiente) "
            "para que los lectores de pantalla usen la pronunciación correcta.",
            "html", "", "error"
        ))
    elif len(lang) < 2:
        issues.append(_make(
            "lang-attr",
            f"El atributo lang=\"{lang}\" del elemento <html> no parece un código de idioma válido. "
            "Usa códigos como \"es\", \"en\", \"es-MX\".",
            "html", "", "warning"
        ))
    return issues


def check_semantic_headings(page: Page) -> list[dict]:
    """
    semantic-headings: Detecta <div> o <span> que simulan encabezados mediante clases CSS
    (class que contiene 'title', 'heading', 'h1'-'h6', etc.) pero no son etiquetas de encabezado reales.
    """
    issues = []
    results = page.evaluate("""() => {
        const pattern = /\\btitle\\b|\\bheading\\b|\\bh[1-6]\\b/i;
        const candidates = Array.from(document.querySelectorAll('div, span, p'));
        return candidates.filter(el => {
            const cls = el.className || '';
            const id  = el.id || '';
            if (!pattern.test(cls) && !pattern.test(id)) return false;
            const tag = el.tagName.toLowerCase();
            // Solo flaggear si tiene texto y es de primer nivel (no dentro de un heading real)
            const inside = !!el.closest('h1,h2,h3,h4,h5,h6');
            const hasText = (el.innerText || '').trim().length > 0;
            return !inside && hasText;
        }).slice(0, 10).map(el => ({
            tag: el.tagName.toLowerCase(),
            cls: el.className,
            html: el.outerHTML.slice(0, 200)
        }));
    }""")
    for r in results:
        issues.append(_make(
            "semantic-headings",
            f"El elemento <{r['tag']} class=\"{r['cls']}\"> parece simular un encabezado visualmente "
            "pero no usa una etiqueta <h1>–<h6>. Usa el elemento de encabezado adecuado para "
            "que los lectores de pantalla puedan navegar por la estructura del documento.",
            f"{r['tag']}.{r['cls'].split()[0] if r['cls'] else ''}", r["html"], "warning"
        ))
    return issues


def check_real_lists(page: Page) -> list[dict]:
    """
    real-lists: Detecta listas simuladas con texto plano (•, -, *, 1., 2.) dentro de <p> o <div>.
    """
    issues = []
    results = page.evaluate(r"""() => {
        const listPattern = /^(\s*[•\-\*✓✗▸▶►→]\s+.{5,}|\s*\d+[\.\)]\s+.{5,})/m;
        return Array.from(document.querySelectorAll('p, div')).filter(el => {
            if (el.querySelector('ul,ol,li,table')) return false;
            const text = el.innerText || '';
            const lines = text.split('\n').filter(l => l.trim().length > 0);
            const listLike = lines.filter(l => listPattern.test(l));
            return listLike.length >= 2;
        }).slice(0, 5).map(el => ({
            html: el.outerHTML.slice(0, 200),
            tag: el.tagName.toLowerCase()
        }));
    }""")
    for r in results:
        issues.append(_make(
            "real-lists",
            f"El elemento <{r['tag']}> parece contener una lista simulada con texto plano "
            "(caracteres como •, -, 1., etc.). Usa <ul>/<ol> con <li> para una estructura semántica correcta.",
            r["tag"], r["html"], "warning"
        ))
    return issues


# ─────────────────────────────────────────────────────────────────────────────
# Checks creativos avanzados
# ─────────────────────────────────────────────────────────────────────────────

def check_content_without_css(page: Page) -> list[dict]:
    """
    content-without-css: Deshabilita todas las hojas de estilo y verifica que el contenido
    sigue siendo legible y estructurado. Detecta:
    - Texto invisible (color == background heredado de body blanco → texto blanco)
    - Contenido que solo existe como background-image CSS (no <img>)
    - Botones sin texto visible (solo icono CSS)
    """
    issues = []
    results = page.evaluate("""() => {
        const problems = [];

        // 1. Detectar elementos con color de texto igual al fondo de body (texto invisible sin CSS)
        const bodyBg = window.getComputedStyle(document.body).backgroundColor;
        const allText = Array.from(document.querySelectorAll('p, span, a, button, h1, h2, h3, li'));
        allText.slice(0, 200).forEach(el => {
            const st = window.getComputedStyle(el);
            const color = st.color;
            const bg = st.backgroundColor;
            // Si el color del texto es el mismo que el fondo del body y no es transparente
            if (color === bodyBg && color !== 'rgba(0, 0, 0, 0)' && (el.innerText || '').trim().length > 0) {
                problems.push({
                    type: 'invisible-text',
                    html: el.outerHTML.slice(0, 150)
                });
            }
        });

        // 2. Elementos cuyo contenido visible depende de background-image CSS (no <img>)
        const divs = Array.from(document.querySelectorAll('div, span, a, button'));
        divs.slice(0, 200).forEach(el => {
            const st = window.getComputedStyle(el);
            const bgImg = st.backgroundImage;
            const hasRealImg = !!el.querySelector('img, svg, picture');
            const hasText = (el.innerText || '').trim().length > 0;
            if (bgImg && bgImg !== 'none' && !hasRealImg && !hasText) {
                problems.push({
                    type: 'css-only-content',
                    html: el.outerHTML.slice(0, 150)
                });
            }
        });

        return problems.slice(0, 10);
    }""")

    for r in results:
        if r["type"] == "invisible-text":
            issues.append(_make(
                "content-without-css",
                "Este elemento tiene texto del mismo color que el fondo del body: sería invisible sin CSS.",
                "", r["html"], "error"
            ))
        elif r["type"] == "css-only-content":
            issues.append(_make(
                "content-without-css",
                "Este elemento muestra contenido solo mediante background-image CSS. "
                "Sin hoja de estilos el contenido desaparece. Usa <img> con alt o SVG en línea.",
                "", r["html"], "warning"
            ))
    return issues


def check_error_association(page: Page) -> list[dict]:
    """
    error-programmatic: Detecta campos con mensaje de error visible cercano pero sin
    aria-describedby apuntando a ese mensaje. Estrategia:
    - Busca elementos con class/role que indiquen error próximos a un input.
    - Verifica que el input tenga aria-describedby o aria-errormessage apuntando a ese elemento.
    """
    issues = []
    results = page.evaluate("""() => {
        const errorPattern = /error|invalid|alert|warning|danger|fail/i;
        const messages = Array.from(document.querySelectorAll(
            '[role="alert"], [aria-live], .error, .invalid, .field-error, .form-error, ' +
            '[class*="error"], [class*="invalid"], [class*="alert"]'
        )).filter(el => (el.innerText || '').trim().length > 0);

        return messages.map(msg => {
            const id = msg.id;
            // Buscar el input más cercano (hermano anterior o dentro del mismo contenedor)
            const container = msg.closest('form, fieldset, .form-group, .field, [class*="input"], [class*="form"]') || msg.parentElement;
            if (!container) return null;
            const input = container.querySelector('input, select, textarea');
            if (!input) return null;
            const described = input.getAttribute('aria-describedby') || '';
            const errMsg = input.getAttribute('aria-errormessage') || '';
            const linked = id && (described.includes(id) || errMsg.includes(id));
            if (!linked) {
                return {
                    inputHtml: input.outerHTML.slice(0, 150),
                    msgHtml: msg.outerHTML.slice(0, 150),
                    hasId: !!id
                };
            }
            return null;
        }).filter(Boolean).slice(0, 5);
    }""")

    for r in results:
        if not r["hasId"]:
            issues.append(_make(
                "error-programmatic",
                "Se encontró un mensaje de error visible sin atributo id. "
                "Sin id no puede vincularse al campo con aria-describedby.",
                "input, select, textarea", r["msgHtml"], "error"
            ))
        else:
            issues.append(_make(
                "error-programmatic",
                "El campo de formulario tiene un mensaje de error cercano pero no está vinculado "
                "mediante aria-describedby o aria-errormessage. Los lectores de pantalla no lo asociarán.",
                "input, select, textarea", r["inputHtml"], "error"
            ))
    return issues


def check_cookie_banner_accessible(page: Page) -> list[dict]:
    """
    cookie-accessible: Detecta banners de cookies y verifica:
    - Que tenga role="dialog" o aria-live
    - Que el botón de aceptar/rechazar sea operable por teclado (es <button> o tiene role=button)
    - Que el banner tenga un aria-label o aria-labelledby
    """
    issues = []
    result = page.evaluate("""() => {
        const bannerSelectors = [
            '[id*="cookie"]', '[class*="cookie"]', '[id*="consent"]', '[class*="consent"]',
            '[id*="gdpr"]', '[class*="gdpr"]', '[aria-label*="cookie" i]',
            '[id*="privacy-banner"]', '[class*="privacy-banner"]'
        ];
        let banner = null;
        for (const sel of bannerSelectors) {
            banner = document.querySelector(sel);
            if (banner) break;
        }
        if (!banner) return { found: false };

        const role = banner.getAttribute('role') || '';
        const ariaLive = banner.getAttribute('aria-live') || '';
        const ariaLabel = banner.getAttribute('aria-label') || banner.getAttribute('aria-labelledby') || '';
        const hasProperRole = ['dialog','alertdialog','region','alert'].includes(role) || ariaLive;

        const buttons = Array.from(banner.querySelectorAll('a, div, span')).filter(el => {
            const t = (el.innerText || '').toLowerCase();
            return t.includes('accept') || t.includes('acepto') || t.includes('aceptar') ||
                   t.includes('rechaz') || t.includes('reject') || t.includes('ok');
        });
        const fakeButtons = buttons.filter(el => {
            const tag = el.tagName.toLowerCase();
            const roleEl = el.getAttribute('role') || '';
            return tag !== 'button' && tag !== 'input' && roleEl !== 'button';
        });

        return {
            found: true,
            hasProperRole,
            hasAriaLabel: !!ariaLabel,
            fakeButtons: fakeButtons.map(el => el.outerHTML.slice(0, 150)),
            bannerHtml: banner.outerHTML.slice(0, 200)
        };
    }""")

    if not result.get("found"):
        return issues

    if not result.get("hasProperRole"):
        issues.append(_make(
            "cookie-accessible",
            "El banner de cookies no tiene role=\"dialog\" ni aria-live. "
            "Los lectores de pantalla pueden no anunciarlo al usuario.",
            "[class*='cookie'], [id*='cookie']", result.get("bannerHtml", ""), "warning"
        ))
    if not result.get("hasAriaLabel"):
        issues.append(_make(
            "cookie-accessible",
            "El banner de cookies no tiene aria-label ni aria-labelledby. "
            "Añade un nombre accesible para que los lectores de pantalla identifiquen el diálogo.",
            "[class*='cookie'], [id*='cookie']", result.get("bannerHtml", ""), "warning"
        ))
    for fb in result.get("fakeButtons", []):
        issues.append(_make(
            "cookie-accessible",
            "El botón de aceptar/rechazar cookies no es un elemento <button>. "
            "No es operable con teclado ni anunciado correctamente por lectores de pantalla.",
            "", fb, "error"
        ))
    return issues


def check_legal_links_in_footer(page: Page) -> list[dict]:
    """
    legal-readable: Verifica que existen enlaces a avisos legales, política de privacidad
    y cookies en el pie de página, y que son accesibles (tienen texto visible y href válido).
    """
    issues = []
    result = page.evaluate("""() => {
        const footer = document.querySelector('footer, [role="contentinfo"]');
        if (!footer) return { hasFooter: false };

        const links = Array.from(footer.querySelectorAll('a[href]'));
        const legalPattern = /privac|pol[ií]tica|legal|aviso|cookie|t[eé]rminos|condiciones|policy|terms|gdpr|accesibilidad|accessibility|descargo|responsabilidad|disclaimer/i;
        const legalLinks = links.filter(a => {
            const text = (a.innerText || a.getAttribute('aria-label') || a.getAttribute('title') || '').trim();
            const href = a.getAttribute('href') || '';
            // Match against visible text, href path/slug, and decoded href for Spanish chars
            const decodedHref = decodeURIComponent(href);
            return legalPattern.test(text) || legalPattern.test(href) || legalPattern.test(decodedHref);
        });

        const problems = legalLinks.filter(a => {
            const text = (a.innerText || '').trim();
            const href = (a.getAttribute('href') || '').trim();
            return !text || href === '#' || href === '';
        });

        return {
            hasFooter: true,
            hasLegalLinks: legalLinks.length > 0,
            problemLinks: problems.map(a => a.outerHTML.slice(0, 150))
        };
    }""")

    if not result.get("hasFooter"):
        return issues

    if not result.get("hasLegalLinks"):
        issues.append(_make(
            "legal-readable",
            "No se encontraron enlaces a política de privacidad, aviso legal ni cookies en el pie de página. "
            "Son obligatorios por normativa y deben ser fácilmente localizables.",
            "footer", "", "warning"
        ))
    for pl in result.get("problemLinks", []):
        issues.append(_make(
            "legal-readable",
            "Enlace legal en el pie de página sin texto visible o con href='#'. "
            "No es navegable ni descriptivo para lectores de pantalla.",
            "footer a", pl, "error"
        ))
    return issues


def check_image_with_text_has_caption(page: Page) -> list[dict]:
    """
    img-text-description: Detecta imágenes cuyo nombre de archivo o alt sugiere que
    contienen texto (infografía, banner, slide, chart, tabla-imagen, captura, screenshot…)
    pero no tienen un elemento de texto visible inmediatamente después (<figcaption>, <p>, etc.).
    """
    issues = []
    results = page.evaluate("""() => {
        const textImgPattern = /infograf|banner|slide|chart|graf|tabla|captura|screenshot|flyer|poster|diagram/i;
        return Array.from(document.querySelectorAll('img')).filter(img => {
            const src = img.getAttribute('src') || '';
            const alt = img.getAttribute('alt') || '';
            return textImgPattern.test(src) || textImgPattern.test(alt);
        }).map(img => {
            // Buscar figcaption, párrafo hermano posterior o descripción aria
            const fig = img.closest('figure');
            const hasCaption = fig ? !!fig.querySelector('figcaption') : false;
            const ariaDesc = img.getAttribute('aria-describedby') || img.getAttribute('longdesc') || '';
            // Buscar párrafo hermano inmediato posterior
            const parent = img.parentElement;
            let nextText = false;
            if (parent) {
                let sib = img.nextElementSibling;
                while (sib) {
                    if (['P','DIV','SPAN','FIGCAPTION'].includes(sib.tagName) && (sib.innerText||'').trim().length > 10) {
                        nextText = true;
                        break;
                    }
                    sib = sib.nextElementSibling;
                }
            }
            const hasDescription = hasCaption || !!ariaDesc || nextText;
            return { hasDescription, src: src.slice(-60), alt: alt.slice(0,80), html: img.outerHTML.slice(0,200) };
        }).filter(r => !r.hasDescription).slice(0, 8);
    }""")

    for r in results:
        issues.append(_make(
            "img-text-description",
            f"La imagen '{r['src']}' parece contener texto o datos (infografía, gráfico, captura…) "
            "pero no tiene <figcaption>, aria-describedby ni texto descriptivo visible justo después. "
            "Añade una descripción textual que transmita la misma información.",
            "img", r["html"], "warning"
        ))
    return issues


def check_decorative_images(page: Page) -> list[dict]:
    """
    img-decorative-alt: Detecta imágenes que probablemente son decorativas
    (están dentro de elementos que ya tienen texto, su src contiene palabras como
    background/decoration/icon/separator/divider/spacer) pero tienen alt con texto,
    lo cual añade ruido a los lectores de pantalla.
    """
    issues = []
    results = page.evaluate("""() => {
        const decorPattern = /background|decoration|decorat|separator|divider|spacer|ornament|pattern/i;
        return Array.from(document.querySelectorAll('img[alt]')).filter(img => {
            const alt = img.getAttribute('alt') || '';
            if (!alt.trim()) return false; // ya tiene alt vacío, correcto
            const src = img.getAttribute('src') || '';
            if (!decorPattern.test(src)) return false;
            return true;
        }).slice(0, 5).map(img => ({
            alt, src: img.getAttribute('src').slice(-60), html: img.outerHTML.slice(0, 200)
        }));
    }""")

    for r in results:
        issues.append(_make(
            "img-decorative-alt",
            f"La imagen '{r['src']}' parece decorativa (su nombre sugiere fondo, separador o adorno) "
            f"pero tiene alt=\"{r.get('alt','')}\". Las imágenes decorativas deben tener alt=\"\" "
            "para que los lectores de pantalla las ignoren.",
            "img", r["html"], "warning"
        ))
    return issues


def check_nav_consistency(page: Page) -> list[dict]:
    """
    nav-consistency: Comprueba que el <nav> principal tiene aria-label o aria-labelledby
    y que si hay múltiples <nav>, cada uno está diferenciado con un label único.
    También detecta si hay duplicados de texto en la navegación (mismo enlace repetido
    con distintos textos → incoherencia).
    """
    issues = []
    results = page.evaluate("""() => {
        const navs = Array.from(document.querySelectorAll('nav, [role="navigation"]'));
        const problems = [];

        navs.forEach((nav, i) => {
            const label = nav.getAttribute('aria-label') || nav.getAttribute('aria-labelledby') || '';
            if (!label && navs.length > 1) {
                problems.push({
                    type: 'unlabeled-nav',
                    html: nav.outerHTML.slice(0, 200),
                    index: i + 1
                });
            }
        });

        // Detectar enlaces de navegación con href igual pero texto distinto (incoherencia)
        if (navs.length > 0) {
            const mainNav = navs[0];
            const links = Array.from(mainNav.querySelectorAll('a[href]'));
            const hrefMap = {};
            links.forEach(a => {
                const href = a.getAttribute('href');
                const text = (a.innerText || '').trim();
                if (href && text) {
                    if (!hrefMap[href]) hrefMap[href] = new Set();
                    hrefMap[href].add(text);
                }
            });
            Object.entries(hrefMap).forEach(([href, texts]) => {
                if (texts.size > 1) {
                    problems.push({
                        type: 'inconsistent-link',
                        href,
                        texts: Array.from(texts)
                    });
                }
            });
        }
        return problems.slice(0, 6);
    }""")

    for r in results:
        if r["type"] == "unlabeled-nav":
            issues.append(_make(
                "nav-consistency",
                f"Hay {r['index']} o más elementos <nav> en la página y el #{r['index']} no tiene "
                "aria-label ni aria-labelledby. Con múltiples navs, cada uno debe tener un nombre "
                "único para que los usuarios de lector de pantalla los distingan.",
                "nav", r["html"], "warning"
            ))
        elif r["type"] == "inconsistent-link":
            texts = ", ".join(f'"{t}"' for t in r["texts"])
            issues.append(_make(
                "nav-consistency",
                f"El enlace '{r['href']}' aparece en la navegación con textos distintos: {texts}. "
                "El mismo destino debe tener siempre el mismo texto de enlace.",
                f"nav a[href='{r['href']}']", "", "warning"
            ))
    return issues


def check_zoom_200(page: Page) -> list[dict]:
    """
    zoom-200: Simula zoom al 200% (duplica el font-size del html) y detecta:
    - Texto truncado con overflow:hidden + texto cortado
    - Elementos que se superponen (overflow visible fuera de su contenedor)
    - Botones o inputs cuyo texto desaparece
    """
    issues = []
    original_size = page.viewport_size
    try:
        # Simular zoom 200%: duplicar font-size base y reducir viewport a la mitad
        page.evaluate("document.documentElement.style.fontSize = '200%'")
        page.wait_for_timeout(300)

        results = page.evaluate("""() => {
            const problems = [];

            // Detectar texto truncado (overflow hidden con scrollWidth > clientWidth)
            const all = Array.from(document.querySelectorAll('p, h1, h2, h3, h4, button, a, li, label, span'));
            all.slice(0, 300).forEach(el => {
                const st = window.getComputedStyle(el);
                const overflow = st.overflow + st.overflowX;
                if (overflow.includes('hidden') && el.scrollWidth > el.clientWidth + 2) {
                    problems.push({
                        type: 'text-truncated',
                        html: el.outerHTML.slice(0, 150)
                    });
                }
            });

            // Detectar elementos que salen del viewport horizontal
            const rect = el => el.getBoundingClientRect();
            const vw = document.documentElement.clientWidth;
            const interactive = Array.from(document.querySelectorAll('button, input, a, select'));
            interactive.slice(0, 100).forEach(el => {
                const r = el.getBoundingClientRect();
                if (r.right > vw + 10 && r.width > 0) {
                    problems.push({
                        type: 'overflow-viewport',
                        html: el.outerHTML.slice(0, 150)
                    });
                }
            });

            return problems.slice(0, 8);
        }""")

        for r in results:
            if r["type"] == "text-truncated":
                issues.append(_make(
                    "zoom-200",
                    "Con zoom al 200% este elemento trunca su texto (overflow:hidden). "
                    "El contenido textual no debe quedar oculto al aumentar el tamaño de fuente.",
                    "", r["html"], "error"
                ))
            elif r["type"] == "overflow-viewport":
                issues.append(_make(
                    "zoom-200",
                    "Con zoom al 200% este elemento interactivo queda fuera del viewport horizontal. "
                    "Todo el contenido debe ser accesible sin scroll horizontal al usar zoom.",
                    "", r["html"], "warning"
                ))
    finally:
        page.evaluate("document.documentElement.style.fontSize = ''")
        if original_size:
            page.set_viewport_size(original_size)
    return issues


def check_sensory_instructions(page: Page) -> list[dict]:
    """
    no-sensory-only: Detecta instrucciones que dependen solo de posición, forma,
    tamaño o color usando patrones de texto. Ejemplo: "haz clic en el botón verde",
    "ver la columna de la derecha", "el campo cuadrado", etc.
    """
    issues = []
    results = page.evaluate(r"""() => {
        const patterns = [
            /haz clic en el (bot[oó]n|enlace|icono|elemento) (rojo|verde|azul|amarillo|naranja|gris|negro|blanco)/i,
            /el (bot[oó]n|campo|secci[oó]n|cuadro|bloque) de la (derecha|izquierda|arriba|abajo)/i,
            /ver (m[aá]s en|el panel|la columna|la secci[oó]n) (derecha|izquierda|superior|inferior)/i,
            /click (the )?(red|green|blue|yellow|gray|black|white|orange) (button|link|icon)/i,
            /see the (right|left|top|bottom) (column|panel|section)/i,
            /el bot[oó]n (redondo|cuadrado|circular|triangular)/i,
            /el (recuadro|cuadrado|c[ií]rculo) (rojo|verde|azul)/i,
        ];

        const textNodes = Array.from(document.querySelectorAll('p, li, label, span, div'))
            .filter(el => !el.querySelector('p, li, label') && (el.innerText || '').trim().length > 10);

        const found = [];
        textNodes.slice(0, 500).forEach(el => {
            const text = (el.innerText || '').trim();
            for (const pat of patterns) {
                if (pat.test(text)) {
                    found.push({ text: text.slice(0, 120), html: el.outerHTML.slice(0, 200) });
                    break;
                }
            }
        });
        return found.slice(0, 5);
    }""")

    for r in results:
        issues.append(_make(
            "no-sensory-only",
            f"Instrucción que depende de características sensoriales (color, posición, forma): "
            f"\"{r['text']}\". Añade una referencia adicional que no dependa solo de la apariencia visual.",
            "", r["html"], "warning"
        ))
    return issues


def check_focus_order(page: Page) -> list[dict]:
    """
    tab-order: Detecta elementos con tabindex > 0, que fuerzan un orden de tabulación
    artificial y a menudo rompen el flujo lógico de navegación por teclado.
    También detecta tabindex muy alto (>10) como señal de diseño problemático.
    """
    issues = []
    results = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('[tabindex]'))
            .map(el => ({
                tabindex: parseInt(el.getAttribute('tabindex')),
                html: el.outerHTML.slice(0, 150)
            }))
            .filter(r => r.tabindex > 0)
            .slice(0, 10);
    }""")

    for r in results:
        level = "error" if r["tabindex"] > 10 else "warning"
        issues.append(_make(
            "tab-order",
            f"El elemento tiene tabindex=\"{r['tabindex']}\". Los valores de tabindex mayores que 0 "
            "alteran el orden natural de tabulación y suelen causar problemas de navegación por teclado. "
            "Usa tabindex=\"0\" para incluir el elemento en el flujo o reorganiza el DOM.",
            f"[tabindex='{r['tabindex']}']", r["html"], level
        ))
    return issues


def check_keyboard_trap(page: Page) -> list[dict]:
    """
    no-keyboard-trap: Detecta iframes, objetos embebidos y modales sin mecanismo de escape.
    - iframes sin title
    - Elementos con role=dialog sin aria-modal o sin botón de cierre
    - focus-trap implementados con JS que no tienen Escape key listener detectable
    """
    issues = []
    results = page.evaluate("""() => {
        const problems = [];

        // iframes sin title
        Array.from(document.querySelectorAll('iframe')).forEach(frame => {
            const title = frame.getAttribute('title') || frame.getAttribute('aria-label') || '';
            if (!title.trim()) {
                problems.push({ type: 'iframe-no-title', html: frame.outerHTML.slice(0, 150) });
            }
        });

        // Modales/diálogos sin botón de cierre evidente ni aria-modal
        Array.from(document.querySelectorAll('[role="dialog"], [role="alertdialog"]')).forEach(modal => {
            const hasClose = !!modal.querySelector(
                'button[aria-label*="cerrar" i], button[aria-label*="close" i], ' +
                'button[title*="cerrar" i], button[title*="close" i], ' +
                '[class*="close"], [class*="cerrar"], [class*="dismiss"]'
            );
            const ariaModal = modal.getAttribute('aria-modal');
            if (!hasClose) {
                problems.push({ type: 'modal-no-close', html: modal.outerHTML.slice(0, 150) });
            }
            if (ariaModal !== 'true') {
                problems.push({ type: 'modal-no-aria-modal', html: modal.outerHTML.slice(0, 150) });
            }
        });

        return problems.slice(0, 8);
    }""")

    for r in results:
        if r["type"] == "iframe-no-title":
            issues.append(_make(
                "no-keyboard-trap",
                "El <iframe> no tiene atributo title ni aria-label. Los lectores de pantalla no pueden "
                "identificar su propósito y el usuario no sabe qué encontrará al entrar.",
                "iframe", r["html"], "error"
            ))
        elif r["type"] == "modal-no-close":
            issues.append(_make(
                "no-keyboard-trap",
                "Este diálogo modal no tiene un botón de cierre identificable (aria-label='cerrar/close'). "
                "El usuario de teclado podría quedar atrapado dentro.",
                "[role='dialog']", r["html"], "error"
            ))
        elif r["type"] == "modal-no-aria-modal":
            issues.append(_make(
                "no-keyboard-trap",
                "Este diálogo modal no tiene aria-modal=\"true\". Sin él, los lectores de pantalla "
                "siguen leyendo el contenido detrás del modal como si fuera accesible.",
                "[role='dialog']", r["html"], "warning"
            ))
    return issues


def check_error_states_not_color_only(page: Page) -> list[dict]:
    """
    error-not-color-only: Analiza inputs que tienen clase de error/inválido aplicada.
    Verifica que además del cambio de color haya un indicador textual o icono con texto alternativo.
    """
    issues = []
    results = page.evaluate("""() => {
        const errorSelectors = [
            'input.error', 'input.invalid', 'input[aria-invalid="true"]',
            'input.is-invalid', 'input.has-error', 'select.error', 'textarea.error',
            'input.error-field', '.field-error input', '.form-error input'
        ];
        const found = [];
        errorSelectors.forEach(sel => {
            document.querySelectorAll(sel).forEach(input => {
                const parent = input.closest('.form-group, .field, fieldset, .input-wrap, .form-row') || input.parentElement;
                const errorText = parent ? Array.from(parent.querySelectorAll(
                    '.error-message, .invalid-feedback, [class*="error-msg"], [aria-live], [role="alert"]'
                )).filter(el => (el.innerText || '').trim().length > 0) : [];
                if (errorText.length === 0) {
                    found.push({ html: input.outerHTML.slice(0, 150) });
                }
            });
        });
        return found.slice(0, 5);
    }""")

    for r in results:
        issues.append(_make(
            "error-not-color-only",
            "Este campo tiene una clase de estado de error (error, invalid…) pero no se encontró "
            "texto de error visible asociado. El estado de error no debe indicarse solo mediante color; "
            "añade un mensaje de texto visible próximo al campo.",
            "input, select, textarea", r["html"], "error"
        ))
    return issues


def check_required_fields_visible(page: Page) -> list[dict]:
    """
    required-fields: Detecta campos con required/aria-required=true pero sin indicador
    visual (asterisco, texto 'obligatorio'/'required') cerca del campo o su label.
    """
    issues = []
    results = page.evaluate(r"""() => {
        const required = Array.from(document.querySelectorAll(
            'input[required], input[aria-required="true"], select[required], textarea[required]'
        ));
        return required.map(input => {
            const id = input.id;
            const label = id ? document.querySelector('label[for="' + id + '"]') : input.closest('label');
            const labelText = (label ? label.innerText : '') || '';
            const container = input.closest('.form-group, .field, fieldset, .input-wrap') || input.parentElement;
            const containerText = container ? container.innerText : '';
            // Buscar indicador visual
            const hasAsterisk = /\*|✱|✲|＊/.test(labelText + containerText);
            const hasWordRequired = /(requerido|obligatorio|required)/i.test(labelText + containerText);
            if (!hasAsterisk && !hasWordRequired) {
                return { html: input.outerHTML.slice(0, 150), labelText: labelText.slice(0, 80) };
            }
            return null;
        }).filter(Boolean).slice(0, 5);
    }""")

    for r in results:
        issues.append(_make(
            "required-fields",
            f"El campo obligatorio (required) no tiene un indicador visual claro como asterisco (*) "
            f"ni el texto 'obligatorio' en su etiqueta. Label encontrada: \"{r['labelText'] or 'ninguna'}\". "
            "Los usuarios deben poder identificar visualmente qué campos son obligatorios antes de enviar.",
            "input[required], select[required], textarea[required]", r["html"], "warning"
        ))
    return issues


def check_success_messages(page: Page) -> list[dict]:
    """
    success-messages: Verifica que los mensajes de éxito usan role=status/alert o aria-live
    para ser anunciados por lectores de pantalla. Detecta elementos con clase 'success',
    'ok', 'confirmed' sin role ni aria-live.
    """
    issues = []
    results = page.evaluate("""() => {
        const successPattern = /success|ok\\b|confirmed|enviado|exito|éxito|completado|correcto/i;
        return Array.from(document.querySelectorAll('[class]')).filter(el => {
            const cls = el.className || '';
            return successPattern.test(cls) && (el.innerText || '').trim().length > 0;
        }).map(el => {
            const role = el.getAttribute('role') || '';
            const ariaLive = el.getAttribute('aria-live') || '';
            const accessible = ['status','alert','log'].includes(role) || ariaLive;
            return { accessible, html: el.outerHTML.slice(0, 150) };
        }).filter(r => !r.accessible).slice(0, 5);
    }""")

    for r in results:
        issues.append(_make(
            "success-messages",
            "Elemento de mensaje de éxito sin role=\"status\" ni aria-live. "
            "Los lectores de pantalla no anunciarán este mensaje al usuario si aparece dinámicamente.",
            "[class*='success'], [class*='confirmed']", r["html"], "warning"
        ))
    return issues


def check_sticky_elements_coverage(page: Page) -> list[dict]:
    """
    sticky-no-block: Detecta elementos sticky/fixed que cubren más del 25% del viewport
    en altura, lo que puede bloquear la lectura del contenido.
    """
    issues = []
    results = page.evaluate("""() => {
        const vh = window.innerHeight;
        return Array.from(document.querySelectorAll('*')).filter(el => {
            const st = window.getComputedStyle(el);
            return (st.position === 'fixed' || st.position === 'sticky');
        }).map(el => {
            const rect = el.getBoundingClientRect();
            const heightPercent = Math.round((rect.height / vh) * 100);
            return { heightPercent, html: el.outerHTML.slice(0, 150), tag: el.tagName.toLowerCase() };
        }).filter(r => r.heightPercent > 25 && r.heightPercent < 100).slice(0, 5);
    }""")

    for r in results:
        issues.append(_make(
            "sticky-no-block",
            f"El elemento <{r['tag']}> es fixed/sticky y ocupa el {r['heightPercent']}% del alto del viewport. "
            "Los elementos pegados que ocupan más del 25% de la pantalla pueden bloquear la lectura "
            "del contenido y la navegación por teclado.",
            r["tag"], r["html"], "warning"
        ))
    return issues


def check_cta_labels(page: Page) -> list[dict]:
    """
    cta-labels: Detecta botones y enlaces con textos genéricos e inútiles para lectores de pantalla:
    'aquí', 'clic aquí', 'leer más', 'ver más', 'más', 'click here', 'read more', 'more'.
    """
    issues = []
    results = page.evaluate("""() => {
        const vague = /^(aquí|aqui|clic aquí|click here|haz clic|leer más|leer mas|ver más|ver mas|más|mas|more|read more|here|click|ver todo|see all|descargar|download)$/i;
        return Array.from(document.querySelectorAll('a[href], button')).filter(el => {
            const text = (el.innerText || el.getAttribute('aria-label') || '').trim();
            return vague.test(text);
        }).slice(0, 10).map(el => ({
            text: (el.innerText || '').trim(),
            html: el.outerHTML.slice(0, 150)
        }));
    }""")

    for r in results:
        issues.append(_make(
            "cta-labels",
            f"El enlace o botón con texto \"{r['text']}\" no es descriptivo. "
            "Los usuarios de lector de pantalla navegan por listas de enlaces y necesitan "
            "que cada texto de enlace tenga sentido por sí solo sin el contexto visual.",
            "a, button", r["html"], "warning"
        ))
    return issues


# ─────────────────────────────────────────────────────────────────────────────
# Registro de todos los checks
# ─────────────────────────────────────────────────────────────────────────────

ALL_CHECKS = [
    # Básicos estructurales
    check_lang_attribute,
    check_single_h1,
    check_heading_hierarchy,
    check_semantic_landmarks,
    check_semantic_headings,
    check_logo_home_link,
    check_real_lists,
    # Imágenes
    check_image_with_text_has_caption,
    check_decorative_images,
    # Formularios
    check_placeholder_no_label,
    check_required_fields_visible,
    check_error_association,
    check_error_states_not_color_only,
    # Navegación y operabilidad
    check_new_window_warning,
    check_nav_consistency,
    check_focus_order,
    check_focus_visible,
    check_accordion_aria_expanded,
    check_keyboard_trap,
    check_cta_labels,
    # Comprensibilidad
    check_sensory_instructions,
    check_success_messages,
    check_cookie_banner_accessible,
    check_legal_links_in_footer,
    # Responsive y visual
    check_reflow_320,
    check_zoom_200,
    check_content_without_css,
    check_sticky_elements_coverage,
]


def run_dom_checks(page: Page) -> list[dict]:
    """
    Ejecuta todos los checks DOM y devuelve la lista consolidada de issues.
    Los errores de un check individual no abortan los demás.
    """
    issues: list[dict] = []
    for check_fn in ALL_CHECKS:
        try:
            issues.extend(check_fn(page))
        except Exception as exc:
            issues.append(_make(
                check_fn.__name__,
                f"Error interno al ejecutar el check '{check_fn.__name__}': {exc}",
                "", "", "notice"
            ))
    return issues
