from backend.services.audit_pipeline import AuditPipeline
import asyncio

async def main():
    # --- CONFIGURACIÓN DEL USUARIO ---
    PAGINA_PRINCIPAL = "https://prismalia.com/"  # <--- Coloca aquí la URL a auditar
    MAX_PAGINAS = 10                            # Límite de páginas para evitar auditorías infinitas

    pipeline = AuditPipeline(target_url=PAGINA_PRINCIPAL, max_pages=MAX_PAGINAS)
    results = await pipeline.run()

    print("\n" + "="*50)
    print(f"PROCESO FINALIZADO")
    print(f"Páginas auditadas: {len(results)}")
    print(f"Directorio de reportes: {pipeline.results_dir}")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())
