"""Pestaña Resumen: KPI arriba, tendencia y regiones al centro, mapa abajo (lectura en Z)."""

import altair as alt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import kpis
from data import META_DIAS_ENTREGA, Contexto, etiqueta_mes
from theme import (CONFIG_PLOTLY, COLORES, estilo, estilo_altair, fmt_entero, fmt_millones, fmt_nota,
                   fmt_pct, fmt_pp, texto_delta)

CLAVE_REGION = "resumen_region"
CLAVE_INDICADOR = "resumen_indicador"

FORMATO = {"cop": fmt_millones, "pct": fmt_pct, "nota": fmt_nota}

AYUDAS = {
    "ingreso": "Σ (ingreso neto por unidad × unidades). Millones de COP.",
    "margen": "(Σ ingreso − Σ costo) / Σ ingreso. Se calcula sobre las sumas, "
              "no como promedio de márgenes.",
    "descuento": "Σ (precio de lista − ingreso neto) de cada línea. Millones de COP.",
    "tarde": f"Líneas entregadas en más de {META_DIAS_ENTREGA} días / total de "
             f"líneas. Meta: {META_DIAS_ENTREGA} días o menos.",
    "devolucion": "Líneas devueltas en los primeros 30 días / total de líneas.",
    "satisfaccion": "Promedio de la calificación del cliente (1 a 5). "
                    "Excluye las líneas sin calificación.",
}

FILAS_KPI = [["ingreso", "margen", "descuento"],
             ["tarde", "devolucion", "satisfaccion"]]

INDICADORES = {"Ingreso": "ingreso", "Margen": "margen", "Devolución": "devolucion",
               "Entregas tarde": "tarde", "Satisfacción": "satisfaccion"}
SUJETO = {"ingreso": "El ingreso mensual", "margen": "El margen",
          "devolucion": "La tasa de devolución", "tarde": "El % de entregas tarde",
          "satisfaccion": "La satisfacción"}
EJE_Y = {"ingreso": "Millones de COP", "margen": "% del ingreso",
         "devolucion": "% de líneas devueltas", "tarde": "% de líneas tarde",
         "satisfaccion": "Calificación (1 a 5)"}

# Cambio mínimo en la recta de tendencia para no llamarla "estable"
UMBRAL_ESTABLE = {"cop": 0.05, "pct": 0.01, "nota": 0.10}

# Con menos líneas por mes la tendencia es ruido y el título no concluye
MIN_LINEAS_MES = 100

COORDENADAS_CIUDADES = {
    "Bogotá D.C.": (4.711, -74.072), "Medellín": (6.244, -75.581),
    "Cali": (3.452, -76.532), "Barranquilla": (10.964, -74.796),
    "Cartagena": (10.391, -75.479), "Santa Marta": (11.240, -74.199),
    "Bucaramanga": (7.119, -73.122), "Cúcuta": (7.893, -72.508),
    "Ibagué": (4.438, -75.232), "Manizales": (5.070, -75.517),
    "Pereira": (4.813, -75.696), "Villavicencio": (4.142, -73.627),
}

def _cambio_tendencia(valores: pd.Series, tipo: str) -> float | None:
    """Cambio de la recta de tendencia en el periodo (relativo en montos)."""
    y = valores.astype(float).to_numpy()
    mascara = ~np.isnan(y)
    if mascara.sum() < 3:
        return None
    x = np.arange(len(y))[mascara]
    pendiente = np.polyfit(x, y[mascara], 1)[0]
    cambio = pendiente * (x[-1] - x[0])
    if tipo == "cop":
        promedio = y[mascara].mean()
        return cambio / promedio if promedio else None
    return cambio


def titulo_tendencia(clave: str, mensual: pd.DataFrame, valor_periodo) -> str:
    """Título con la conclusión de la línea: estable, sube o baja."""
    tipo = kpis.KPIS[clave]["tipo"]
    sujeto = SUJETO[clave]
    cambio = _cambio_tendencia(mensual[clave], tipo)
    if cambio is None or mensual["lineas"].median() < MIN_LINEAS_MES:
        return f"{kpis.KPIS[clave]['nombre']} por mes"
    if tipo == "cop":
        referencia = f"en torno a {fmt_millones(mensual[clave].mean())} al mes"
        variacion = f"{fmt_pct(abs(cambio), 0)} en el periodo"
    elif tipo == "pct":
        referencia = f"cerca de {fmt_pct(valor_periodo)}"
        variacion = f"{fmt_pp(abs(cambio)).lstrip('+')} en el periodo"
    else:
        referencia = f"cerca de {fmt_nota(valor_periodo)} sobre 5"
        variacion = f"{fmt_nota(abs(cambio))} puntos en el periodo"
    if abs(cambio) < UMBRAL_ESTABLE[tipo]:
        return f"{sujeto} se mantiene estable, {referencia}"
    if tipo == "cop":
        verbo = "crece" if cambio > 0 else "cae"
    else:
        verbo = "sube" if cambio > 0 else "baja"
    return f"{sujeto} {verbo} {variacion}"


