# Glosario Técnico y de Negocio

Este documento define el vocabulario del negocio y los términos técnicos clave utilizados en el sistema de predicción de demanda.

## 1. Términos de Dominio y Negocio
* **Forecasting (Predicción de Demanda):** Estimación de la cantidad de unidades de un producto que los clientes comprarán en el futuro.
* **Clasificador (Categoría):** Identificador único del grupo de productos que el modelo evalúa de forma independiente (ej. electrodomésticos, bebidas).
* **Lag (Desfase):** Valor histórico desfasado en el tiempo (ej. ventas de hace 7, 14 o 21 días) utilizado como feature de entrada para el modelo predictivo.
* **Inferencia:** El proceso en el que el modelo ML procesa los datos de entrada para calcular una predicción de demanda final.
* **Precio Medio (precio_medio):** Valor promedio ponderado de venta por unidad del producto en el día histórico registrado.
* **Horizonte de Predicción:** El marco temporal hacia adelante para el cual se realiza el pronóstico (puede ser diario, semanal o mensual).
* **Reentrenamiento (Retraining):** Proceso periódico para actualizar los pesos del modelo de Machine Learning (XGBoost) utilizando datos históricos recientes para evitar el desvanecimiento de precisión (concept drift).

## 2. Términos Técnico-Seguridad y Procesos
* **REST API:** Arquitectura de servicios web que permite la transferencia de datos mediante endpoints HTTP estándar.
* **JWT (JSON Web Token):** Estándar abierto para la transmisión segura de información entre partes en forma de objeto JSON estructurado y firmado.
* **JWT Rotation (Rotación de Refresh Tokens):** Mecanismo de seguridad que expira un refresh token tras su primer uso y emite uno nuevo para evitar ataques de replay.
* **Rate Limiting:** Control de tasa que restringe el número de peticiones que un cliente puede hacer en un periodo para evitar abuso del servidor.
* **Migrations (Migraciones):** Scripts versionados que modifican el esquema de base de datos de manera incremental y controlada.
* **Seed (Semilla):** Script que pobla la base de datos vacía con datos ficticios iniciales pero realistas para facilitar pruebas y desarrollo local.
* **Event Loop (Bucle de Eventos):** Núcleo de la programación asíncrona en Python que planifica y ejecuta las tareas cooperativas (FastAPI).
* **CORS (Cross-Origin Resource Sharing):** Cabeceras HTTP que permiten a un servidor frontend en un origen acceder de forma segura al backend de otro origen.
