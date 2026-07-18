"""Tests de integracion de la ingesta y consulta del historico de ventas."""

import io

import pandas as pd
from httpx import AsyncClient


async def test_upload_json_requires_admin(
    client: AsyncClient, user_headers: dict[str, str]
) -> None:
    r = await client.post(
        "/sales-history/",
        json={
            "registros": [
                {
                    "clasificador": "JUGUETES",
                    "dia": "2026-07-11",
                    "cantidad_vendida": 10,
                    "precio_medio": 5.0,
                }
            ]
        },
        headers=user_headers,
    )
    assert r.status_code == 403


async def test_upload_json_upserts_and_rejects_unknown_clasificador(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await client.post(
        "/sales-history/",
        json={
            "registros": [
                {
                    "clasificador": "JUGUETES",
                    "dia": "2026-07-11",
                    "cantidad_vendida": 10,
                    "precio_medio": 5.0,
                },
                {
                    "clasificador": "CATEGORIA_INVENTADA",
                    "dia": "2026-07-11",
                    "cantidad_vendida": 1,
                    "precio_medio": 1.0,
                },
            ]
        },
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["rows_received"] == 2
    assert body["rows_upserted"] == 1
    assert body["rows_rejected"] == 1
    assert "CATEGORIA_INVENTADA" in body["errors"][0]["reason"]


async def test_upload_json_upsert_overwrites_existing_row(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    payload = {
        "registros": [
            {
                "clasificador": "JUGUETES",
                "dia": "2026-07-11",
                "cantidad_vendida": 10,
                "precio_medio": 5.0,
            }
        ]
    }
    await client.post("/sales-history/", json=payload, headers=admin_headers)

    payload["registros"][0]["cantidad_vendida"] = 99
    r = await client.post("/sales-history/", json=payload, headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["rows_upserted"] == 1

    listed = await client.get(
        "/sales-history/", params={"clasificador": "JUGUETES"}, headers=admin_headers
    )
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["cantidad_vendida"] == 99


async def test_upload_csv_file(client: AsyncClient, admin_headers: dict[str, str]) -> None:
    df = pd.DataFrame(
        [
            {
                "clasificador": "DESCANSO",
                "dia": "2026-07-11",
                "cantidad_vendida": 4,
                "precio_medio": 12.0,
            }
        ]
    )
    csv_bytes = df.to_csv(index=False).encode("utf-8")

    r = await client.post(
        "/sales-history/upload",
        files={"file": ("ventas.csv", csv_bytes, "text/csv")},
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["rows_upserted"] == 1


async def test_upload_unsupported_extension_returns_422(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await client.post(
        "/sales-history/upload",
        files={"file": ("ventas.txt", b"hola", "text/plain")},
        headers=admin_headers,
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INVALID_FILE"


async def test_upload_xlsx_file(client: AsyncClient, admin_headers: dict[str, str]) -> None:
    df = pd.DataFrame(
        [
            {
                "clasificador": "VESTIMENTA",
                "dia": "2026-07-11",
                "cantidad_vendida": 6,
                "precio_medio": 15.0,
            }
        ]
    )
    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)

    r = await client.post(
        "/sales-history/upload",
        files={
            "file": (
                "ventas.xlsx",
                buf.read(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=admin_headers,
    )
    assert r.status_code == 200
    assert r.json()["rows_upserted"] == 1


async def test_download_sales_template_includes_valid_clasificadores(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await client.get("/sales-history/template", headers=admin_headers)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    lineas = r.text.strip().splitlines()
    assert lineas[0] == "clasificador,dia,cantidad_vendida,precio_medio"
    # Una fila de ejemplo por cada categoria reconocida por el modelo, no solo
    # el encabezado -- asi el usuario ve los nombres EXACTOS que puede usar.
    assert len(lineas) > 1
    assert all(linea.endswith(",0,0.0") for linea in lineas[1:])
    assert "PASEO_SUJECION" in r.text
