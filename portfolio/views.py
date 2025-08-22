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
    KnowledgeSourcesSerializer,
    KnowledgeIngestRequestSerializer,
    KnowledgeIngestResponseSerializer,
)
from .tasks import send_contact_email
from django.db import transaction
from django.utils import timezone
from .ai_providers import ask as ai_ask
from django.conf import settings
import requests
from django.http import HttpResponse
import base64
from django.db.models import Q

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
    ordering_fields = ["created_at", "title", "id"]

class ExperienceViewSet(viewsets.ModelViewSet):
    queryset = Experience.objects.all()
    serializer_class = ExperienceSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["company", "role"]
    ordering_fields = ["start_date", "end_date", "id"]

class SkillViewSet(viewsets.ModelViewSet):
    queryset = Skill.objects.all()
    serializer_class = SkillSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["level", "name", "id"]

class BlogPostViewSet(viewsets.ModelViewSet):
    queryset = BlogPost.objects.all()
    serializer_class = BlogPostSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "slug", "summary"]
    ordering_fields = ["published_at", "id"]


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

    @extend_schema(request=None, responses={200: KnowledgeDocumentSerializer(many=True)})
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

            # GitHub ingestion disabled here (metadata/README). We'll ingest code via a dedicated endpoint.
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
        max_tokens = data.get("max_tokens")  # allow None to remove our cap
        structured = data.get("structured", True)
        top_n = data.get("top_n", 6)

        # Detect code-focused requests to allow code blocks and better retrieval
        q_lower = question.lower()
        code_triggers = ["show code", "snippet", "code block", "line by line", "file:", "path:", "implementation", "source code", "function", "class"]
        wants_code = any(t in q_lower for t in code_triggers)
        if wants_code:
            structured = False  # free-form so we can include fenced code blocks

        # Prioritize actual GitHub code chunks first, then projects, then other knowledge
        if KnowledgeDocument.objects.exists():
            from django.db.models import Q
            code_qs = KnowledgeDocument.objects.filter(source__startswith="github_code:")
            if wants_code:
                # Simple keyword-based filter to focus relevant files
                terms = [w for w in q_lower.replace("/", " ").replace("\\", " ").split() if len(w) > 2]
                cond = Q()
                for t in terms[:8]:
                    cond |= Q(content__icontains=t)
                if cond:
                    code_qs = code_qs.filter(cond)
            code_chunks = list(code_qs.order_by("-updated_at").values_list("content", flat=True)[:50])

            project_chunks = list(
                KnowledgeDocument.objects.filter(source__startswith="project:").values_list("content", flat=True)
            )
            other_chunks = list(
                KnowledgeDocument.objects.exclude(source__startswith="project:")
                .exclude(source__startswith="github_code:")
                .order_by("-updated_at")
                .values_list("content", flat=True)
            )
            chunks = code_chunks + project_chunks + other_chunks
            knowledge = "\n---\n".join(chunks)
        else:
            # Fallback: assemble knowledge on the fly from DB if no cached docs exist
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
            knowledge = "\n---\n".join(parts)

        started = timezone.now()
        log = ChatLog(provider=provider, model=model, question=question)
        try:
            # Build prompt variables from Profile if available
            prof = Profile.objects.first()
            system_vars = {
                "owner_name": getattr(prof, "full_name", ""),
                "owner_title": getattr(prof, "title", ""),
                "primary_stack": ", ".join(Skill.objects.order_by("-level").values_list("name", flat=True)[:5]),
                "summary_tokens": max_tokens or 512,
                "top_n": top_n,
            }
            res = ai_ask(provider, question, knowledge, model=model, max_tokens=max_tokens, system_vars=system_vars, structured=structured)
            log.answer = res.text
            log.answer_json = dict(res.data) if isinstance(res.data, dict) else None
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


class KnowledgeSourcesView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses={200: KnowledgeSourcesSerializer})
    def get(self, request):
        total = KnowledgeDocument.objects.count()
        prefixes = ["profile", "project:", "skill:", "blog:", "experience:", "github_code:"]
        counts = {}
        for pfx in prefixes:
            if pfx.endswith(":"):
                counts[pfx] = KnowledgeDocument.objects.filter(source__startswith=pfx).count()
            else:
                counts[pfx] = KnowledgeDocument.objects.filter(source=pfx).count()
        sample = list(
            KnowledgeDocument.objects.filter(source__startswith="github_code:")
            .order_by("-updated_at")
            .values_list("title", flat=True)[:20]
        )
        return Response({"total": total, "counts": counts, "github_code_samples": sample})


