from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db import Base

class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