def _regiones_seleccionadas(disponibles) -> list[str]:
    """Regiones elegidas con clic en las barras de Altair (selección cruzada)."""
    estado = st.session_state.get(CLAVE_REGION)
    try:
        puntos = estado["selection"]["region"]
    except (KeyError, TypeError):
        return []
    elegidas = []
    for punto in puntos:
        region = punto.get("region")
        if region in disponibles and region not in elegidas:
            elegidas.append(region)
    return elegidas


def _ticks_mensuales(fechas: pd.Series) -> tuple[list, list]:
    n = len(fechas)
    paso = 1 if n <= 8 else 2 if n <= 16 else 3 if n <= 24 else 6
    marcas = list(fechas.iloc[::paso])
    return marcas, [etiqueta_mes(f) for f in marcas]


def _tarjetas_kpi(ctx: Contexto) -> None:
    actual = kpis.calcular_kpis(ctx.filtrados)
    anterior = kpis.calcular_kpis(ctx.anterior) if ctx.anterior is not None else None
    mensual = kpis.serie_mensual(ctx.filtrados)

    for fila in FILAS_KPI:
        columnas = st.columns(len(fila))
        for columna, clave in zip(columnas, fila):
            meta = kpis.KPIS[clave]
            valor = actual[clave]
            delta, neutro = None, False
            if anterior is not None:
                delta, neutro = texto_delta(
                    kpis.variacion(valor, anterior[clave], meta["tipo"]), meta["tipo"]
                )
            if neutro:
                color_delta = "off"
            else:
                color_delta = "normal" if meta["mayor_es_mejor"] else "inverse"
            ayuda = AYUDAS[clave]
            if clave == "descuento":
                ayuda += (" Equivale al "
                          f"{fmt_pct(kpis.descuento_pct_lista(ctx.filtrados))} "
                          "del precio de lista.")
            serie = mensual[clave].dropna().tolist() if not mensual.empty else []
            columna.metric(
                meta["nombre"],
                FORMATO[meta["tipo"]](valor),
                delta=delta,
                delta_color=color_delta,
                delta_arrow="off" if neutro else "auto",
                delta_description=f"vs {ctx.etiqueta_anterior}" if delta else None,
                help=ayuda,
                border=True,
                chart_data=serie if len(serie) >= 2 else None,
                chart_type="line",
            )


