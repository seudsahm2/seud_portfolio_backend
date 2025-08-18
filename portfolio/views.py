from rest_framework import viewsets, filters, status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from drf_spectacular.utils import extend_schema
from django_filters.rest_framework import DjangoFilterBackend
from .models import Profile, Project, Experience, Skill, BlogPost, KnowledgeDocument, ChatLog
from .serializers import (
    ProfileSerializer,
    ProjectSerializer,
    ExperienceSerializer,
    SkillSerializer,
    BlogPostSerializer,
    ContactSerializer,
    KnowledgeDocumentSerializer,
    ChatLogSerializer,
    ChatAskSerializer,
)
from .tasks import send_contact_email
from django.db import transaction
from django.utils import timezone
from .ai_providers import ask as ai_ask
from django.conf import settings
import requests

class ProfileViewSet(viewsets.ModelViewSet):
    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["full_name", "title", "email"]

class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["featured", "skills__name"]
    search_fields = ["title", "description"]

class ExperienceViewSet(viewsets.ModelViewSet):
    queryset = Experience.objects.all()
    serializer_class = ExperienceSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["company", "role"]

class SkillViewSet(viewsets.ModelViewSet):
    queryset = Skill.objects.all()
    serializer_class = SkillSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]

class BlogPostViewSet(viewsets.ModelViewSet):
    queryset = BlogPost.objects.all()
    serializer_class = BlogPostSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "slug", "summary"]


class ContactThrottle(ScopedRateThrottle):
    scope = "contact"


class ContactView(APIView):
    throttle_classes = [ContactThrottle]
    permission_classes = [AllowAny]

    @extend_schema(request=ContactSerializer, responses={202: None})
    def post(self, request):
        serializer = ContactSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        # enqueue email task
        send_contact_email.delay(data["name"], data["email"], data["message"])
        return Response(status=status.HTTP_202_ACCEPTED)


