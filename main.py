from wcag_auditor import WCAGAuditor
import asyncio

async def main():
    # --- CONFIGURACIÓN DEL USUARIO ---
    PAGINA_PRINCIPAL = "https://prismalia.com/"  # <--- Coloca aquí la URL a auditar
    CRAWL_DEEP = True                           # True para obtener todas las URLs del sitio
    MAX_PAGINAS = 10                            # Límite de páginas para evitar auditorías infinitas
    
    # Iniciar Auditor
    auditor = WCAGAuditor(
        start_url=PAGINA_PRINCIPAL, 
        crawl_deep=CRAWL_DEEP, 
        max_pages=MAX_PAGINAS
    )
    
    # 1. Fase de Crawling (Obtener URLs y generar .xlsx)
    urls = await auditor.crawl()
    
    # 2. Fase de Auditoría (Generar informes .json por cada página)
    await auditor.run_audit(urls)
    
    print("\n" + "="*50)
    print(f"PROCESO FINALIZADO")
    print(f"Directorio de reportes: {auditor.results_dir}")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())
