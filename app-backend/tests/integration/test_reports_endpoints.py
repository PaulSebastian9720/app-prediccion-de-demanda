"""Tests de integracion de los reportes PDF y del stub de reentrenamiento.

Nota: estos tests generan un PDF real (WeasyPrint) y, si `OPENAI_API_KEY` esta
configurada en el entorno de test, tambien llaman al LLM real para el resumen
ejecutivo (con fallback automatico si falla) — no se mockea, para validar el
flujo completo tal como lo usa un usuario.
"""

from httpx import AsyncClient


async def test_weekly_report_requires_admin(
    client: AsyncClient,
    user_headers: dict[str, str],
    seeded_sales_history: None,
    seeded_products_and_stock: None,
) -> None:
    r = await client.get(
        "/reports/weekly", params={"fecha_inicio": "2026-07-15"}, headers=user_headers
    )
    assert r.status_code == 403


async def test_weekly_report_returns_valid_pdf(
    client: AsyncClient,
    admin_headers: dict[str, str],
    seeded_sales_history: None,
    seeded_products_and_stock: None,
) -> None:
    r = await client.get(
        "/reports/weekly", params={"fecha_inicio": "2026-07-15"}, headers=admin_headers
    )
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")
    assert len(r.content) > 1000
    assert "attachment" in r.headers["content-disposition"]


async def test_monthly_report_returns_valid_pdf(
    client: AsyncClient,
    admin_headers: dict[str, str],
    seeded_sales_history: None,
    seeded_products_and_stock: None,
) -> None:
    r = await client.get(
        "/reports/monthly", params={"fecha_inicio": "2026-07-15"}, headers=admin_headers
    )
    assert r.status_code == 200
    assert r.content.startswith(b"%PDF")


async def test_retraining_trigger_creates_pending_job(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await client.post("/retraining/trigger", headers=admin_headers)
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "pending"
    assert body["id"]


async def test_retraining_trigger_requires_admin(
    client: AsyncClient, user_headers: dict[str, str]
) -> None:
    r = await client.post("/retraining/trigger", headers=user_headers)
    assert r.status_code == 403
