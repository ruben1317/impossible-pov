from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_env, get_config
from app.core.db import init_db

app = FastAPI(title=get_config().get("app.name", "IMPOSSIBLE POV Content Studio"))
origins = [x.strip() for x in get_env().cors_origins.split(",") if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(router)

@app.on_event("startup")
def startup():
    init_db()
