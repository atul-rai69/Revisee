from fastapi import APIRouter

from src.modules.auth.router import router as auth_router
from src.modules.ai_credentials.router import router as ai_credentials_router
from src.modules.dashboard.router import router as dashboard_router
from src.modules.labels.router import router as labels_router
from src.modules.learning_items.router import router as learning_items_router
from src.modules.mastery.router import router as mastery_router
from src.modules.revisions.router import router as revisions_router


api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(ai_credentials_router)
api_router.include_router(labels_router)
api_router.include_router(learning_items_router)
api_router.include_router(dashboard_router)
api_router.include_router(mastery_router)
api_router.include_router(revisions_router)
