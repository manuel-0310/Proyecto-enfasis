"""Punto de entrada del dashboard: filtros de la barra lateral y pestañas."""

import pandas as pd
import streamlit as st

import data
from tabs import comercial, conclusiones, datos as pestana_datos, operaciones, resumen

st.set_page_config(
    page_title="Electrodomésticos · Dashboard BI",
    layout="wide",
    initial_sidebar_state="expanded",
)

try:
    datos = data.cargar_datos()
except FileNotFoundError:
    st.error("No se encontró el archivo de datos en data/raw/ ni en data/processed/.")
    st.stop()

faltantes = data.columnas_faltantes(datos, data.COLUMNAS_PROCESADO)
if faltantes:
    st.error(f"Faltan columnas requeridas en los datos: {faltantes}")
    st.stop()

FECHA_MIN = datos["fecha"].min().normalize()
FECHA_MAX = datos["fecha"].max().normalize()

PERIODOS = {"Todo el periodo": (FECHA_MIN, FECHA_MAX)}
for anio in sorted(datos["anio"].unique()):
    ini = max(pd.Timestamp(anio, 1, 1), FECHA_MIN)
    fin = min(pd.Timestamp(anio, 12, 31), FECHA_MAX)
    PERIODOS[data.etiqueta_rango(ini, fin)] = (ini, fin)
PERIODOS["Personalizado"] = None

CLAVES_FILTROS = ["f_periodo", "f_fechas", "f_region", "f_canal", "f_categoria"]


def restablecer_filtros():
    for clave in CLAVES_FILTROS:
        st.session_state.pop(clave, None)


with st.sidebar:
    st.header("Filtros")

    periodo = st.selectbox("Periodo", list(PERIODOS), key="f_periodo")
    if PERIODOS[periodo] is None:
        rango = st.date_input(
            "Rango de fechas", value=(FECHA_MIN.date(), FECHA_MAX.date()),
            min_value=FECHA_MIN.date(), max_value=FECHA_MAX.date(),
            format="DD/MM/YYYY", key="f_fechas",
        )
        if len(rango) != 2:
            st.info("Elige la fecha final del rango.")
            st.stop()
        fecha_ini, fecha_fin = pd.Timestamp(rango[0]), pd.Timestamp(rango[1])
    else:
        fecha_ini, fecha_fin = PERIODOS[periodo]

    regiones = st.multiselect("Región", sorted(datos["region"].unique()),
                              placeholder="Todas", key="f_region")
    canales = st.multiselect("Canal", sorted(datos["canal"].unique()),
                             placeholder="Todos", key="f_canal")
    categorias = st.multiselect("Categoría", sorted(datos["categoria"].unique()),
                                placeholder="Todas", key="f_categoria")

    st.button("Restablecer filtros", on_click=restablecer_filtros, width="stretch")

filtrados = data.aplicar_filtros(datos, fecha_ini, fecha_fin,
                                 regiones, canales, categorias)

# Mismo periodo un año antes, para la variación de los KPI
rango_anterior = data.rango_anio_anterior(fecha_ini, fecha_fin, FECHA_MIN)
anterior, etiqueta_anterior = None, None
if rango_anterior is not None:
    anterior = data.aplicar_filtros(datos, *rango_anterior,
                                    regiones, canales, categorias)
    etiqueta_anterior = data.etiqueta_rango(*rango_anterior)
    if anterior.empty:
        anterior, etiqueta_anterior = None, None

st.title("Ventas, descuentos y entregas")
st.caption("Fabricante nacional de electrodomésticos")

if filtrados.empty:
    st.warning("Ninguna venta cumple los filtros elegidos. "
               "Amplía el periodo o quita alguna región, canal o categoría.")
    st.stop()

ctx = data.Contexto(
    datos=datos,
    filtrados=filtrados,
    anterior=anterior,
    fecha_ini=fecha_ini,
    fecha_fin=fecha_fin,
    etiqueta_periodo=data.etiqueta_rango(fecha_ini, fecha_fin),
    etiqueta_anterior=etiqueta_anterior,
    filtros={"region": regiones, "canal": canales, "categoria": categorias},
)

(pestana_resumen, pestana_comercial, pestana_operaciones, pestana_conclusiones,
 pestana_tabla) = st.tabs(["Resumen", "Comercial", "Operaciones", "Conclusiones", "Datos"])
with pestana_resumen:
    resumen.render(ctx)
with pestana_comercial:
    comercial.render(ctx)
with pestana_operaciones:
    operaciones.render(ctx)
with pestana_conclusiones:
    conclusiones.render(ctx)
with pestana_tabla:
    pestana_datos.render(ctx)
