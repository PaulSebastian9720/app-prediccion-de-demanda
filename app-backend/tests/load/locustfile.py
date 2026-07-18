"""Prueba de carga con Locust.

Uso: `make locust` (requiere el backend corriendo, local o via Docker) o
`uv run locust -f tests/load/locustfile.py --host http://localhost:8000` para
la UI interactiva.

Cada usuario simulado se registra/inicia sesion una vez (`on_start`) y luego
reparte trafico entre `/health`, predicciones (dia/dia-x/semana/rango) y
consulta de categorias, ponderado hacia los endpoints de prediccion (el camino
critico).
"""

import random
import uuid
from datetime import date, timedelta

from locust import HttpUser, between, task

CLASIFICADORES = [
    "ALIMENTACION_HIDRATACION",
    "DESCANSO",
    "HIGIENE_ASEO",
    "JUGUETES",
    "PASEO_SUJECION",
    "TRANSPORTE_VIAJE",
    "VESTIMENTA",
]

# Fecha con historial sembrado por `make seed` (dentro del dataset de entrenamiento).
FECHA_CON_HISTORIAL = "2026-07-05"


class VentasForecastUser(HttpUser):
    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        email = f"locust-{uuid.uuid4().hex[:12]}@example.com"
        password = "LocustPass123"
        self.client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password},
            name="/auth/register",
        )
        r = self.client.post(
            "/api/v1/auth/login", json={"email": email, "password": password}, name="/auth/login"
        )
        token = r.json().get("access_token", "")
        self.headers = {"Authorization": f"Bearer {token}"}

    @task(2)
    def health(self) -> None:
        self.client.get("/api/v1/health", name="/health")

    @task(5)
    def predict_day(self) -> None:
        clasificador = random.choice(CLASIFICADORES)
        self.client.post(
            "/api/v1/predictions/day",
            json={"clasificador": clasificador, "fecha": FECHA_CON_HISTORIAL},
            headers=self.headers,
            name="/predictions/day",
        )

    @task(4)
    def predict_day_x(self) -> None:
        clasificador = random.choice(CLASIFICADORES)
        fecha_objetivo = (date.today() + timedelta(days=random.randint(1, 20))).isoformat()
        self.client.post(
            "/api/v1/predictions/day-x",
            json={"clasificador": clasificador, "fecha_objetivo": fecha_objetivo},
            headers=self.headers,
            name="/predictions/day-x",
        )

    @task(2)
    def predict_week(self) -> None:
        clasificador = random.choice(CLASIFICADORES)
        self.client.post(
            "/api/v1/predictions/week",
            json={"clasificador": clasificador, "fecha_inicio": FECHA_CON_HISTORIAL},
            headers=self.headers,
            name="/predictions/week",
        )

    @task(1)
    def predict_range_month(self) -> None:
        clasificador = random.choice(CLASIFICADORES)
        self.client.post(
            "/api/v1/predictions/range",
            json={"clasificador": clasificador, "fecha_inicio": FECHA_CON_HISTORIAL, "dias": 30},
            headers=self.headers,
            name="/predictions/range",
        )

    @task(2)
    def list_clasificadores(self) -> None:
        self.client.get(
            "/api/v1/predictions/clasificadores",
            headers=self.headers,
            name="/predictions/clasificadores",
        )

    @task(1)
    def model_metrics(self) -> None:
        self.client.get("/api/v1/metrics/model", headers=self.headers, name="/metrics/model")
