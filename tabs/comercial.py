"""Pestaña Comercial: responde P1 y P2.

P1: ¿Qué categoría deja el mayor margen de utilidad real y por qué canal es
    más rentable distribuirla?
P2: ¿Los descuentos generan más ventas o solo reducen la utilidad, y en qué
    rango conviene poner un límite?

KPI arriba y cinco gráficos (barras simples y agrupadas, sin apilar):
  P1 · utilidad por categoría, margen por categoría, utilidad por categoría y canal
  P2 · utilidad por línea y unidades por línea según el rango de descuento
Los cálculos viven aquí; no depende de kpis.py.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

from data import Contexto
from theme import (COLORES, estilo, fmt_cop, fmt_millones, fmt_nota, fmt_pct,
                   fmt_pp, fmt_variacion)

CONFIG_PLOTLY = {"displaylogo": False,
                 "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"]}

ORDEN_RANGO = ["0–5 %", "5–10 %", "10–15 %", "15–20 %", "20 % o más"]
COLORES_CANAL = [COLORES["dato"], COLORES["atencion"], COLORES["bien"],
                 COLORES["contexto"]]

# Si el margen entre categorías varía menos que esto (en puntos), se llama "igual"
UMBRAL_MARGEN_PLANO = 0.01
# Si las unidades por línea varían menos que esto (relativo), se llaman "iguales"
UMBRAL_PLANO = 0.05
# Un rango de descuento "pierde" cuando su utilidad por línea queda al menos
# 10 % por debajo de la del rango más bajo (el de referencia)
CAIDA_LIMITE = 0.10

ESTADO_OK = "Utilidad cercana a la referencia"
ESTADO_CAIDA = "Utilidad 10 % o más bajo la referencia"


# ---------------------------------------------------------------- cálculos

def _dividir(numerador: float, denominador: float) -> float | None:
    return numerador / denominador if denominador else None


def _kpis(df: pd.DataFrame) -> dict[str, float | None]:
    """KPI comerciales, calculados sobre sumas (no promedios de promedios)."""
    ingreso = float(df["ingreso"].sum())
    utilidad = float(df["utilidad"].sum())
    return {
        "ingreso": ingreso,
        "utilidad": utilidad,
        "margen": _dividir(utilidad, ingreso),
        "desc_cop": float(df["descuento_cop"].sum()),
        "desc_pct": _dividir(df["descuento_cop"].sum(), df["precio_lista_total"].sum()),
    }


def _variacion(actual: float | None, anterior: float | None, relativa: bool):
    """Cambio relativo en montos; diferencia absoluta (pp) en porcentajes."""
    if actual is None or anterior is None:
        return None
    if relativa:
        return (actual - anterior) / anterior if anterior else None
    return actual - anterior


def _delta(valor: float | None, relativa: bool) -> str | None:
    """Texto para st.metric. Streamlit lee el '-' ASCII para pintar la flecha."""
    if valor is None:
        return None
    texto = fmt_variacion(valor) if relativa else fmt_pp(valor)
    if not any(c in "123456789" for c in texto):  # cambio nulo: sin signo ni flecha
        return texto.lstrip("+−")
    return texto.replace("−", "-")


def _por_categoria(df: pd.DataFrame) -> pd.DataFrame:
    """Utilidad, ingreso y margen por categoría, de mayor a menor utilidad."""
    t = (df.groupby("categoria", observed=True)[["utilidad", "ingreso"]]
         .sum().reset_index())
    t["margen"] = t["utilidad"] / t["ingreso"]
    t["pct_utilidad"] = t["utilidad"] / t["utilidad"].sum()
    return t.sort_values("utilidad", ascending=False).reset_index(drop=True)


def _por_rango(df: pd.DataFrame) -> pd.DataFrame:
    """Utilidad y unidades promedio por línea en cada rango de descuento."""
    t = (df.groupby("rango_descuento", observed=True)
         .agg(utilidad_linea=("utilidad", "mean"),
              unidades=("unidades", "mean"),
              lineas=("unidades", "size"))
         .reindex(ORDEN_RANGO).dropna().reset_index())
    return t


# ----------------------------------------------------------------- gráficos

def _utilidad_por_categoria(df: pd.DataFrame) -> None:
    t = _por_categoria(df)
    t["etiqueta"] = [f"{fmt_millones(u)} · {fmt_pct(p, 0)}"
                     for u, p in zip(t["utilidad"], t["pct_utilidad"])]
    lider = t.iloc[0]
    titulo = (f"{lider['categoria']} deja la mayor utilidad: "
              f"{fmt_pct(lider['pct_utilidad'], 0)} del total")
    fig = px.bar(t, x="utilidad", y="categoria", orientation="h", text="etiqueta",
                 color_discrete_sequence=[COLORES["dato"]])
    fig.update_traces(textposition="outside", cliponaxis=False,
                      hovertemplate="%{y}<br>%{text}<extra></extra>")
    fig.update_yaxes(categoryorder="array",
                     categoryarray=t["categoria"][::-1].tolist(), title=None)
    fig.update_xaxes(title="Utilidad en millones de COP", showticklabels=False)
    estilo(fig, title=dict(text=titulo), height=340, showlegend=False,
           margin=dict(l=10, r=100, t=60, b=10))
    st.plotly_chart(fig, theme=None, config=CONFIG_PLOTLY, key="comercial_util_cat")


def _margen_por_categoria(df: pd.DataFrame) -> None:
    t = _por_categoria(df)
    t["etiqueta"] = t["margen"].map(lambda v: fmt_pct(v, 1))
    dispersion = t["margen"].max() - t["margen"].min()
    if len(t) < 2:
        titulo = "Margen de la categoría"
    elif dispersion < UMBRAL_MARGEN_PLANO:
        titulo = (f"El margen es casi igual en todas las categorías "
                  f"({fmt_pct(t['margen'].min(), 1)} a {fmt_pct(t['margen'].max(), 1)})")
    else:
        mejor = t.loc[t["margen"].idxmax()]
        titulo = f"{mejor['categoria']} tiene el mayor margen: {fmt_pct(mejor['margen'], 1)}"
    fig = px.bar(t, x="margen", y="categoria", orientation="h", text="etiqueta",
                 color_discrete_sequence=[COLORES["dato"]])
    fig.update_traces(textposition="outside", cliponaxis=False,
                      hovertemplate="%{y}<br>Margen %{text}<extra></extra>")
    fig.update_yaxes(categoryorder="array",
                     categoryarray=t["categoria"][::-1].tolist(), title=None)
    fig.update_xaxes(title="Margen sobre ingreso (el eje parte de 0)",
                     tickformat=".0%", range=[0, max(t["margen"].max() * 1.25, 0.1)])
    estilo(fig, title=dict(text=titulo), height=340, showlegend=False,
           margin=dict(l=10, r=40, t=60, b=10))
    st.plotly_chart(fig, theme=None, config=CONFIG_PLOTLY, key="comercial_margen_cat")


def _utilidad_categoria_canal(df: pd.DataFrame) -> None:
    t = (df.groupby(["categoria", "canal"], observed=True)[["utilidad", "ingreso"]]
         .sum().reset_index())
    t["margen"] = t["utilidad"] / t["ingreso"]
    t["utilidad_m"] = t["utilidad"] / 1e6      # millones, para el tooltip
    t["utilidad_mm"] = t["utilidad"] / 1e9     # miles de millones (MM), para el eje
    orden_cat = _por_categoria(df)["categoria"].tolist()
    orden_canal = (df.groupby("canal", observed=True)["utilidad"].sum()
                   .sort_values(ascending=False).index.tolist())
    lider_cat = orden_cat[0]
    de_lider = t[t["categoria"] == lider_cat].sort_values("utilidad", ascending=False)
    mejor = de_lider.iloc[0]
    titulo = (f"{lider_cat} deja más utilidad por {mejor['canal']} "
              f"({fmt_millones(mejor['utilidad'])}, margen {fmt_pct(mejor['margen'], 1)})")
    fig = px.bar(t, x="categoria", y="utilidad_mm", color="canal", barmode="group",
                 category_orders={"categoria": orden_cat, "canal": orden_canal},
                 color_discrete_sequence=COLORES_CANAL, custom_data=["margen", "utilidad_m"])
    fig.update_traces(hovertemplate="%{x} · %{fullData.name}<br>"
                                    "Utilidad %{customdata[1]:,.0f} M de COP<br>"
                                    "Margen %{customdata[0]:.1%}<extra></extra>")
    fig.update_xaxes(title=None)
    fig.update_yaxes(title="Utilidad en miles de millones de COP (MM)",
                     tickformat=",.1f", ticksuffix=" MM")
    estilo(fig, title=dict(text=titulo), height=380, legend_title_text="")
    st.plotly_chart(fig, theme=None, config=CONFIG_PLOTLY, key="comercial_cat_canal")


def _utilidad_por_descuento(df: pd.DataFrame) -> None:
    t = _por_rango(df)
    base = t["utilidad_linea"].iloc[0] if len(t) else None
    t["caida"] = (1 - t["utilidad_linea"] / base) if base else 0
    t["estado"] = [ESTADO_CAIDA if c >= CAIDA_LIMITE else ESTADO_OK for c in t["caida"]]
    t["etiqueta"] = t["utilidad_linea"].map(fmt_cop)
    pierden = t[t["estado"] == ESTADO_CAIDA]
    if len(t) < 2:
        titulo = "Utilidad por línea según el descuento aplicado"
    elif pierden.empty:
        titulo = "La utilidad por línea se mantiene en todos los rangos de descuento"
    else:
        limite = pierden.iloc[0]
        titulo = (f"Desde {limite['rango_descuento']} de descuento, la utilidad por "
                  f"línea cae {fmt_pct(limite['caida'], 0)}")
    fig = px.bar(t, x="rango_descuento", y="utilidad_linea", text="etiqueta",
                 color="estado",
                 color_discrete_map={ESTADO_OK: COLORES["dato"],
                                     ESTADO_CAIDA: COLORES["atencion"]},
                 category_orders={"estado": [ESTADO_OK, ESTADO_CAIDA]},
                 custom_data=["lineas", "caida"])
    fig.update_traces(textposition="outside", cliponaxis=False,
                      hovertemplate="Descuento %{x}<br>%{y:,.0f} COP de utilidad por línea"
                                    "<br>%{customdata[1]:.1%} frente al rango más bajo"
                                    "<br>%{customdata[0]:,.0f} líneas<extra></extra>")
    fig.update_xaxes(title="Rango de descuento", categoryorder="array",
                     categoryarray=ORDEN_RANGO)
    fig.update_yaxes(title="Utilidad por línea (promedio, COP)", tickformat=",.0f",
                     range=[0, max(t["utilidad_linea"].max() * 1.2, 1)])
    estilo(fig, title=dict(text=titulo), height=340)
    st.plotly_chart(fig, theme=None, config=CONFIG_PLOTLY, key="comercial_util_desc")


def _unidades_por_descuento(df: pd.DataFrame) -> None:
    t = _por_rango(df)
    t["etiqueta"] = t["unidades"].map(lambda v: fmt_nota(v, 2))
    media = t["unidades"].mean()
    dispersion = (t["unidades"].max() - t["unidades"].min()) / media if media else 0
    if len(t) < 2:
        titulo = "Unidades por línea según el descuento aplicado"
    elif dispersion < UMBRAL_PLANO:
        titulo = "Más descuento no vende más unidades por línea"
    else:
        mejor = t.loc[t["unidades"].idxmax(), "rango_descuento"]
        titulo = f"Las líneas con descuento de {mejor} venden más unidades"
    fig = px.bar(t, x="rango_descuento", y="unidades", text="etiqueta",
                 color_discrete_sequence=[COLORES["dato"]], custom_data=["lineas"])
    fig.update_traces(textposition="outside", cliponaxis=False,
                      hovertemplate="Descuento %{x}<br>%{y:.2f} unidades por línea"
                                    "<br>%{customdata[0]:,.0f} líneas<extra></extra>")
    fig.update_xaxes(title="Rango de descuento", categoryorder="array",
                     categoryarray=ORDEN_RANGO)
    fig.update_yaxes(title="Unidades por línea (promedio)",
                     range=[0, max(t["unidades"].max() * 1.25, 1)])
    estilo(fig, title=dict(text=titulo), height=340, showlegend=False)
    st.plotly_chart(fig, theme=None, config=CONFIG_PLOTLY, key="comercial_uni_desc")


# ------------------------------------------------------------------- render

def render(ctx: Contexto) -> None:
    df = ctx.filtrados
    if df.empty:
        st.warning("No hay ventas con los filtros actuales. "
                   "Amplía el periodo o limpia los filtros.")
        return

    actual = _kpis(df)
    previo = _kpis(ctx.anterior) if ctx.anterior is not None and not ctx.anterior.empty \
        else {k: None for k in actual}
    if previo["ingreso"] is not None:
        st.caption(f"Variación frente a {ctx.etiqueta_anterior}.")

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Ingreso neto", fmt_millones(actual["ingreso"]),
              _delta(_variacion(actual["ingreso"], previo["ingreso"], True), True),
              help="Σ (ingreso neto por unidad × unidades). Millones de COP.")
    c2.metric("Utilidad", fmt_millones(actual["utilidad"]),
              _delta(_variacion(actual["utilidad"], previo["utilidad"], True), True),
              help="Σ ingreso − Σ costo estimado. Millones de COP.")
    c3.metric("Margen", fmt_pct(actual["margen"]),
              _delta(_variacion(actual["margen"], previo["margen"], False), False),
              help="Σ utilidad / Σ ingreso. Se calcula sobre las sumas.")
    c4.metric("Descuento cedido", fmt_millones(actual["desc_cop"]),
              _delta(_variacion(actual["desc_cop"], previo["desc_cop"], True), True),
              delta_color="off",
              help="Σ (precio de lista − ingreso neto). Millones de COP.")
    c5.metric("Descuento sobre lista", fmt_pct(actual["desc_pct"]),
              _delta(_variacion(actual["desc_pct"], previo["desc_pct"], False), False),
              delta_color="off",
              help="Descuento cedido / Σ precio de lista.")

    st.subheader("P1 · Categoría y canal más rentables")
    st.caption("¿Cuál es la categoría que genera el mayor margen de utilidad real "
               "y a través de qué canal es más rentable distribuirla?")
    fila1 = st.columns(2, gap="large")
    with fila1[0]:
        _utilidad_por_categoria(df)
    with fila1[1]:
        _margen_por_categoria(df)
    _utilidad_categoria_canal(df)

    st.subheader("P2 · Descuentos: ¿venden más o solo cuestan utilidad?")
    st.caption("¿Los descuentos generan más ventas o solo reducen la utilidad, "
               "y en qué rango conviene poner un límite?")
    fila2 = st.columns(2, gap="large")
    with fila2[0]:
        _utilidad_por_descuento(df)
    with fila2[1]:
        _unidades_por_descuento(df)