import pandas as pd
import json
import os

class ReportGenerator:
    def __init__(self, run_id: str, results_dir: str):
        self.run_id = run_id
        self.results_dir = results_dir

    def create_excel_report(self, all_page_results: list):
        """Convierte los resultados de la auditoría en un archivo Excel con múltiples pestañas."""
        
        # 1. Resumen Ejecutivo (Global)
        summary_rows = []
        for page in all_page_results:
            eval_data = page.get('llm_evaluation', {})
            summary_rows.append({
                "URL": page.get('url'),
                "Puntaje (0-100)": eval_data.get('global_score', 'N/A'),
                "Resumen": eval_data.get('accessibility_summary', 'Sin resumen')
            })
        df_summary = pd.DataFrame(summary_rows)

        # 2. Detalle de Errores por Criterio
        error_rows = []
        for page in all_page_results:
            evaluations = page.get('llm_evaluation', {}).get('evaluations', [])
            for eval_item in evaluations:
                error_rows.append({
                    "URL": page.get('url'),
                    "Criterio": eval_item.get('criterion_id'),
                    "Estado": eval_item.get('status'),
                    "Hallazgo": eval_item.get('finding'),
                    "Recomendación": eval_item.get('recommendation'),
                    "Severidad": eval_item.get('severity')
                })
        df_errors = pd.DataFrame(error_rows)

        # 3. Inventario Técnico (Imágenes, Formularios, etc.)
        technical_rows = []
        for page in all_page_results:
            dom_data = page.get('dom_data', {})
            technical_rows.append({
                "URL": page.get('url'),
                "Imágenes Totales": len(dom_data.get('images_and_icons', {}).get('images', [])),
                "Íconos Detectados": len(dom_data.get('images_and_icons', {}).get('icons', [])),
                "H1 Count": dom_data.get('semantics', {}).get('h1_count', 0),
                "Falsos Encabezados": len(dom_data.get('semantics', {}).get('faux_headings', [])),
                "Inputs": len(dom_data.get('forms', []))
            })
        df_tech = pd.DataFrame(technical_rows)

        # Guardar en Excel
        excel_path = f"{self.results_dir}/reporte_accesibilidad_{self.run_id}.xlsx"
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            df_summary.to_excel(writer, sheet_name='Resumen Ejecutivo', index=False)
            df_errors.to_excel(writer, sheet_name='Detalle de Errores', index=False)
            df_tech.to_excel(writer, sheet_name='Inventario Técnico', index=False)
        
        return excel_path
