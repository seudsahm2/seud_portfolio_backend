from pathlib import Path
from typing import Iterable

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

try:
    from portfolio.storage_backends import _get_client  # type: ignore
except Exception:  # pragma: no cover  # noqa: BLE001
    _get_client = None  # type: ignore


def iter_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*"):
        if p.is_file():
            yield p


class Command(BaseCommand):
    help = "Sync local MEDIA_ROOT files to Supabase Storage bucket, preserving paths (upsert)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List files that would be uploaded without performing uploads.",
        )
        parser.add_argument(
            "--prefix",
            default="",
            help="Optional key prefix to add when uploading to the bucket (e.g., 'media/').",
        )

    def handle(self, *args, **options):
        media_root = getattr(settings, "MEDIA_ROOT", None)
        bucket = getattr(settings, "SUPABASE_BUCKET", None)
        project_url = getattr(settings, "SUPABASE_PROJECT_URL", None) or getattr(
            settings, "SUPABASE_URL", None
        )

        if not media_root:
            raise CommandError("MEDIA_ROOT is not configured.")
        if not bucket or not project_url:
            raise CommandError(
                "Supabase not configured. Ensure SUPABASE_PROJECT_URL (or SUPABASE_URL) and SUPABASE_BUCKET are set."
            )
        if _get_client is None:
            raise CommandError("supabase package not installed or storage backend unavailable.")

        root_path = Path(media_root)
        if not root_path.exists():
            raise CommandError(f"MEDIA_ROOT does not exist: {root_path}")

        prefix = str(options.get("prefix") or "").strip("/")
        dry_run = bool(options.get("dry_run"))

        client = _get_client()
        storage = client.storage.from_(bucket)

        uploaded = 0
        skipped = 0
        total = 0
        for file_path in iter_files(root_path):
            total += 1
            key = str(file_path.relative_to(root_path)).replace("\\", "/")
            if prefix:
                key = f"{prefix}/{key}"

            if dry_run:
                self.stdout.write(f"DRY-RUN would upload: {key}")
                skipped += 1
                continue

            # Read and upsert
            with open(file_path, "rb") as f:
                data = f.read()
            # Try upload; if it fails (e.g., object exists), remove then upload
            try:
                storage.upload(key, data)
            except Exception:  # noqa: BLE001
                try:
                    storage.remove([key])
                except Exception:  # noqa: BLE001
                    pass
                storage.upload(key, data)
                uploaded += 1
                if uploaded % 50 == 0:
                    self.stdout.write(self.style.NOTICE(f"Uploaded {uploaded} files so far..."))
            # Any unexpected exception above would have raised; continue

        self.stdout.write(
            f"Sync complete. Uploaded={uploaded}, DryRun/Skipped={skipped}, TotalSeen={total}"
        )
