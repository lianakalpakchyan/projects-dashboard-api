import uuid
from typing import Any

from app.models import Role
from app.repositories.interfaces import (
    AccessRepositoryInterface,
    DocumentRepositoryInterface,
    ProjectRepositoryInterface,
    UserRepositoryInterface,
)


class RawSQLUserRepository(UserRepositoryInterface):
    def __init__(self, conn: Any) -> None:
        self.conn = conn

    def get(self, id_: uuid.UUID) -> dict[str, Any] | None:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, login, hashed_password, created_at FROM users WHERE id = %s",
                (str(id_),),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": uuid.UUID(row[0]),
                "login": row[1],
                "hashed_password": row[2],
                "created_at": row[3],
            }

    def get_by_login(self, login: str) -> dict[str, Any] | None:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, login, hashed_password, created_at FROM users WHERE login = %s",
                (login,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": uuid.UUID(row[0]),
                "login": row[1],
                "hashed_password": row[2],
                "created_at": row[3],
            }

    def add(self, user: dict[str, Any]) -> dict[str, Any]:
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (id, login, hashed_password) VALUES (%s, %s, %s) "
                "RETURNING id, login, hashed_password, created_at",
                (str(user["id"]), user["login"], user["hashed_password"]),
            )
            row = cur.fetchone()
            self.conn.commit()
            return {
                "id": uuid.UUID(row[0]),
                "login": row[1],
                "hashed_password": row[2],
                "created_at": row[3],
            }


class RawSQLProjectRepository(ProjectRepositoryInterface):
    def __init__(self, conn: Any) -> None:
        self.conn = conn

    def get(self, id_: uuid.UUID) -> dict[str, Any] | None:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, description, storage_bytes, over_quota, created_at, updated_at "
                "FROM projects WHERE id = %s",
                (str(id_),),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": uuid.UUID(row[0]),
                "name": row[1],
                "description": row[2],
                "storage_bytes": row[3],
                "over_quota": row[4],
                "created_at": row[5],
                "updated_at": row[6],
            }

    def list_for_user(self, user_id: uuid.UUID) -> list[dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT p.id, p.name, p.description, p.storage_bytes, "
                "p.over_quota, p.created_at, p.updated_at "
                "FROM projects p "
                "JOIN project_access pa ON p.id = pa.project_id "
                "WHERE pa.user_id = %s",
                (str(user_id),),
            )
            rows = cur.fetchall()
            results = []
            for r in rows:
                p_id = uuid.UUID(r[0])
                results.append(
                    {
                        "id": p_id,
                        "name": r[1],
                        "description": r[2],
                        "storage_bytes": r[3],
                        "over_quota": r[4],
                        "created_at": r[5],
                        "updated_at": r[6],
                        "documents": self._list_docs_internal(p_id),
                    }
                )
            return results

    def _list_docs_internal(self, project_id: uuid.UUID) -> list[dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, filename, content_type, size_bytes, uploaded_at "
                "FROM documents WHERE project_id = %s",
                (str(project_id),),
            )
            return [
                {
                    "id": uuid.UUID(r[0]),
                    "filename": r[1],
                    "content_type": r[2],
                    "size_bytes": r[3],
                    "uploaded_at": r[4],
                }
                for r in cur.fetchall()
            ]

    def add(self, name: str, description: str) -> dict[str, Any]:
        id_ = uuid.uuid4()
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO projects (id, name, description) VALUES (%s, %s, %s) "
                "RETURNING id, name, description, storage_bytes, "
                "over_quota, created_at, updated_at",
                (str(id_), name, description),
            )
            row = cur.fetchone()
            self.conn.commit()
            return {
                "id": uuid.UUID(row[0]),
                "name": row[1],
                "description": row[2],
                "storage_bytes": row[3],
                "over_quota": row[4],
                "created_at": row[5],
                "updated_at": row[6],
            }

    def update(self, id_: uuid.UUID, name: str | None, description: str | None) -> dict[str, Any]:
        with self.conn.cursor() as cur:
            if name is not None and description is not None:
                cur.execute(
                    "UPDATE projects SET name = %s, description = %s, "
                    "updated_at = NOW() WHERE id = %s RETURNING id, name, description, "
                    "storage_bytes, over_quota, created_at, updated_at",
                    (name, description, str(id_)),
                )
            elif name is not None:
                cur.execute(
                    "UPDATE projects SET name = %s, updated_at = NOW() "
                    "WHERE id = %s RETURNING id, name, description, "
                    "storage_bytes, over_quota, created_at, updated_at",
                    (name, str(id_)),
                )
            elif description is not None:
                cur.execute(
                    "UPDATE projects SET description = %s, updated_at = NOW() "
                    "WHERE id = %s RETURNING id, name, description, storage_bytes, "
                    "over_quota, created_at, updated_at",
                    (description, str(id_)),
                )
            row = cur.fetchone()
            self.conn.commit()
            return {
                "id": uuid.UUID(row[0]),
                "name": row[1],
                "description": row[2],
                "storage_bytes": row[3],
                "over_quota": row[4],
                "created_at": row[5],
                "updated_at": row[6],
            }

    def delete(self, instance: dict[str, Any]) -> None:
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM projects WHERE id = %s", (str(instance["id"]),))
            self.conn.commit()


