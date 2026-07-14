"""Agrega todos los routers de la API v1 en uno solo."""

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    health,
    inventory,
    logs,
    metrics,
    predictions,
    products,
    reports,
    retraining,
    sales_history,
    users,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(predictions.router)
api_router.include_router(sales_history.router)
api_router.include_router(products.router)
api_router.include_router(inventory.router)
api_router.include_router(reports.router)
api_router.include_router(retraining.router)
api_router.include_router(metrics.router)
api_router.include_router(logs.router)