def _tendencia(datos: pd.DataFrame, regiones: list[str]) -> None:
    eleccion = st.segmented_control(
        "Indicador de la tendencia", list(INDICADORES), default="Ingreso",
        key=CLAVE_INDICADOR, label_visibility="collapsed",
    ) or "Ingreso"
    clave = INDICADORES[eleccion]
    tipo = kpis.KPIS[clave]["tipo"]

    mensual = kpis.serie_mensual(datos)
    mensual["fecha"] = pd.to_datetime(mensual["anio_mes"])
    escala = {"cop": 1e-6, "pct": 100, "nota": 1}[tipo]
    y = mensual[clave].astype(float) * escala
    valor_periodo = kpis.KPIS[clave]["funcion"](datos)

    texto_valor = [FORMATO[tipo](v) for v in mensual[clave]]
    fig = go.Figure(go.Scatter(
        x=mensual["fecha"], y=y,
        mode="lines+markers",
        line=dict(color=COLORES["dato"], width=2.5),
        marker=dict(size=6, color=COLORES["dato"]),
        customdata=np.column_stack([
            [etiqueta_mes(f) for f in mensual["fecha"]], texto_valor,
            [fmt_entero(n) for n in mensual["lineas"]],
        ]),
        hovertemplate=("<b>%{customdata[0]}</b><br>"
                       f"{kpis.KPIS[clave]['nombre']}: " "%{customdata[1]}<br>"
                       "Líneas de venta: %{customdata[2]}<extra></extra>"),
    ))

    if tipo == "cop":
        referencia = y.mean()
        texto_ref = f"Promedio mensual: {fmt_millones(mensual[clave].mean())}"
    else:
        referencia = (valor_periodo or 0) * escala
        texto_ref = f"Periodo: {FORMATO[tipo](valor_periodo)}"
    fig.add_hline(y=referencia, line_dash="dash", line_width=1,
                  line_color=COLORES["texto_sec"])
    fig.add_annotation(xref="paper", yref="paper", x=0, y=1, xanchor="left",
                       yanchor="top", showarrow=False, text=f"- - -  {texto_ref}",
                       font=dict(color=COLORES["texto_sec"], size=12))

    # Montos y tasas desde 0 y calificación en su escala 1–5, para no exagerar cambios
    maximo = float(np.nanmax(y))
    rango_y = [1, 5] if tipo == "nota" else [0, maximo * 1.3 if maximo else 1]
    marcas, etiquetas = _ticks_mensuales(mensual["fecha"])
    titulo = titulo_tendencia(clave, mensual, valor_periodo)
    if regiones:
        titulo = f"{', '.join(regiones)} · {titulo[0].lower()}{titulo[1:]}"
    estilo(
        fig, height=380,
        title=titulo,
        yaxis=dict(title=EJE_Y[clave], range=rango_y,
                   tickformat={"cop": ",.0f", "pct": ",.1~f", "nota": ".1~f"}[tipo],
                   ticksuffix=" %" if tipo == "pct" else ""),
        xaxis=dict(title=None, tickvals=marcas, ticktext=etiquetas, tickangle=0),
        showlegend=False,
    )
    st.plotly_chart(fig, theme=None, config=CONFIG_PLOTLY, key="resumen_tendencia")


def _ingreso_por_region(ctx: Contexto, seleccion: list[str]) -> None:
    """Barras en Altair; el clic en una región filtra la tendencia de Plotly."""
    t = (ctx.filtrados.groupby("region")
         .agg(ingreso=("ingreso", "sum"), lineas=("ingreso", "size"))
         .sort_values("ingreso", ascending=False).reset_index())
    t["participacion"] = t["ingreso"] / t["ingreso"].sum()
    lider = t.loc[0, "region"]
    resaltadas = seleccion or [lider]
    t = t.assign(
        millones=t["ingreso"] / 1e6,
        color=[COLORES["dato"] if r in resaltadas else COLORES["contexto"] for r in t["region"]],
        etiqueta=[f"{fmt_millones(v)} · {fmt_pct(p, 0)}"
                  for v, p in zip(t["ingreso"], t["participacion"])],
        ingreso_txt=t["ingreso"].map(fmt_millones),
        participacion_txt=t["participacion"].map(fmt_pct),
        lineas_txt=t["lineas"].map(fmt_entero),
        ticket_txt=(t["ingreso"] / t["lineas"]).map(lambda v: fmt_millones(v, 2)),
    )
    titulo = (f"{lider} concentra el {fmt_pct(t.loc[0, 'participacion'], 0)} del ingreso"
              if len(t) > 1 else f"Ingreso de {lider}")

    clic = alt.selection_point(name="region", fields=["region"], on="click",
                               clear="dblclick")
    base = alt.Chart(t).encode(
        y=alt.Y("region:N", sort=None, title=None,
                axis=alt.Axis(labelLimit=200, ticks=False, domain=False)),
        x=alt.X("millones:Q", title="Ingreso neto (millones de COP)",
                scale=alt.Scale(domain=[0, t["millones"].max() * 1.6]),
                axis=alt.Axis(tickCount=4, format=",.0f",
                              labelExpr="replace(datum.label, regexp(',', 'g'), '.')")),
        tooltip=[alt.Tooltip("region:N", title="Región"),
                 alt.Tooltip("ingreso_txt:N", title="Ingreso"),
                 alt.Tooltip("participacion_txt:N", title="Participación"),
                 alt.Tooltip("lineas_txt:N", title="Líneas de venta"),
                 alt.Tooltip("ticket_txt:N", title="Ticket promedio")],
    )
    barras = base.mark_bar(size=30, cursor="pointer").encode(
        color=alt.Color("color:N", scale=None)).add_params(clic)
    etiquetas = base.mark_text(align="left", dx=4, fontSize=12,
                               color=COLORES["texto_sec"]).encode(text="etiqueta:N")
    grafico = estilo_altair((barras + etiquetas).properties(
        title=alt.TitleParams(titulo, anchor="start", fontSize=16, fontWeight="normal",
                              color=COLORES["texto"], offset=14),
        height=max(250, min(420, 60 * len(t))),
    ))

    st.altair_chart(grafico, theme=None, width="stretch", key=CLAVE_REGION,
                    on_select="rerun", selection_mode="region")


