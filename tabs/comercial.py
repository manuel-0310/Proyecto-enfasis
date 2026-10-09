"""Pestaña Comercial (Manuel 2): P1 concentración del ingreso y P2 descuentos."""

import altair as alt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import kpis
from data import ETIQUETAS_DESCUENTO, Contexto
from theme import (CONFIG_PLOTLY, COLORES, FUENTE, estilo, fmt_cop, fmt_entero,
                   fmt_millones, fmt_nota, fmt_pct, texto_delta)

CLAVE_PARETO = "comercial_pareto"
CLAVE_TOPE = "comercial_tope"

# Grupos con menos líneas no se usan para sacar conclusiones en los títulos
MIN_LINEAS = 300

def _corto(nombre: str) -> str:
    return nombre.replace(" ", "<br>", 1) if len(nombre) > 12 else nombre


TARJETAS = [
    ("Utilidad", kpis.utilidad, "cop", True, fmt_millones,
     "Σ ingreso − Σ costo estimado. Millones de COP."),
    ("Ticket promedio", kpis.ticket_promedio, "cop", True, lambda v: fmt_millones(v, 2),
     "Ingreso / número de líneas de venta. Millones de COP."),
    ("Descuento sobre lista", kpis.descuento_pct_lista, "pct", False, fmt_pct,
     "Σ descuento cedido / Σ precio de lista."),
    ("Unidades por línea", kpis.unidades_por_linea, "nota", True, fmt_nota,
     "Unidades vendidas / número de líneas de venta."),
]


def _tarjetas(ctx: Contexto) -> None:
    mensual = {anio_mes: grupo for anio_mes, grupo in ctx.filtrados.groupby("anio_mes")}
    for columna, (nombre, funcion, tipo, mayor_es_mejor, formato, ayuda) in zip(
            st.columns(len(TARJETAS)), TARJETAS):
        valor = funcion(ctx.filtrados)
        delta, neutro = None, False
        if ctx.anterior is not None:
            delta, neutro = texto_delta(
                kpis.variacion(valor, funcion(ctx.anterior), tipo), tipo)
        serie = [v for v in (funcion(g) for g in mensual.values()) if v is not None]
        columna.metric(
            nombre, formato(valor), delta=delta,
            delta_color="off" if neutro else ("normal" if mayor_es_mejor else "inverse"),
            delta_arrow="off" if neutro else "auto",
            delta_description=f"vs {ctx.etiqueta_anterior}" if delta else None,
            help=ayuda, border=True,
            chart_data=serie if len(serie) >= 2 else None, chart_type="line",
        )


def _categorias_seleccionadas(disponibles) -> list[str]:
    """Categorías elegidas con clic en las barras del Pareto (selección cruzada)."""
    estado = st.session_state.get(CLAVE_PARETO)
    try:
        puntos = estado["selection"]["points"]
    except (KeyError, TypeError):
        return []
    elegidas = []
    for punto in puntos:
        categoria = punto.get("x")
        if punto.get("curve_number", 0) == 0 and categoria in disponibles \
                and categoria not in elegidas:
            elegidas.append(categoria)
    return elegidas


