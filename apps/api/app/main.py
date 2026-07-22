from __future__ import annotations

from fastapi import FastAPI

from app.api.routes import router


def create_app() -> FastAPI:
    app = FastAPI(
        title="EduDocs AI API",
        version="0.1.0",
        description="API inicial para ingestão e consulta de documentos educacionais fictícios.",
    )
    app.include_router(router)
    return app


app = create_app()