class RawSQLAccessRepository(AccessRepositoryInterface):
    def __init__(self, conn: Any) -> None:
        self.conn = conn

    def get_for_user_and_project(
        self, user_id: uuid.UUID, project_id: uuid.UUID
    ) -> dict[str, Any] | None:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, user_id, project_id, role FROM project_access "
                "WHERE user_id = %s AND project_id = %s",
                (str(user_id), str(project_id)),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": uuid.UUID(row[0]),
                "user_id": uuid.UUID(row[1]),
                "project_id": uuid.UUID(row[2]),
                "role": row[3],
            }

    def grant(self, user_id: uuid.UUID, project_id: uuid.UUID, role: Role) -> dict[str, Any]:
        id_ = uuid.uuid4()
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO project_access (id, user_id, "
                "project_id, role) VALUES (%s, %s, %s, %s) "
                "RETURNING id, user_id, project_id, role",
                (str(id_), str(user_id), str(project_id), str(role)),
            )
            row = cur.fetchone()
            self.conn.commit()
            return {
                "id": uuid.UUID(row[0]),
                "user_id": uuid.UUID(row[1]),
                "project_id": uuid.UUID(row[2]),
                "role": row[3],
            }


class RawSQLDocumentRepository(DocumentRepositoryInterface):
    def __init__(self, conn: Any) -> None:
        self.conn = conn

    def add(
        self, project_id: uuid.UUID, filename: str, content_type: str, s3_key: str, size_bytes: int
    ) -> dict[str, Any]:
        id_ = uuid.uuid4()
        with self.conn.cursor() as cur:
            cur.execute(
                "INSERT INTO documents (id, project_id, filename, "
                "content_type, s3_key, size_bytes) "
                "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id, "
                "filename, content_type, size_bytes, uploaded_at",
                (str(id_), str(project_id), filename, content_type, s3_key, size_bytes),
            )
            row = cur.fetchone()
            self.conn.commit()
            return {
                "id": uuid.UUID(row[0]),
                "filename": row[1],
                "content_type": row[2],
                "size_bytes": row[3],
                "uploaded_at": row[4],
            }

    def get(self, id_: uuid.UUID) -> dict[str, Any] | None:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, project_id, filename, "
                "content_type, s3_key, size_bytes, uploaded_at "
                "FROM documents WHERE id = %s",
                (str(id_),),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "id": uuid.UUID(row[0]),
                "project_id": uuid.UUID(row[1]),
                "filename": row[2],
                "content_type": row[3],
                "s3_key": row[4],
                "size_bytes": row[5],
                "uploaded_at": row[6],
            }

    def delete(self, instance: dict[str, Any]) -> None:
        with self.conn.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE id = %s", (str(instance["id"]),))
            self.conn.commit()

    def list_for_project(self, project_id: uuid.UUID) -> list[dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, filename, content_type, size_bytes, "
                "uploaded_at FROM documents WHERE project_id = %s",
                (str(project_id),),
            )
            return [
                {
                    "id": uuid.UUID(r[0]),
                    "filename": r[1],
                    "content_type": r[2],
                    "size_bytes": r[3],
                    "uploaded_at": r[4],
                }
                for r in cur.fetchall()
            ]

    def total_size_for_project(self, project_id: uuid.UUID) -> int:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(SUM(size_bytes), 0) FROM documents WHERE project_id = %s",
                (str(project_id),),
            )
            return int(cur.fetchone()[0])
