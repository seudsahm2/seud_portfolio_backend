from rest_framework import viewsets, filters, status
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from drf_spectacular.utils import extend_schema
from django_filters.rest_framework import DjangoFilterBackend
from .models import (
    Profile,
    Project,
    Experience,
    Skill,
    BlogPost,
    BlogSeries,
    BlogComment,
    BlogLike,
    BlogBookmark,
    BlogSubscription,
    KnowledgeDocument,
    ChatLog,
)
from .serializers import (
    ProfileSerializer,
    ProjectSerializer,
    ExperienceSerializer,
    SkillSerializer,
    BlogPostSerializer,
    BlogSeriesSerializer,
    BlogCommentSerializer,
    BlogSubscriptionSerializer,
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
    search_fields = ["title", "tagline", "location", "primary_stack"]

    def create(self, request, *args, **kwargs):
        if Profile.objects.exists():
            return Response({"detail": "Profile already exists. Update it instead."}, status=status.HTTP_400_BAD_REQUEST)
        return super().create(request, *args, **kwargs)

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
    search_fields = ["name", "description", "category"]
    filterset_fields = ["category", "primary"]
    ordering_fields = ["order", "name", "id"]


class BlogSeriesViewSet(viewsets.ModelViewSet):
    queryset = BlogSeries.objects.all()
    serializer_class = BlogSeriesSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "slug", "description"]
    ordering_fields = ["order", "title", "id"]

from django.db.models import F
from rest_framework.decorators import action
import hashlib


def _client_fingerprint(request):
    ua = request.META.get("HTTP_USER_AGENT", "")
    ip = request.META.get("REMOTE_ADDR", "") or request.META.get("HTTP_X_FORWARDED_FOR", "")
    raw = f"{ip}|{ua}".encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()


class BlogPostViewSet(viewsets.ModelViewSet):
    queryset = BlogPost.objects.all()
    serializer_class = BlogPostSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "slug", "summary", "content", "tags"]
    ordering_fields = ["published_at", "updated_at", "views_count", "likes_count", "id"]

    def retrieve(self, request, *args, **kwargs):
        # Increment views atomically
        pk = kwargs.get(self.lookup_field or "pk")
        try:
            BlogPost.objects.filter(pk=pk).update(views_count=F("views_count") + 1)
        except Exception:
            pass
        return super().retrieve(request, *args, **kwargs)

    @action(detail=True, methods=["post"], permission_classes=[AllowAny])
    def like(self, request, pk=None):
        post = self.get_object()
        fp = _client_fingerprint(request)
        BlogLike.objects.get_or_create(post=post, fingerprint=fp)
        post.likes_count = BlogLike.objects.filter(post=post).count()
        post.save(update_fields=["likes_count"])
        return Response({"likes": post.likes_count})

    @action(detail=True, methods=["delete"], permission_classes=[AllowAny])
    def unlike(self, request, pk=None):
        post = self.get_object()
        fp = _client_fingerprint(request)
        BlogLike.objects.filter(post=post, fingerprint=fp).delete()
        post.likes_count = BlogLike.objects.filter(post=post).count()
        post.save(update_fields=["likes_count"])
        return Response({"likes": post.likes_count})

    @action(detail=True, methods=["post"], permission_classes=[AllowAny])
    def bookmark(self, request, pk=None):
        post = self.get_object()
        fp = _client_fingerprint(request)
        BlogBookmark.objects.get_or_create(post=post, fingerprint=fp)
        post.bookmarks_count = BlogBookmark.objects.filter(post=post).count()
        post.save(update_fields=["bookmarks_count"])
        return Response({"bookmarks": post.bookmarks_count})

    @action(detail=True, methods=["delete"], permission_classes=[AllowAny])
    def unbookmark(self, request, pk=None):
        post = self.get_object()
        fp = _client_fingerprint(request)
        BlogBookmark.objects.filter(post=post, fingerprint=fp).delete()
        post.bookmarks_count = BlogBookmark.objects.filter(post=post).count()
        post.save(update_fields=["bookmarks_count"])
        return Response({"bookmarks": post.bookmarks_count})

    @action(detail=True, methods=["get", "post"], permission_classes=[AllowAny], url_path="comments")
    def comments(self, request, pk=None):
        post = self.get_object()
        if request.method.lower() == "get":
            qs = BlogComment.objects.filter(post=post, is_deleted=False, is_approved=True).order_by("created_at")
            return Response(BlogCommentSerializer(qs, many=True).data)
        # POST create
        if not post.allow_comments:
            return Response({"error": "comments disabled"}, status=400)
        data = request.data or {}
        parent_id = data.get("parent")
        parent = None
        if parent_id:
            parent = BlogComment.objects.filter(pk=parent_id, post=post).first()
        comment = BlogComment.objects.create(
            post=post,
            parent=parent,
            name=(data.get("name") or "Anonymous").strip()[:120],
            email=(data.get("email") or "").strip(),
            content=(data.get("content") or "").strip(),
            is_approved=True,
        )
        post.comments_count = BlogComment.objects.filter(post=post, is_deleted=False, is_approved=True).count()
        post.save(update_fields=["comments_count"])
        return Response(BlogCommentSerializer(comment).data, status=201)

    @action(detail=True, methods=["get"], permission_classes=[AllowAny])
    def related(self, request, pk=None):
        post = self.get_object()
        qs = BlogPost.objects.exclude(pk=post.pk).filter(status="published")
        # Boost same series first
        results = []
        if post.series_id:
            results.extend(list(qs.filter(series_id=post.series_id).order_by("pinned_order", "-published_at")[:6]))
        # By tag overlap
        tags = set([t.lower() for t in (post.tags or [])])
        if tags:
            tagged = []
            for cand in qs:
                ctags = set([t.lower() for t in (cand.tags or [])])
                if ctags & tags:
                    tagged.append((len(ctags & tags), cand))
            tagged.sort(key=lambda x: (-x[0], -x[1].published_at.timestamp() if x[1].published_at else 0))
            results.extend([c for _, c in tagged[:6]])
        # Fallback recent
        if len(results) < 6:
            for cand in qs.order_by("-published_at")[:6]:
                if cand not in results:
                    results.append(cand)
        results = results[:6]
        return Response(BlogPostSerializer(results, many=True).data)


