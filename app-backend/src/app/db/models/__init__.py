"""Importa todos los modelos ORM para que `Base.metadata` quede completa.

Este import es lo que le permite a Alembic (`env.py`) y a la aplicacion
descubrir todas las tablas sin tener que importarlas una por una en cada
lugar donde se necesite `Base.metadata`.
"""

from app.db.models.inference_log import InferenceLog
from app.db.models.inventory_stock import InventoryStock
from app.db.models.model_version import ModelVersion
from app.db.models.pipeline_event import PipelineEvent
from app.db.models.prediction_explanation import PredictionExplanation
from app.db.models.product import Product
from app.db.models.refresh_token import RefreshToken
from app.db.models.report_generation_log import ReportGenerationLog
from app.db.models.request_log import RequestLog
from app.db.models.retraining_job import RetrainingJob
from app.db.models.sales_history import SalesHistory
from app.db.models.user import User

__all__ = [
    "InferenceLog",
    "InventoryStock",
    "ModelVersion",
    "PipelineEvent",
    "PredictionExplanation",
    "Product",
    "RefreshToken",
    "ReportGenerationLog",
    "RequestLog",
    "RetrainingJob",
    "SalesHistory",
    "User",
]
