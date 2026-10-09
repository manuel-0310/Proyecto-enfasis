"""Paleta, formato de números y estilo de Plotly compartidos por todas las pestañas."""

import math

import plotly.graph_objects as go
import plotly.io as pio

# Paleta semántica de la clase 3: el rojo solo marca riesgo y el ámbar, atención
COLORES = {
    "dato": "#1F4E79",
    "bien": "#2A9D8F",
    "atencion": "#F4A261",
    "alerta": "#D1495B",
    "contexto": "#C9CED6",
    "texto": "#1F2933",
    "texto_sec": "#6B7280",
    "rejilla": "#E5E7EB",
    "fondo": "#FAFAF7",
    "tarjeta": "#FFFFFF",
}

FUENTE = "Source Sans Pro, Arial, sans-serif"


def _es_vacio(valor) -> bool:
    return valor is None or (isinstance(valor, float) and math.isnan(valor))


def _miles(numero: float, decimales: int = 0) -> str:
    """Formato colombiano: punto de miles y coma decimal."""
    texto = f"{numero:,.{decimales}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def fmt_millones(valor: float | None, decimales: int = 0) -> str:
    if _es_vacio(valor):
        return "–"
    return f"{_miles(valor / 1e6, decimales)} M"


def fmt_cop(valor: float | None) -> str:
    if _es_vacio(valor):
        return "–"
    return f"$ {_miles(valor)}"


def fmt_pct(valor: float | None, decimales: int = 1) -> str:
    if _es_vacio(valor):
        return "–"
    return f"{_miles(valor * 100, decimales)} %"


def fmt_pp(valor: float | None, decimales: int = 1) -> str:
    """Diferencia entre dos porcentajes, en puntos porcentuales."""
    if _es_vacio(valor):
        return "–"
    return f"{'+' if valor >= 0 else '−'}{_miles(abs(valor) * 100, decimales)} pp"


def fmt_variacion(valor: float | None, decimales: int = 1) -> str:
    if _es_vacio(valor):
        return "–"
    return f"{'+' if valor >= 0 else '−'}{_miles(abs(valor) * 100, decimales)} %"


def fmt_nota(valor: float | None, decimales: int = 2) -> str:
    if _es_vacio(valor):
        return "–"
    return _miles(valor, decimales)


def fmt_entero(valor: float | None) -> str:
    if _es_vacio(valor):
        return "–"
    return _miles(valor)


def texto_delta(valor: float | None, tipo: str) -> tuple[str | None, bool]:
    """Variación para st.metric y si es neutra. Streamlit lee el '-' ASCII para la flecha."""
    if valor is None:
        return None, False
    if tipo == "cop":
        texto = fmt_variacion(valor)
    elif tipo == "pct":
        texto = fmt_pp(valor)
    else:
        texto = ("+" if valor >= 0 else "−") + fmt_nota(abs(valor))
    if not any(c in "123456789" for c in texto):
        return texto.lstrip("+−"), True
    return texto.replace("−", "-"), False


CONFIG_PLOTLY = {"displaylogo": False,
                 "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"]}


PLANTILLA = go.layout.Template(
    layout=dict(
        font=dict(family=FUENTE, size=13, color=COLORES["texto"]),
        title=dict(font=dict(size=16, color=COLORES["texto"]), x=0, xanchor="left"),
        paper_bgcolor=COLORES["tarjeta"],
        plot_bgcolor=COLORES["tarjeta"],
        colorway=[COLORES["dato"], COLORES["atencion"], COLORES["bien"],
                  COLORES["alerta"], COLORES["contexto"]],
        separators=",.",
        margin=dict(l=10, r=20, t=60, b=10),
        hoverlabel=dict(bgcolor=COLORES["tarjeta"], font=dict(color=COLORES["texto"])),
        xaxis=dict(showgrid=False, linecolor=COLORES["rejilla"], ticks="",
                   tickfont=dict(color=COLORES["texto_sec"]),
                   title=dict(font=dict(color=COLORES["texto_sec"]))),
        yaxis=dict(gridcolor=COLORES["rejilla"], zeroline=False, ticks="",
                   tickfont=dict(color=COLORES["texto_sec"]),
                   title=dict(font=dict(color=COLORES["texto_sec"]))),
        legend=dict(orientation="h", y=1.02, yanchor="bottom", x=0, title=None),
    )
)
pio.templates["grupo2"] = PLANTILLA


def estilo(fig: go.Figure, **layout) -> go.Figure:
    """Aplica el estilo del grupo. Mostrar luego con st.plotly_chart(fig, theme=None)."""
    fig.update_layout(template=PLANTILLA, paper_bgcolor=COLORES["tarjeta"],
                      plot_bgcolor=COLORES["tarjeta"], **layout)
    fig.update_xaxes(automargin=True)
    fig.update_yaxes(automargin=True)
    return fig
