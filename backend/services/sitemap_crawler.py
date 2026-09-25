"""
sitemap_crawler.py

Módulo de descubrimiento de páginas y crawler para Prismalia Auditor.
Diseñado para funcionar con sitios en Siteground, Cloudflare, WordPress y cualquier servidor web.
Utiliza Playwright Chromium para eludir firewalls y bloqueos anti-bot (403 Forbidden y retos 202/sgcaptcha),
e implementa un crawler de enlaces internos si el sitemap no existe o contiene pocas páginas.
"""

import re
import time
from urllib.parse import urljoin, urlparse
from playwright.sync_api import sync_playwright

IGNORED_EXTENSIONS = {
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico', '.bmp', '.tiff',
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.zip', '.tar', '.gz',
    '.mp3', '.mp4', '.avi', '.mov', '.wmv', '.webm', '.ogg',
    '.css', '.js', '.xml', '.json', '.txt'
}

IGNORED_SUBSTRINGS = [
    '/wp-admin', '/wp-login', '/feed', '/trackback', '/comments/feed',
    'add-to-cart=', 'action=logout', '/logout', 'xmlrpc.php'
]


def clean_url(u: str) -> str:
    """Normaliza una URL eliminando fragmentos y normalizando slash final."""
    p = urlparse(u)
    path = p.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    return f"{p.scheme}://{p.netloc}{path}"


def is_same_domain(url: str, base_domain: str) -> bool:
    """Verifica si una URL pertenece al mismo dominio o subdominio www."""
    netloc = urlparse(url).netloc.lower()
    base = base_domain.lower()
    return netloc == base or netloc == f"www.{base}" or f"www.{netloc}" == base


def is_valid_html_url(url: str, base_domain: str) -> bool:
    """Filtra recursos estáticos, endpoints de WordPress admin o dominios externos."""
    if not url or not url.startswith(("http://", "https://")):
        return False
    if not is_same_domain(url, base_domain):
        return False
    path_lower = urlparse(url).path.lower()
    if any(path_lower.endswith(ext) for ext in IGNORED_EXTENSIONS):
        return False
    if any(sub in url.lower() for sub in IGNORED_SUBSTRINGS):
        return False
    return True


def get_page_links_safely(page, max_retries: int = 5) -> list[str]:
    """Extrae enlaces del DOM esperando si hay redirección o challenge anti-bot."""
    for _ in range(max_retries):
        try:
            page.wait_for_timeout(1000)
            title = page.title()
            if "challenge" in title.lower() or "captcha" in page.url:
                page.wait_for_timeout(1500)
                continue
            links = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
            if links:
                return links
        except Exception:
            page.wait_for_timeout(1000)
    return []


