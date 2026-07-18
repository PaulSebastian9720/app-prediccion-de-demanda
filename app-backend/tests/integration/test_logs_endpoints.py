"""Tests de integracion de los endpoints de logs y metricas (solo administradores)."""

from httpx import AsyncClient


async def test_requests_logs_forbidden_for_normal_user(
    client: AsyncClient, user_headers: dict[str, str]
) -> None:
    r = await client.get("/logs/requests", headers=user_headers)
    assert r.status_code == 403


async def test_request_logs_are_recorded_and_visible_to_admin(
    client: AsyncClient, user_headers: dict[str, str], admin_headers: dict[str, str]
) -> None:
    # Genera al menos un request de por medio (el propio /auth/me del fixture ya cuenta,
    # pero disparamos uno explicito para tener un path predecible que buscar).
    await client.get("/predictions/clasificadores", headers=user_headers)

    r = await client.get(
        "/logs/requests", params={"path": "clasificadores", "page_size": 10}, headers=admin_headers
    )
    assert r.status_code == 200
    body = r.json()
    assert body["meta"]["total_items"] >= 1
    assert any("clasificadores" in item["path"] for item in body["items"])


async def test_inference_log_events_endpoint(
    client: AsyncClient,
    user_headers: dict[str, str],
    admin_headers: dict[str, str],
    seeded_sales_history: None,
) -> None:
    predict = await client.post(
        "/predictions/day",
        json={"clasificador": "PASEO_SUJECION", "fecha": "2026-07-02"},
        headers=user_headers,
    )
    inference_log_id = predict.json()["inference_log_id"]

    r = await client.get(f"/logs/inferences/{inference_log_id}/events", headers=admin_headers)
    assert r.status_code == 200
    stages = [e["stage"] for e in r.json()]
    assert stages == [
        "fetch_history",
        "build_features",
        "encode_align",
        "model_inference",
        "postprocess",
        "explanation",  # generacion de la explicacion XAI (solo /predictions/day)
    ]


async def test_inference_log_events_not_found_returns_404(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    fake_id = "00000000-0000-0000-0000-000000000000"
    r = await client.get(f"/logs/inferences/{fake_id}/events", headers=admin_headers)
    assert r.status_code == 404


async def test_service_metrics_requires_admin(
    client: AsyncClient, user_headers: dict[str, str], admin_headers: dict[str, str]
) -> None:
    forbidden = await client.get("/metrics/service", headers=user_headers)
    assert forbidden.status_code == 403

    ok = await client.get("/metrics/service", headers=admin_headers)
    assert ok.status_code == 200
    assert "total_requests_24h" in ok.json()


async def test_model_metrics_available_to_any_authenticated_user(
    client: AsyncClient, user_headers: dict[str, str]
) -> None:
    r = await client.get("/metrics/model", headers=user_headers)
    assert r.status_code == 200
    assert r.json()["r2"] is not None
