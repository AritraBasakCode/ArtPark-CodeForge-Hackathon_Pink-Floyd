import os
from app.core.db import Base, engine
from app.models.plan import PlanRecord


def init():
    os.makedirs("/app/data", exist_ok=True)
    Base.metadata.create_all(bind=engine)
    print("DB initialized.")


if __name__ == "__main__":
    init()