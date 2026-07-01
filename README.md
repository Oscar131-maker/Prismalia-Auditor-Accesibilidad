# Prismalia Auditor — Accesibilidad Web

Aplicación profesional para auditoría de accesibilidad web basada en WCAG 2.2 AA.

**Stack:** FastAPI · PostgreSQL · Playwright · Pa11y · Puppeteer · Google Gemini AI

## Características

- Auditoría automática con Pa11y (WCAG 2.2 AA)
- Verificaciones DOM avanzadas con Playwright (50+ checks propios)
- Detección de WordPress (tema, plugins, versiones)
- Consejos de corrección con IA (Google Gemini)
- Interfaz SPA moderna con panel de criterios WCAG
- Marcar issues como superados con actualización de contadores
- Logs en tiempo real del pipeline de auditoría
- Análisis de sitemap completo o limitado por número de páginas

---

## Despliegue en Railway

### 1. Subir a GitHub

```bash
cd accessibility_auditor
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/TU_USUARIO/prismalia-auditor.git
git push -u origin main
```

### 2. Crear proyecto en Railway

1. Ve a [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
2. Selecciona tu repositorio `prismalia-auditor`
3. Railway detectará el `Dockerfile` y `railway.json` automáticamente

### 3. Añadir PostgreSQL

1. En tu proyecto Railway → **+ New** → **Database** → **PostgreSQL**
2. Railway inyecta automáticamente `DATABASE_URL` en tu servicio

### 4. Variables de entorno

En la pestaña **Variables** del servicio de la app, añade:

| Variable | Valor | Requerida |
|----------|-------|-----------|
| `DATABASE_URL` | (auto-inyectada por Railway PostgreSQL) | ✅ |
| `GEMINI_API_KEY` | Tu API key de Google Gemini | ✅ |
| `AUTH_PASSWORD` | Contraseña de acceso al sistema | ✅ |
| `PORT` | `8080` (Railway lo detecta auto) | Opcional |

### 5. Deploy

Railway hará build automático del Dockerfile. El primer deploy toma ~5 min por la imagen de Playwright + Node.js.

Una vez deployado, accede a la URL pública que Railway asigna.

---

## Instalación Local

```bash
# 1. Clonar
git clone https://github.com/TU_USUARIO/prismalia-auditor.git
cd prismalia-auditor

# 2. Python (3.11+)
pip install -r requirements.txt
playwright install chromium

# 3. Node.js (para pa11y)
npm install

# 4. PostgreSQL local
# Asegúrate de tener PostgreSQL corriendo

# 5. Configurar entorno
cp .env.example .env
# Edita .env con tus credenciales

# 6. Ejecutar
python run.py
```

La app estará disponible en `http://localhost:8000`

---

## Estructura del proyecto

```
├── backend/
│   ├── main.py            # FastAPI app + endpoints
│   ├── models.py          # SQLAlchemy models
│   ├── database.py        # DB connection
│   ├── criteria.py        # WCAG criteria mapping
│   ├── logger.py          # Structured logging
│   ├── services/
│   │   ├── dom_checker.py # 50+ Playwright DOM checks
│   │   ├── fix_advisor.py # Gemini LLM integration
│   │   └── wp_fingerprint.py # WordPress detection
│   └── prompts/
│       └── como_solucionar.txt  # LLM prompt template
├── frontend/
│   ├── index.html         # Main SPA
│   ├── login.html         # Auth page
│   ├── logs.html          # Pipeline logs viewer
│   ├── script.js          # Frontend logic
│   └── style.css          # Styles
├── pa11y_runner.js        # Pa11y + Puppeteer enrichment
├── start.py               # Production entrypoint (migrations + uvicorn)
├── run.py                 # Dev entrypoint (with reload)
├── ensure_db.py           # DB creation helper
├── Dockerfile             # Production container
├── railway.json           # Railway deployment config
├── requirements.txt       # Python deps
└── package.json           # Node deps (pa11y)
```

---

## Seguridad

- Acceso protegido por contraseña (`AUTH_PASSWORD`)
- Token Bearer en todas las peticiones API
- No se almacenan credenciales en código

---

## Notas para Railway

- La imagen usa ~2.5 GB (Playwright + Chromium + Node). Plan Hobby es suficiente.
- Single worker (`workers=1`) porque Playwright/Puppeteer no son thread-safe.
- Las auditorías de sitios grandes (+50 páginas) pueden tardar varios minutos.
- Si necesitas más RAM, ajusta el plan en Railway settings.