def _pareto(df: pd.DataFrame, seleccion: list[str]) -> None:
    t = (df.groupby("categoria").agg(ingreso=("ingreso", "sum"), lineas=("ingreso", "size"))
         .sort_values("ingreso", ascending=False).reset_index())
    t["participacion"] = t["ingreso"] / t["ingreso"].sum()
    t["acumulado"] = t["participacion"].cumsum()

    if len(t) >= 2:
        titulo = (f"{t.loc[0, 'categoria']} y {t.loc[1, 'categoria']} generan el "
                  f"{fmt_pct(t.loc[1, 'acumulado'], 0)} del ingreso")
    else:
        titulo = f"Ingreso de {t.loc[0, 'categoria']}"

    colores = [COLORES["dato"] if not seleccion or c in seleccion else COLORES["contexto"]
               for c in t["categoria"]]
    fig = go.Figure()
    fig.add_bar(
        x=t["categoria"], y=t["ingreso"] / 1e6, marker_color=colores, name="Ingreso",
        text=[fmt_pct(p, 0) for p in t["participacion"]], textposition="outside",
        cliponaxis=False, textfont=dict(color=COLORES["texto_sec"]),
        customdata=np.column_stack([[fmt_millones(v) for v in t["ingreso"]],
                                    [fmt_pct(p) for p in t["participacion"]],
                                    [fmt_entero(n) for n in t["lineas"]]]),
        hovertemplate=("<b>%{x}</b><br>Ingreso: %{customdata[0]}<br>"
                       "Participación: %{customdata[1]}<br>"
                       "Líneas de venta: %{customdata[2]}<extra></extra>"),
        selected=dict(marker=dict(opacity=1)), unselected=dict(marker=dict(opacity=1)),
    )
    fig.add_scatter(
        x=t["categoria"], y=t["acumulado"] * 100, yaxis="y2", name="% acumulado",
        mode="lines+markers", line=dict(color=COLORES["atencion"], width=2),
        marker=dict(size=7), hovertemplate="%{x}<br>Acumulado: %{y:.1f} %<extra></extra>",
    )
    fig.add_shape(type="line", xref="paper", x0=0, x1=1, yref="y2", y0=80, y1=80,
                  line=dict(dash="dash", width=1, color=COLORES["texto_sec"]))
    estilo(
        fig, title=titulo, height=400, clickmode="event+select", dragmode=False,
        showlegend=False,
        xaxis=dict(title=None, tickangle=0, tickvals=t["categoria"],
                   ticktext=[_corto(c) for c in t["categoria"]]),
        yaxis=dict(title="Ingreso neto (millones de COP)", tickformat=",.0f",
                   range=[0, t["ingreso"].max() / 1e6 * 1.2]),
        yaxis2=dict(title="% acumulado", overlaying="y", side="right", range=[0, 105],
                    tickmode="array", tickvals=[0, 20, 40, 60, 80, 100],
                    ticktext=[f"{v} %" for v in (0, 20, 40, 60, 80, 100)], showgrid=False,
                    tickfont=dict(color=COLORES["texto_sec"])),
    )
    st.plotly_chart(fig, theme=None, config=CONFIG_PLOTLY, key=CLAVE_PARETO,
                    on_select="rerun", selection_mode="points")


def _lineas_vs_ingreso(df: pd.DataFrame) -> None:
    """Qué parte de las líneas atiende cada categoría frente a lo que aporta al ingreso."""
    t = df.groupby("categoria").agg(ingreso=("ingreso", "sum"), lineas=("ingreso", "size"))
    t["pct_lineas"] = t["lineas"] / t["lineas"].sum()
    t["pct_ingreso"] = t["ingreso"] / t["ingreso"].sum()
    t["ticket"] = t["ingreso"] / t["lineas"]
    t = t.sort_values("pct_ingreso")

    brecha = t["pct_lineas"] - t["pct_ingreso"]
    if len(t) < 2:
        titulo = f"Líneas e ingreso de {t.index[0]}"
    elif brecha.max() > 0.05:
        c = brecha.idxmax()
        titulo = (f"{c} ocupa el {fmt_pct(t.loc[c, 'pct_lineas'], 0)} de las líneas<br>"
                  f"y aporta solo el {fmt_pct(t.loc[c, 'pct_ingreso'], 0)} del ingreso")
    else:
        titulo = "Cada categoría aporta al ingreso en proporción a sus líneas"

    fig = go.Figure()
    for categoria, fila in t.iterrows():
        fig.add_scatter(x=[fila["pct_lineas"] * 100, fila["pct_ingreso"] * 100],
                        y=[categoria, categoria], mode="lines",
                        line=dict(color=COLORES["rejilla"], width=6),
                        hoverinfo="skip", showlegend=False)
    for columna, nombre, color in [("pct_lineas", "% de las líneas", COLORES["texto_sec"]),
                                   ("pct_ingreso", "% del ingreso", COLORES["dato"])]:
        fig.add_scatter(
            x=t[columna] * 100, y=t.index, mode="markers", name=nombre,
            marker=dict(size=13, color=color),
            customdata=np.column_stack([[fmt_pct(v) for v in t[columna]],
                                        [fmt_cop(v) for v in t["ticket"]]]),
            hovertemplate=(f"<b>%{{y}}</b><br>{nombre}: %{{customdata[0]}}<br>"
                           "Ticket promedio: %{customdata[1]}<extra></extra>"),
        )
    estilo(fig, title=titulo, height=400, margin=dict(l=10, r=20, t=95, b=10),
           xaxis=dict(title="% del total", ticksuffix=" %", showgrid=True,
                      gridcolor=COLORES["rejilla"], rangemode="tozero"),
           yaxis=dict(title=None, showgrid=False, tickvals=list(t.index),
                      ticktext=[_corto(c) for c in t.index]),
           legend=dict(orientation="h", y=1.0, yanchor="bottom", x=0))
    st.plotly_chart(fig, theme=None, config=CONFIG_PLOTLY, key="comercial_brecha")


