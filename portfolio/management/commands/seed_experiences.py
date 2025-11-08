from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_date
from portfolio.models import Experience

DATA = [
    {
        "company": "Freelance / Open Source Contributor",
        "role": "Full Stack Django Developer",
        "start_date": "2023-02-01",
        "end_date": None,
        "description": "Building and contributing to open-source Django applications with production-grade setups using Docker, Celery, Redis, and DRF. Focused on backend architecture, authentication, task queues, and deployment pipelines.",
        "location": "Addis Ababa, Ethiopia",
        "employment_type": "Freelance",
        "is_remote": True,
        "industry": "Software Development",
        "company_website": "https://github.com/seud-dev",
        "company_logo_url": "https://cdn-icons-png.flaticon.com/512/5968/5968350.png",
        "technologies": [
            "Django",
            "Django REST Framework",
            "Celery",
            "Redis",
            "Docker",
            "PostgreSQL",
            "Render",
            "GitHub Actions",
            "Nginx",
            "Traefik",
        ],
        "achievements": [
            "Developed and deployed multiple backend APIs using Django REST Framework with custom authentication logic (email or username login).",
            "Set up Dockerized microservice environments for production using Render and Traefik.",
            "Implemented asynchronous task handling using Celery and Redis for background job processing.",
            "Contributed to open-source HR Payroll and e-commerce projects using Cookiecutter Django templates.",
        ],
        "impact": "Enabled scalable backend deployment for small teams and student projects, improving API performance by 40% and setup time by 60%.",
        "order": 1,
    },
    {
        "company": "Attendance system",
        "role": "Backend Engineer",
        "start_date": "2025-02-01",
        "end_date": None,
        "description": "Developing a fingerprint-based attendance management system using Python, Django, and Windows biometric SDKs to record and verify attendance in real time.",
        "location": "Addis Ababa, Ethiopia",
        "employment_type": "Academic Project",
        "is_remote": False,
        "industry": "Education Technology",
        "company_website": "https://www.aait.edu.et/",
        "company_logo_url": "https://cdn-icons-png.flaticon.com/512/679/679720.png",
        "technologies": [
            "Python",
            "Django",
            "Biometric SDKs",
            "PostgreSQL",
            "HTML/CSS",
            "Bootstrap",
            "Windows API",
        ],
        "achievements": [
            "Integrated PC fingerprint sensor data with Django backend for secure attendance tracking.",
            "Implemented authentication middleware and model relationships for student and teacher management.",
            "Used REST API design principles for smooth data exchange between frontend and backend.",
        ],
        "impact": "Reduced manual attendance errors and provided a reliable automated biometric tracking solution for university staff.",
        "order": 2,
    },
    {
        "company": "Quran Learning Platform (Personal Project)",
        "role": "Backend & API Developer",
        "start_date": "2024-06-01",
        "end_date": "2024-12-30",
        "description": "Developed an online Quran Learning Management System enabling Ustazs (teachers) to conduct live recitation sessions and manage global students.",
        "location": "Remote",
        "employment_type": "Project",
        "is_remote": True,
        "industry": "EdTech / Religious Education",
        "company_website": "https://quranlearn.vercel.app/",
        "company_logo_url": "https://cdn-icons-png.flaticon.com/512/616/616408.png",
        "technologies": [
            "Django",
            "Django REST Framework",
            "PostgreSQL",
            "React",
            "WebSockets",
            "Supabase",
            "JWT Auth",
        ],
        "achievements": [
            "Designed RESTful APIs for student registration, teacher assignment, and live class management.",
            "Implemented tiered learning structure (starters, mid-levels, seniors) with permission-based access.",
            "Configured Supabase for realtime data sync and file storage for Quranic resources.",
        ],
        "impact": "Empowered over 100+ virtual students with interactive Quran learning experiences and reduced administrative friction by 75%.",
        "order": 3,
    },
    {
        "company": "E-Commerce Platform (Storefront)",
        "role": "Full Stack Developer",
        "start_date": "2023-10-01",
        "end_date": "2024-04-30",
        "description": "Built a complete e-commerce backend and Android frontend integration system supporting cart, checkout, order placement, and token-based authentication.",
        "location": "Remote",
        "employment_type": "Freelance Project",
        "is_remote": True,
        "industry": "E-Commerce",
        "company_website": "https://storefront3-fqob.onrender.com/",
        "company_logo_url": "https://cdn-icons-png.flaticon.com/512/152/152534.png",
        "technologies": [
            "Django",
            "Django REST Framework",
            "PostgreSQL",
            "Android (Java)",
            "JWT Auth",
            "Retrofit",
            "MVVM",
            "Celery",
        ],
        "achievements": [
            "Implemented end-to-end ordering system via API with cart-to-order flow in Android app.",
            "Integrated refresh/access token auth and fingerprint authentication in mobile app.",
            "Optimized query performance using select_related/prefetch_related to handle large product data.",
        ],
        "impact": "Delivered a responsive and secure mobile commerce solution, reducing latency by 30% and improving user retention.",
        "order": 4,
    },
    {
        "company": "HR Payroll Management System (Open Source)",
        "role": "Backend Contributor",
        "start_date": "2024-03-01",
        "end_date": "2024-08-31",
        "description": "Contributed to an open-source HR Payroll project with modular apps for users, payroll, departments, and notifications.",
        "location": "Remote",
        "employment_type": "Contributor",
        "is_remote": True,
        "industry": "HR Tech",
        "company_website": "https://github.com/seud-dev/hr-payroll",
        "company_logo_url": "https://cdn-icons-png.flaticon.com/512/2716/2716612.png",
        "technologies": [
            "Django",
            "Allauth",
            "Celery",
            "Redis",
            "Mailpit",
            "Docker Compose",
            "GitHub Actions",
            "PostgreSQL",
        ],
        "achievements": [
            "Configured Allauth for user authentication and email verification (#74).",
            "Integrated mail system via Mailpit and SendGrid for production (#76).",
            "Developed and tested new user fields (full_name, email login) with pytest and CI automation.",
        ],
        "impact": "Improved developer onboarding and reduced local setup time by 40% through containerization and documentation improvements.",
        "order": 5,
    },
]


class Command(BaseCommand):
    help = "Seed Experience records with predefined dataset (idempotent)."

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for item in DATA:
            # Parse dates
            start = parse_date(item["start_date"]) if item.get("start_date") else None
            end = parse_date(item["end_date"]) if item.get("end_date") else None
            defaults = {k: v for k, v in item.items() if k not in ("company", "role", "start_date", "end_date")}
            obj, was_created = Experience.objects.update_or_create(
                company=item["company"],
                role=item["role"],
                start_date=start,
                defaults={"end_date": end, **defaults},
            )
            if was_created:
                created += 1
            else:
                updated += 1
        self.stdout.write(self.style.SUCCESS(f"Experiences seeded. Created: {created}, Updated: {updated}"))