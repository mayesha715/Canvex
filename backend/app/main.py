from fastapi import FastAPI

from app.routers.auth import router as auth_router

app = FastAPI(title="Canvex API")

app.include_router(auth_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
