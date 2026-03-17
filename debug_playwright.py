import asyncio
from playwright.async_api import async_playwright

async def debug_accessibility():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        attrs = dir(page)
        access_attrs = [a for a in attrs if 'access' in a.lower()]
        print(f"Atributos relacionados con 'access': {access_attrs}")
        if hasattr(page, 'accessibility'):
            print("Page tiene el atributo 'accessibility'")
            try:
                snapshot = await page.accessibility.snapshot()
                print("Snapshot de accesibilidad generado con éxito")
            except Exception as e:
                print(f"Error al tomar snapshot: {e}")
        else:
            print("Page NO tiene el atributo 'accessibility'")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_accessibility())
