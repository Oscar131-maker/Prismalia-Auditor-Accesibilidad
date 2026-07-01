# Playwright base image includes Python 3.12 + Chromium deps
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

WORKDIR /app

# ── Install Node.js 22 + unzip (needed for pa11y + Puppeteer) ──
RUN apt-get update && apt-get install -y unzip && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# ── Python dependencies ──
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Install Playwright Chromium ──
RUN playwright install chromium

# ── Node dependencies (pa11y + puppeteer) ──
# Skip Puppeteer browser download — we use Playwright's Chromium
ENV PUPPETEER_SKIP_DOWNLOAD=true
COPY package.json .
RUN npm install --omit=dev

# ── Copy application code ──
COPY . .

# ── Create audits/logs dirs ──
RUN mkdir -p audits logs

# ── Port (Railway overrides with $PORT env var) ──
EXPOSE 8080
ENV PORT=8080
ENV PYTHONUNBUFFERED=1
ENV NODE_ENV=production

# ── Start: run migrations then uvicorn ──
CMD ["python", "start.py"]