def fetch_sitemap_urls(base_url: str, limit: int = 10, log=None) -> list[str]:
    """
    Descubre URLs para auditar:
    1. Carga la página de inicio en Chromium para extraer enlaces y superar retos anti-bot.
    2. Si se necesitan más páginas, busca en sitemaps (/sitemaps.xml, /sitemap_index.xml, /wp-sitemap.xml, /robots.txt).
    3. Si aún faltan URLs, ejecuta un crawler interno (BFS) por las páginas encontradas.
    """
    if not base_url.startswith(("http://", "https://")):
        base_url = "https://" + base_url

    parsed = urlparse(base_url)
    base_domain = parsed.netloc
    base_origin = f"{parsed.scheme}://{parsed.netloc}"
    normalized_base = clean_url(base_url)

    collected: list[str] = [normalized_base]
    seen: set[str] = {normalized_base}

    def add_candidate(u: str) -> bool:
        c = clean_url(u)
        if c not in seen and is_valid_html_url(c, base_domain):
            seen.add(c)
            collected.append(c)
            return True
        return False

    if log:
        log.info("iniciando descubrimiento de páginas (sitemaps y crawler)", phase="sitemap", url=base_url)

    browser_args = [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-blink-features=AutomationControlled",
    ]

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=browser_args)
            page = browser.new_page()

            # ── 1. Extraer enlaces de la página de inicio ─────────────────────────
            try:
                page.goto(base_url, wait_until="domcontentloaded", timeout=25000)
                home_links = get_page_links_safely(page, max_retries=5)
                for link in home_links:
                    if link.startswith(("javascript:", "mailto:", "tel:", "#")):
                        continue
                    full = urljoin(base_url, link)
                    add_candidate(full)
                    if len(collected) >= limit:
                        break
                if log and len(collected) > 1:
                    log.info(f"página de inicio analizada: {len(collected)} URLs recopiladas", phase="sitemap")
            except Exception as e:
                if log:
                    log.warning(f"advertencia al cargar página de inicio: {e}", phase="sitemap")

            # ── 2. Consultar sitemaps si aún faltan URLs ───────────────────────────
            if len(collected) < limit:
                # Comprobar robots.txt primero
                sitemap_candidates = []
                try:
                    page.goto(f"{base_origin}/robots.txt", wait_until="domcontentloaded", timeout=12000)
                    page.wait_for_timeout(500)
                    r_text = page.content()
                    r_matches = re.findall(r"Sitemap:\s*(https?://[^\s<]+)", r_text, re.IGNORECASE)
                    for rm in r_matches:
                        sitemap_candidates.append(rm.strip())
                except Exception:
                    pass

                common = [
                    f"{base_origin}/sitemaps.xml",
                    f"{base_origin}/sitemap_index.xml",
                    f"{base_origin}/sitemap.xml",
                    f"{base_origin}/wp-sitemap.xml",
                ]
                for c in common:
                    if c not in sitemap_candidates:
                        sitemap_candidates.append(c)

                for sm_url in sitemap_candidates:
                    if len(collected) >= limit:
                        break
                    try:
                        page.goto(sm_url, wait_until="domcontentloaded", timeout=15000)
                        page.wait_for_timeout(1000)
                        if "challenge" in page.title().lower() or "captcha" in page.url:
                            continue
                        content = page.content()
                        locs = re.findall(r"<loc>\s*(https?://[^\s<]+)\s*</loc>", content, re.IGNORECASE)
                        dom = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
                        entries = list(dict.fromkeys(locs + dom))

                        child_sitemaps = []
                        for l in entries:
                            p_l = urlparse(l)
                            if p_l.path.lower().endswith(".xml") or "sitemap" in p_l.path.lower():
                                if l not in sitemap_candidates and l not in child_sitemaps:
                                    child_sitemaps.append(l)
                            else:
                                add_candidate(l)
                                if len(collected) >= limit:
                                    break

                        # Si el sitemap era un índice (como sitemap_index.xml o wp-sitemap.xml), explorar sitemaps hijos
                        for child_sm in child_sitemaps[:6]:
                            if len(collected) >= limit:
                                break
                            try:
                                page.goto(child_sm, wait_until="domcontentloaded", timeout=12000)
                                page.wait_for_timeout(800)
                                child_content = page.content()
                                child_locs = re.findall(r"<loc>\s*(https?://[^\s<]+)\s*</loc>", child_content, re.IGNORECASE)
                                child_dom = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
                                for cl in list(dict.fromkeys(child_locs + child_dom)):
                                    if not urlparse(cl).path.lower().endswith(".xml"):
                                        add_candidate(cl)
                                        if len(collected) >= limit:
                                            break
                            except Exception:
                                continue
                    except Exception:
                        continue

            # ── 3. Crawler BFS si aún no alcanzamos el límite ──────────────────────
            if len(collected) < limit:
                needed = limit - len(collected)
                if log:
                    log.info(f"ejecutando crawler interno para alcanzar {limit} páginas (faltan {needed})", phase="sitemap")

                crawl_queue = list(collected)
                visited = set()
                while crawl_queue and len(collected) < limit:
                    curr = crawl_queue.pop(0)
                    norm_curr = clean_url(curr)
                    if norm_curr in visited:
                        continue
                    visited.add(norm_curr)
                    try:
                        page.goto(curr, wait_until="domcontentloaded", timeout=15000)
                        links = get_page_links_safely(page, max_retries=3)
                        for l in links:
                            if l.startswith(("javascript:", "mailto:", "tel:", "#")):
                                continue
                            full = urljoin(curr, l)
                            if add_candidate(full):
                                crawl_queue.append(clean_url(full))
                            if len(collected) >= limit:
                                break
                    except Exception:
                        continue

            browser.close()

    except Exception as exc:
        if log:
            log.error(f"error en motor de sitemap/crawler: {exc}", phase="sitemap", exc=str(exc))

    if not collected:
        collected = [normalized_base]

    return collected[:limit]
