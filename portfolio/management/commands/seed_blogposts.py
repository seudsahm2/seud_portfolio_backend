from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime
from portfolio.models import BlogPost

DATA = [
    {
        "title": "The State of Django in 2025: Trends You Should Know",
        "slug": "the-state-of-django-in-2025-trends-you-should-know",
        "summary": "An in-depth look at how Django has evolved in 2025—with community survey data, new frontend patterns, and how backend devs are adapting.",
        "content": "",
        "content_format": "markdown",
        "language": "en",
        "status": "published",
        "published_at": "2025-10-27T00:00:00Z",
        "updated_at": "2025-10-27T00:00:00Z",
        "excerpt": "Django is celebrating its 20th anniversary this year and remains strong. New survey data shows major shifts toward HTMX and Alpine.js and growing AI-tool usage among developers.",
        "table_of_contents": [
            {"id": "key-django-trends-2025", "text": "Key Django Trends in 2025", "level": 1},
            {"id": "ai-usage-in-django", "text": "AI Usage in Django Development", "level": 1},
            {"id": "frontend-patterns-with-django", "text": "Frontend Patterns with Django", "level": 1},
            {"id": "next-steps-for-developers", "text": "Next Steps for Developers", "level": 1},
        ],
        "reading_time": 8,
        "tags": ["Django", "backend", "web development", "trends", "AI"],
        "views_count": 0,
        "likes_count": 0,
        "bookmarks_count": 0,
        "comments_count": 0,
        "allow_comments": True,
        "featured": False,
        "pinned_order": 0,
        "seo_title": "The State of Django in 2025",
        "seo_description": "Discover how Django has changed in 2025, from new frontend integrations like HTMX to growing AI adoption in development workflows.",
        "canonical_url": "https://blog.jetbrains.com/pycharm/2025/10/the-state-of-django-2025/",
        "og_image_url": "",
    },
    {
        "title": "React JS vs Django: Finding the Best Framework for 2025",
        "slug": "react-js-vs-django-finding-the-best-framework-for-2025",
        "summary": "Compare React and Django in 2025: strengths, use-cases, and how full-stack developers are combining them for modern web apps.",
        "content": "",
        "content_format": "markdown",
        "language": "en",
        "status": "published",
        "published_at": "2025-03-05T00:00:00Z",
        "updated_at": "2025-03-06T00:00:00Z",
        "excerpt": "React and Django each offer unique strengths. For full-stack apps in 2025, understanding how they fit and when to use one or both is key.",
        "table_of_contents": [
            {"id": "introduction", "text": "Introduction", "level": 1},
            {"id": "django-overview", "text": "Django Overview", "level": 1},
            {"id": "react-overview", "text": "React Overview", "level": 1},
            {"id": "comparison", "text": "Comparison: React vs Django", "level": 1},
            {"id": "conclusion", "text": "Conclusion & Recommendation", "level": 1},
        ],
        "reading_time": 6,
        "tags": ["React", "Django", "full-stack", "web development", "frontend", "backend"],
        "views_count": 0,
        "likes_count": 0,
        "bookmarks_count": 0,
        "comments_count": 0,
        "allow_comments": True,
        "featured": False,
        "pinned_order": 0,
        "seo_title": "React JS vs Django 2025",
        "seo_description": "A detailed look at React and Django in 2025, helping you decide which framework to use or how to combine them for full-stack development.",
        "canonical_url": "https://www.angularminds.com/blog/react-js-vs-django",
        "og_image_url": "",
    },
    {
        "title": "Seamlessly Integrating React with Django CMS: A Modern Approach",
        "slug": "seamlessly-integrating-react-with-django-cms-a-modern-approach",
        "summary": "Learn how to embed React applications inside a Django CMS setup using Vite for builds, enabling rich interactivity while keeping CMS strengths.",
        "content": "",
        "content_format": "markdown",
        "language": "en",
        "status": "published",
        "published_at": "2025-06-17T00:00:00Z",
        "updated_at": "2025-06-17T00:00:00Z",
        "excerpt": "Combining React within Django CMS pages offers the best of both worlds: content editors manage pages while developers build interactive features.",
        "table_of_contents": [
            {"id": "why-integrate", "text": "Why Integrate React with Django CMS?", "level": 1},
            {"id": "architecture-overview", "text": "Architecture Overview", "level": 1},
            {"id": "implementation-deep-dive", "text": "Implementation Deep Dive", "level": 1},
            {"id": "conclusion", "text": "Conclusion", "level": 1},
        ],
        "reading_time": 5,
        "tags": ["Django CMS", "React", "CMS", "frontend", "integration"],
        "views_count": 0,
        "likes_count": 0,
        "bookmarks_count": 0,
        "comments_count": 0,
        "allow_comments": True,
        "featured": False,
        "pinned_order": 0,
        "seo_title": "Integrating React with Django CMS",
        "seo_description": "A modern guide to combining React and Django CMS using Vite to build interactive, modular apps within traditional CMS pages.",
        "canonical_url": "https://www.django-cms.org/en/blog/2025/06/17/seamlessly-integrating-react-with-django-cms-a-modern-approach/",
        "og_image_url": "",
    },
    {
        "title": "25+ Epic Django Project Ideas You Need to Build in 2025!",
        "slug": "25-epic-django-project-ideas-you-need-to-build-in-2025",
        "summary": "Explore over 25 Django project ideas—ranging from beginner to advanced—that help you apply core web-dev concepts and grow your skillset in 2025.",
        "content": "",
        "content_format": "markdown",
        "language": "en",
        "status": "published",
        "published_at": "2025-09-10T00:00:00Z",
        "updated_at": "2025-09-10T00:00:00Z",
        "excerpt": "From task managers to e-commerce platforms, these Django project ideas will help you build real apps and sharpen your full-stack skills.",
        "table_of_contents": [
            {"id": "intro", "text": "Introduction", "level": 1},
            {"id": "beginner-ideas", "text": "Beginner Ideas", "level": 1},
            {"id": "intermediate-ideas", "text": "Intermediate Ideas", "level": 1},
            {"id": "advanced-ideas", "text": "Advanced Ideas", "level": 1},
            {"id": "how-to-choose", "text": "How to Choose the Right Project", "level": 1},
        ],
        "reading_time": 7,
        "tags": ["Django", "project ideas", "2025", "learning", "full-stack"],
        "views_count": 0,
        "likes_count": 0,
        "bookmarks_count": 0,
        "comments_count": 0,
        "allow_comments": True,
        "featured": False,
        "pinned_order": 0,
        "seo_title": "Django Project Ideas 2025",
        "seo_description": "Get more than 25 project ideas for Django in 2025 to build and enhance your web development skills in real-world apps.",
        "canonical_url": "https://www.upgrad.com/blog/top-django-project-ideas-topics/",
        "og_image_url": "",
    },
    {
        "title": "Improving Front-end Performance through Modular Rendering and Adaptive Hydration in React Apps",
        "slug": "improving-front-end-performance-through-modular-rendering-and-adaptive-hydration",
        "summary": "A deep research-driven article about modular rendering, adaptive hydration and how React/Next.js applications can optimize load times and interactivity.",
        "content": "",
        "content_format": "markdown",
        "language": "en",
        "status": "published",
        "published_at": "2025-04-04T00:00:00Z",
        "updated_at": "2025-04-04T00:00:00Z",
        "excerpt": "Adaptive hydration and modular rendering techniques are the next frontier in React/Next performance—especially for large scale interactive apps.",
        "table_of_contents": [
            {"id": "motivation", "text": "Motivation", "level": 1},
            {"id": "modular-rendering", "text": "Modular Rendering", "level": 1},
            {"id": "adaptive-hydration", "text": "Adaptive Hydration", "level": 1},
            {"id": "evaluations", "text": "Evaluations & Results", "level": 1},
            {"id": "implications-for-developers", "text": "Implications for Developers", "level": 1},
        ],
        "reading_time": 9,
        "tags": ["React", "performance", "frontend", "Next.js", "research"],
        "views_count": 0,
        "likes_count": 0,
        "bookmarks_count": 0,
        "comments_count": 0,
        "allow_comments": True,
        "featured": False,
        "pinned_order": 0,
        "seo_title": "Modular Rendering & Adaptive Hydration in React",
        "seo_description": "Explore cutting-edge research on how modular rendering and adaptive hydration in React/Next.js can dramatically improve front-end performance.",
        "canonical_url": "https://arxiv.org/abs/2504.03884",
        "og_image_url": "",
    },
]


class Command(BaseCommand):
    help = "Seed BlogPost records with predefined dataset (idempotent by slug)."

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for item in DATA:
            slug = item["slug"]
            published_at = parse_datetime(item.get("published_at")) if item.get("published_at") else None
            updated_at = parse_datetime(item.get("updated_at")) if item.get("updated_at") else None
            defaults = {k: v for k, v in item.items() if k not in ("slug", "published_at", "updated_at")}
            if published_at:
                defaults["published_at"] = published_at
            if updated_at:
                defaults["updated_at"] = updated_at
            obj, was_created = BlogPost.objects.update_or_create(slug=slug, defaults=defaults)
            if was_created:
                created += 1
            else:
                updated += 1
        self.stdout.write(self.style.SUCCESS(f"Blog posts seeded. Created: {created}, Updated: {updated}"))