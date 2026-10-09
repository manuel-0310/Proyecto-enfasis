"""Carga, limpieza y filtrado de los datos. El notebook usa este mismo limpiar()."""

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parent
RUTA_RAW = RAIZ / "data" / "raw" / "02_fabricante_electrodomesticos.csv"
RUTA_PROCESADO = RAIZ / "data" / "processed" / "electrodomesticos_procesado.csv"

# Desde el día 9 la devolución salta de ~2,5 % a 100 % (sección 10 del notebook)
META_DIAS_ENTREGA = 8

LIMITES_DESCUENTO = [0, 5, 10, 15, 20, float("inf")]
ETIQUETAS_DESCUENTO = ["0–5 %", "5–10 %", "10–15 %", "15–20 %", "20 % o más"]

COLUMNAS_RAW = [
    "id_linea_venta", "fecha", "ciudad", "departamento", "region", "categoria",
    "subcategoria", "canal", "clasificacion_energetica", "precio_lista_cop",
    "descuento_pct", "ingreso_neto_cop", "costo_estimado_cop", "unidades",
    "dias_entrega", "devolucion_30_dias", "motivo_devolucion", "garantia_meses",
    "calificacion_cliente_1a5",
]

# Contrato de datos acordado por el grupo
COLUMNAS_PROCESADO = [
    "id_linea_venta",
    "fecha", "anio", "mes", "anio_mes", "trimestre",
    "region", "departamento", "ciudad",
    "categoria", "subcategoria", "canal", "clasificacion_energetica",
    "unidades", "precio_lista_total", "ingreso", "costo", "utilidad",
    "descuento_pct", "descuento_cop", "rango_descuento",
    "dias_entrega", "entrega_tarde", "devolucion", "motivo_devolucion",
    "calificacion", "garantia_meses",
]

SIN_DEVOLUCION = "Sin devolución"

MESES = ["ene", "feb", "mar", "abr", "may", "jun",
         "jul", "ago", "sep", "oct", "nov", "dic"]


def columnas_faltantes(df: pd.DataFrame, requeridas: list[str]) -> list[str]:
    return [c for c in requeridas if c not in df.columns]


def limpiar(raw: pd.DataFrame, meta_dias: int = META_DIAS_ENTREGA) -> pd.DataFrame:
    """Convierte el CSV original en la tabla del contrato de datos.

    Los montos del CSV son por unidad, por eso se multiplican por unidades.
    La evidencia de cada decisión está en prep_datos.ipynb.
    """
    faltantes = columnas_faltantes(raw, COLUMNAS_RAW)
    if faltantes:
        raise ValueError(f"Faltan columnas en el CSV original: {faltantes}")

    df = raw.copy()
    df["fecha"] = pd.to_datetime(df["fecha"], format="%Y-%m-%d")
    df["devolucion"] = df["devolucion_30_dias"].str.strip().eq("Sí")

    df["precio_lista_total"] = df["precio_lista_cop"] * df["unidades"]
    df["ingreso"] = df["ingreso_neto_cop"] * df["unidades"]
    df["costo"] = df["costo_estimado_cop"] * df["unidades"]
    df["utilidad"] = df["ingreso"] - df["costo"]
    df["descuento_cop"] = df["precio_lista_total"] - df["ingreso"]

    df["motivo_devolucion"] = df["motivo_devolucion"].fillna(SIN_DEVOLUCION)
    df = df.rename(columns={"calificacion_cliente_1a5": "calificacion"})

    df["rango_descuento"] = pd.cut(
        df["descuento_pct"], bins=LIMITES_DESCUENTO, labels=ETIQUETAS_DESCUENTO,
        right=False, include_lowest=True,
    )
    df["entrega_tarde"] = df["dias_entrega"] > meta_dias
    df["anio"] = df["fecha"].dt.year
    df["mes"] = df["fecha"].dt.month
    df["anio_mes"] = df["fecha"].dt.to_period("M").astype(str)
    df["trimestre"] = df["anio"].astype(str) + "-T" + df["fecha"].dt.quarter.astype(str)

    return df[COLUMNAS_PROCESADO]


def tipar_procesado(df: pd.DataFrame) -> pd.DataFrame:
    """Recupera los tipos que se pierden al guardar el CSV procesado."""
    df = df.copy()
    df["fecha"] = pd.to_datetime(df["fecha"])
    df["rango_descuento"] = pd.Categorical(
        df["rango_descuento"], categories=ETIQUETAS_DESCUENTO, ordered=True
    )
    for col in ["entrega_tarde", "devolucion"]:
        df[col] = df[col].astype(str).str.lower().eq("true")
    return df


def guardar_procesado(df: pd.DataFrame, ruta: Path = RUTA_PROCESADO) -> Path:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(ruta, index=False, encoding="utf-8")
    return ruta


@st.cache_data(show_spinner="Cargando datos…")
def cargar_datos(ruta_procesado: str = str(RUTA_PROCESADO),
                 ruta_raw: str = str(RUTA_RAW)) -> pd.DataFrame:
    """Lee los datos una sola vez; si no existe el procesado, lo genera."""
    if Path(ruta_procesado).exists():
        return tipar_procesado(pd.read_csv(ruta_procesado))
    return limpiar(pd.read_csv(ruta_raw))


def aplicar_filtros(df: pd.DataFrame, fecha_ini, fecha_fin,
                    regiones=None, canales=None, categorias=None) -> pd.DataFrame:
    """Filtra por fechas y por listas de valores; una lista vacía significa todas."""
    mascara = df["fecha"].between(pd.Timestamp(fecha_ini), pd.Timestamp(fecha_fin))
    for columna, valores in (("region", regiones), ("canal", canales),
                             ("categoria", categorias)):
        if valores:
            mascara &= df[columna].isin(valores)
    return df.loc[mascara]


@dataclass(frozen=True)
class Contexto:
    """Lo que app.py le entrega a cada pestaña en render(ctx)."""
    datos: pd.DataFrame
    filtrados: pd.DataFrame
    anterior: pd.DataFrame | None
    fecha_ini: pd.Timestamp
    fecha_fin: pd.Timestamp
    etiqueta_periodo: str
    etiqueta_anterior: str | None
    filtros: dict = field(default_factory=dict)


def rango_anio_anterior(fecha_ini, fecha_fin, fecha_min_datos):
    """Mismo rango un año antes, o None si empieza antes del primer dato."""
    ini = pd.Timestamp(fecha_ini) - pd.DateOffset(years=1)
    fin = pd.Timestamp(fecha_fin) - pd.DateOffset(years=1)
    if ini < pd.Timestamp(fecha_min_datos):
        return None
    return ini, fin


def etiqueta_mes(fecha) -> str:
    fecha = pd.Timestamp(fecha)
    return f"{MESES[fecha.month - 1]} {fecha.year}"


def etiqueta_rango(fecha_ini, fecha_fin) -> str:
    """Nombre corto de un rango: '2025', 'ene–sep 2026' o 'ene 2024 – sep 2026'."""
    ini, fin = pd.Timestamp(fecha_ini), pd.Timestamp(fecha_fin)
    if not (ini.day == 1 and fin.is_month_end):
        return f"{ini:%d/%m/%Y} – {fin:%d/%m/%Y}"
    if ini.year == fin.year:
        if ini.month == 1 and fin.month == 12:
            return str(ini.year)
        if ini.month == fin.month:
            return etiqueta_mes(ini)
        return f"{MESES[ini.month - 1]}–{MESES[fin.month - 1]} {ini.year}"
    return f"{etiqueta_mes(ini)} – {etiqueta_mes(fin)}"
