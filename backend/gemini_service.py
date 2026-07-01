import os
import json
from google import genai
from google.genai import types

class GeminiService:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("WARNING: GEMINI_API_KEY no encontrada en el entorno.")
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-2.0-flash"

    def generate_page_analysis(self, raw_data):
        prompt = f"""
        Actúa como un experto en accesibilidad web (WCAG 2.2 AA). 
        Analiza los siguientes datos crudos obtenidos de una auditoría automática de Playwright para la URL: {raw_data.get('url')}

        DATOS AUDITORÍA:
        {json.dumps(raw_data, indent=2, ensure_ascii=False)}

        Tu tarea es generar dos secciones de contenido:
        1. RESUMEN: Divide los hallazgos en Críticos, Advertencias y Buenos. Sé conciso pero específico.
        2. PLAN DE ACCIÓN: Proporciona pasos claros para corregir los problemas Críticos y las Advertencias mencionadas.

        Formato de respuesta estrictamente en JSON con estas dos llaves:
        {{
          "summary": "...", 
          "action_plan": "..."
        }}
        Usa Markdown dentro de los strings para formatear listas o negritas si es necesario.
        """
        
        config = types.GenerateContentConfig(
            temperature=0.3,
            response_mime_type="application/json"
        )
        
        # This is a synchronous call in the google-genai SDK
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config
        )
        
        usage = response.usage_metadata
        try:
            data = json.loads(response.text)
            return {
                "data": data,
                "usage": {
                    "prompt_tokens": usage.prompt_token_count,
                    "candidates_tokens": usage.candidates_token_count,
                    "total_tokens": usage.total_token_count
                }
            }
        except:
            return {
                "data": {
                    "summary": "Error procesando resumen.",
                    "action_plan": "Error procesando plan de acción."
                },
                "usage": {
                    "prompt_tokens": usage.prompt_token_count,
                    "candidates_tokens": usage.candidates_token_count,
                    "total_tokens": usage.total_token_count
                }
            }

    def generate_global_summary(self, all_page_summaries):
        prompt = f"""
        Actúa como un consultor senior de accesibilidad. 
        A continuación tienes los resúmenes de accesibilidad de varias páginas de un mismo sitio web.
        Proporciona un resumen ejecutivo global de la salud de accesibilidad del sitio completo.
        Identifica patrones comunes de errores y da una visión general del impacto para el usuario.

        REPORTE DE PÁGINAS:
        {json.dumps(all_page_summaries, indent=2, ensure_ascii=False)}

        Responde en Markdown claro y profesional.
        """
        
        config = types.GenerateContentConfig(
            temperature=0.3
        )
        
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=config
        )
        
        usage = response.usage_metadata
        return {
            "text": response.text,
            "usage": {
                "prompt_tokens": usage.prompt_token_count,
                "candidates_tokens": usage.candidates_token_count,
                "total_tokens": usage.total_token_count
            }
        }
