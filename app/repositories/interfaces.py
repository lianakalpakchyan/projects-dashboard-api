import uuid
from abc import ABC, abstractmethod
from typing import Any


class UserRepositoryInterface[T](ABC):
    @abstractmethod
    def get(self, id_: uuid.UUID) -> T | None: ...

    @abstractmethod
    def get_by_login(self, login: str) -> T | None: ...

    @abstractmethod
    def add(self, user: T) -> T: ...


class ProjectRepositoryInterface[T](ABC):
    @abstractmethod
    def get(self, id_: uuid.UUID) -> T | None: ...

    @abstractmethod
    def list_for_user(self, user_id: uuid.UUID) -> list[T]: ...

    @abstractmethod
    def add(self, name: str, description: str) -> T: ...

    @abstractmethod
    def update(self, id_: uuid.UUID, name: str | None, description: str | None) -> T | None: ...

    @abstractmethod
    def delete(self, instance: T) -> None: ...


class AccessRepositoryInterface[T](ABC):
    @abstractmethod
    def get_for_user_and_project(self, user_id: uuid.UUID, project_id: uuid.UUID) -> T | None: ...

    @abstractmethod
    def grant(self, user_id: uuid.UUID, project_id: uuid.UUID, role: Any) -> T: ...


class DocumentRepositoryInterface[T](ABC):
    @abstractmethod
    def add(
        self, project_id: uuid.UUID, filename: str, content_type: str, s3_key: str, size_bytes: int
    ) -> T: ...

    @abstractmethod
    def get(self, id_: uuid.UUID) -> T | None: ...

    @abstractmethod
    def delete(self, instance: T) -> None: ...

    @abstractmethod
    def list_for_project(self, project_id: uuid.UUID) -> list[T]: ...

    @abstractmethod
    def total_size_for_project(self, project_id: uuid.UUID) -> int: ...
