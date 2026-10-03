"""API server:  uv run uvicorn app.main:app --reload"""

from fastapi import FastAPI

from app.api import auth, people, viewpoints

app = FastAPI(title="Their Take API")
app.include_router(viewpoints.router)
app.include_router(people.router)
app.include_router(auth.router)


@app.get("/api/health")
def health():
    return {"ok": True}
