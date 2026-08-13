import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

if TYPE_CHECKING:
    from app.models import Project, User


class Role(enum.StrEnum):
    OWNER = "OWNER"
    PARTICIPANT = "PARTICIPANT"


class ProjectAccess(Base):
    __tablename__ = "project_access"
    __table_args__ = (UniqueConstraint("user_id", "project_id", name="uq_user_project"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))

    role: Mapped[Role] = mapped_column(
        Enum(Role), default=Role.PARTICIPANT, server_default="PARTICIPANT"
    )

    user: Mapped["User"] = relationship(back_populates="accesses")
    project: Mapped["Project"] = relationship(back_populates="accesses")
