"""Los 6 KPI del dashboard, calculados sobre sumas y conteos."""

import pandas as pd


def _dividir(numerador: float, denominador: float) -> float | None:
    return numerador / denominador if denominador else None


def ingreso_neto(df: pd.DataFrame) -> float:
    return float(df["ingreso"].sum())


def margen_pct(df: pd.DataFrame) -> float | None:
    """(Σ ingreso − Σ costo) / Σ ingreso, no el promedio de márgenes por línea."""
    ingreso = df["ingreso"].sum()
    return _dividir(ingreso - df["costo"].sum(), ingreso)


def descuento_cedido(df: pd.DataFrame) -> float:
    return float(df["descuento_cop"].sum())


def descuento_pct_lista(df: pd.DataFrame) -> float | None:
    return _dividir(df["descuento_cop"].sum(), df["precio_lista_total"].sum())


def pct_entregas_tarde(df: pd.DataFrame) -> float | None:
    return _dividir(df["entrega_tarde"].sum(), len(df))


def tasa_devolucion(df: pd.DataFrame) -> float | None:
    return _dividir(df["devolucion"].sum(), len(df))


def satisfaccion(df: pd.DataFrame) -> float | None:
    """Promedio de la calificación 1–5, sin las líneas que no tienen calificación."""
    calificaciones = df["calificacion"].dropna()
    return float(calificaciones.mean()) if len(calificaciones) else None


# mayor_es_mejor define el color de la variación en las tarjetas
KPIS = {
    "ingreso": {"nombre": "Ingreso neto", "funcion": ingreso_neto,
                "tipo": "cop", "mayor_es_mejor": True},
    "margen": {"nombre": "Margen %", "funcion": margen_pct,
               "tipo": "pct", "mayor_es_mejor": True},
    "descuento": {"nombre": "Descuento cedido", "funcion": descuento_cedido,
                  "tipo": "cop", "mayor_es_mejor": False},
    "tarde": {"nombre": "Entregas tarde", "funcion": pct_entregas_tarde,
              "tipo": "pct", "mayor_es_mejor": False},
    "devolucion": {"nombre": "Tasa de devolución", "funcion": tasa_devolucion,
                   "tipo": "pct", "mayor_es_mejor": False},
    "satisfaccion": {"nombre": "Satisfacción", "funcion": satisfaccion,
                     "tipo": "nota", "mayor_es_mejor": True},
}


def calcular_kpis(df: pd.DataFrame) -> dict[str, float | None]:
    if df.empty:
        return {clave: None for clave in KPIS}
    return {clave: meta["funcion"](df) for clave, meta in KPIS.items()}


def variacion(actual: float | None, anterior: float | None,
              tipo: str) -> float | None:
    """Montos: cambio relativo. Porcentajes y calificación: diferencia absoluta."""
    if actual is None or anterior is None:
        return None
    if tipo == "cop":
        return _dividir(actual - anterior, anterior)
    return actual - anterior


def serie_mensual(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["anio_mes", "lineas", *KPIS])
    filas = []
    for anio_mes, grupo in df.groupby("anio_mes", sort=True):
        fila = {"anio_mes": anio_mes, "lineas": len(grupo)}
        fila.update(calcular_kpis(grupo))
        filas.append(fila)
    return pd.DataFrame(filas)
