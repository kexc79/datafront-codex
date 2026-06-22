from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, SessionLocal, engine
from app.routers import admin, auth, engineer
from app.seed import bootstrap


def create_app() -> FastAPI:
    app = FastAPI(title="DataFront API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    app.include_router(engineer.router, prefix="/api/v1")

    @app.on_event("startup")
    def startup() -> None:
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        try:
            bootstrap(db)
        finally:
            db.close()

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    return app


app = create_app()

