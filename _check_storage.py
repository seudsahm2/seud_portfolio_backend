import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "seud_portfolio_backend.settings")

import django

django.setup()

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

print("DEFAULT_FILE_STORAGE:", getattr(settings, "DEFAULT_FILE_STORAGE", None))
print("MEDIA_URL:", settings.MEDIA_URL)
print("Storage class:", default_storage.__class__.__name__)
print("SUPABASE_PROJECT_URL:", getattr(settings, "SUPABASE_PROJECT_URL", None))
print("SUPABASE_BUCKET:", getattr(settings, "SUPABASE_BUCKET", None))

# Try a tiny write to test backend
try:
    path = default_storage.save("check/hello.txt", ContentFile(b"hello from test"))
    url = default_storage.url(path)
    print("WROTE:", path)
    print("URL:", url)
    # Optionally delete to keep clean
    try:
        default_storage.delete(path)
        print("DELETED:", path)
    except Exception as e:
        print("DELETE FAILED:", e)
except Exception as e:
    print("WRITE FAILED:", e)
    sys.exit(1)
