"""Graficas de tendencia de demanda/stock para el reporte (matplotlib -> PNG base64).

Se generan en memoria (sin escribir a disco) a dpi alto y se incrustan en el
HTML como `data:image/png;base64,...` antes de convertir a PDF, para no perder
resolucion. Los titulos de cada grafica se ponen en el HTML (no aqui via
`ax.set_title`), para que compartan tipografia/color con el resto del
documento; estas funciones solo dibujan el area de datos. Paleta de colores
acotada y consistente con la del PDF (ver `templates/report.html.jinja`):
verde/ambar/rojo para prioridad (tambien usados para colorear la linea de
tendencia de cada categoria, ver `render_category_trend_chart`).
"""

import base64
import io
from datetime import date

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

from app.reports.metrics import PRIORIDAD_ALTA, PRIORIDAD_BAJA, PRIORIDAD_MEDIA, CategoryReportRow

_COLOR_ALTA = "#dc2626"
_COLOR_MEDIA = "#d97706"
_COLOR_BAJA = "#16a34a"
_COLOR_STOCK = "#312e81"
_COLOR_DEMANDA = "#6366f1"

_COLOR_POR_PRIORIDAD = {
    PRIORIDAD_ALTA: _COLOR_ALTA,
    PRIORIDAD_MEDIA: _COLOR_MEDIA,
    PRIORIDAD_BAJA: _COLOR_BAJA,
}


def _figure_to_data_uri(fig: "plt.Figure") -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    encoded = base64.b64encode(buf.read()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _style_axes(ax: "plt.Axes") -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cbd5e1")
    ax.spines["bottom"].set_color("#cbd5e1")
    ax.tick_params(colors="#475569", labelsize=8)
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True, nbins=6))
    ax.grid(axis="y", color="#e2e8f0", linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)


def render_demand_chart(rows: list[CategoryReportRow]) -> str:
    """Barras de demanda proyectada por categoria, coloreadas por prioridad."""
    ordenadas = sorted(rows, key=lambda r: r.demanda_proyectada, reverse=True)
    nombres = [r.nombre_display for r in ordenadas]
    demandas = [r.demanda_proyectada for r in ordenadas]
    colores = [_COLOR_POR_PRIORIDAD.get(r.prioridad, _COLOR_DEMANDA) for r in ordenadas]

    fig, ax = plt.subplots(figsize=(9, 4), dpi=150)
    barras = ax.bar(nombres, demandas, color=colores, width=0.6, zorder=3)
    ax.set_ylabel("Unidades proyectadas", fontsize=9, color="#334155")
    _style_axes(ax)
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right", fontsize=8.5)
    for barra, valor in zip(barras, demandas, strict=True):
        ax.annotate(
            str(valor),
            (barra.get_x() + barra.get_width() / 2, barra.get_height()),
            ha="center",
            va="bottom",
            fontsize=8,
            color="#1e293b",
        )
    fig.tight_layout()
    return _figure_to_data_uri(fig)


def render_stock_vs_demand_chart(rows: list[CategoryReportRow]) -> str:
    """Barras agrupadas: stock actual vs. demanda proyectada por categoria."""
    ordenadas = sorted(rows, key=lambda r: r.clasificador)
    nombres = [r.nombre_display for r in ordenadas]
    stock = [r.stock_actual for r in ordenadas]
    demanda = [r.demanda_proyectada for r in ordenadas]

    posiciones = range(len(nombres))
    ancho = 0.36

    fig, ax = plt.subplots(figsize=(9, 4), dpi=150)
    ax.bar(
        [p - ancho / 2 for p in posiciones],
        stock,
        ancho,
        label="Stock actual",
        color=_COLOR_STOCK,
        zorder=3,
    )
    ax.bar(
        [p + ancho / 2 for p in posiciones],
        demanda,
        ancho,
        label="Demanda proyectada",
        color=_COLOR_DEMANDA,
        zorder=3,
    )
    ax.set_xticks(list(posiciones))
    ax.set_xticklabels(nombres, rotation=30, ha="right", fontsize=8.5)
    ax.set_ylabel("Unidades", fontsize=9, color="#334155")
    _style_axes(ax)
    ax.legend(frameon=False, fontsize=8.5, loc="upper right")
    fig.tight_layout()
    return _figure_to_data_uri(fig)


def render_category_trend_chart(row: CategoryReportRow) -> str:
    """Linea de tendencia de la demanda diaria predicha para UNA sola categoria.

    Se analiza cada categoria por separado (una figura por categoria, llamada
    una vez por fila desde `pdf_generator`) en vez de superponer todas las
    series en una sola grafica: con 9 categorias el resultado combinado queda
    ilegible. El color de la linea es el mismo semantico de prioridad que el
    resto del reporte, para que un vistazo rapido ya diga si esa categoria
    esta en riesgo. Cada punto queda etiquetado con su cantidad exacta.
    """
    fechas: list[date] = [f for f, _ in row.predicciones_diarias]
    valores = [cantidad for _, cantidad in row.predicciones_diarias]
    color = _COLOR_POR_PRIORIDAD.get(row.prioridad, _COLOR_DEMANDA)

    fig, ax = plt.subplots(figsize=(8.2, 3.0), dpi=150)
    ax.plot(
        range(len(valores)),
        valores,
        marker="o",
        markersize=3.5,
        linewidth=1.8,
        color=color,
        zorder=3,
    )
    # Con periodos largos (30 dias) etiquetar cada punto satura la grafica;
    # solo se anotan valores exactos para periodos cortos (semanal).
    if len(valores) <= 10:
        for x, valor in enumerate(valores):
            ax.annotate(
                str(valor),
                (x, valor),
                ha="center",
                va="bottom",
                fontsize=6.5,
                color="#334155",
                xytext=(0, 4),
                textcoords="offset points",
            )

    if fechas:
        paso = max(1, len(fechas) // 7)
        posiciones = list(range(0, len(fechas), paso))
        ax.set_xticks(posiciones)
        ax.set_xticklabels([f"{fechas[p]:%d/%m}" for p in posiciones], fontsize=7.5, rotation=0)

    ax.set_ylabel("Unidades / dia", fontsize=8, color="#334155")
    ax.margins(y=0.25)
    _style_axes(ax)
    fig.tight_layout()
    return _figure_to_data_uri(fig)
