import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Document, Project, ProjectAccess, Role, User
from app.repositories.interfaces import (
    AccessRepositoryInterface,
    DocumentRepositoryInterface,
    ProjectRepositoryInterface,
    UserRepositoryInterface,
)


class SQLAlchemyUserRepository(UserRepositoryInterface[User]):
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, id_: uuid.UUID) -> User | None:
        return self.db.execute(select(User).where(User.id == id_)).scalar_one_or_none()

    def get_by_login(self, login: str) -> User | None:
        return self.db.execute(select(User).where(User.login == login)).scalar_one_or_none()

    def add(self, user: User) -> User:
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user


class SQLAlchemyProjectRepository(ProjectRepositoryInterface[Project]):
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, id_: uuid.UUID) -> Project | None:
        return self.db.execute(select(Project).where(Project.id == id_)).scalar_one_or_none()

    def list_for_user(self, user_id: uuid.UUID) -> list[Project]:
        stmt = (
            select(Project)
            .join(ProjectAccess, ProjectAccess.project_id == Project.id)
            .where(ProjectAccess.user_id == user_id)
            .options(selectinload(Project.documents))
        )
        return list(self.db.execute(stmt).scalars().all())

    def add(self, name: str, description: str) -> Project:
        project = Project(name=name, description=description)
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def update(self, id_: uuid.UUID, name: str | None, description: str | None) -> Project | None:
        project = self.db.execute(select(Project).where(Project.id == id_)).scalar_one_or_none()
        if project:
            if name is not None:
                project.name = name
            if description is not None:
                project.description = description
            self.db.commit()
            self.db.refresh(project)
        return project

    def delete(self, instance: Project) -> None:
        self.db.delete(instance)
        self.db.commit()


class SQLAlchemyAccessRepository(AccessRepositoryInterface[ProjectAccess]):
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_for_user_and_project(
        self, user_id: uuid.UUID, project_id: uuid.UUID
    ) -> ProjectAccess | None:
        stmt = select(ProjectAccess).where(
            ProjectAccess.user_id == user_id, ProjectAccess.project_id == project_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def grant(self, user_id: uuid.UUID, project_id: uuid.UUID, role: Role) -> ProjectAccess:
        access = ProjectAccess(user_id=user_id, project_id=project_id, role=role)
        self.db.add(access)
        self.db.commit()
        self.db.refresh(access)
        return access


class SQLAlchemyDocumentRepository(DocumentRepositoryInterface[Document]):
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(
        self, project_id: uuid.UUID, filename: str, content_type: str, s3_key: str, size_bytes: int
    ) -> Document:
        doc = Document(
            project_id=project_id,
            filename=filename,
            content_type=content_type,
            s3_key=s3_key,
            size_bytes=size_bytes,
        )
        self.db.add(doc)
        self.db.commit()
        self.db.refresh(doc)
        return doc

    def get(self, id_: uuid.UUID) -> Document | None:
        return self.db.execute(select(Document).where(Document.id == id_)).scalar_one_or_none()

    def delete(self, instance: Document) -> None:
        self.db.delete(instance)
        self.db.commit()

    def list_for_project(self, project_id: uuid.UUID) -> list[Document]:
        return list(
            self.db.execute(select(Document).where(Document.project_id == project_id))
            .scalars()
            .all()
        )

    def total_size_for_project(self, project_id: uuid.UUID) -> int:
        stmt = select(func.coalesce(func.sum(Document.size_bytes), 0)).where(
            Document.project_id == project_id
        )
        return int(self.db.execute(stmt).scalar_one())
