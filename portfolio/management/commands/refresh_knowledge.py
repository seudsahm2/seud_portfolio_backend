from django.core.management.base import BaseCommand
from django.db import transaction
from portfolio.models import KnowledgeDocument, Profile, Project, Experience


class Command(BaseCommand):
    help = "Refresh knowledge documents by extracting from current DB data."

    def handle(self, *args, **options):
        docs = []
        with transaction.atomic():
            KnowledgeDocument.objects.all().delete()
            for p in Profile.objects.all():
                content = f"Profile: {p.full_name}\nTitle: {p.title}\nBio: {p.bio}\nLocation: {p.location}\nWebsite: {p.website}\n"
                docs.append(KnowledgeDocument.objects.create(source="profile", title=p.full_name, content=content))
            for pr in Project.objects.all():
                skills = ", ".join(pr.skills.values_list("name", flat=True))
                content = f"Project: {pr.title}\nDescription: {pr.description}\nSkills: {skills}\nFeatured: {pr.featured}\n"
                docs.append(KnowledgeDocument.objects.create(source=f"project:{pr.id}", title=pr.title, content=content))
            for e in Experience.objects.all():
                content = f"Experience: {e.company}\nRole: {e.role}\nPeriod: {e.start_date} - {e.end_date or 'present'}\n{e.description}\n"
                docs.append(KnowledgeDocument.objects.create(source=f"experience:{e.id}", title=e.role, content=content))
        self.stdout.write(self.style.SUCCESS(f"Knowledge refreshed: {len(docs)} docs."))
