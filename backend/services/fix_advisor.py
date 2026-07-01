"""
fix_advisor.py

Construye el prompt de "cómo arreglar" para un error de accesibilidad usando
el contexto de WordPress del sitio (tema + plugins) y llama a Gemini.
"""

import os
import json
import asyncio
from pathlib import Path

from google import genai
from google.genai import types

PROMPT_TEMPLATE = Path(__file__).parent.parent / "prompts" / "como_solucionar.txt"
MODEL = "gemini-3.1-flash-lite"

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))
    return _client


def build_prompt(
    issue_code: str,
    issue_message: str,
    issue_context: str,
    issue_selector: str,
    theme_str: str,
    plugins_str: str,
) -> str:
    template = PROMPT_TEMPLATE.read_text(encoding="utf-8")

    issue_data = (
        f"Código WCAG: {issue_code}\n"
        f"Mensaje: {issue_message}\n"
        f"Selector CSS: {issue_selector}"
    )
    html_fragment = issue_context.strip() if issue_context else "(sin contexto HTML disponible)"

    prompt = (
        template
        .replace("[DATA_DEL ERROR_ENCONTRADO]",        issue_data)
        .replace("[HTML_DEL_ELEMENTO_PROBLEMATICO]",   html_fragment)
        .replace("[INFORMACIÓN_DEL_TEMA_DE_WORDPRESS]",   theme_str)
        .replace("[INFORMACIÓN_DEL_PLUGINS_DE_WORDPRESS]", plugins_str)
    )
    return prompt


def _run_gemini_sync(prompt: str) -> str:
    """Synchronous Gemini call that collects all streaming chunks."""
    client = _get_client()
    contents = [
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=prompt)],
        )
    ]
    config = types.GenerateContentConfig(
        thinking_config=types.ThinkingConfig(thinking_level="MEDIUM"),
    )
    full_text = ""
    for chunk in client.models.generate_content_stream(
        model=MODEL,
        contents=contents,
        config=config,
    ):
        if chunk.text:
            full_text += chunk.text
    return full_text


async def get_fix_advice(
    issue_code: str,
    issue_message: str,
    issue_context: str,
    issue_selector: str,
    theme_str: str,
    plugins_str: str,
    log=None,
) -> str:
    """Async wrapper: runs Gemini in a thread executor, logs the prompt."""
    prompt = build_prompt(
        issue_code, issue_message, issue_context, issue_selector,
        theme_str, plugins_str,
    )

    if log:
        log.info(
            "fix-advice: prompt construido",
            phase="fix-advice",
            issue_code=issue_code,
            prompt_chars=len(prompt),
        )
        # Log the full prompt for review/debugging
        truncated = prompt if len(prompt) <= 3000 else prompt[:3000] + "\n…(truncado)"
        log.info(
            f"fix-advice PROMPT:\n{truncated}",
            phase="fix-advice-prompt",
        )

    loop = asyncio.get_event_loop()
    try:
        advice = await loop.run_in_executor(None, _run_gemini_sync, prompt)
    except Exception as e:
        if log:
            log.error(f"fix-advice Gemini error: {e}", phase="fix-advice")
        advice = f"❌ Error al consultar la IA: {e}"

    if log:
        log.info(
            "fix-advice: respuesta recibida",
            phase="fix-advice",
            response_chars=len(advice),
        )

    return advice