class GitHubReposJSONView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(parameters=None, responses={200: None})
    def get(self, request):
        username = request.query_params.get("username")
        include_private = request.query_params.get("include_private") in {"1", "true", "True", "yes"}
        if not username and not include_private:
            return Response({"error": "username is required unless include_private=1"}, status=400)
        gh_token = getattr(settings, "GITHUB_TOKEN", "")
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "portfolio-backend/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if gh_token:
            headers["Authorization"] = f"Bearer {gh_token}"
        try:
            # Choose endpoint: /user/repos for private (requires token), else public /users/{username}/repos
            if include_private:
                if not gh_token:
                    return Response({"error": "GITHUB_TOKEN not configured; cannot fetch private repos."}, status=400)
                url = "https://api.github.com/user/repos?per_page=100&sort=updated&visibility=all&affiliation=owner"
            else:
                url = f"https://api.github.com/users/{username}/repos?per_page=100&sort=updated"

            titles = []
            seen_urls = set()
            while url and url not in seen_urls:
                seen_urls.add(url)
                r = requests.get(url, headers=headers, timeout=20)
                if not r.ok:
                    return Response({"error": "github request failed", "status": r.status_code, "detail": r.text[:300]}, status=502)
                repos = r.json() or []
                titles.extend([repo.get("name") for repo in repos if isinstance(repo, dict)])
                # Parse pagination Link header
                link = r.headers.get("Link", "")
                next_url = None
                if link:
                    parts = [p.strip() for p in link.split(",")]
                    for p in parts:
                        if "rel=\"next\"" in p:
                            segs = p.split(";")
                            if segs:
                                raw = segs[0].strip()
                                if raw.startswith("<") and raw.endswith(">"):
                                    next_url = raw[1:-1]
                                    break
                url = next_url
                # Safety cap to avoid excessive pages
                if len(seen_urls) >= 10:
                    break
            return Response({
                "username": username,
                "include_private": include_private,
                "count": len(titles),
                "titles": titles,
            })
        except Exception as e:
            return Response({"error": str(e)}, status=500)


class GitHubReposHTMLView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(exclude=True)
    def get(self, request):
        username = request.GET.get("username")
        include_private = request.GET.get("include_private") in {"1", "true", "True", "yes"}
        if not username and not include_private:
            return HttpResponse("<h3>Pass ?username=YOUR_GITHUB_USERNAME or ?include_private=1 (requires token)</h3>")
        # Reuse the JSON logic by calling the view method directly
        json_response = GitHubReposJSONView().get(request)
        if json_response.status_code != 200:
            return HttpResponse(f"<pre>Error: {json_response.data}</pre>", status=json_response.status_code)
        data = json_response.data
        items = "".join(f"<li>{title}</li>" for title in data.get("titles", []))
        html = f"""
            <html>
              <head><title>GitHub Repos for {username}</title></head>
              <body>
                <h2>GitHub Repositories for {username or 'authenticated user'} (total: {data.get('count', 0)})</h2>
                <p>include_private={data.get('include_private', False)}</p>
                <ul>{items}</ul>
              </body>
            </html>
        """
        return HttpResponse(html)