def _canal_de_categoria(df: pd.DataFrame, seleccion: list[str], nombre: str) -> None:
    datos = df[df["categoria"].isin(seleccion)] if seleccion else df
    t = (datos.groupby("canal").agg(ingreso=("ingreso", "sum"), lineas=("ingreso", "size"))
         .sort_values("ingreso"))
    t["participacion"] = t["ingreso"] / t["ingreso"].sum()
    lider = t.index[-1]
    titulo = f"{lider} vende el {fmt_pct(t.loc[lider, 'participacion'], 0)} de {nombre}"

    fig = go.Figure(go.Bar(
        x=t["ingreso"] / 1e6, y=t.index, orientation="h",
        marker_color=[COLORES["dato"] if c == lider else COLORES["contexto"] for c in t.index],
        text=[f"{fmt_millones(v)} · {fmt_pct(p, 0)}"
              for v, p in zip(t["ingreso"], t["participacion"])],
        textposition="outside", cliponaxis=False,
        textfont=dict(color=COLORES["texto_sec"], size=12),
        customdata=[fmt_entero(n) for n in t["lineas"]],
        hovertemplate="<b>%{y}</b><br>%{text}<br>Líneas de venta: %{customdata}<extra></extra>",
    ))
    estilo(fig, title=titulo, height=300, showlegend=False,
           xaxis=dict(title="Ingreso neto (millones de COP)", tickformat=",.0f", nticks=4,
                      showgrid=True, gridcolor=COLORES["rejilla"],
                      range=[0, t["ingreso"].max() / 1e6 * 1.45]),
           yaxis=dict(title=None))
    st.plotly_chart(fig, theme=None, config=CONFIG_PLOTLY, key="comercial_canal")


def _margen_categoria_canal(df: pd.DataFrame) -> None:
    t = df.groupby(["categoria", "canal"]).agg(
        ingreso=("ingreso", "sum"), utilidad=("utilidad", "sum"), lineas=("ingreso", "size"))
    t["margen"] = t["utilidad"] / t["ingreso"]
    validos = t[t["lineas"] >= MIN_LINEAS]
    if len(validos) < 2:
        titulo = "Margen por categoría y canal"
    elif validos["margen"].max() - validos["margen"].min() < 0.01:
        titulo = (f"El margen va de {fmt_pct(validos['margen'].min())} a "
                  f"{fmt_pct(validos['margen'].max())} en todos los cruces de categoría y canal")
    else:
        categoria, canal = validos["margen"].idxmax()
        titulo = (f"El mayor margen está en {categoria} por {canal}: "
                  f"{fmt_pct(validos['margen'].max())}")

    matriz = t["margen"].unstack("canal")
    fig = go.Figure(go.Heatmap(
        z=matriz.values, x=[_corto(c) for c in matriz.columns],
        y=[_corto(c) for c in matriz.index],
        text=[[fmt_pct(v) for v in fila] for fila in matriz.values],
        texttemplate="%{text}", hovertemplate="%{y}<br>%{x}: %{text}<extra></extra>",
        colorscale=[[0, "#F3F4F6"], [1, "#F3F4F6"]], showscale=False, xgap=3, ygap=3,
        textfont=dict(color=COLORES["texto"]),
    ))
    estilo(fig, title=titulo.replace(" en todos", "<br>en todos"), height=340,
           margin=dict(l=10, r=10, t=120, b=10),
           xaxis=dict(side="top", showgrid=False), yaxis=dict(showgrid=False,
                                                             autorange="reversed"))
    st.plotly_chart(fig, theme=None, config=CONFIG_PLOTLY, key="comercial_margen")


def _por_rango(df: pd.DataFrame) -> pd.DataFrame:
    t = (df.groupby("rango_descuento", observed=False)
         .agg(lineas=("ingreso", "size"), descuento_cop=("descuento_cop", "sum"),
              utilidad=("utilidad", "mean"), unidades=("unidades", "mean"),
              satisfaccion=("calificacion", "mean"), devolucion=("devolucion", "mean"))
         .reindex(ETIQUETAS_DESCUENTO).reset_index())
    t = t[t["lineas"] > 0].copy()
    t["rango_descuento"] = t["rango_descuento"].astype(str)
    t["confiable"] = t["lineas"] >= MIN_LINEAS
    return t


