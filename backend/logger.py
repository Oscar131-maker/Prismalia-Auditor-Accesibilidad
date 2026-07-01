"""
logger.py  —  Sistema de logging estructurado para el auditor de accesibilidad.

Usa structlog para producir entradas JSON con campos ricos:
  timestamp, level, analysis_id, phase, url, message, duration_ms, extra...

Almacenamiento:
  - Buffer en memoria (collections.deque) indexado por analysis_id para consultas rápidas.
  - Buffer global circular (últimas 2000 entradas) para la vista general.
  - Archivo JSON-lines en audits/run_<analysis_id>/audit.log para persistencia.
  - Salida a consola con formato legible por humanos (coloreado).
"""

from __future__ import annotations

import collections
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import structlog

# ── Configuración base ────────────────────────────────────────────────────────

AUDITS_DIR = Path(__file__).parent.parent / "audits"
AUDITS_DIR.mkdir(exist_ok=True)

# Buffer global: últimas 2000 entradas de cualquier auditoría
_global_buffer: collections.deque[dict] = collections.deque(maxlen=2000)

# Buffer por analysis_id: { analysis_id: deque[dict] }
_per_analysis: dict[int | str, collections.deque[dict]] = {}


# ── Procesadores structlog ────────────────────────────────────────────────────

def _add_timestamp(logger, method, event_dict: dict) -> dict:
    event_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
    return event_dict


def _add_level(logger, method, event_dict: dict) -> dict:
    event_dict["level"] = method.upper()
    return event_dict


class _MemoryAndFileProcessor:
    """Guarda cada entrada en los buffers en memoria y en el archivo de la auditoría."""

    def __call__(self, logger, method, event_dict: dict) -> dict:
        entry = dict(event_dict)

        # Buffer global
        _global_buffer.append(entry)

        # Buffer por analysis_id
        aid = entry.get("analysis_id")
        if aid is not None:
            if aid not in _per_analysis:
                _per_analysis[aid] = collections.deque(maxlen=5000)
            _per_analysis[aid].append(entry)

            # Escribir al archivo de la auditoría
            run_dir = AUDITS_DIR / f"run_{aid}"
            run_dir.mkdir(exist_ok=True)
            log_file = run_dir / "audit.log"
            try:
                with open(log_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except Exception:
                pass

        return event_dict


def _console_renderer(logger, method, event_dict: dict) -> str:
    """Formato legible por humanos para la consola."""
    ts = event_dict.get("timestamp", "")[:19].replace("T", " ")
    level = event_dict.get("level", "INFO").ljust(7)
    aid = event_dict.get("analysis_id", "")
    phase = event_dict.get("phase", "")
    url = event_dict.get("url", "")
    msg = event_dict.get("event", "")
    dur = event_dict.get("duration_ms")

    # Colores ANSI
    COLORS = {
        "DEBUG":   "\033[37m",    # gris
        "INFO":    "\033[36m",    # cyan
        "WARNING": "\033[33m",    # amarillo
        "ERROR":   "\033[31m",    # rojo
        "CRITICAL":"\033[35m",    # magenta
    }
    RESET = "\033[0m"
    color = COLORS.get(level.strip(), "")

    parts = [f"{color}{ts} [{level}]{RESET}"]
    if aid:
        parts.append(f"\033[90m[audit:{aid}]\033[0m")
    if phase:
        parts.append(f"\033[90m[{phase}]\033[0m")
    parts.append(msg)
    if url:
        parts.append(f"\033[90m→ {url[:80]}\033[0m")
    if dur is not None:
        parts.append(f"\033[90m({dur}ms)\033[0m")

    return " ".join(parts)


# ── Configurar structlog ──────────────────────────────────────────────────────

structlog.configure(
    processors=[
        _add_timestamp,
        _add_level,
        structlog.stdlib.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _MemoryAndFileProcessor(),
        _console_renderer,
    ],
    wrapper_class=structlog.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
    cache_logger_on_first_use=True,
)

# Logger raíz del proyecto
_base_logger = structlog.get_logger("accessibility_auditor")


# ── API pública ───────────────────────────────────────────────────────────────

def get_audit_logger(analysis_id: int | str) -> structlog.BoundLogger:
    """Devuelve un logger pre-enlazado con el analysis_id."""
    return _base_logger.bind(analysis_id=analysis_id)


def get_logs(analysis_id: int | str | None = None, level: str | None = None,
             phase: str | None = None, limit: int = 500) -> list[dict]:
    """
    Devuelve entradas de log como lista de dicts.
    - analysis_id: filtrar por auditoría específica (None = global)
    - level: filtrar por nivel (INFO, WARNING, ERROR…)
    - phase: filtrar por fase (sitemap, pa11y, dom-checker…)
    - limit: máximo de entradas a devolver (más recientes primero)
    """
    source = list(_per_analysis.get(analysis_id, [])) if analysis_id is not None else list(_global_buffer)
    if level:
        source = [e for e in source if e.get("level", "").upper() == level.upper()]
    if phase:
        source = [e for e in source if e.get("phase", "").lower() == phase.lower()]
    return source[-limit:][::-1]  # más recientes primero


def get_analysis_ids() -> list[int | str]:
    """Lista de analysis_ids que tienen logs en memoria."""
    return list(_per_analysis.keys())


def load_logs_from_file(analysis_id: int | str) -> list[dict]:
    """Carga logs desde el archivo en disco para una auditoría (útil tras reinicio)."""
    log_file = AUDITS_DIR / f"run_{analysis_id}" / "audit.log"
    if not log_file.exists():
        return []
    entries = []
    try:
        with open(log_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except Exception:
        pass
    return entries


# Compatibilidad con el logger anterior
logger = _base_logger
