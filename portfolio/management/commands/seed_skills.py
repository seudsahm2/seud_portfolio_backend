import json
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from portfolio.models import Skill


DEFAULT_SKILLS = [
  {
    "name": "Django",
    "category": "backend",
    "description": "High-level Python web framework for building fast, secure, and scalable backends.",
    "docs_url": "https://docs.djangoproject.com/en/stable/",
    "icon": "django",
    "highlights": [
      "Developed RESTful APIs with Django REST Framework",
      "Integrated Celery for async task processing",
      "Customized admin and authentication system",
      "Deployed Dockerized apps on Render"
    ],
    "since_year": 2022,
    "primary": True,
    "accent": "#092E20",
    "order": 1
  },
  {
    "name": "React",
    "category": "frontend",
    "description": "Modern JavaScript library for dynamic and responsive user interfaces.",
    "docs_url": "https://react.dev/",
    "icon": "react",
    "highlights": [
      "Built reusable UI components with hooks",
      "Integrated with Django REST APIs",
      "Styled with TailwindCSS and Bootstrap",
      "Optimized performance using memoization and lazy loading"
    ],
    "since_year": 2022,
    "primary": True,
    "accent": "#61DAFB",
    "order": 2
  },
  {
    "name": "Next.js",
    "category": "frontend",
    "description": "React framework for production-grade SSR and static web apps.",
    "docs_url": "https://nextjs.org/docs",
    "icon": "nextjs",
    "highlights": [
      "Used for portfolio and dashboard frontends",
      "Implemented SSR for better SEO and speed",
      "Integrated API routes for client–server synergy"
    ],
    "since_year": 2023,
    "primary": True,
    "accent": "#000000",
    "order": 3
  },
  {
    "name": "Python",
    "category": "backend",
    "description": "Versatile programming language powering my backend and AI work.",
    "docs_url": "https://docs.python.org/3/",
    "icon": "python",
    "highlights": [
      "Used across backend, AI prototypes, and automation",
      "Strong focus on clean and maintainable code",
      "Integrated with data and ML libraries"
    ],
    "since_year": 2021,
    "primary": True,
    "accent": "#3776AB",
    "order": 4
  },
  {
    "name": "PostgreSQL",
    "category": "database",
    "description": "Advanced relational database system for scalable, reliable data storage.",
    "docs_url": "https://www.postgresql.org/docs/",
    "icon": "postgresql",
    "highlights": [
      "Designed normalized schemas and foreign key relations",
      "Used via Supabase for hosted DB + realtime APIs",
      "Handled complex queries and indexing for performance"
    ],
    "since_year": 2022,
    "primary": True,
    "accent": "#336791",
    "order": 5
  },
  {
    "name": "Docker",
    "category": "devops",
    "description": "Container platform for consistent deployment and CI/CD workflows.",
    "docs_url": "https://docs.docker.com/",
    "icon": "docker",
    "highlights": [
      "Containerized Django + React projects",
      "Created Docker Compose setups for local/production",
      "Integrated with Celery, Redis, and PostgreSQL"
    ],
    "since_year": 2023,
    "primary": False,
    "accent": "#0db7ed",
    "order": 6
  },
  {
    "name": "Celery",
    "category": "backend",
    "description": "Distributed task queue for handling asynchronous jobs in Django.",
    "docs_url": "https://docs.celeryq.dev/",
    "icon": "celery",
    "highlights": [
      "Handled background jobs like email notifications",
      "Used Redis as message broker",
      "Monitored tasks with Flower"
    ],
    "since_year": 2023,
    "primary": False,
    "accent": "#37814A",
    "order": 7
  },
  {
    "name": "Redis",
    "category": "backend",
    "description": "In-memory data store for caching and message brokering.",
    "docs_url": "https://redis.io/docs/",
    "icon": "redis",
    "highlights": [
      "Used as Celery broker and cache backend",
      "Improved API performance with caching layers"
    ],
    "since_year": 2023,
    "primary": False,
    "accent": "#DC382D",
    "order": 8
  },
  {
    "name": "TailwindCSS",
    "category": "frontend",
    "description": "Utility-first CSS framework for building modern and responsive UIs fast.",
    "docs_url": "https://tailwindcss.com/docs",
    "icon": "tailwindcss",
    "highlights": [
      "Styled React components with responsive utilities",
      "Built clean dashboards and portfolio UIs",
      "Ensured mobile-first design principles"
    ],
    "since_year": 2023,
    "primary": False,
    "accent": "#38BDF8",
    "order": 9
  },
  {
    "name": "Supabase",
    "category": "cloud",
    "description": "Open-source Firebase alternative for Postgres-based backends.",
    "docs_url": "https://supabase.com/docs",
    "icon": "supabase",
    "highlights": [
      "Used for hosting PostgreSQL database",
      "Handled storage and user auth services",
      "Integrated with Django for file storage"
    ],
    "since_year": 2024,
    "primary": False,
    "accent": "#3ECF8E",
    "order": 10
  }
]


class Command(BaseCommand):
    help = "Seed or update Skill entries using provided JSON (idempotent)."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--file", dest="file", help="Path to JSON file of skills array.")
        parser.add_argument("--reset", action="store_true", help="Delete skills not present in input (synchronize by name).")

    def handle(self, *args, **opts):
        data = None
        if opts.get("file"):
            with open(opts["file"], "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = DEFAULT_SKILLS

        if not isinstance(data, list):
            self.stderr.write(self.style.ERROR("Input must be a list of skill objects"))
            return

        by_name = {str(item.get("name")).strip(): item for item in data if item.get("name")}
        names = list(by_name.keys())

        created = 0
        updated = 0

        with transaction.atomic():
            for name, item in by_name.items():
                defaults = {
                    "category": item.get("category", ""),
                    "description": item.get("description", ""),
                    "docs_url": item.get("docs_url", ""),
                    "icon": item.get("icon", ""),
                    "highlights": item.get("highlights", []) or [],
                    "since_year": item.get("since_year"),
                    "primary": bool(item.get("primary", False)),
                    "accent": item.get("accent", ""),
                    "order": int(item.get("order", 0)),
                }
                obj, was_created = Skill.objects.update_or_create(name=name, defaults=defaults)
                created += int(was_created)
                updated += int(not was_created)

            if opts.get("reset"):
                Skill.objects.exclude(name__in=names).delete()

        self.stdout.write(self.style.SUCCESS(f"Skills upserted. created={created} updated={updated} total_now={Skill.objects.count()}"))