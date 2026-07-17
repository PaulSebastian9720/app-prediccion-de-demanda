"""Resumen ejecutivo del reporte, generado por un LLM (OpenAI, modelo mini economico).

Si no hay `OPENAI_API_KEY` configurada o la llamada falla por cualquier motivo,
cae a un resumen generado por plantilla con los mismos datos agregados: la
generacion del reporte nunca se bloquea por falta de LLM.
"""

import logging

from openai import AsyncOpenAI

from app.core.config import Settings
from app.reports.metrics import PRIORIDAD_ALTA, CategoryReportRow

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "Eres un analista de inventario y demanda para una tienda de productos para mascotas. "
    "Recibes una tabla de categorias con su demanda proyectada, stock actual, dias de "
    "inventario restante, prioridad de reabastecimiento y costos asociados. Escribe un "
    "resumen ejecutivo en espanol, claro y accionable, de 3 a 4 parrafos cortos, para un "
    "gerente que no tiene tiempo de leer la tabla completa. Menciona explicitamente las "
    "categorias en riesgo de quiebre de stock (prioridad Alta), el costo de oportunidad "
    "total en juego, y una recomendacion concreta de que reponer primero. No inventes "
    "numeros que no esten en los datos que te paso. Responde en texto plano, sin markdown."
)


def _build_user_prompt(rows: list[CategoryReportRow], horizonte_label: str, currency: str) -> str:
    lineas = [
        f"Periodo del reporte: {horizonte_label}.",
        "Datos por categoria (nombre: demanda proyectada, stock actual, dias de inventario "
        "restante, prioridad, costo de oportunidad por quiebre, costo aproximado de reposicion):",
    ]
    for row in rows:
        dias_restantes = (
            f"{row.dias_inventario_restante:.1f} dias"
            if row.dias_inventario_restante is not None
            else "sin demanda proyectada"
        )
        lineas.append(
            f"- {row.nombre_display}: demanda={row.demanda_proyectada}u, "
            f"stock={row.stock_actual:.0f}u, inventario_restante={dias_restantes}, "
            f"prioridad={row.prioridad}, "
            f"costo_oportunidad={currency}{row.costo_oportunidad_quiebre:,.2f}, "
            f"costo_reposicion={currency}{row.costo_reposicion_total:,.2f}"
        )
    return "\n".join(lineas)


def _fallback_summary(rows: list[CategoryReportRow], horizonte_label: str, currency: str) -> str:
    """Resumen sin LLM: agregados simples sobre los mismos datos, siempre disponible."""
    alta = [r for r in rows if r.prioridad == PRIORIDAD_ALTA]
    costo_total_oportunidad = sum(r.costo_oportunidad_quiebre for r in rows)
    costo_total_reposicion = sum(r.costo_reposicion_total for r in rows)

    if not alta:
        riesgo = "Ninguna categoria muestra riesgo alto de quiebre de stock en este periodo."
    else:
        nombres = ", ".join(r.nombre_display for r in alta)
        riesgo = f"Las categorias con prioridad alta de reabastecimiento son: {nombres}."

    return (
        f"Resumen para el periodo {horizonte_label}. {riesgo} "
        f"El costo de oportunidad total estimado por posibles quiebres de stock es de "
        f"{currency}{costo_total_oportunidad:,.2f}, y el costo aproximado de reposicion total "
        f"recomendado para este periodo es de {currency}{costo_total_reposicion:,.2f}. "
        f"Se recomienda priorizar la reposicion de las categorias marcadas como prioridad alta "
        f"antes de que se agote su inventario."
    )


async def generate_executive_summary(
    settings: Settings, rows: list[CategoryReportRow], horizonte_label: str
) -> str:
    """Genera el resumen con `settings.openai_model` (default `gpt-4o-mini`); si no hay
    API key configurada o la llamada falla, usa `_fallback_summary`."""
    currency = settings.report_currency_symbol

    if settings.openai_api_key is None:
        logger.info("OPENAI_API_KEY no configurada; usando resumen por plantilla.")
        return _fallback_summary(rows, horizonte_label, currency)

    try:
        # `async with` cierra el cliente (y su pool de conexiones httpx) al
        # salir -- sin esto, cada llamada deja una conexion sin cerrar que,
        # acumulada en un proceso de larga duracion, termina provocando
        # errores de conexion (`httpcore.ConnectError`) en llamadas futuras.
        async with AsyncOpenAI(api_key=settings.openai_api_key.get_secret_value()) as client:
            response = await client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": _build_user_prompt(rows, horizonte_label, currency),
                    },
                ],
                temperature=0.4,
                max_tokens=500,
            )
        content = response.choices[0].message.content
        if not content or not content.strip():
            raise ValueError("Respuesta vacia del LLM.")
        return content.strip()
    except Exception:
        logger.warning(
            "Fallo la generacion del resumen con OpenAI, usando fallback.", exc_info=True
        )
        return _fallback_summary(rows, horizonte_label, currency)
