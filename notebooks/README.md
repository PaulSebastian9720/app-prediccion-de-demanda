# Documentación y Guía de Uso de Notebooks

Esta carpeta contiene los cuadernos de Jupyter utilizados para el análisis exploratorio de datos, entrenamiento del modelo de predicción de demanda, testeo de inferencia y explicabilidad del modelo (XAI).

---

## 1. Cuadernos Disponibles

*   **[01_EDA.ipynb](file:///home/paul/universidad/septimo_v2/Aprendiza_Automatico/app-prediccion-de-demanda/notebooks/01_EDA.ipynb):** Análisis Exploratorio de Datos (EDA) sobre las series de tiempo del histórico de ventas, tendencias y estacionalidades por categoría.
*   **[02_XGBoost_entrenamiento.ipynb](file:///home/paul/universidad/septimo_v2/Aprendiza_Automatico/app-prediccion-de-demanda/notebooks/02_XGBoost_entrenamiento.ipynb):** Pipeline completo de entrenamiento del modelo XGBoost, ajuste de hiperparámetros y métricas de validación cruzada.
*   **[03_prediccion.ipynb](file:///home/paul/universidad/septimo_v2/Aprendiza_Automatico/app-prediccion-de-demanda/notebooks/03_prediccion.ipynb):** Testeo y simulación de predicciones para horizontes diarios y semanales acumulados.
*   **[04_XAI.ipynb](file:///home/paul/universidad/septimo_v2/Aprendiza_Automatico/app-prediccion-de-demanda/notebooks/04_XAI.ipynb):** Explicabilidad del modelo utilizando valores SHAP para analizar el impacto de las variables en las inferencias.

---

## 2. Configuración y Entorno de Desarrollo

Para ejecutar y probar los notebooks con el mismo entorno y versiones del proyecto, utiliza el gestor `uv`:

1.  Ubícate en la carpeta `app-backend` e instala las dependencias (incluyendo Jupyter y nbstripout):
    ```bash
    cd app-backend
    uv sync
    ```
2.  Levanta tu servidor de Jupyter o abre tu editor (VS Code, JupyterLab) apuntando al entorno virtual `.venv` generado en `app-backend/`.

---

## 3. Limpieza Automática de Salidas (Control de Versiones Limpio)

Para evitar confirmar gráficos pesados, ejecuciones duplicadas y metadatos ruidosos en Git, hemos integrado la herramienta **`nbstripout`**. Esta limpia las salidas de ejecución de forma inteligente.

### Opción A: Configurar el Filtro Automático en Git (Recomendado)
Puedes hacer que Git limpie los metadatos y gráficos **automáticamente en segundo plano** cada vez que haces `git diff` o `git commit`. Los archivos conservarán sus salidas localmente en tu editor, pero se subirán limpios a GitHub.

Para activar este filtro en tu consola local, ubícate en la carpeta `app-backend` y corre:
```bash
make git-notebooks-init
```
*Esto creará el archivo `.gitattributes` en la raíz del proyecto y registrará el filtro en tu configuración local de Git (`.git/config`).*

### Opción B: Limpieza Manual por Consola
Si deseas limpiar los outputs físicamente en el disco duro de todos los notebooks antes de subirlos, corre:
```bash
make clean-notebooks
```
