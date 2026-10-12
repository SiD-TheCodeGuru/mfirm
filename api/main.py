from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from api.core.database import connect_to_mongo, close_mongo_connection
from api.routers.auth import router as auth_router
from api.routers.items import router as items_router
from api.routers.purchases import router as purchases_router
from api.routers.stocks import router as stocks_router
from api.routers.expenses import router as expenses_router
from api.routers.batches import router as batches_router
from api.routers.reports import router as reports_router

from api.dependencies import get_active_firm_context

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()

app = FastAPI(
    title="Mushroom Farm ERP API",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register authentication routes
app.include_router(auth_router)
app.include_router(items_router)
app.include_router(purchases_router)
app.include_router(stocks_router)
app.include_router(expenses_router)
app.include_router(batches_router)
app.include_router(reports_router)

@app.get("/health")
async def health_check():
    return {"status": "online", "system": "Mushroom Firm Backend"}

# Verification route testing the Active Firm Resolution
@app.get("/api/v1/context-check")
async def verify_context(context: dict = Depends(get_active_firm_context)):
    return {
        "status": "authorized",
        "active_firm_id": context["firm_id"],
        "caller_role": context["role"],
        "user_id": context["user_id"]
    }