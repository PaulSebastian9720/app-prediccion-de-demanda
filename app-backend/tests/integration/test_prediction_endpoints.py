"""Tests de integracion de los endpoints de prediccion (day/day-x/week/range).

Los valores esperados son los mismos calculados en `notebooks/03_prediccion.ipynb`
para `PASEO_SUJECION` (ver tambien `tests/unit/test_features.py`).

Nota sobre `/predictions/day` y la explicacion XAI: si `OPENAI_API_KEY` esta
configurada en el entorno de test, la llamada real al LLM se hace tal cual
(no se mockea — mismo criterio que `test_reports_endpoints.py`), con fallback
automatico a la plantilla si falla. Por eso los tests de aqui abajo solo
verifican invariantes estructurales (que `explicacion` exista, que
`generado_por` sea uno de los dos valores validos, que los factores cuadren
con la prediccion) y nunca el texto exacto del resumen.
"""

from datetime import date, timedelta

import pytest
from httpx import AsyncClient

from app.services import explanation_service


async def test_predict_day_matches_notebook_reference(
    client: AsyncClient, user_headers: dict[str, str], seeded_sales_history: None
) -> None:
    r = await client.post(
        "/predictions/day",
        json={"clasificador": "PASEO_SUJECION", "fecha": "2026-07-02"},
        headers=user_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["cantidad_predicha"] == 17
    assert body["dias_historial_usados"] == 21
    assert body["inference_log_id"]


async def test_predict_week_matches_notebook_reference(
    client: AsyncClient, user_headers: dict[str, str], seeded_sales_history: None
) -> None:
    r = await client.post(
        "/predictions/week",
        json={"clasificador": "PASEO_SUJECION", "fecha_inicio": "2026-07-02"},
        headers=user_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["dias"] == 7
    assert len(body["predicciones_diarias"]) == 7
    assert body["total_periodo"] == 214


async def test_predict_range_30_dias(
    client: AsyncClient, user_headers: dict[str, str], seeded_sales_history: None
) -> None:
    r = await client.post(
        "/predictions/range",
        json={"clasificador": "PASEO_SUJECION", "fecha_inicio": "2026-07-09", "dias": 30},
        headers=user_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["dias"] == 30
    assert len(body["predicciones_diarias"]) == 30
    assert body["total_periodo"] == sum(d["cantidad"] for d in body["predicciones_diarias"])


async def test_predict_day_without_history_returns_422(
    client: AsyncClient, user_headers: dict[str, str]
) -> None:
    r = await client.post(
        "/predictions/day",
        json={"clasificador": "PASEO_SUJECION", "fecha": "2026-07-02"},
        headers=user_headers,
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INSUFFICIENT_HISTORY"


async def test_predict_day_unknown_clasificador_returns_422(
    client: AsyncClient, user_headers: dict[str, str], seeded_sales_history: None
) -> None:
    r = await client.post(
        "/predictions/day",
        json={"clasificador": "NO_EXISTE", "fecha": "2026-07-02"},
        headers=user_headers,
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "UNKNOWN_CLASSIFIER"


async def test_predict_day_x_individual_and_accumulated_are_coherent(
    client: AsyncClient, user_headers: dict[str, str], seeded_sales_history: None
) -> None:
    fecha_objetivo = date.today() + timedelta(days=10)
    r = await client.post(
        "/predictions/day-x",
        json={"clasificador": "PASEO_SUJECION", "fecha_objetivo": fecha_objetivo.isoformat()},
        headers=user_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["fecha_objetivo"] == fecha_objetivo.isoformat()
    suma = sum(d["cantidad"] for d in body["predicciones_diarias"])
    assert suma == body["prediccion_acumulada"]
    assert body["predicciones_diarias"][-1]["cantidad"] == body["prediccion_individual"]
    assert body["dias_proyectados"] == len(body["predicciones_diarias"])


async def test_predict_day_x_past_date_does_not_chain(
    client: AsyncClient, user_headers: dict[str, str], seeded_sales_history: None
) -> None:
    r = await client.post(
        "/predictions/day-x",
        json={"clasificador": "PASEO_SUJECION", "fecha_objetivo": "2026-07-02"},
        headers=user_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["dias_proyectados"] == 1
    assert body["prediccion_individual"] == 17
    assert body["prediccion_acumulada"] == 17


async def test_predict_day_x_matches_plain_day_for_far_future_date(
    client: AsyncClient, user_headers: dict[str, str], seeded_sales_history: None
) -> None:
    """El fix de huecos de calendario: /day y /day-x deben coincidir para la
    misma fecha lejana, ya que ambos rellenan el hueco con la misma cadena."""
    fecha_objetivo = date.today() + timedelta(days=12)

    r1 = await client.post(
        "/predictions/day-x",
        json={"clasificador": "PASEO_SUJECION", "fecha_objetivo": fecha_objetivo.isoformat()},
        headers=user_headers,
    )
    r2 = await client.post(
        "/predictions/day",
        json={"clasificador": "PASEO_SUJECION", "fecha": fecha_objetivo.isoformat()},
        headers=user_headers,
    )
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["prediccion_individual"] == r2.json()["cantidad_predicha"]


async def test_predict_day_x_unknown_clasificador_returns_422(
    client: AsyncClient, user_headers: dict[str, str], seeded_sales_history: None
) -> None:
    r = await client.post(
        "/predictions/day-x",
        json={"clasificador": "NO_EXISTE", "fecha_objetivo": "2026-08-01"},
        headers=user_headers,
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "UNKNOWN_CLASSIFIER"


async def test_list_clasificadores(client: AsyncClient, user_headers: dict[str, str]) -> None:
    r = await client.get("/predictions/clasificadores", headers=user_headers)
    assert r.status_code == 200
    assert "PASEO_SUJECION" in r.json()["clasificadores"]
    assert len(r.json()["clasificadores"]) == 9


async def test_predict_day_includes_explanation(
    client: AsyncClient, user_headers: dict[str, str], seeded_sales_history: None
) -> None:
    r = await client.post(
        "/predictions/day",
        json={"clasificador": "PASEO_SUJECION", "fecha": "2026-07-02"},
        headers=user_headers,
    )
    assert r.status_code == 200
    explicacion = r.json()["explicacion"]
    assert explicacion is not None
    assert explicacion["generado_por"] in ("llm", "fallback")
    assert explicacion["resumen"].strip() != ""
    assert isinstance(explicacion["factores"], list)
    for factor in explicacion["factores"]:
        assert factor["direccion"] in ("sube", "baja")
        assert factor["impacto_unidades"] != 0
    # margen_error_habitual es None hasta que haya predicciones DAY vencidas
    # contra las que comparar (no las hay en un test recien seedeado).
    assert explicacion["margen_error_habitual"] is None


async def test_predict_week_and_range_include_period_explanation(
    client: AsyncClient, user_headers: dict[str, str], seeded_sales_history: None
) -> None:
    """/week y /range generan UNA sola explicacion para el periodo completo
    (no una por dia): `factores` viene vacio y `dia_similar` es None -- a
    diferencia de /day y /day-x, que si calculan factores por perturbacion.
    Una unica llamada al LLM por periodo, sin importar `dias`."""
    r_week = await client.post(
        "/predictions/week",
        json={"clasificador": "PASEO_SUJECION", "fecha_inicio": "2026-07-02"},
        headers=user_headers,
    )
    r_range = await client.post(
        "/predictions/range",
        json={"clasificador": "PASEO_SUJECION", "fecha_inicio": "2026-07-02", "dias": 10},
        headers=user_headers,
    )
    for r in (r_week, r_range):
        assert r.status_code == 200
        explicacion = r.json()["explicacion"]
        assert explicacion is not None
        assert explicacion["factores"] == []
        assert explicacion["dia_similar"] is None
        assert explicacion["resumen"].strip() != ""
        assert explicacion["generado_por"] in ("llm", "fallback")


async def test_prediction_history_lists_all_horizons(
    client: AsyncClient, user_headers: dict[str, str], seeded_sales_history: None
) -> None:
    """/day y /week generan explicacion cada uno a su manera (por dia vs. en
    conjunto) y ambos deben aparecer en el historial -- no solo el /day."""
    day_r = await client.post(
        "/predictions/day",
        json={"clasificador": "PASEO_SUJECION", "fecha": "2026-07-02"},
        headers=user_headers,
    )
    week_r = await client.post(
        "/predictions/week",
        json={"clasificador": "PASEO_SUJECION", "fecha_inicio": "2026-07-02"},
        headers=user_headers,
    )

    r = await client.get(
        "/predictions/history", params={"clasificador": "PASEO_SUJECION"}, headers=user_headers
    )
    assert r.status_code == 200
    body = r.json()
    assert body["meta"]["total_items"] == 2
    by_id = {item["inference_log_id"]: item for item in body["items"]}

    day_item = by_id[day_r.json()["inference_log_id"]]
    assert day_item["horizonte"] == "day"
    assert day_item["cantidad_predicha"] == 17
    assert day_item["resumen"]

    week_item = by_id[week_r.json()["inference_log_id"]]
    assert week_item["horizonte"] == "week"
    assert week_item["cantidad_predicha"] == week_r.json()["total_periodo"]
    assert week_item["resumen"]


async def test_prediction_history_requires_authentication(client: AsyncClient) -> None:
    r = await client.get("/predictions/history")
    assert r.status_code in (401, 403)  # mismo criterio que test_products_inventory_endpoints.py


async def test_prediction_history_detail_matches_day_response(
    client: AsyncClient, user_headers: dict[str, str], seeded_sales_history: None
) -> None:
    day_r = await client.post(
        "/predictions/day",
        json={"clasificador": "PASEO_SUJECION", "fecha": "2026-07-02"},
        headers=user_headers,
    )
    inference_log_id = day_r.json()["inference_log_id"]

    r = await client.get(f"/predictions/history/{inference_log_id}", headers=user_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["cantidad_predicha"] == 17
    assert body["explicacion"]["generado_por"] == day_r.json()["explicacion"]["generado_por"]
    assert body["explicacion"]["resumen"] == day_r.json()["explicacion"]["resumen"]


async def test_prediction_history_detail_404_for_unknown_id(
    client: AsyncClient, user_headers: dict[str, str]
) -> None:
    r = await client.get(
        "/predictions/history/00000000-0000-0000-0000-000000000000", headers=user_headers
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


async def test_predict_day_survives_explanation_failure(
    client: AsyncClient,
    user_headers: dict[str, str],
    seeded_sales_history: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regresion: si la explicacion falla al GENERARSE (p.ej. la tabla
    `prediction_explanations` no existe todavia por una migracion pendiente),
    la prediccion debe seguir respondiendo 200 con el numero correcto y
    `explicacion: null` -- nunca un 500. La explicacion y el `InferenceLog` se
    persisten en transacciones SEPARADAS (ver `_persist_explanation`)
    precisamente para que un fallo aqui no deje el `inference_log_id`
    devuelto apuntando a un objeto con atributos expirados por un rollback
    ajeno (`sqlalchemy.exc.MissingGreenlet`)."""

    async def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("fallo simulado: prediction_explanations no existe")

    monkeypatch.setattr(explanation_service, "generar_explicacion", _boom)

    r = await client.post(
        "/predictions/day",
        json={"clasificador": "PASEO_SUJECION", "fecha": "2026-07-02"},
        headers=user_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["cantidad_predicha"] == 17
    assert body["inference_log_id"]
    assert body["explicacion"] is None


async def test_predict_day_x_survives_explanation_failure(
    client: AsyncClient,
    user_headers: dict[str, str],
    seeded_sales_history: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("fallo simulado: prediction_explanations no existe")

    monkeypatch.setattr(explanation_service, "generar_explicacion", _boom)

    fecha_objetivo = date.today() + timedelta(days=5)
    r = await client.post(
        "/predictions/day-x",
        json={"clasificador": "PASEO_SUJECION", "fecha_objetivo": fecha_objetivo.isoformat()},
        headers=user_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["inference_log_id"]
    assert body["explicacion"] is None


async def test_predict_day_x_includes_explanation(
    client: AsyncClient, user_headers: dict[str, str], seeded_sales_history: None
) -> None:
    """Desde la perspectiva de quien consulta, 'Dia X' tambien predice un dia
    especifico (aunque internamente encadene desde hoy) -- por eso tambien
    genera explicacion, a diferencia de /week y /range."""
    fecha_objetivo = date.today() + timedelta(days=5)
    r = await client.post(
        "/predictions/day-x",
        json={"clasificador": "PASEO_SUJECION", "fecha_objetivo": fecha_objetivo.isoformat()},
        headers=user_headers,
    )
    assert r.status_code == 200
    explicacion = r.json()["explicacion"]
    assert explicacion is not None
    assert explicacion["generado_por"] in ("llm", "fallback")
    assert explicacion["resumen"].strip() != ""


async def test_prediction_history_includes_day_x_predictions(
    client: AsyncClient, user_headers: dict[str, str], seeded_sales_history: None
) -> None:
    fecha_objetivo = date.today() + timedelta(days=5)
    day_x_r = await client.post(
        "/predictions/day-x",
        json={"clasificador": "PASEO_SUJECION", "fecha_objetivo": fecha_objetivo.isoformat()},
        headers=user_headers,
    )
    inference_log_id = day_x_r.json()["inference_log_id"]

    r = await client.get(
        "/predictions/history", params={"clasificador": "PASEO_SUJECION"}, headers=user_headers
    )
    assert r.status_code == 200
    ids = [item["inference_log_id"] for item in r.json()["items"]]
    assert inference_log_id in ids


async def test_prediction_history_detail_includes_range_prediction(
    client: AsyncClient, user_headers: dict[str, str], seeded_sales_history: None
) -> None:
    """Una prediccion de /week tambien genera su explicacion en conjunto y
    debe poder consultarse en el detalle del historial, igual que /day."""
    week_r = await client.post(
        "/predictions/week",
        json={"clasificador": "PASEO_SUJECION", "fecha_inicio": "2026-07-02"},
        headers=user_headers,
    )
    inference_log_id = week_r.json()["inference_log_id"]

    r = await client.get(f"/predictions/history/{inference_log_id}", headers=user_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["horizonte"] == "week"
    assert body["cantidad_predicha"] == week_r.json()["total_periodo"]
    explicacion = body["explicacion"]
    assert explicacion is not None
    assert explicacion["factores"] == []
    assert explicacion["dia_similar"] is None
    assert explicacion["resumen"]