class BlogSubscriptionView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=BlogSubscriptionSerializer, responses={200: BlogSubscriptionSerializer})
    def post(self, request):
        s = BlogSubscriptionSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        email = s.validated_data["email"].lower()
        sub, created = BlogSubscription.objects.get_or_create(email=email)
        if not created and not sub.active:
            sub.active = True
            sub.save(update_fields=["active"])
        return Response({"email": sub.email, "verified": sub.verified, "active": sub.active})


class BlogSubscriptionVerifyView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=BlogSubscriptionSerializer, responses={200: BlogSubscriptionSerializer})
    def post(self, request):
        token = request.data.get("token") or ""
        try:
            uuid.UUID(token)
        except Exception:
            return Response({"error": "invalid token"}, status=400)
        sub = BlogSubscription.objects.filter(verify_token=token).first()
        if not sub:
            return Response({"error": "not found"}, status=404)
        if not sub.verified:
            sub.verified = True
            sub.save(update_fields=["verified"])
        return Response({"email": sub.email, "verified": sub.verified, "active": sub.active})


class BlogSubscriptionUnsubscribeView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=BlogSubscriptionSerializer, responses={200: None})
    def post(self, request):
        token = request.data.get("token") or ""
        try:
            uuid.UUID(token)
        except Exception:
            return Response({"error": "invalid token"}, status=400)
        sub = BlogSubscription.objects.filter(unsub_token=token).first()
        if not sub:
            return Response({"error": "not found"}, status=404)
        if sub.active:
            sub.active = False
            sub.save(update_fields=["active"])
        return Response(status=200)


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
    # Admin-only: rebuilds knowledge base from DB
    permission_classes = [IsAdminUser]

    @extend_schema(request=None, responses={200: KnowledgeDocumentSerializer(many=True)})
    def post(self, request):
        docs = []
        with transaction.atomic():
            KnowledgeDocument.objects.all().delete()
            for p in Profile.objects.all():
                name = getattr(p.user, "get_full_name", lambda: "")() or (p.user.username if p.user else "")
                content = (
                    f"Profile: {name}\nTitle: {p.title}\nTagline: {p.tagline}\nBio: {p.bio}\n"
                    f"Location: {p.location}\nWebsite: {p.website}\nPrimary Stack: {p.primary_stack}\n"
                    f"Years Experience: {p.years_experience}\nOpen To Opportunities: {p.open_to_opportunities}\n"
                    f"Highlights: {'; '.join(p.highlights or [])}\n"
                )
                docs.append(KnowledgeDocument.objects.create(source="profile", title=name or "profile", content=content))
            for pr in Project.objects.all():
                skills = ", ".join(pr.skills.values_list("name", flat=True))
                topics = ", ".join((pr.topics or []))
                meta = (
                    f"Stars: {pr.stars} | Forks: {pr.forks} | Language: {pr.language} | "
                    f"Topics: {topics} | Last Pushed: {pr.last_pushed or ''}"
                )
                content = (
                    f"Project: {pr.title}\nDescription: {pr.description}\nSkills: {skills}\nFeatured: {pr.featured}\n"
                    f"Link: {pr.link}\nRepo: {pr.repo}\n{meta}\n"
                )
                docs.append(KnowledgeDocument.objects.create(source=f"project:{pr.id}", title=pr.title, content=content))
            for s in Skill.objects.all():
                content = (
                    f"Skill: {s.name}\nCategory: {s.category}\nPrimary: {s.primary}\n"
                    f"Since: {s.since_year or ''}\nDocs: {s.docs_url}\n"
                    f"Description: {s.description}\nHighlights: {'; '.join(s.highlights or [])}\n"
                )
                docs.append(KnowledgeDocument.objects.create(source=f"skill:{s.id}", title=s.name, content=content))
            for b in BlogPost.objects.all():
                tg = ", ".join(b.tags or [])
                content = (
                    f"Blog: {b.title}\nSlug: {b.slug}\nSummary: {b.summary}\nTags: {tg}\n"
                    f"Reading: {b.reading_time} min\nContent: {b.content[:1500]}\n"
                )
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
                nm = getattr(p.user, "get_full_name", lambda: "")() or (p.user.username if p.user else "")
                parts.append(
                    f"Profile: {nm}\nTitle: {p.title}\nTagline: {p.tagline}\nBio: {p.bio}\nLocation: {p.location}\nWebsite: {p.website}\n"
                )
            for pr in Project.objects.all():
                skills = ", ".join(pr.skills.values_list("name", flat=True))
                topics = ", ".join((pr.topics or []))
                meta = (
                    f"Stars: {pr.stars} | Forks: {pr.forks} | Language: {pr.language} | "
                    f"Topics: {topics} | Last Pushed: {pr.last_pushed or ''}"
                )
                parts.append(
                    f"Project: {pr.title}\nDescription: {pr.description}\nSkills: {skills}\nFeatured: {pr.featured}\n"
                    f"Link: {pr.link}\nRepo: {pr.repo}\n{meta}\n"
                )
            for s in Skill.objects.all():
                parts.append(
                    f"Skill: {s.name}\nCategory: {s.category}\nPrimary: {s.primary}\nSince: {s.since_year or ''}\n"
                )
            for b in BlogPost.objects.all():
                parts.append(f"Blog: {b.title}\nSlug: {b.slug}\nSummary: {b.summary}\nContent: {b.content[:1500]}\n")
            knowledge = "\n---\n".join(parts)

        started = timezone.now()
        log = ChatLog(provider=provider, model=model, question=question)
        try:
            # Build prompt variables from Profile if available
            prof = Profile.objects.first()
            owner_name = None
            if prof and prof.user and hasattr(prof.user, "get_full_name"):
                owner_name = prof.user.get_full_name() or prof.user.username
            system_vars = {
                "owner_name": owner_name or "",
                "owner_title": getattr(prof, "title", ""),
                "owner_tagline": getattr(prof, "tagline", ""),
                "primary_stack": getattr(prof, "primary_stack", "") or ", ".join(
                    Skill.objects.order_by("order", "name").values_list("name", flat=True)[:5]
                ),
                "highlights": "; ".join(getattr(prof, "highlights", []) or []),
                "summary_tokens": max_tokens or 512,
                "top_n": top_n,
                "years_experience": getattr(prof, "years_experience", 0),
                "open_to_opportunities": getattr(prof, "open_to_opportunities", True),
            }
            res = ai_ask(provider, question, knowledge, model=model, max_tokens=max_tokens, system_vars=system_vars, structured=structured)
            log.answer = res.text or "(empty answer)"
            log.answer_json = dict(res.data) if isinstance(res.data, dict) else None
            log.tokens_prompt = res.tokens_prompt
            log.tokens_completion = res.tokens_completion
            log.status = "ok"
        except Exception as e:
            # Provide a user-visible fallback answer instead of leaving blank
            log.status = "error"
            log.error = str(e)
            log.answer = f"AI provider error: {e}. Please check API keys or try again later."
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
    # Admin-only: pulls code from GitHub and stores in DB
    permission_classes = [IsAdminUser]

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


