from rest_framework import viewsets, filters, status
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
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


class ContactThrottle(AnonRateThrottle):
    rate = "10/hour"


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
                content = f"Project: {pr.title}\nDescription: {pr.description}\nSkills: {skills}\nFeatured: {pr.featured}\n"
                docs.append(KnowledgeDocument.objects.create(source=f"project:{pr.id}", title=pr.title, content=content))
            for e in Experience.objects.all():
                content = f"Experience: {e.company}\nRole: {e.role}\nPeriod: {e.start_date} - {e.end_date or 'present'}\n{e.description}\n"
                docs.append(KnowledgeDocument.objects.create(source=f"experience:{e.id}", title=e.role, content=content))
        return Response(KnowledgeDocumentSerializer(docs, many=True).data)


class ChatAskView(APIView):
    throttle_classes = [ContactThrottle]
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
        knowledge_chunks = KnowledgeDocument.objects.order_by("-updated_at").values_list("content", flat=True)
        knowledge = "\n---\n".join(knowledge_chunks)[:8000]
        started = timezone.now()
        log = ChatLog(provider=provider, model=model, question=question)
        try:
            res = ai_ask(provider, question, knowledge, model=model, max_tokens=max_tokens)
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
