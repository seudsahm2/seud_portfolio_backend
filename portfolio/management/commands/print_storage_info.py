from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from portfolio.models import Project, BlogPost
from portfolio.storage_backends import SupabaseMediaStorage


class Command(BaseCommand):
    help = "Print effective storage config and run a tiny upload test via model ImageField"

    def handle(self, *args, **options):
        self.stdout.write("== Storage configuration ==")
        self.stdout.write(f"DEBUG: {settings.DEBUG}")
        self.stdout.write(f"MEDIA_URL: {settings.MEDIA_URL}")
        self.stdout.write(f"STORAGES.default: {settings.STORAGES.get('default')}")
        self.stdout.write(f"DEFAULT_FILE_STORAGE: {getattr(settings, 'DEFAULT_FILE_STORAGE', None)}")
        self.stdout.write(f"default_storage class: {type(default_storage).__name__}")
        self.stdout.write("")

        # Field storages
        p_image_storage = Project._meta.get_field("image").storage
        b_image_storage = BlogPost._meta.get_field("cover_image").storage
        self.stdout.write(f"Project.image.storage: {type(p_image_storage).__name__}")
        self.stdout.write(f"BlogPost.cover_image.storage: {type(b_image_storage).__name__}")

        # Supabase details (if configured)
        try:
            sb = SupabaseMediaStorage()
            self.stdout.write(f"Supabase bucket: {sb.bucket}")
            self.stdout.write(f"Supabase public base: {sb.public_base}")
        except Exception as e:
            self.stdout.write(f"Supabase storage init failed: {e}")

        # Upload test through ImageField (bypasses form validation)
        self.stdout.write("\n== Upload test via Project.image ==")
        p = Project.objects.create(title="__storage_test__")
        try:
            p.image.save("check/hello.txt", ContentFile(b"hello-from-admin-upload-test"))
            p.save(update_fields=["image"])
            url = p.image.url if p.image else None
            self.stdout.write(f"Saved as: {p.image.name}")
            self.stdout.write(f"Public URL: {url}")
        finally:
            # cleanup best-effort
            try:
                if p.image:
                    p.image.storage.delete(p.image.name)
            except Exception:
                pass
            p.delete()
        self.stdout.write("Done.")
