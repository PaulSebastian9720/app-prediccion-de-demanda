"""Tests de integracion del catalogo de productos y del inventario/stock."""

from httpx import AsyncClient


async def test_list_products_requires_auth(client: AsyncClient) -> None:
    r = await client.get("/products/")
    assert r.status_code in (401, 403)


async def test_list_products(
    client: AsyncClient, user_headers: dict[str, str], seeded_products_and_stock: None
) -> None:
    r = await client.get("/products/", headers=user_headers)
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 9
    assert all(p["precio_venta"] == 10.0 for p in body)


async def test_update_product_requires_admin(
    client: AsyncClient, user_headers: dict[str, str], seeded_products_and_stock: None
) -> None:
    r = await client.patch(
        "/products/PASEO_SUJECION", json={"precio_venta": 15.0}, headers=user_headers
    )
    assert r.status_code == 403


async def test_update_product_as_admin(
    client: AsyncClient, admin_headers: dict[str, str], seeded_products_and_stock: None
) -> None:
    r = await client.patch(
        "/products/PASEO_SUJECION", json={"precio_venta": 15.0}, headers=admin_headers
    )
    assert r.status_code == 200
    assert r.json()["precio_venta"] == 15.0
    assert r.json()["costo_reposicion"] == 6.0  # no tocado, sigue el valor sembrado


async def test_list_stock(
    client: AsyncClient, user_headers: dict[str, str], seeded_products_and_stock: None
) -> None:
    r = await client.get("/inventory/", headers=user_headers)
    assert r.status_code == 200
    assert len(r.json()) == 9


async def test_upsert_stock_requires_admin(
    client: AsyncClient, user_headers: dict[str, str]
) -> None:
    r = await client.post(
        "/inventory/",
        json={"registros": [{"clasificador": "JUGUETES", "stock_actual": 5, "stock_minimo": 1}]},
        headers=user_headers,
    )
    assert r.status_code == 403


async def test_upsert_stock_updates_existing_row(
    client: AsyncClient, admin_headers: dict[str, str], seeded_products_and_stock: None
) -> None:
    r = await client.post(
        "/inventory/",
        json={"registros": [{"clasificador": "JUGUETES", "stock_actual": 5, "stock_minimo": 1}]},
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["rows_upserted"] == 1
    assert body["rows_rejected"] == 0

    r = await client.get("/inventory/", headers=admin_headers)
    fila = next(row for row in r.json() if row["clasificador"] == "JUGUETES")
    assert fila["stock_actual"] == 5
    assert fila["stock_minimo"] == 1


async def test_upsert_stock_unknown_clasificador_rejected_as_row_error(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    """Un clasificador desconocido se reporta como fila rechazada (no aborta
    el lote completo) -- mismo criterio que `/sales-history/`, para que la
    subida de archivo tenga exito parcial en vez de un 422 duro."""
    r = await client.post(
        "/inventory/",
        json={"registros": [{"clasificador": "NO_EXISTE", "stock_actual": 5, "stock_minimo": 1}]},
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["rows_upserted"] == 0
    assert body["rows_rejected"] == 1
    assert "NO_EXISTE" in body["errors"][0]["reason"]


async def test_upload_stock_csv_partial_success(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    csv_content = (
        b"clasificador,stock_actual,stock_minimo\n"
        b"JUGUETES,12,3\n"
        b"NO_EXISTE,5,1\n"
    )
    r = await client.post(
        "/inventory/upload",
        files={"file": ("stock.csv", csv_content, "text/csv")},
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["rows_received"] == 2
    assert body["rows_upserted"] == 1
    assert body["rows_rejected"] == 1


async def test_upload_stock_csv_rejects_decimal_stock(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    csv_content = b"clasificador,stock_actual,stock_minimo\nJUGUETES,12.5,3\n"
    r = await client.post(
        "/inventory/upload",
        files={"file": ("stock.csv", csv_content, "text/csv")},
        headers=admin_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["rows_upserted"] == 0
    assert body["rows_rejected"] == 1


async def test_download_stock_template_includes_valid_clasificadores(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    r = await client.get("/inventory/upload/template", headers=admin_headers)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    lineas = r.text.strip().splitlines()
    assert lineas[0] == "clasificador,stock_actual,stock_minimo"
    assert len(lineas) > 1
    assert "PASEO_SUJECION" in r.text


async def test_download_stock_template_prefills_existing_stock(
    client: AsyncClient, admin_headers: dict[str, str], seeded_products_and_stock: None
) -> None:
    """A diferencia de una plantilla en blanco, esta sirve para ACTUALIZAR --
    debe traer el stock ya cargado, no ceros, para que el usuario solo edite
    lo que cambio."""
    r = await client.get("/inventory/upload/template", headers=admin_headers)
    assert r.status_code == 200
    assert "JUGUETES,50,10" in r.text
