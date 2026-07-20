# Referencia de API REST

Este documento detalla los principales endpoints de la API REST del sistema, incluyendo sus estructuras de petición y respuesta, además del acceso a la documentación interactiva local.

---

## 1. Documentación Interactiva y Pruebas Locales
FastAPI expone de forma automática dos interfaces de documentación interactiva que facilitan la exploración de rutas, esquemas y la ejecución de pruebas directas:
*   **Swagger UI:** Disponible localmente en [http://localhost:8000/docs](http://localhost:8000/docs). Permite autenticarse mediante JWT (botón "Authorize") e interactuar de forma directa con los endpoints enviando parámetros reales.
*   **ReDoc:** Disponible localmente en [http://localhost:8000/redoc](http://localhost:8000/redoc). Proporciona una interfaz limpia y estructurada en tres columnas ideal para inspeccionar en profundidad el modelo de datos.

---

## 2. Autenticación y Gestión de Sesiones

### Iniciar Sesión (`POST /api/v1/auth/login`)
Valida las credenciales del usuario y genera los tokens de acceso y refresco.
* **Petición (JSON):**
  ```json
  {"email": "admin@example.com", "password": "change-this-password"}
  ```
* **Respuesta exitosa (200 OK):**
  ```json
  {"access_token": "eyJhbGciOi...", "refresh_token": "def456...", "expires_in": 900}
  ```

### Rotar Tokens (`POST /api/v1/auth/refresh`)
Intercambia un refresh token activo por un nuevo par access/refresh (rotación de un solo uso).
* **Petición (JSON):**
  ```json
  {"refresh_token": "def456..."}
  ```
* **Respuesta exitosa (200 OK):** Mismo formato que `/auth/login`.

---

## 3. Servicios de Predicción (Forecasting)

### Listar Categorías / Clasificadores (`GET /api/v1/predictions/clasificadores`)
Obtiene la lista de categorías que el modelo XGBoost cargado reconoce.
* **Respuesta exitosa (200 OK):**
  ```json
  {"clasificadores": ["electrodomesticos", "bebidas", "snacks"]}
  ```

### Predicción Diaria con Explicación (`POST /api/v1/predictions/day`)
*Requiere cabecera: `Authorization: Bearer <access_token>`*
Genera la inferencia para un día específico e incluye un análisis en lenguaje natural.
* **Petición (JSON):**
  ```json
  {"clasificador": "bebidas", "fecha": "2026-07-25"}
  ```
* **Respuesta exitosa (200 OK):**
  ```json
  {
    "clasificador": "bebidas",
    "fecha": "2026-07-25",
    "cantidad_predicha": 142.0,
    "dias_historial_usados": 21,
    "model_version": "v1.0.0",
    "inference_log_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "explicacion": {
      "resumen": "Se predice un aumento del 10% por fin de semana.",
      "factores": [{"nombre": "Día de la semana", "impacto": "+15 unidades"}],
      "dia_similar": {"fecha": "2026-07-18", "cantidad": 138},
      "margen_error_habitual": 8.5,
      "promedio_dia_semana": 120.0,
      "stock_actual": 250,
      "recomendacion": "Mantener inventario actual.",
      "generado_por": "openai",
      "historial_reciente": []
    }
  }
  ```

---

## 4. Ingesta de Histórico (Solo Administradores)

### Carga Masiva mediante Archivo (`POST /api/v1/sales-history/upload`)
*Requiere cabecera: `Authorization: Bearer <access_token>`*
Inserta o actualiza registros de ventas (upsert) desde un archivo CSV, XLSX o XML.
* **Petición (Multipart Form):**
  * `file`: Archivo con columnas `clasificador,dia,cantidad_vendida,precio_medio`
* **Respuesta exitosa (200 OK):**
  ```json
  {
    "rows_received": 150,
    "rows_upserted": 148,
    "rows_rejected": 2,
    "errors": ["Línea 12: Clasificador 'desconocido' no es válido."]
  }
  ```
