from fastapi import FastAPI

from app.api.routers import auth

app = FastAPI(title="Projects Dashboard API", version="0.1.0")

app.include_router(auth.router)


@app.get("/health", tags=["system"])
def health_check() -> dict[str, str]:
    return {"status": "ok"}
