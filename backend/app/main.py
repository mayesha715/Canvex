from fastapi import FastAPI

from app.routers.auth import router as auth_router
from app.routers.channels import router as channels_router

app = FastAPI(title="Canvex API")

app.include_router(auth_router)
app.include_router(channels_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
