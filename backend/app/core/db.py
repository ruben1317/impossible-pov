from sqlmodel import SQLModel, Session, create_engine
from app.models.project import Project  # noqa: F401
from app.models.cost import GenerationCost  # noqa: F401
from app.models.setting import RuntimeSetting  # noqa: F401
from app.models.idea_history import IdeaHistory  # noqa: F401
from .config import get_env

engine = create_engine(get_env().database_url, echo=False)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
