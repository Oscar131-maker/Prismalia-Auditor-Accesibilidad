import os
import json
import base64
import asyncio
from google import genai
from google.genai import types

class LLMEvaluator:
    def __init__(self):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY no encontrada.")
        self.client = genai.Client(api_key=api_key)
        self.model = "gemini-1.5-flash-latest" # O gemini-2.0-flash-exp si está disponible

    async def evaluate_page(self, extraction_data: dict, screenshot_path: str, screenshot_no_css_path: str = None):
        """Analiza una página combinando datos del DOM, capturas visuales y AOM."""
        
        # Leer capturas en base64
        with open(screenshot_path, "rb") as f:
            screenshot_b64 = base64.b64encode(f.read()).decode('utf-8')
        
        screenshot_no_css_b64 = None
        if screenshot_no_css_path and os.path.exists(screenshot_no_css_path):
            with open(screenshot_no_css_path, "rb") as f:
                screenshot_no_css_b64 = base64.b64encode(f.read()).decode('utf-8')

        prompt = self._build_prompt(extraction_data)
        
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=prompt),
                    types.Part.from_bytes(data=base64.b64decode(screenshot_b64), mime_type="image/png")
                ]
            )
        ]

        if screenshot_no_css_b64:
            contents[0].parts.append(
                types.Part.from_bytes(data=base64.b64decode(screenshot_no_css_b64), mime_type="image/png")
            )

        config = types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json"
        )

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config
            )
        )

        try:
            return json.loads(response.text)
        except Exception as e:
            return {
                "error": f"Error parseando respuesta de Gemini: {str(e)}",
                "raw_response": response.text
            }

    def _build_prompt(self, data: dict):
        return f"""
        Actúa como un Auditor Senior de Accesibilidad Web (WCAG 2.2 AA).
        Analiza la captura de pantalla adjunta (y la versión sin CSS si se provee) junto con los datos técnicos del DOM.
        
        URL de la página: {data.get('url')}

        DATOS TÉCNICOS EXTRAÍDOS (FRAGMENTOS):
        {json.dumps(data, indent=2, ensure_ascii=False)}

        CRITERIOS A EVALUAR (FASE HEURÍSTICA):
        1. Criterio 2 (Imágenes Decorativas): Revisa imágenes con alt="" o sin alt en la captura. ¿Son realmente decorativas o transmiten información ignorada?
        2. Criterio 5 (Texto en Imágenes): ¿Ves texto incrustado en imágenes en la captura? ¿Existe el mismo texto en el HTML adyacente?
        3. Criterio 6 (Gráficos/Infografías): ¿Hay gráficos complejos? ¿Tienen descripción textual cercana?
        4. Criterio 11 (Sin CSS): Compara la captura normal vs la captura sin CSS (si existe). ¿Se mantiene el orden lógico y la comprensión?
        5. Criterio 12 (Orientación): ¿La estructura parece que se rompería en móvil (vertical) o tablet (horizontal)?
        6. Criterio 13 & 14 (Dependencia del Color): Mira los botones y mensajes de error. ¿La información depende SOLO del color o hay iconos/texto de apoyo?
        7. Criterio 18 (Cierre de contenido): ¿Los menús o tooltips visibles parecen fáciles de cerrar sin ratón (ej. tecla Escape)?

        RESPUESTA REQUERIDA (JSON):
        {{
            "evaluations": [
                {{
                    "criterion_id": "C2",
                    "status": "PASS | FAIL | WARNING",
                    "finding": "Descripción del hallazgo visual...",
                    "recommendation": "Cómo corregirlo...",
                    "severity": "CRITICAL | MEDIUM | LOW"
                }},
                ... (para cada criterio)
            ],
            "global_score": 0-100,
            "accessibility_summary": "Resumen ejecutivo de la página."
        }}
        """
