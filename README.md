# Dashboard de ventas, descuentos y entregas

Proyecto final de Herramientas de Visualización para la Inteligencia de Negocios, grupo 2.

Es un tablero en Streamlit para un fabricante de electrodomésticos. Está pensado para la gerencia comercial y la de operaciones, y responde tres preguntas:

1. ¿Dónde se concentra el ingreso y qué cuesta atender cada segmento?
2. ¿Cuánto se cede en descuentos y qué se obtiene a cambio?
3. ¿Cuánto cuestan las entregas tarde en devoluciones y satisfacción?

App publicada: (pegar aquí el enlace)

## Cómo correrlo

```
pip install -r requirements.txt
python -m streamlit run app.py
```

## Qué hay en cada archivo

- `app.py`: abre la app, arma los filtros y las pestañas.
- `data.py`: limpia los datos y aplica los filtros.
- `kpis.py`: las fórmulas de los indicadores.
- `theme.py`: colores y formato de los números.
- `tabs/`: una pestaña por archivo (Resumen, Comercial, Operaciones, Conclusiones y Datos).
- `prep_datos.ipynb`: la revisión de los datos y por qué los limpiamos así.
- `data/raw/`: el archivo original que nos dieron.
- `data/processed/`: el archivo ya limpio, que es el que lee la app.

## Sobre los datos

Son 56.000 líneas de venta sintéticas, de enero de 2024 a septiembre de 2026. El ingreso y el costo venían por unidad, así que los multiplicamos por la cantidad vendida. El detalle de la limpieza está en el notebook.
