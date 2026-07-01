"""
wp_fingerprint.py (service)

Detecta pasivamente el tema y plugins de WordPress de un sitio,
junto con sus versiones, a partir del HTML público, style.css y readme.txt.

Cache en memoria por dominio para no repetir peticiones en la misma sesión.
"""

import re
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse

import requests

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 AccessibilityAuditor/1.0"
)

VERSION_RE      = re.compile(r"[\?&]ver=([0-9][0-9a-zA-Z\.\-_]*)")
STYLE_VER_RE    = re.compile(r"Version:\s*([0-9][0-9a-zA-Z\.\-_]*)", re.IGNORECASE)
STABLE_TAG_RE   = re.compile(r"Stable tag:\s*([0-9][0-9a-zA-Z\.\-_]*)", re.IGNORECASE)
THEME_PATH_RE   = re.compile(r"wp-content/themes/([^/\"'?\s]+)")
PLUGIN_PATH_RE  = re.compile(r"wp-content/plugins/([^/\"'?\s]+)")

# In-memory cache: domain → fingerprint result
_cache: dict[str, dict] = {}


class WPFingerprinter:
    def __init__(self, base_url: str, timeout: float = 8, workers: int = 10):
        if not base_url.startswith(("http://", "https://")):
            base_url = "https://" + base_url
        self.base_url = base_url.rstrip("/")
        self.timeout  = timeout
        self.workers  = workers
        self.session  = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def _get(self, path: str):
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        try:
            r = self.session.get(url, timeout=self.timeout, verify=False,
                                 allow_redirects=True)
            return url, r
        except requests.RequestException:
            return url, None

    def _homepage_html(self) -> str | None:
        _, r = self._get("/")
        if r is None or r.status_code >= 400:
            return None
        return r.text

    def _extract_assets(self, html: str):
        themes   = set(THEME_PATH_RE.findall(html))
        plugins  = set(PLUGIN_PATH_RE.findall(html))
        hints: dict[tuple, str] = {}
        for line in re.findall(r'(?:href|src)=["\']([^"\']+)["\']', html):
            ver = (VERSION_RE.search(line) or None)
            if ver:
                ver = ver.group(1)
            else:
                continue
            tm = THEME_PATH_RE.search(line)
            pm = PLUGIN_PATH_RE.search(line)
            if tm:
                hints[("theme",  tm.group(1))] = ver
            if pm:
                hints[("plugin", pm.group(1))] = ver
        return themes, plugins, hints

    def _theme_version(self, slug: str, hint: str | None = None):
        _, r = self._get(f"/wp-content/themes/{slug}/style.css")
        if r and r.status_code == 200:
            m = STYLE_VER_RE.search(r.text[:3000])
            if m:
                return m.group(1)
        return hint

    def _plugin_version(self, slug: str, hint: str | None = None):
        for fname in ("readme.txt", "README.txt", "readme.md"):
            _, r = self._get(f"/wp-content/plugins/{slug}/{fname}")
            if r and r.status_code == 200:
                m = STABLE_TAG_RE.search(r.text[:5000])
                if m:
                    return m.group(1)
        return hint

    def run(self) -> dict:
        result: dict = {
            "url": self.base_url,
            "is_wordpress": False,
            "theme": None,
            "plugins": [],
            "errors": [],
        }
        html = self._homepage_html()
        if html is None:
            result["errors"].append("No se pudo descargar la página principal.")
            return result

        result["is_wordpress"] = "wp-content" in html

        themes, plugins, hints = self._extract_assets(html)

        theme_list = []
        for slug in themes:
            ver = self._theme_version(slug, hints.get(("theme", slug)))
            theme_list.append({"slug": slug, "version": ver or "desconocida"})
        result["theme"] = theme_list[0] if len(theme_list) == 1 else theme_list

        plugin_list = []
        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            futs = {
                ex.submit(self._plugin_version, slug, hints.get(("plugin", slug))): slug
                for slug in plugins
            }
            for fut in as_completed(futs):
                slug = futs[fut]
                try:
                    ver = fut.result()
                except Exception:
                    ver = None
                plugin_list.append({"slug": slug, "version": ver or "desconocida"})

        result["plugins"] = sorted(plugin_list, key=lambda p: p["slug"].lower())
        return result


def get_wp_fingerprint(site_url: str) -> dict:
    """Run fingerprint with in-memory cache (keyed by domain)."""
    domain = urlparse(site_url).netloc or site_url
    if domain in _cache:
        return _cache[domain]
    try:
        fp = WPFingerprinter(site_url)
        data = fp.run()
    except Exception as e:
        data = {"url": site_url, "is_wordpress": False, "theme": None,
                "plugins": [], "errors": [str(e)]}
    _cache[domain] = data
    return data


def summarize_for_prompt(fp_data: dict) -> tuple[str, str]:
    """Return (theme_str, plugins_str) suitable for the LLM prompt."""
    theme = fp_data.get("theme")
    if not theme:
        theme_str = "No detectado"
    elif isinstance(theme, list):
        theme_str = "\n".join(f"- {t['slug']} (v{t['version']})" for t in theme)
    else:
        theme_str = f"- {theme['slug']} (v{theme['version']})"

    plugins = fp_data.get("plugins", [])
    if not plugins:
        plugins_str = "Ninguno detectado en el HTML público"
    else:
        plugins_str = "\n".join(f"- {p['slug']} (v{p['version']})" for p in plugins)

    return theme_str, plugins_str