def _descuento_cedido(t: pd.DataFrame) -> None:
    t = t.copy()
    t["participacion"] = t["descuento_cop"] / t["descuento_cop"].sum()
    top = t.sort_values("descuento_cop", ascending=False).head(2)
    if len(top) == 2:
        titulo = (f"Los descuentos de {top.iloc[0]['rango_descuento']} y "
                  f"{top.iloc[1]['rango_descuento']} concentran el "
                  f"{fmt_pct(top['participacion'].sum(), 0)} de lo cedido")
    else:
        titulo = "Descuento cedido por rango"

    fig = go.Figure(go.Bar(
        x=t["rango_descuento"], y=t["descuento_cop"] / 1e6, marker_color=COLORES["atencion"],
        text=[f"{fmt_millones(v)} · {fmt_pct(p, 0)}"
              for v, p in zip(t["descuento_cop"], t["participacion"])],
        textposition="outside", cliponaxis=False,
        textfont=dict(color=COLORES["texto_sec"], size=12),
        customdata=[fmt_entero(n) for n in t["lineas"]],
        hovertemplate="Descuento %{x}<br>%{text}<br>Líneas: %{customdata}<extra></extra>",
    ))
    estilo(fig, title=titulo, height=360, showlegend=False,
           xaxis=dict(title="Rango de descuento"),
           yaxis=dict(title="Descuento cedido (millones de COP)", tickformat=",.0f",
                      range=[0, t["descuento_cop"].max() / 1e6 * 1.25]))
    st.plotly_chart(fig, theme=None, config=CONFIG_PLOTLY, key="comercial_cedido")


def _utilidad_por_linea(t: pd.DataFrame) -> None:
    validos = t[t["confiable"]]
    if len(validos) >= 2:
        inicio, fin = validos.iloc[0], validos.iloc[-1]
        caida = 1 - fin["utilidad"] / inicio["utilidad"]
        if caida >= 0.05:
            titulo = (f"La utilidad por línea baja {fmt_pct(caida, 0)} entre "
                      f"{inicio['rango_descuento']} y {fin['rango_descuento']} de descuento")
        else:
            titulo = "La utilidad por línea se mantiene en todos los rangos de descuento"
    else:
        titulo = "Utilidad por línea según el descuento"

    fig = go.Figure(go.Bar(
        x=t["rango_descuento"], y=t["utilidad"],
        marker_color=[COLORES["dato"] if c else COLORES["contexto"] for c in t["confiable"]],
        text=[fmt_cop(v) for v in t["utilidad"]], textposition="outside", cliponaxis=False,
        textfont=dict(color=COLORES["texto_sec"], size=12),
        customdata=[fmt_entero(n) + ("" if c else " (muy pocas para comparar)")
                    for n, c in zip(t["lineas"], t["confiable"])],
        hovertemplate=("Descuento %{x}<br>Utilidad por línea: %{text}<br>"
                       "Líneas: %{customdata}<extra></extra>"),
    ))
    estilo(fig, title=titulo, height=360, showlegend=False,
           xaxis=dict(title="Rango de descuento"),
           yaxis=dict(title="Utilidad promedio por línea (COP)", tickformat=",.0f",
                      range=[0, t["utilidad"].max() * 1.2]))
    st.plotly_chart(fig, theme=None, config=CONFIG_PLOTLY, key="comercial_utilidad")


def _grafico_altair(t: pd.DataFrame, columna: str, titulo: str, dominio, formato) -> alt.Chart:
    datos = t.assign(valor=t[columna], etiqueta=t[columna].map(formato))
    base = alt.Chart(datos).encode(
        x=alt.X("rango_descuento:N", sort=ETIQUETAS_DESCUENTO, title=None,
                axis=alt.Axis(labelAngle=0)),
        y=alt.Y("valor:Q", title=None, scale=alt.Scale(domain=dominio),
                axis=alt.Axis(labelExpr="replace(datum.label, '.', ',')", tickCount=4)),
        tooltip=[alt.Tooltip("rango_descuento:N", title="Descuento"),
                 alt.Tooltip("etiqueta:N", title=titulo),
                 alt.Tooltip("lineas:Q", title="Líneas", format=",")],
    )
    linea = base.mark_line(color=COLORES["dato"], strokeWidth=2.5)
    puntos = base.mark_circle(size=70, color=COLORES["dato"], opacity=1)
    return (linea + puntos).properties(title=titulo, height=220).configure(
        font=FUENTE, background=COLORES["tarjeta"],
    ).configure_title(anchor="start", fontSize=14, fontWeight="normal",
                      color=COLORES["texto"]).configure_axis(
        labelColor=COLORES["texto_sec"], gridColor=COLORES["rejilla"],
        domainColor=COLORES["rejilla"], tickColor=COLORES["rejilla"], labelFontSize=11,
    ).configure_view(strokeWidth=0)


