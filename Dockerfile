# Usar la imagen oficial de Playwright con Python
FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

# Directorio de trabajo
WORKDIR /app

# Copiar archivos de requisitos primero para aprovechar la caché de Docker
COPY requirements.txt .

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Instalar los navegadores de Playwright (Chromium es el que usamos)
RUN playwright install chromium

# Copiar el resto del código
COPY . .

# Exponer el puerto que usará Railway (por defecto 8080 o el que definas)
EXPOSE 8080

# Variables de entorno para producción (Railway sobreescribirá estas)
ENV PORT=8080
ENV PYTHONUNBUFFERED=1

# Comando para arrancar la aplicación usando uvicorn directamente
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
