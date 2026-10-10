"""Pestaña Conclusiones (Camilo): hallazgos, decisiones y limitaciones."""

import pandas as pd
import streamlit as st

import kpis
from data import ETIQUETAS_DESCUENTO, META_DIAS_ENTREGA, Contexto
from tabs.operaciones import devoluciones_evitables, tasa_base
from theme import COLORES, fmt_entero, fmt_millones, fmt_nota, fmt_pct

# Mismo tope que el simulador de Comercial; 10 % si no se ha movido
CLAVE_TOPE = "comercial_tope"

# Grupos con menos líneas no se usan para sacar conclusiones
MIN_LINEAS = 300


def _hallazgo(numero: int, pregunta: str, color: str, cifra: str, etiqueta: str,
              detalle: str | None, significa: str, decision: str) -> None:
    """Un hallazgo: cifra → qué significa → decisión."""
    with st.container(border=True):
        st.markdown(f"<span style='color:{color};font-weight:700'>P{numero}</span> · "
                    f"**{pregunta}**", unsafe_allow_html=True)
        cifra_col, significa_col, decision_col = st.columns([1, 1.6, 1.6], gap="large")
        cifra_col.metric(etiqueta, cifra, delta=detalle, delta_color="off",
                         delta_arrow="off")
        significa_col.markdown(f"**Qué significa**  \n{significa}")
        decision_col.markdown(f"**Decisión**  \n{decision}")


def _p1(df: pd.DataFrame) -> None:
    t = df.groupby("categoria")["ingreso"].sum().sort_values(ascending=False)
    participacion = t / t.sum()
    cruce = df.groupby(["categoria", "canal"]).agg(
        ingreso=("ingreso", "sum"), utilidad=("utilidad", "sum"), lineas=("ingreso", "size"))
    cruce = cruce[cruce["lineas"] >= MIN_LINEAS]
    margen = cruce["utilidad"] / cruce["ingreso"]

    if len(t) >= 2:
        primeras = f"{t.index[0]} y {t.index[1]}"
        cifra, etiqueta = fmt_pct(participacion.iloc[:2].sum(), 0), f"Ingreso de {primeras}"
        concentra = (f"Dos de {len(t)} categorías generan "
                     f"{fmt_pct(participacion.iloc[:2].sum(), 0)} del ingreso.")
    else:
        primeras = t.index[0]
        cifra, etiqueta = fmt_millones(t.iloc[0]), f"Ingreso de {primeras}"
        concentra = f"Con los filtros elegidos solo queda {primeras}."

    if len(margen) >= 2 and margen.max() - margen.min() < 0.01:
        costo = (f"El margen va de {fmt_pct(margen.min())} a {fmt_pct(margen.max())} en "
                 "todos los cruces de categoría y canal: atender cada segmento cuesta "
                 "casi lo mismo.")
        decision = (f"Concentrar inventario, entregas y campañas en {primeras}. "
                    "No hace falta diferenciar precios por canal según su costo.")
    elif len(margen) >= 2:
        categoria, canal = margen.idxmax()
        costo = (f"El mayor margen está en {categoria} por {canal} "
                 f"({fmt_pct(margen.max())}) y el menor en {fmt_pct(margen.min())}.")
        decision = (f"Concentrar inventario y campañas en {primeras} y empujar las ventas "
                    f"de {categoria} por {canal}, que deja más margen.")
    else:
        costo = "No hay suficientes líneas para comparar el margen entre segmentos."
        decision = f"Concentrar inventario y campañas en {primeras}."

    _hallazgo(1, "¿Dónde se concentra el ingreso y qué cuesta atender cada segmento?",
              COLORES["dato"], cifra, etiqueta, None, f"{concentra} {costo}", decision)


def _p2(df: pd.DataFrame) -> None:
    cedido = kpis.descuento_cedido(df)
    sobre_lista = kpis.descuento_pct_lista(df)
    tope = st.session_state.get(CLAVE_TOPE, 10)
    exceso = (df["descuento_pct"] - tope).clip(lower=0) / 100
    recuperado = float((exceso * df["precio_lista_total"]).sum())

    rangos = (df.groupby("rango_descuento", observed=False)
              .agg(unidades=("unidades", "mean"), lineas=("unidades", "size"))
              .reindex(ETIQUETAS_DESCUENTO))
    rangos = rangos[rangos["lineas"] >= MIN_LINEAS]

    significa = f"Se cede el {fmt_pct(sobre_lista)} del precio de lista."
    if len(rangos) >= 2:
        minimo, maximo = rangos["unidades"].min(), rangos["unidades"].max()
        if (maximo - minimo) / rangos["unidades"].mean() < 0.05:
            significa += (f" Con más descuento no se venden más unidades: todas las líneas "
                          f"venden entre {fmt_nota(minimo)} y {fmt_nota(maximo)} por línea.")
        else:
            mejor = rangos["unidades"].idxmax()
            significa += (f" Las líneas con descuento de {mejor} venden más unidades "
                          f"({fmt_nota(maximo)} por línea).")

    decision = (f"Poner un tope de {tope} % al descuento: recuperaría "
                f"{fmt_millones(recuperado)} de ingreso si las unidades no cambian.")
    _hallazgo(2, "¿Cuánto se cede en descuentos y qué se obtiene a cambio?",
              COLORES["atencion"], fmt_millones(cedido), "Descuento cedido",
              f"{fmt_pct(sobre_lista)} del precio de lista", significa, decision)


