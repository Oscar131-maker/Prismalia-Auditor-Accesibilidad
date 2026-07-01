# Playwright base image includes Python 3.12 + Chromium deps
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

WORKDIR /app

# ── Install Node.js 20 (needed for pa11y + Puppeteer) ──
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# ── Python dependencies ──
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Install Playwright Chromium ──
RUN playwright install chromium

# ── Node dependencies (pa11y + puppeteer) ──
COPY package.json .
RUN npm install --production

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
