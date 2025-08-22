from django.db import models
from django.core.files.storage import default_storage
from django.utils.module_loading import import_string
SupabaseMediaStorage = import_string('portfolio.storage_backends.SupabaseMediaStorage')

class Profile(models.Model):
    full_name = models.CharField(max_length=120)
    title = models.CharField(max_length=120, blank=True)
    bio = models.TextField(blank=True)
    email = models.EmailField(blank=True)
    location = models.CharField(max_length=120, blank=True)
    website = models.URLField(blank=True)

    def __str__(self):
        return self.full_name

class Skill(models.Model):
    name = models.CharField(max_length=80)
    level = models.PositiveSmallIntegerField(default=3)  # 1-5

    def __str__(self):
        return f"{self.name} ({self.level})"

    class Meta:
        ordering = ["-level", "name", "id"]

class Project(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    link = models.URLField(blank=True)
    repo = models.URLField(blank=True)
    skills = models.ManyToManyField(Skill, blank=True)
    featured = models.BooleanField(default=False)
    created_at = models.DateField(null=True, blank=True)
    # Local dev image storage; when using Supabase we store the path/URL
    image = models.ImageField(upload_to="projects/", storage=SupabaseMediaStorage(), blank=True, null=True)
    image_url = models.URLField(blank=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # First save to ensure the file is uploaded via the active storage backend
        super().save(*args, **kwargs)
        # If an image exists, ensure image_url reflects the storage URL (Supabase when configured)
        new_url = None
        if self.image:
            try:
                new_url = self.image.url
            except Exception:  # best-effort; keep existing
                try:
                    from django.conf import settings as _s
                    if self.image.name and getattr(_s, "MEDIA_URL", ""):
                        new_url = f"{_s.MEDIA_URL.rstrip('/')}/{self.image.name}"
                except Exception:
                    new_url = None
        if new_url and new_url != self.image_url:
            type(self).objects.filter(pk=self.pk).update(image_url=new_url)

    class Meta:
        ordering = ["-created_at", "title", "-id"]

class Experience(models.Model):
    company = models.CharField(max_length=200)
    role = models.CharField(max_length=200)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.role} @ {self.company}"

    class Meta:
        ordering = ["-start_date", "-end_date", "-id"]

class BlogPost(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    summary = models.TextField(blank=True)
    content = models.TextField(blank=True)
    published_at = models.DateTimeField(auto_now_add=True)
    cover_image = models.ImageField(upload_to="blog/", storage=SupabaseMediaStorage(), blank=True, null=True)
    cover_image_url = models.URLField(blank=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        new_url = None
        if self.cover_image:
            try:
                new_url = self.cover_image.url
            except Exception:
                try:
                    from django.conf import settings as _s
                    if self.cover_image.name and getattr(_s, "MEDIA_URL", ""):
                        new_url = f"{_s.MEDIA_URL.rstrip('/')}/{self.cover_image.name}"
                except Exception:
                    new_url = None
        if new_url and new_url != self.cover_image_url:
            type(self).objects.filter(pk=self.pk).update(cover_image_url=new_url)

    class Meta:
        ordering = ["-published_at", "-id"]


class KnowledgeDocument(models.Model):
    """Simple text knowledge item built from site data."""
    source = models.CharField(max_length=100)  # e.g., profile, project:1, experience:2
    title = models.CharField(max_length=200, blank=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["source"])]

    def __str__(self):
        return f"{self.source}"


class ChatLog(models.Model):
    """Stores each chat interaction for auditing and analytics."""
    provider = models.CharField(max_length=50)
    model = models.CharField(max_length=100, blank=True)
    question = models.TextField()
    answer = models.TextField(blank=True)
    answer_json = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=20, default="ok")  # ok / error
    error = models.TextField(blank=True)
    tokens_prompt = models.IntegerField(null=True, blank=True)
    tokens_completion = models.IntegerField(null=True, blank=True)
    latency_ms = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
