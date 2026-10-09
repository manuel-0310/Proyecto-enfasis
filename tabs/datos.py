"""Pestaña Datos (Manuel): tabla con las líneas de venta filtradas."""

import streamlit as st

from data import Contexto

COLUMNAS = ["id_linea_venta", "fecha", "region", "ciudad", "categoria",
            "subcategoria", "canal", "unidades", "ingreso", "descuento_pct",
            "utilidad", "dias_entrega", "entrega_tarde", "devolucion",
            "motivo_devolucion", "calificacion"]


def render(ctx: Contexto) -> None:
    st.dataframe(
        ctx.filtrados[COLUMNAS].sort_values("fecha"),
        hide_index=True, height=620,
        column_config={
            "id_linea_venta": "Línea",
            "fecha": st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
            "region": "Región", "ciudad": "Ciudad", "categoria": "Categoría",
            "subcategoria": "Subcategoría", "canal": "Canal", "unidades": "Unidades",
            "ingreso": st.column_config.NumberColumn("Ingreso (COP)", format="localized"),
            "descuento_pct": st.column_config.NumberColumn("Descuento %", format="%.1f"),
            "utilidad": st.column_config.NumberColumn("Utilidad (COP)", format="localized"),
            "dias_entrega": "Días de entrega",
            "entrega_tarde": st.column_config.CheckboxColumn("Tarde"),
            "devolucion": st.column_config.CheckboxColumn("Devuelta"),
            "motivo_devolucion": "Motivo",
            "calificacion": st.column_config.NumberColumn("Calificación", format="%.0f"),
        },
    )