class KnowledgeIngestCodeView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        description="Ingest actual GitHub repo code into KnowledgeDocument."
        " Body: { repos: [\"owner/repo\"... ] | optional, username: string | optional, include_private: bool | optional }."
        " If repos not provided, uses username (or include_private=1 to use authenticated user) to list repos.",
        request=KnowledgeIngestRequestSerializer,
        responses={200: KnowledgeIngestResponseSerializer},
    )
    def post(self, request):
        body = request.data or {}
        repos = body.get("repos") or []
        username = body.get("username")
        include_private = bool(body.get("include_private"))
        gh_token = getattr(settings, "GITHUB_TOKEN", "")
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "portfolio-backend/1.0",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if gh_token:
            headers["Authorization"] = f"Bearer {gh_token}"
        # If no explicit repos, resolve from username or authenticated user
        try:
            if not repos:
                if include_private:
                    if not gh_token:
                        return Response({"error": "GITHUB_TOKEN not configured; cannot fetch private repos."}, status=400)
                    list_url = "https://api.github.com/user/repos?per_page=100&sort=updated&visibility=all&affiliation=owner"
                else:
                    if not username:
                        return Response({"error": "username required if include_private is false and repos not provided"}, status=400)
                    list_url = f"https://api.github.com/users/{username}/repos?per_page=100&sort=updated"
                seen = set()
                while list_url and list_url not in seen:
                    seen.add(list_url)
                    lr = requests.get(list_url, headers=headers, timeout=20)
                    if not lr.ok:
                        return Response({"error": "github list repos failed", "status": lr.status_code, "detail": lr.text[:300]}, status=502)
                    for repo in lr.json() or []:
                        full = repo.get("full_name")  # owner/name
                        if full:
                            repos.append(full)
                    link = lr.headers.get("Link", "")
                    next_url = None
                    if link:
                        for p in [p.strip() for p in link.split(",")]:
                            if "rel=\"next\"" in p:
                                raw = p.split(";")[0].strip()
                                if raw.startswith("<") and raw.endswith(">"):
                                    next_url = raw[1:-1]
                                    break
                    list_url = next_url
                    if len(seen) >= 10:
                        break
        except Exception as e:
            return Response({"error": f"repo discovery failed: {e}"}, status=500)

        ingested = []
        skipped = 0
        # Filters
        skip_dirs = {".git", "node_modules", "dist", "build", ".next", ".venv", "venv", ".cache", "__pycache__"}
        # Common code/text extensions
        include_ext = {
            ".py", ".js", ".jsx", ".ts", ".tsx", ".json", ".yml", ".yaml", ".toml", ".ini", ".cfg",
            ".css", ".scss", ".sass", ".html", ".md", ".txt", ".sql", ".sh", ".bat", ".ps1", ".rs", ".go",
            ".java", ".kt", ".rb", ".php", ".c", ".h", ".cpp", ".hpp", ".cs"
        }
        # Per-file safety cap (bytes); set to None for unlimited. Use a large cap to avoid memory blow-ups.
        max_blob_bytes = None

        for full_name in repos:
            try:
                owner, repo = full_name.split("/", 1)
            except ValueError:
                continue
            try:
                # Get default branch
                meta = requests.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers, timeout=20)
                if not meta.ok:
                    skipped += 1
                    continue
                default_branch = (meta.json() or {}).get("default_branch") or "main"
                # Get tree (recursive)
                tree_r = requests.get(
                    f"https://api.github.com/repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1",
                    headers=headers,
                    timeout=30,
                )
                if not tree_r.ok:
                    skipped += 1
                    continue
                tree = (tree_r.json() or {}).get("tree") or []
                for entry in tree:
                    if entry.get("type") != "blob":
                        continue
                    path = entry.get("path") or ""
                    # Skip unneeded directories
                    parts = path.split("/")
                    if any(p in skip_dirs for p in parts):
                        continue
                    # Extension filter
                    ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
                    if ext and ext.lower() not in include_ext:
                        continue
                    sha = entry.get("sha")
                    if not sha:
                        continue
                    blob_r = requests.get(
                        f"https://api.github.com/repos/{owner}/{repo}/git/blobs/{sha}",
                        headers=headers,
                        timeout=30,
                    )
                    if not blob_r.ok:
                        continue
                    blob = blob_r.json() or {}
                    if blob.get("encoding") == "base64":
                        raw = base64.b64decode(blob.get("content", ""))
                    else:
                        raw = (blob.get("content") or "").encode("utf-8", errors="ignore")
                    if max_blob_bytes and len(raw) > max_blob_bytes:
                        continue
                    try:
                        text = raw.decode("utf-8")
                    except Exception:
                        # Try latin-1 fallback
                        try:
                            text = raw.decode("latin-1")
                        except Exception:
                            continue
                    header = f"Repo: {owner}/{repo}\nFile: {path}\n\n"
                    doc = KnowledgeDocument.objects.create(
                        source=f"github_code:{owner}/{repo}:{path}",
                        title=f"{owner}/{repo}:{path}",
                        content=header + text,
                    )
                    ingested.append(doc)
            except Exception:
                skipped += 1
                continue

        return Response({
            "ingested": KnowledgeDocumentSerializer(ingested, many=True).data,
            "ingested_count": len(ingested),
            "skipped": skipped,
        })