def _p3(df: pd.DataFrame) -> None:
    tarde = df["entrega_tarde"]
    tasa_tarde = kpis.tasa_devolucion(df[tarde]) if tarde.any() else None
    tasa_ok = kpis.tasa_devolucion(df[~tarde]) if (~tarde).any() else None
    pregunta = "¿Cuánto cuestan las entregas tarde en devoluciones y satisfacción?"

    if tasa_tarde is None or tasa_ok is None:
        _hallazgo(3, pregunta, COLORES["alerta"], fmt_pct(kpis.pct_entregas_tarde(df)),
                  "Entregas tarde", None,
                  "Con los filtros elegidos no hay entregas a tiempo y tarde para comparar.",
                  f"Mantener la meta de {META_DIAS_ENTREGA} días y ampliar los filtros.")
        return

    r = devoluciones_evitables(df, META_DIAS_ENTREGA, tasa_base(df))
    parte = (df["devolucion"] & tarde).sum() / df["devolucion"].sum()
    sat_ok = kpis.satisfaccion(df[~tarde])
    sat_tarde = kpis.satisfaccion(df[tarde])

    significa = (f"Solo el {fmt_pct(tarde.mean())} de las entregas pasa de "
                 f"{META_DIAS_ENTREGA} días, pero explica el {fmt_pct(parte, 0)} de las "
                 "devoluciones.")
    if sat_ok is not None and sat_tarde is not None:
        significa += (f" La calificación baja de {fmt_nota(sat_ok)} a "
                      f"{fmt_nota(sat_tarde)}.")

    region = df.groupby("region").agg(tarde=("entrega_tarde", "mean"),
                                      lineas=("entrega_tarde", "size"))
    region = region[region["lineas"] >= MIN_LINEAS]["tarde"]
    if len(region) >= 2 and region.max() - region.min() >= 0.01:
        donde = f" Empezar por {region.idxmax()}, la región con más entregas tarde."
    else:
        donde = (" El retraso es parejo entre regiones, así que el cambio es en la "
                 "logística general y no en una zona.")
    decision = (f"Fijar {META_DIAS_ENTREGA} días como meta de entrega: cumplirla evitaría "
                f"unas {fmt_entero(r['evitables'])} devoluciones y "
                f"{fmt_millones(r['ingreso'])} de ingreso devuelto.{donde}")

    _hallazgo(3, pregunta, COLORES["alerta"], fmt_pct(tasa_tarde, 0),
              f"Devolución con más de {META_DIAS_ENTREGA} días",
              f"vs {fmt_pct(tasa_ok)} a tiempo", significa, decision)


def _limitaciones(df: pd.DataFrame) -> None:
    sin_calificacion = int(df["calificacion"].isna().sum())
    st.subheader("Limitaciones")
    st.markdown(
        f"- **Asociación, no causa.** La devolución es cercana al 2,5 % hasta el día "
        f"{META_DIAS_ENTREGA} y del 100 % desde el día {META_DIAS_ENTREGA + 1}. Un salto "
        "tan exacto parece una regla de cómo se generaron los datos; el dashboard muestra "
        "la relación, no prueba que la demora cause la devolución.\n"
        "- **El motivo no explica el salto.** Los motivos de devolución se reparten igual "
        "con entrega a tiempo o tarde.\n"
        "- **El costo es estimado** (`costo_estimado_cop`), así que el margen y la "
        "utilidad son aproximados.\n"
        f"- **Calificaciones faltantes.** {fmt_entero(sin_calificacion)} líneas no tienen "
        "calificación; la satisfacción se calcula sin ellas.\n"
        "- **2026 llega hasta septiembre.** La comparación con el año anterior usa el "
        "mismo rango de meses.\n"
        "- **Los simuladores tienen supuestos.** El tope de descuento supone que las "
        "unidades no cambian y la meta de entrega, que las líneas a tiempo se devuelven "
        "a la tasa base.\n"
        "- **No hay costo logístico ni de devolución.** El costo de una devolución se mide "
        "como ingreso devuelto, no como pérdida real."
    )


def render(ctx: Contexto) -> None:
    df = ctx.filtrados
    if df.empty:
        st.warning("Ninguna venta cumple los filtros elegidos.")
        return

    st.subheader("Tres hallazgos y tres decisiones")
    st.caption(f"Cifras calculadas con los filtros actuales · {ctx.etiqueta_periodo}")
    _p1(df)
    _p2(df)
    _p3(df)

    _limitaciones(df)

    st.subheader("Qué aporta el dashboard")
    st.markdown(
        "- Responde las tres preguntas en un solo lugar, con los mismos filtros de "
        "periodo, región, canal y categoría.\n"
        "- Cada título dice la conclusión y se recalcula al filtrar.\n"
        "- Los simuladores de tope de descuento y meta de entrega convierten el hallazgo "
        "en una cifra para decidir."
    )
