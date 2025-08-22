import io
import mimetypes
from typing import Tuple, List

from django.conf import settings
from django.core.files.base import File
from django.core.files.storage import Storage
from django.utils import timezone

try:
    from supabase import create_client  # type: ignore
except Exception:  # pragma: no cover  # noqa: BLE001
    create_client = None  # type: ignore

_supabase_client = None


def _get_client():
    global _supabase_client  # noqa: PLW0603
    if _supabase_client is None:
        if create_client is None:
            raise RuntimeError("supabase package not installed")
        url = getattr(settings, "SUPABASE_PROJECT_URL", "") or getattr(settings, "SUPABASE_URL", "")
        key = (
            getattr(settings, "SUPABASE_SERVICE_ROLE_KEY", None)
            or getattr(settings, "SUPABASE_SERVICE_KEY", None)
            or getattr(settings, "SUPABASE_ANON_KEY", "")
        )
        if not url or not key:
            raise RuntimeError("SUPABASE_PROJECT_URL and service/anon key must be set")
        _supabase_client = create_client(url, key)
    return _supabase_client


class SupabaseMediaStorage(Storage):
    """Django Storage backend for Supabase Storage public buckets."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.bucket: str = getattr(settings, "SUPABASE_BUCKET", "media")
        if not self.bucket:
            raise RuntimeError("SUPABASE_BUCKET must be set")
        base = getattr(settings, "SUPABASE_PROJECT_URL", "") or getattr(settings, "SUPABASE_URL", "")
        if not base:
            raise RuntimeError("SUPABASE_PROJECT_URL (or SUPABASE_URL) must be set to project API URL")
        self.public_base = f"{base.rstrip('/')}/storage/v1/object/public/{self.bucket}"

    def _full_path(self, name: str) -> str:
        return name.lstrip("/")

    def _open(self, name: str, mode: str = "rb") -> File:
        client = _get_client()
        path = self._full_path(name)
        resp = client.storage.from_(self.bucket).download(path)
        data = getattr(resp, "content", None) or resp
        return File(io.BytesIO(data), name=name)

    def _save(self, name: str, content: File) -> str:
        client = _get_client()
        path = self._full_path(name)
        if hasattr(content, "seek"):
            try:
                content.seek(0)
            except Exception:  # noqa: BLE001
                pass
        data = content.read()
        if isinstance(data, str):
            data = data.encode("utf-8")
        # Content type best-effort
        ctype = (
            getattr(content, "content_type", None)
            or mimetypes.guess_type(path)[0]
            or "application/octet-stream"
        )
        # Prefer upload; if it already exists, remove then upload
        storage = client.storage.from_(self.bucket)
        try:
            storage.upload(path, data)
        except Exception:  # noqa: BLE001
            try:
                storage.remove([path])
            except Exception:  # noqa: BLE001
                pass
            storage.upload(path, data)
        return name

    def exists(self, name: str) -> bool:
        client = _get_client()
        path = self._full_path(name)
        from_pos = path.rfind("/")
        prefix = path[:from_pos] if from_pos != -1 else ""
        target = path[from_pos + 1 :] if from_pos != -1 else path
        items = client.storage.from_(self.bucket).list(path=prefix or None)
        for it in items:
            if getattr(it, "name", None) == target:
                return True
        return False

    def url(self, name: str) -> str:
        return f"{self.public_base}/{self._full_path(name)}"

    def delete(self, name: str) -> None:
        client = _get_client()
        path = self._full_path(name)
        client.storage.from_(self.bucket).remove([path])

    # Minimal implementations for abstract methods
    def size(self, name: str) -> int:
        return 0

    def path(self, name: str) -> str:
        raise NotImplementedError("Supabase storage has no local path")

    def listdir(self, path: str) -> Tuple[List[str], List[str]]:
        client = _get_client()
        files: List[str] = []
        dirs: List[str] = []
        items = client.storage.from_(self.bucket).list(path=path or None)
        for it in items:
            # Supabase returns objects with name; we can't distinguish dirs reliably
            files.append(getattr(it, "name", ""))
        return dirs, files

    def get_modified_time(self, name: str):
        return timezone.now()

    def get_created_time(self, name: str):
        return timezone.now()

    def get_accessed_time(self, name: str):
        return timezone.now()

