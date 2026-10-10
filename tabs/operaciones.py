"""Pestaña Operaciones (Camilo): P3 costo de las entregas tarde."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import kpis
from data import META_DIAS_ENTREGA, SIN_DEVOLUCION, Contexto
from theme import (CONFIG_PLOTLY, COLORES, estilo, fmt_entero, fmt_millones, fmt_nota,
                   fmt_pct, texto_delta)

CLAVE_META = "operaciones_meta"
CLAVE_DIMENSION = "operaciones_dimension"

# Grupos con menos líneas no se usan para sacar conclusiones en los títulos
MIN_LINEAS = 300

# Devoluciones mínimas por grupo para comparar motivos
MIN_DEVOLUCIONES = 100

# Desde este día se agrupan en una sola barra: hay muy pocas líneas
DIA_MAXIMO = 12

DIMENSIONES = {
    "Región": ("region", "región", "todas las regiones"),
    "Canal": ("canal", "canal", "todos los canales"),
    "Categoría": ("categoria", "categoría", "todas las categorías"),
}


def _titulo(que_es: str, conclusion: str) -> str:
    """Título en dos niveles: qué muestra el gráfico (negrita) y su conclusión."""
    return f"<b>{que_es}</b><br>{conclusion}"


def _dividir(numerador: float, denominador: float) -> float | None:
    return float(numerador / denominador) if denominador else None


def _promedio(serie: pd.Series) -> float | None:
    serie = serie.dropna()
    return float(serie.mean()) if len(serie) else None


def dias_promedio(df: pd.DataFrame) -> float | None:
    return _promedio(df["dias_entrega"])


def ingreso_devuelto(df: pd.DataFrame) -> float:
    return float(df.loc[df["devolucion"], "ingreso"].sum())


def pct_devoluciones_tarde(df: pd.DataFrame) -> float | None:
    """Parte de las devoluciones que viene de entregas que pasaron la meta."""
    return _dividir((df["devolucion"] & df["entrega_tarde"]).sum(), df["devolucion"].sum())


def brecha_satisfaccion(df: pd.DataFrame) -> float | None:
    """Calificación a tiempo − calificación tarde, en puntos de 1 a 5."""
    a_tiempo = _promedio(df.loc[~df["entrega_tarde"], "calificacion"])
    tarde = _promedio(df.loc[df["entrega_tarde"], "calificacion"])
    if a_tiempo is None or tarde is None:
        return None
    return a_tiempo - tarde


def tasa_base(df: pd.DataFrame) -> float:
    """Tasa de devolución de las entregas dentro de la meta del grupo."""
    return _dividir(df.loc[~df["entrega_tarde"], "devolucion"].sum(),
                    (~df["entrega_tarde"]).sum()) or 0.0


def devoluciones_evitables(df: pd.DataFrame, meta: int, base: float) -> dict:
    """Devoluciones e ingreso que se evitarían si ninguna entrega pasara de `meta` días.

    Supone que esas líneas se devolverían a la tasa base (la de las entregas a tiempo).
    """
    sobre = df[df["dias_entrega"] > meta]
    devueltas = int(sobre["devolucion"].sum())
    evitables = max(devueltas - base * len(sobre), 0.0)
    ingreso = float(sobre.loc[sobre["devolucion"], "ingreso"].sum())
    return {
        "lineas": len(sobre),
        "evitables": evitables,
        "ingreso": ingreso * evitables / devueltas if devueltas else 0.0,
    }


TARJETAS = [
    ("Días de entrega promedio", dias_promedio, "nota", False, lambda v: fmt_nota(v, 1),
     "Promedio de días entre la venta y la entrega."),
    ("Devoluciones por entrega tarde", pct_devoluciones_tarde, "pct", False, fmt_pct,
     f"Devoluciones de líneas entregadas en más de {META_DIAS_ENTREGA} días / "
     "total de devoluciones."),
    ("Ingreso devuelto", ingreso_devuelto, "cop", False, fmt_millones,
     "Σ ingreso de las líneas devueltas en los primeros 30 días. Millones de COP."),
    ("Brecha de satisfacción", brecha_satisfaccion, "nota", False, fmt_nota,
     "Calificación promedio a tiempo − calificación promedio tarde (escala 1 a 5)."),
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


def _por_dia(df: pd.DataFrame) -> pd.DataFrame:
    dia = df["dias_entrega"].clip(upper=DIA_MAXIMO).rename("dia")
    t = (df.groupby(dia)
         .agg(lineas=("devolucion", "size"), devoluciones=("devolucion", "sum"),
              satisfaccion=("calificacion", "mean"),
              calificadas=("calificacion", "count"))
         .reset_index())
    t["tasa"] = t["devoluciones"] / t["lineas"]
    t["tarde"] = t["dia"] > META_DIAS_ENTREGA
    t["etiqueta"] = [f"{d}+" if d == DIA_MAXIMO else str(d) for d in t["dia"]]
    return t


def _eje_dias(t: pd.DataFrame) -> dict:
    return dict(title="Días de entrega", tickmode="array", tickvals=t["dia"],
                ticktext=t["etiqueta"], range=[t["dia"].min() - 0.6, t["dia"].max() + 0.6])


def _linea_referencia(fig: go.Figure, x: float, texto: str) -> None:
    """Línea vertical punteada con su texto encima del área del gráfico."""
    fig.add_vline(x=x, line_dash="dash", line_width=1, line_color=COLORES["texto_sec"])
    fig.add_annotation(x=x, y=1, yref="paper", yanchor="bottom", text=texto,
                       showarrow=False, font=dict(color=COLORES["texto_sec"], size=12))


def _linea_meta(fig: go.Figure) -> None:
    _linea_referencia(fig, META_DIAS_ENTREGA + 0.5, f"Meta: {META_DIAS_ENTREGA} días")


def _devolucion_por_dias(df: pd.DataFrame, t: pd.DataFrame) -> None:
    a_tiempo = _dividir(df.loc[~df["entrega_tarde"], "devolucion"].sum(),
                        (~df["entrega_tarde"]).sum())
    tarde = _dividir(df.loc[df["entrega_tarde"], "devolucion"].sum(),
                     df["entrega_tarde"].sum())
    if tarde is None:
        conclusion = f"Ninguna entrega pasó la meta de {META_DIAS_ENTREGA} días"
    elif a_tiempo is None:
        conclusion = f"Todas las entregas pasaron la meta de {META_DIAS_ENTREGA} días"
    else:
        conclusion = (f"Con más de {META_DIAS_ENTREGA} días la devolución pasa de "
                      f"{fmt_pct(a_tiempo)} a {fmt_pct(tarde, 0)}")

    fig = go.Figure(go.Bar(
        x=t["dia"], y=t["tasa"] * 100,
        marker_color=[COLORES["alerta"] if x else COLORES["contexto"] for x in t["tarde"]],
        text=[fmt_pct(v, 0 if v >= 0.995 else 1) for v in t["tasa"]],
        textposition="outside", cliponaxis=False,
        textfont=dict(color=COLORES["texto_sec"], size=11),
        customdata=np.column_stack([t["etiqueta"],
                                    [fmt_entero(n) for n in t["devoluciones"]],
                                    [fmt_entero(n) for n in t["lineas"]]]),
        hovertemplate=("<b>%{customdata[0]} días</b><br>Devolución: %{text}<br>"
                       "Devueltas: %{customdata[1]} de %{customdata[2]} líneas"
                       "<extra></extra>"),
    ))
    _linea_meta(fig)
    estilo(fig, title=_titulo("Tasa de devolución por días de entrega", conclusion),
           height=390, margin=dict(l=10, r=20, t=100, b=10), showlegend=False,
           xaxis=_eje_dias(t),
           yaxis=dict(title="% de líneas devueltas", ticksuffix=" %",
                      range=[0, max(t["tasa"].max() * 100 * 1.15, 5)]))
    st.plotly_chart(fig, theme=None, config=CONFIG_PLOTLY, key="operaciones_devolucion")


def _satisfaccion_por_dias(df: pd.DataFrame, t: pd.DataFrame) -> None:
    t = t.dropna(subset=["satisfaccion"])
    a_tiempo = _promedio(df.loc[~df["entrega_tarde"], "calificacion"])
    tarde = _promedio(df.loc[df["entrega_tarde"], "calificacion"])
    if a_tiempo is None or tarde is None:
        conclusion = "Calificación promedio según los días de espera"
    else:
        conclusion = (f"La calificación baja de {fmt_nota(a_tiempo)} a tiempo a "
                      f"{fmt_nota(tarde)} con entrega tarde")

    fig = go.Figure(go.Scatter(
        x=t["dia"], y=t["satisfaccion"], mode="lines+markers",
        line=dict(color=COLORES["dato"], width=2),
        marker=dict(size=9, color=[COLORES["alerta"] if x else COLORES["dato"]
                                   for x in t["tarde"]]),
        customdata=np.column_stack([t["etiqueta"],
                                    [fmt_nota(v) for v in t["satisfaccion"]],
                                    [fmt_entero(n) for n in t["calificadas"]]]),
        hovertemplate=("<b>%{customdata[0]} días</b><br>Satisfacción: %{customdata[1]}<br>"
                       "Líneas calificadas: %{customdata[2]}<extra></extra>"),
    ))
    _linea_meta(fig)
    # La calificación va de 1 a 5; el eje se ajusta al rango observado
    bajo = max(1.0, np.floor((t["satisfaccion"].min() - 0.2) * 2) / 2)
    alto = min(5.0, np.ceil((t["satisfaccion"].max() + 0.2) * 2) / 2)
    estilo(fig, title=_titulo("Satisfacción promedio por días de entrega", conclusion),
           height=390, margin=dict(l=10, r=20, t=100, b=10), showlegend=False,
           xaxis=_eje_dias(t),
           yaxis=dict(title="Calificación promedio (1 a 5)", tickformat=".1f",
                      range=[bajo, alto]))
    st.plotly_chart(fig, theme=None, config=CONFIG_PLOTLY, key="operaciones_satisfaccion")


def _tarde_por_dimension(df: pd.DataFrame) -> None:
    eleccion = st.segmented_control("Ver entregas tarde por", list(DIMENSIONES),
                                    default="Región", key=CLAVE_DIMENSION) or "Región"
    columna, nombre, todas = DIMENSIONES[eleccion]

    t = (df.groupby(columna).agg(tarde=("entrega_tarde", "mean"),
                                 n_tarde=("entrega_tarde", "sum"),
                                 lineas=("entrega_tarde", "size"))
         .sort_values("tarde"))
    t["confiable"] = t["lineas"] >= MIN_LINEAS
    promedio = float(df["entrega_tarde"].mean())
    validos = t[t["confiable"]]

    destacar = False
    if len(validos) < 2:
        conclusion = f"% de entregas tarde por {nombre}"
    elif validos["tarde"].max() - validos["tarde"].min() < 0.01:
        conclusion = (f"Es parejo: entre {fmt_pct(validos['tarde'].min())} y "
                      f"{fmt_pct(validos['tarde'].max())} en {todas}")
    else:
        destacar = True
        peor = validos["tarde"].idxmax()
        conclusion = (f"{peor} tiene más entregas tarde: {fmt_pct(validos.loc[peor, 'tarde'])}"
                      f" frente a {fmt_pct(promedio)} en promedio")

    def color(fila) -> str:
        if not fila.confiable:
            return COLORES["contexto"]
        if destacar:
            return COLORES["alerta"] if fila.tarde > promedio else COLORES["contexto"]
        return COLORES["dato"]

    fig = go.Figure(go.Bar(
        x=t["tarde"] * 100, y=t.index, orientation="h",
        marker_color=[color(fila) for fila in t.itertuples()],
        text=[fmt_pct(v) for v in t["tarde"]], textposition="outside", cliponaxis=False,
        textfont=dict(color=COLORES["texto_sec"], size=12),
        customdata=[f"{fmt_entero(n)} de {fmt_entero(l)}"
                    + ("" if c else " (muy pocas para comparar)")
                    for n, l, c in zip(t["n_tarde"], t["lineas"], t["confiable"])],
        hovertemplate=("<b>%{y}</b><br>Entregas tarde: %{text}<br>"
                       "Líneas tarde: %{customdata}<extra></extra>"),
    ))
    _linea_referencia(fig, promedio * 100, f"Promedio {fmt_pct(promedio)}")
    estilo(fig, title=_titulo(f"% de entregas tarde por {nombre}", conclusion),
           height=max(280, 90 + 42 * len(t)), margin=dict(l=10, r=20, t=105, b=10),
           showlegend=False,
           xaxis=dict(title=f"% de líneas entregadas en más de {META_DIAS_ENTREGA} días",
                      ticksuffix=" %", showgrid=True, gridcolor=COLORES["rejilla"],
                      range=[0, max(t["tarde"].max() * 100 * 1.25, 1)]),
           yaxis=dict(title=None))
    st.plotly_chart(fig, theme=None, config=CONFIG_PLOTLY, key="operaciones_dimension_fig")


def _motivos(df: pd.DataFrame) -> None:
    devueltas = df[df["devolucion"] & df["motivo_devolucion"].ne(SIN_DEVOLUCION)]
    if devueltas.empty:
        st.info("No hay devoluciones con los filtros elegidos.")
        return
    grupo = np.where(devueltas["entrega_tarde"], "Tarde", "A tiempo")
    conteo = pd.crosstab(devueltas["motivo_devolucion"], grupo)
    reparto = conteo / conteo.sum()
    orden = "Tarde" if "Tarde" in reparto else "A tiempo"
    reparto = reparto.sort_values(orden)
    conteo = conteo.loc[reparto.index]

    if {"Tarde", "A tiempo"} <= set(reparto.columns) \
            and conteo.sum().min() >= MIN_DEVOLUCIONES:
        diferencia = reparto["Tarde"] - reparto["A tiempo"]
        motivo = diferencia.idxmax()
        if diferencia.abs().max() < 0.05:
            conclusion = "Los motivos se reparten igual con entrega a tiempo o tarde"
        else:
            conclusion = (f"Con entrega tarde pesa más «{motivo}»: "
                          f"{fmt_pct(reparto.loc[motivo, 'Tarde'], 0)} frente a "
                          f"{fmt_pct(reparto.loc[motivo, 'A tiempo'], 0)}")
    else:
        conclusion = "Motivos de devolución según la entrega"

    fig = go.Figure()
    for nombre, color in (("A tiempo", COLORES["contexto"]), ("Tarde", COLORES["alerta"])):
        if nombre not in reparto:
            continue
        fig.add_bar(
            x=reparto[nombre] * 100, y=reparto.index, orientation="h", name=nombre,
            marker_color=color,
            text=[fmt_pct(v, 0) for v in reparto[nombre]], textposition="outside",
            cliponaxis=False, textfont=dict(color=COLORES["texto_sec"], size=12),
            customdata=[fmt_entero(n) for n in conteo[nombre]],
            hovertemplate=(f"<b>%{{y}}</b> · {nombre.lower()}<br>"
                           "%{text} de las devoluciones<br>"
                           "Devoluciones: %{customdata}<extra></extra>"),
        )
    estilo(fig, title=_titulo("Motivos de devolución, a tiempo contra tarde", conclusion),
           height=380, margin=dict(l=10, r=20, t=110, b=10), barmode="group",
           bargap=0.3, showlegend=True,
           legend=dict(orientation="h", y=1.0, yanchor="bottom", x=0,
                       traceorder="reversed", itemclick=False, itemdoubleclick=False),
           xaxis=dict(title="% de las devoluciones del grupo", ticksuffix=" %",
                      showgrid=True, gridcolor=COLORES["rejilla"],
                      range=[0, reparto.max().max() * 100 * 1.25]),
           yaxis=dict(title=None))
    st.plotly_chart(fig, theme=None, config=CONFIG_PLOTLY, key="operaciones_motivos")


def _simulacion_meta(df: pd.DataFrame, base: float) -> int:
    meta = st.session_state.get(CLAVE_META, META_DIAS_ENTREGA)
    r = devoluciones_evitables(df, meta, base)
    total_devueltas = int(df["devolucion"].sum())
    decimales = 1 if r["ingreso"] < 1e8 else 0

    st.markdown(f"**Simulador de la meta de entrega**  \nSi ninguna entrega pasara de "
                f"{meta} días, se evitarían {fmt_entero(r['evitables'])} devoluciones y "
                f"{fmt_millones(r['ingreso'], decimales)} de ingreso devuelto")
    with st.container(border=True):
        st.slider("Meta de días de entrega", min_value=5, max_value=DIA_MAXIMO,
                  value=META_DIAS_ENTREGA, step=1, key=CLAVE_META)
        devoluciones, ingreso, lineas = st.columns(3, gap="medium")
        devoluciones.metric(
            "Devoluciones", fmt_entero(r["evitables"]),
            delta=(fmt_pct(_dividir(r["evitables"], total_devueltas))
                   + " del total") if total_devueltas else None,
            delta_color="off", delta_arrow="off",
            help="Devoluciones de las líneas que pasan la meta, menos las que se "
                 "devolverían igual a la tasa de las entregas a tiempo.")
        ingreso.metric("Ingreso en riesgo", fmt_millones(r["ingreso"], decimales),
                       help="Ingreso de las devoluciones que se evitarían. Millones de COP.")
        lineas.metric("Líneas tarde", fmt_entero(r["lineas"]),
                      delta=fmt_pct(r["lineas"] / len(df)) + " del total",
                      delta_color="off", delta_arrow="off",
                      help="Líneas entregadas en más días que la meta elegida.")
        st.caption(f"Supuesto: si esas líneas se entregaran a tiempo, se devolverían a la "
                   f"tasa de las entregas dentro de {META_DIAS_ENTREGA} días "
                   f"({fmt_pct(base)}).")
    return meta


def _curva_meta(df: pd.DataFrame, base: float, meta: int) -> None:
    metas = list(range(5, DIA_MAXIMO + 1))
    evitables = [devoluciones_evitables(df, m, base)["evitables"] for m in metas]
    maximo = max(evitables)
    if maximo <= 0:
        conclusion = "Con los filtros elegidos no hay devoluciones evitables"
    else:
        # Meta más alta que todavía evita casi todo lo que se puede evitar
        suficiente = max(m for m, e in zip(metas, evitables) if e >= 0.98 * maximo)
        if suficiente >= DIA_MAXIMO:
            conclusion = "La meta elegida no cambia las devoluciones evitables"
        else:
            conclusion = (f"Con {suficiente} días ya se evita casi todo; "
                          f"exigir menos no evita más devoluciones")

    fig = go.Figure(go.Scatter(
        x=metas, y=evitables, mode="lines+markers",
        line=dict(color=COLORES["dato"], width=2),
        marker=dict(size=[13 if m == meta else 7 for m in metas],
                    color=[COLORES["dato"] if m == meta else COLORES["contexto"]
                           for m in metas],
                    line=dict(color=COLORES["dato"], width=1)),
        customdata=[fmt_entero(e) for e in evitables],
        hovertemplate=("Meta de %{x} días<br>Devoluciones evitables: %{customdata}"
                       "<extra></extra>"),
    ))
    estilo(fig, title=_titulo("Devoluciones evitables según la meta", conclusion),
           height=380, margin=dict(l=10, r=20, t=80, b=10), showlegend=False,
           xaxis=dict(title="Meta de días de entrega", tickmode="array", tickvals=metas),
           yaxis=dict(title="Devoluciones evitables", tickformat=",.0f",
                      range=[0, max(maximo * 1.2, 1)]))
    st.plotly_chart(fig, theme=None, config=CONFIG_PLOTLY, key="operaciones_curva")


def render(ctx: Contexto) -> None:
    df = ctx.filtrados
    if df.empty:
        st.warning("Ninguna venta cumple los filtros elegidos.")
        return
    _tarjetas(ctx)

    st.subheader("¿Cuánto cuestan las entregas tarde en devoluciones y satisfacción?")
    dias = _por_dia(df)
    izquierda, derecha = st.columns(2, gap="large")
    with izquierda:
        _devolucion_por_dias(df, dias)
    with derecha:
        _satisfaccion_por_dias(df, dias)
    izquierda, derecha = st.columns(2, gap="large")
    with izquierda:
        _tarde_por_dimension(df)
    with derecha:
        _motivos(df)
    base = tasa_base(df)
    izquierda, derecha = st.columns(2, gap="large")
    with izquierda:
        meta = _simulacion_meta(df, base)
    with derecha:
        _curva_meta(df, base, meta)
