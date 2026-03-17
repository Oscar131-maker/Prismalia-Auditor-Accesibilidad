# WCAG Auditor Fullstack MVP

Aplicación profesional para auditoría de accesibilidad web basada en las pautas WCAG 2.2 AA. Utiliza FastAPI, PostgreSQL, Playwright y la IA de Google Gemini para generar resúmenes ejecutivos y planes de acción automáticos.

## 🚀 Despliegue en Railway

1. **Crear Proyecto:** En Railway, crea un nuevo proyecto desde tu repositorio de GitHub.
2. **Base de Datos:** Añade un servicio de **PostgreSQL** a tu proyecto. Railway inyectará automáticamente la variable `DATABASE_URL`.
3. **Variables de Entorno:** Configura las siguientes variables en la pestaña "Variables" del servicio de la app:
   - `GEMINI_API_KEY`: Tu clave de API de Google Gemini.
   - `AUTH_PASSWORD`: La contraseña para acceder al sistema (ej. `admin123`).
   - `PORT`: `8080` (Railway lo suele detectar, pero es mejor fijarlo).
4. **Navegadores:** El `Dockerfile` ya incluye la instalación de Chromium y las dependencias necesarias. No necesitas configurar nada adicional para Playwright.

## 🛠️ Instalación Local

Si quieres ejecutarlo en tu máquina:

1. Clonar el repo.
2. Instalar dependencias: `pip install -r requirements.txt`
3. Instalar Playwright: `playwright install chromium`
4. Configurar `.env` basado en `.env.example`.
5. Ejecutar: `python run.py`

## 🔒 Seguridad
La aplicación está protegida por un sistema de acceso básico mediante contraseña definido en la variable `AUTH_PASSWORD`.