def _mapa_ciudades(ctx: Contexto) -> None:
    por_ciudad = (ctx.filtrados.groupby(["ciudad", "departamento"])
                  .agg(ingreso=("ingreso", "sum"), lineas=("ingreso", "size"))
                  .reset_index())
    por_ciudad["participacion"] = por_ciudad["ingreso"] / por_ciudad["ingreso"].sum()
    por_ciudad["lat"] = por_ciudad["ciudad"].map(lambda c: COORDENADAS_CIUDADES.get(c, (None, None))[0])
    por_ciudad["lon"] = por_ciudad["ciudad"].map(lambda c: COORDENADAS_CIUDADES.get(c, (None, None))[1])
    por_ciudad = por_ciudad.dropna(subset=["lat", "lon"])
    if por_ciudad.empty:
        st.info("No hay ciudades con coordenadas para los filtros elegidos.")
        return
    por_ciudad["ingreso_txt"] = por_ciudad["ingreso"].map(fmt_millones)
    por_ciudad["participacion_txt"] = por_ciudad["participacion"].map(fmt_pct)
    por_ciudad["lineas_txt"] = por_ciudad["lineas"].map(fmt_entero)

    lider = por_ciudad.loc[por_ciudad["ingreso"].idxmax()]
    # scatter_geo es SVG: no depende de WebGL y funciona en cualquier proyector
    fig = px.scatter_geo(
        por_ciudad, lat="lat", lon="lon", size="ingreso", size_max=38,
        hover_name="ciudad",
        custom_data=["departamento", "ingreso_txt", "participacion_txt", "lineas_txt"],
    )
    fig.update_traces(
        marker=dict(color=COLORES["dato"], opacity=0.7,
                    line=dict(color=COLORES["tarjeta"], width=1)),
        hovertemplate=("<b>%{hovertext}</b> (%{customdata[0]})<br>"
                       "Ingreso: %{customdata[1]}<br>Participación: %{customdata[2]}<br>"
                       "Líneas de venta: %{customdata[3]}<extra></extra>"),
    )
    fig.update_geos(
        projection_type="mercator", resolution=50,
        lataxis_range=[-3, 13.5], lonaxis_range=[-80.5, -66],
        showcountries=True, countrycolor=COLORES["contexto"],
        showland=True, landcolor="#F3F4F6", showocean=True, oceancolor=COLORES["tarjeta"],
        showlakes=False, showframe=False, coastlinecolor=COLORES["contexto"],
        bgcolor=COLORES["tarjeta"],
    )
    estilo(
        fig, height=480, margin=dict(l=0, r=0, t=50, b=0),
        title=(f"{lider['ciudad']} concentra el {fmt_pct(lider['participacion'], 0)} "
               "del ingreso" if len(por_ciudad) > 1 else f"Ingreso de {lider['ciudad']}"),
    )

    mapa, tabla = st.columns([1.3, 1], gap="large")
    with mapa:
        st.plotly_chart(fig, theme=None, config={"displaylogo": False},
                        key="resumen_mapa")
    with tabla:
        ranking = por_ciudad.sort_values("ingreso", ascending=False)
        st.dataframe(
            ranking[["ciudad", "ingreso_txt", "participacion_txt", "lineas_txt"]],
            hide_index=True, height=(len(ranking) + 1) * 35 + 3,
            column_config={"ciudad": "Ciudad", "ingreso_txt": "Ingreso",
                           "participacion_txt": "% del total",
                           "lineas_txt": "Líneas"},
        )


def render(ctx: Contexto) -> None:
    _tarjetas_kpi(ctx)

    disponibles = set(ctx.filtrados["region"].unique())
    seleccion = _regiones_seleccionadas(disponibles)
    datos_tendencia = (ctx.filtrados[ctx.filtrados["region"].isin(seleccion)]
                       if seleccion else ctx.filtrados)

    izquierda, derecha = st.columns([1.55, 1], gap="large")
    with izquierda:
        _tendencia(datos_tendencia, seleccion)
    with derecha:
        _ingreso_por_region(ctx, seleccion)

    with st.expander("Mapa del ingreso por ciudad"):
        _mapa_ciudades(ctx)