def _efecto_descuento(t: pd.DataFrame) -> None:
    validos = t[t["confiable"]]
    if len(validos) >= 2:
        planos = [
            (validos["unidades"].max() - validos["unidades"].min()) / validos["unidades"].mean() < 0.05,
            validos["satisfaccion"].max() - validos["satisfaccion"].min() < 0.1,
            validos["devolucion"].max() - validos["devolucion"].min() < 0.01,
        ]
        titulo = ("Con más descuento no se venden más unidades ni mejoran la satisfacción "
                  "o las devoluciones" if all(planos)
                  else "Unidades, satisfacción y devoluciones según el descuento")
    else:
        titulo = "Unidades, satisfacción y devoluciones según el descuento"
    st.markdown(f"**{titulo}**")

    if len(validos) >= 2:
        t = validos
    t = t.assign(devolucion=lambda d: d["devolucion"] * 100)
    graficos = [
        ("unidades", "Unidades por línea", [0, max(t["unidades"].max() * 1.3, 1)],
         lambda v: fmt_nota(v)),
        ("satisfaccion", "Satisfacción (1 a 5)", [1, 5], lambda v: fmt_nota(v)),
        ("devolucion", "Tasa de devolución (%)", [0, max(t["devolucion"].max() * 1.5, 1)],
         lambda v: fmt_pct(v / 100)),
    ]
    for columna, (campo, titulo_g, dominio, formato) in zip(st.columns(3), graficos):
        with columna:
            st.altair_chart(_grafico_altair(t, campo, titulo_g, dominio, formato),
                            theme=None, width="stretch")


def _simulacion_tope(df: pd.DataFrame) -> None:
    tope = st.session_state.get(CLAVE_TOPE, 10)
    exceso = (df["descuento_pct"] - tope).clip(lower=0) / 100
    recuperado = float((exceso * df["precio_lista_total"]).sum())
    afectadas = int((exceso > 0).sum())

    st.markdown(f"**Con un descuento máximo de {tope} %, se recuperarían "
                f"{fmt_millones(recuperado, 1 if recuperado < 1e8 else 0)} de ingreso**")
    with st.container(border=True):
        control, ingreso, lineas = st.columns([1.4, 1, 1], gap="large",
                                              vertical_alignment="center")
        control.slider("Tope de descuento (%)", min_value=5, max_value=25, value=10,
                       step=1, key=CLAVE_TOPE)
        ingreso.metric("Ingreso recuperado",
                       fmt_millones(recuperado, 1 if recuperado < 1e8 else 0),
                       help="Σ (descuento por encima del tope × precio de lista). "
                            "Supone que las unidades vendidas no cambian.")
        lineas.metric("Líneas con descuento recortado", fmt_entero(afectadas),
                      delta=fmt_pct(afectadas / len(df)) + " del total",
                      delta_color="off", delta_arrow="off")


def render(ctx: Contexto) -> None:
    df = ctx.filtrados
    _tarjetas(ctx)

    st.subheader("¿Dónde se concentra el ingreso y qué cuesta atender cada segmento?")
    seleccion = _categorias_seleccionadas(set(df["categoria"].unique()))
    izquierda, derecha = st.columns([1.2, 1], gap="large")
    with izquierda:
        _pareto(df, seleccion)
    with derecha:
        _lineas_vs_ingreso(df)
    izquierda, derecha = st.columns([1.2, 1], gap="large")
    with izquierda:
        nombre = ", ".join(seleccion or ctx.filtros.get("categoria") or []) \
            or "todas las categorías"
        _canal_de_categoria(df, seleccion, nombre)
    with derecha:
        _margen_categoria_canal(df)

    st.subheader("¿Cuánto se cede en descuentos y qué se obtiene a cambio?")
    rangos = _por_rango(df)
    izquierda, derecha = st.columns(2, gap="large")
    with izquierda:
        _descuento_cedido(rangos)
    with derecha:
        _utilidad_por_linea(rangos)
    _efecto_descuento(rangos)
    _simulacion_tope(df)
