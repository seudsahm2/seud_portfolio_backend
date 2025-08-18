from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.utils.text import slugify
from django.conf import settings
from io import BytesIO
from PIL import Image
from portfolio.models import Profile, Skill, Project, Experience, BlogPost
try:
    from supabase import create_client
except Exception:  # pragma: no cover
    create_client = None


class Command(BaseCommand):
    help = "Seed initial portfolio data (idempotent)."

    def handle(self, *args, **options):
        profile, _ = Profile.objects.get_or_create(
            full_name="Your Name",
            defaults={
                "title": "Software Engineer",
                "bio": "I build delightful products with Django, DRF, and Next.js.",
                "email": "you@example.com",
                "location": "Remote",
                "website": "https://example.com",
            },
        )

        skills = [
            ("Python", 5),
            ("Django", 5),
            ("DRF", 5),
            ("PostgreSQL", 4),
            ("Redis", 4),
            ("Celery", 4),
            ("AWS", 3),
        ]
        skill_objs = []
        for name, level in skills:
            obj, _ = Skill.objects.get_or_create(name=name, defaults={"level": level})
            if obj.level != level:
                obj.level = level
                obj.save(update_fields=["level"])
            skill_objs.append(obj)

        projects_seed = [
            {
                "title": "AI Portfolio",
                "featured": True,
                "desc": "A modern portfolio with AI chatbot and DRF backend.",
            },
            {"title": "Realtime Chat", "desc": "Channels + Redis streaming chat."},
            {"title": "Blog Engine", "desc": "Markdown blog with tagging."},
            {"title": "Task Runner", "desc": "Celery background workers."},
            {"title": "Image Uploader", "desc": "Validated uploads and transforms."},
            {"title": "Analytics", "desc": "Track usage and events."},
            {"title": "Admin Tools", "desc": "Admin utilities and reports."},
        ]

        for i, meta in enumerate(projects_seed):
            proj, _ = Project.objects.get_or_create(
                title=meta["title"],
                defaults={
                    "description": meta.get("desc", ""),
                    "featured": meta.get("featured", False),
                },
            )
            proj.skills.set(Skill.objects.filter(name__in=["Python", "Django", "DRF", "Redis"]))

            # create a simple generated image
            img = Image.new("RGB", (600, 320), (30 * (i + 1) % 255, 120, 180))
            buf = BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)

            filename = f"project_{i+1}.png"
            if settings.SUPABASE_URL and create_client:
                client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
                path = f"projects/{filename}"
                client.storage.from_(settings.SUPABASE_BUCKET).upload(path, buf.getvalue(), {
                    "content-type": "image/png"
                })
                public_url = client.storage.from_(settings.SUPABASE_BUCKET).get_public_url(path)
                proj.image_url = public_url
                proj.save(update_fields=["image_url"])
            else:
                proj.image.save(filename, ContentFile(buf.getvalue()), save=True)

        Experience.objects.get_or_create(
            company="Awesome Co",
            role="Backend Engineer",
            start_date="2023-01-01",
            defaults={"description": "Built APIs and AI features."},
        )

        blog_titles = [
            "Hello World: My Portfolio",
            "Building an AI Chatbot",
            "Streaming APIs with Channels",
            "Async Tasks with Celery",
            "Caching Strategies with Redis",
            "API Design with DRF",
            "Deploying Django Projects",
        ]
        for j, title in enumerate(blog_titles):
            post, _ = BlogPost.objects.get_or_create(
                slug=slugify(title),
                defaults={
                    "title": title,
                    "summary": f"Post about {title}",
                    "content": f"# {title}\nContent coming soon.",
                },
            )
            # simple cover image
            img = Image.new("RGB", (1200, 630), (90, 30 * (j + 1) % 255, 90))
            buf = BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            filename = f"blog_{j+1}.png"
            if settings.SUPABASE_URL and create_client:
                client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
                path = f"blog/{filename}"
                client.storage.from_(settings.SUPABASE_BUCKET).upload(path, buf.getvalue(), {
                    "content-type": "image/png"
                })
                public_url = client.storage.from_(settings.SUPABASE_BUCKET).get_public_url(path)
                post.cover_image_url = public_url
                post.save(update_fields=["cover_image_url"])
            else:
                post.cover_image.save(filename, ContentFile(buf.getvalue()), save=True)

        self.stdout.write(self.style.SUCCESS("Seed data created/updated."))
