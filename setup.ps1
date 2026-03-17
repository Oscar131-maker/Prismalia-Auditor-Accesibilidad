# Setup WCAG Auditor Environment
Write-Host "Instalando dependencias de Python..." -ForegroundColor Cyan
pip install -r requirements.txt

Write-Host "Instalando navegadores de Playwright..." -ForegroundColor Cyan
playwright install chromium

Write-Host "Setup completado con éxito." -ForegroundColor Green