class KnowledgeRefreshView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses={200: KnowledgeDocumentSerializer(many=True)})
    def post(self, request):
        docs = []
        with transaction.atomic():
            KnowledgeDocument.objects.all().delete()
            for p in Profile.objects.all():
                content = f"Profile: {p.full_name}\nTitle: {p.title}\nBio: {p.bio}\nLocation: {p.location}\nWebsite: {p.website}\n"
                docs.append(KnowledgeDocument.objects.create(source="profile", title=p.full_name, content=content))
            for pr in Project.objects.all():
                skills = ", ".join(pr.skills.values_list("name", flat=True))
                content = f"Project: {pr.title}\nDescription: {pr.description}\nSkills: {skills}\nFeatured: {pr.featured}\nLink: {pr.link}\nRepo: {pr.repo}\n"
                docs.append(KnowledgeDocument.objects.create(source=f"project:{pr.id}", title=pr.title, content=content))
            for s in Skill.objects.all():
                content = f"Skill: {s.name}\nLevel: {s.level}\n"
                docs.append(KnowledgeDocument.objects.create(source=f"skill:{s.id}", title=s.name, content=content))
            for b in BlogPost.objects.all():
                content = f"Blog: {b.title}\nSlug: {b.slug}\nSummary: {b.summary}\nContent: {b.content[:1500]}\n"
                docs.append(KnowledgeDocument.objects.create(source=f"blog:{b.id}", title=b.title, content=content))

            # Optional GitHub ingestion (repo metadata + README)
            gh_token = getattr(settings, "GITHUB_TOKEN", "")
            gh_headers = {
                "Accept": "application/vnd.github+json",
                "User-Agent": "portfolio-backend/1.0",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            if gh_token:
                gh_headers["Authorization"] = f"Bearer {gh_token}"
            for pr in Project.objects.exclude(repo=""):
                try:
                    repo_url = pr.repo.rstrip("/")
                    parts = repo_url.split("github.com/")
                    if len(parts) == 2:
                        owner_repo = parts[1]
                        if owner_repo.count("/") >= 1:
                            owner, repo = owner_repo.split("/", 1)
                            api_base = f"https://api.github.com/repos/{owner}/{repo}"
                            r1 = requests.get(api_base, headers=gh_headers, timeout=10)
                            if r1.ok:
                                meta = r1.json()
                                description = meta.get("description") or ""
                                stars = meta.get("stargazers_count")
                                language = meta.get("language")
                                content = f"GitHub Repo: {owner}/{repo}\nDescription: {description}\nStars: {stars}\nLanguage: {language}\nRepo URL: {pr.repo}\n"
                                docs.append(KnowledgeDocument.objects.create(source=f"github:{owner}/{repo}", title=f"{owner}/{repo}", content=content))
                            r2 = requests.get(api_base + "/readme", headers=gh_headers, timeout=10)
                            if r2.ok:
                                j = r2.json()
                                download_url = j.get("download_url")
                                if download_url:
                                    r3 = requests.get(download_url, headers=gh_headers, timeout=10)
                                    if r3.ok:
                                        readme_text = r3.text
                                        docs.append(KnowledgeDocument.objects.create(source=f"github_readme:{owner}/{repo}", title=f"README {owner}/{repo}", content=readme_text[:10000]))
                except Exception:
                    pass
            for e in Experience.objects.all():
                content = f"Experience: {e.company}\nRole: {e.role}\nPeriod: {e.start_date} - {e.end_date or 'present'}\n{e.description}\n"
                docs.append(KnowledgeDocument.objects.create(source=f"experience:{e.id}", title=e.role, content=content))
        return Response(KnowledgeDocumentSerializer(docs, many=True).data)


class ChatAskView(APIView):
    # Use a dedicated throttle for chat so it doesn't share limits with contact.
    # Slightly higher rate to allow interactive testing without frequent 429s.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "chat"
    permission_classes = [AllowAny]

    @extend_schema(request=ChatAskSerializer, responses={200: ChatLogSerializer})
    def post(self, request):
        s = ChatAskSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data
        provider = data["provider"]
        model = data.get("model") or ""
        question = data["question"]
        max_tokens = data.get("max_tokens") or 512
        # Prioritize projects and GitHub docs first, then other knowledge
        if KnowledgeDocument.objects.exists():
            project_chunks = list(KnowledgeDocument.objects.filter(source__startswith("project:")).values_list("content", flat=True))
            github_chunks = list(KnowledgeDocument.objects.filter(source__startswith("github")).values_list("content", flat=True))
            other_chunks = list(
                KnowledgeDocument.objects.exclude(source__startswith("project:")).exclude(source__startswith("github")).order_by("-updated_at").values_list("content", flat=True)
            )
            chunks = project_chunks + github_chunks + other_chunks
            knowledge = "\n---\n".join(chunks)[:50000]
        else:
            # Fallback: assemble knowledge on the fly from DB and GitHub if no cached docs exist
            parts = []
            for p in Profile.objects.all():
                parts.append(
                    f"Profile: {p.full_name}\nTitle: {p.title}\nBio: {p.bio}\nLocation: {p.location}\nWebsite: {p.website}\n"
                )
            for pr in Project.objects.all():
                skills = ", ".join(pr.skills.values_list("name", flat=True))
                parts.append(
                    f"Project: {pr.title}\nDescription: {pr.description}\nSkills: {skills}\nFeatured: {pr.featured}\nLink: {pr.link}\nRepo: {pr.repo}\n"
                )
            for s in Skill.objects.all():
                parts.append(f"Skill: {s.name}\nLevel: {s.level}\n")
            for b in BlogPost.objects.all():
                parts.append(f"Blog: {b.title}\nSlug: {b.slug}\nSummary: {b.summary}\nContent: {b.content[:1500]}\n")
            # Try GitHub ingestion quickly (best effort)
            gh_token = getattr(settings, "GITHUB_TOKEN", "")
            gh_headers = {
                "Accept": "application/vnd.github+json",
                "User-Agent": "portfolio-backend/1.0",
                "X-GitHub-Api-Version": "2022-11-28",
            }
            if gh_token:
                gh_headers["Authorization"] = f"Bearer {gh_token}"
            for pr in Project.objects.exclude(repo=""):
                try:
                    repo_url = pr.repo.rstrip("/")
                    parts_split = repo_url.split("github.com/")
                    if len(parts_split) == 2:
                        owner_repo = parts_split[1]
                        if owner_repo.count("/") >= 1:
                            owner, repo = owner_repo.split("/", 1)
                            api_base = f"https://api.github.com/repos/{owner}/{repo}"
                            r1 = requests.get(api_base, headers=gh_headers, timeout=10)
                            if r1.ok:
                                meta = r1.json()
                                description = meta.get("description") or ""
                                stars = meta.get("stargazers_count")
                                language = meta.get("language")
                                parts.append(
                                    f"GitHub Repo: {owner}/{repo}\nDescription: {description}\nStars: {stars}\nLanguage: {language}\nRepo URL: {pr.repo}\n"
                                )
                            r2 = requests.get(api_base + "/readme", headers=gh_headers, timeout=10)
                            if r2.ok:
                                j = r2.json()
                                download_url = j.get("download_url")
                                if download_url:
                                    r3 = requests.get(download_url, headers=gh_headers, timeout=10)
                                    if r3.ok:
                                        parts.append(r3.text[:10000])
                except Exception:
                    pass
            knowledge = "\n---\n".join(parts)[:50000]
        started = timezone.now()
        log = ChatLog(provider=provider, model=model, question=question)
        try:
            # Build prompt variables from Profile if available
            prof = Profile.objects.first()
            system_vars = {
                "owner_name": getattr(prof, "full_name", ""),
                "owner_title": getattr(prof, "title", ""),
                "primary_stack": ", ".join(Skill.objects.order_by("-level").values_list("name", flat=True)[:5]),
                "summary_tokens": max_tokens,
            }
            res = ai_ask(provider, question, knowledge, model=model, max_tokens=max_tokens, system_vars=system_vars)
            log.answer = res.text
            log.tokens_prompt = res.tokens_prompt
            log.tokens_completion = res.tokens_completion
            log.status = "ok"
        except Exception as e:
            log.status = "error"
            log.error = str(e)
        finally:
            dur = timezone.now() - started
            log.latency_ms = int(dur.total_seconds() * 1000)
            log.save()
        return Response(ChatLogSerializer(log).data)