class GitHubIngestPinnedView(APIView):
    """Admin-only: fetch pinned GitHub repositories (via GraphQL) and upsert Projects.

    Requires GITHUB_TOKEN (with public_repo scope sufficient for public pinned repos; private requires repo scope).
    Upsert logic:
      - Identify project by repo URL (htmlUrl) or link if already stored.
      - Update stars, forks, language, topics, last_pushed, featured=True.
      - If repository topics include names matching existing Skill.name (case-insensitive) or primary language matches a Skill,
        attach those skills (non-destructive; existing associations preserved).
    Body: { username?: string } – if omitted, GraphQL viewer used (token required).
    """
    permission_classes = [IsAdminUser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ingest_pinned"

    @extend_schema(request=None, responses={200: ProjectSerializer(many=True)})
    def post(self, request):
        gh_token = getattr(settings, "GITHUB_TOKEN", "")
        if not gh_token:
            return Response({"error": "GITHUB_TOKEN not configured"}, status=400)
        username = request.data.get("username")
        # Build GraphQL query depending on whether a username was provided.
        if username:
            query = """
            query($login: String!) {
                user(login: $login) {
                    pinnedItems(first: 10, types: REPOSITORY) {
                        totalCount
                        edges { node { ...RepoFields } }
                    }
                }
            }
            fragment RepoFields on Repository {
                name
                description
                url
                homepageUrl
                stargazerCount
                forkCount
                primaryLanguage { name }
                repositoryTopics(first: 20) { edges { node { topic { name } } } }
                pushedAt
                licenseInfo { spdxId name }
                issues(states: OPEN) { totalCount }
                watchers { totalCount }
                defaultBranchRef { name }
                latestRelease { tagName name publishedAt }
                isArchived
                isTemplate
                readme1: object(expression: "HEAD:README.md") { ... on Blob { text byteSize } }
                readme2: object(expression: "HEAD:README.MD") { ... on Blob { text byteSize } }
                readme3: object(expression: "HEAD:README") { ... on Blob { text byteSize } }
                workflowsDir: object(expression: "HEAD:.github/workflows") { ... on Tree { entries { name } } }
            }
            """
            variables = {"login": username}
        else:
            query = """
            query {
                viewer {
                    pinnedItems(first: 10, types: REPOSITORY) {
                        totalCount
                        edges { node { ...RepoFields } }
                    }
                }
            }
            fragment RepoFields on Repository {
                name
                description
                url
                homepageUrl
                stargazerCount
                forkCount
                primaryLanguage { name }
                repositoryTopics(first: 20) { edges { node { topic { name } } } }
                pushedAt
                licenseInfo { spdxId name }
                issues(states: OPEN) { totalCount }
                watchers { totalCount }
                defaultBranchRef { name }
                latestRelease { tagName name publishedAt }
                isArchived
                isTemplate
                readme1: object(expression: "HEAD:README.md") { ... on Blob { text byteSize } }
                readme2: object(expression: "HEAD:README.MD") { ... on Blob { text byteSize } }
                readme3: object(expression: "HEAD:README") { ... on Blob { text byteSize } }
                workflowsDir: object(expression: "HEAD:.github/workflows") { ... on Tree { entries { name } } }
            }
            """
            variables = {}
        headers = {
            "Authorization": f"Bearer {gh_token}",
            "Accept": "application/json",
        }
        # Cache guard to avoid frequent repeated updates (10 minutes)
        from django.core.cache import cache
        cache_key = f"gh_ingest_pinned_lock:{username or 'viewer'}"
        if cache.get(cache_key):
            return Response({"detail": "Ingestion recently performed; please wait a few minutes."}, status=429)
        cache.set(cache_key, True, timeout=10 * 60)
        try:
            r = requests.post("https://api.github.com/graphql", json={"query": query, "variables": variables}, headers=headers, timeout=25)
            if not r.ok:
                return Response({"error": "GraphQL request failed", "status": r.status_code, "detail": r.text[:300]}, status=502)
            data = r.json() or {}
        except Exception as e:
            return Response({"error": str(e)}, status=500)
        # Surface GraphQL errors instead of failing silently
        if isinstance(data, dict) and data.get("errors"):
            return Response({"error": "GitHub GraphQL errors", "details": data.get("errors")}, status=502)

        pinned = []
        container = (data.get("data", {}) or {})
        items = None
        if username:
            user_obj = container.get("user") or {}
            items = user_obj.get("pinnedItems") or {}
        else:
            viewer_obj = container.get("viewer") or {}
            items = viewer_obj.get("pinnedItems") or {}
        edges = (items.get("edges") or []) if isinstance(items, dict) else []
        pinned_count = int((items or {}).get("totalCount") or 0)

        # Skill lookup maps
        skill_by_lower = {s.name.lower(): s for s in Skill.objects.all()}
        updated_projects = []
        from django.utils.dateparse import parse_datetime

        for edge in edges:
            node = edge.get("node") or {}
            url = node.get("url")
            if not url:
                continue
            homepage = node.get("homepageUrl") or ""
            title = node.get("name") or ""
            desc = node.get("description") or ""
            stars = node.get("stargazerCount") or 0
            forks = node.get("forkCount") or 0
            lang = (node.get("primaryLanguage") or {}).get("name") or ""
            topic_edges = (node.get("repositoryTopics") or {}).get("edges") or []
            topics = [te.get("node", {}).get("topic", {}).get("name") for te in topic_edges if isinstance(te, dict)]
            pushed_at_raw = node.get("pushedAt")
            pushed_dt = parse_datetime(pushed_at_raw) if pushed_at_raw else None
            # Rich details
            lic = node.get("licenseInfo") or {}
            license_spdx = lic.get("spdxId") or ""
            license_name = lic.get("name") or ""
            open_issues = ((node.get("issues") or {}).get("totalCount") or 0)
            watchers = ((node.get("watchers") or {}).get("totalCount") or 0)
            default_branch = ((node.get("defaultBranchRef") or {}).get("name") or "")
            latest_rel = node.get("latestRelease") or {}
            latest_release_tag = latest_rel.get("tagName") or (latest_rel.get("name") or "")
            latest_release_published = parse_datetime(latest_rel.get("publishedAt")) if latest_rel.get("publishedAt") else None
            is_archived = bool(node.get("isArchived"))
            is_template = bool(node.get("isTemplate"))
            readme_text = None
            for key in ("readme1", "readme2", "readme3"):
                blob = node.get(key) or {}
                if isinstance(blob, dict) and blob.get("text"):
                    readme_text = blob.get("text")
                    break
            wf = node.get("workflowsDir") or {}
            entries = (wf.get("entries") or []) if isinstance(wf, dict) else []
            has_ci = bool(entries)

            # Upsert Project by repo URL
            proj, _created = Project.objects.get_or_create(repo=url, defaults={
                "title": title or url.rsplit("/", 1)[-1],
                "description": desc or "",
                "link": homepage or url,
            })
            # Update metadata
            changed = False
            for attr, val in [
                ("title", title or proj.title),
                ("description", desc or proj.description),
                ("link", homepage or proj.link or url),
                ("stars", stars),
                ("forks", forks),
                ("language", lang),
                ("topics", topics),
                ("last_pushed", pushed_dt),
                ("featured", True),
                ("license_spdx", license_spdx),
                ("license_name", license_name),
                ("open_issues", open_issues),
                ("watchers", watchers),
                ("default_branch", default_branch),
                ("latest_release_tag", latest_release_tag),
                ("latest_release_published", latest_release_published),
                ("is_archived", is_archived),
                ("is_template", is_template),
                ("has_ci", has_ci),
            ]:
                if getattr(proj, attr) != val:
                    setattr(proj, attr, val)
                    changed = True
            # README excerpt: store first ~3000 chars to keep it lightweight
            if readme_text:
                excerpt = (readme_text or "")[:3000]
                if proj.readme_excerpt != excerpt:
                    proj.readme_excerpt = excerpt
                    changed = True
            if changed:
                proj.save()
            # Associate skills by language/topic names
            to_add = []
            if lang and lang.lower() in skill_by_lower:
                to_add.append(skill_by_lower[lang.lower()])
            for t in topics:
                if t and t.lower() in skill_by_lower:
                    to_add.append(skill_by_lower[t.lower()])
            if to_add:
                for s in to_add:
                    proj.skills.add(s)
            updated_projects.append(proj)

        # Serialize; include pinned count as a header for diagnostics without breaking clients
        resp = Response(ProjectSerializer(updated_projects, many=True).data)
        try:
            resp["X-Pinned-Count"] = str(pinned_count)
            resp["X-Updated-Count"] = str(len(updated_projects))
        except Exception:
            pass
        return resp
