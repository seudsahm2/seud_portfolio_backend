from rest_framework import serializers
from .models import Profile, Project, Experience, Skill, BlogPost, KnowledgeDocument, ChatLog
from django.contrib.auth import get_user_model
User = get_user_model()

class SkillSerializer(serializers.ModelSerializer):
    years_used = serializers.SerializerMethodField()
    project_count = serializers.SerializerMethodField()

    class Meta:
        model = Skill
        fields = [
            "id",
            "name",
            "category",
            "description",
            "docs_url",
            "icon",
            "highlights",
            "since_year",
            "years_used",
            "primary",
            "accent",
            "order",
            "project_count",
        ]
        read_only_fields = ["years_used", "project_count"]

    def get_years_used(self, obj: Skill):
        import datetime
        if obj.since_year:
            return max(0, datetime.datetime.now().year - obj.since_year)
        return None

    def get_project_count(self, obj: Skill):
        from .models import Project  # local import to avoid circulars at import time
        return Project.objects.filter(skills=obj).count()

class ProjectSerializer(serializers.ModelSerializer):
    skills = SkillSerializer(many=True, read_only=True)

    class Meta:
        model = Project
        fields = "__all__"

class ExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Experience
        fields = "__all__"

class ProfileSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()

    class Meta:
        model = Profile
        fields = [
            "id",
            "user",
            "name",
            "email",
            "title",
            "tagline",
            "bio",
            "location",
            "website",
            "primary_stack",
            "years_experience",
            "open_to_opportunities",
            "avatar",
            "avatar_url",
            "socials",
            "highlights",
        ]
        read_only_fields = ["name", "email", "avatar_url"]

    def get_name(self, obj: Profile):
        if obj.user and hasattr(obj.user, "get_full_name"):
            return obj.user.get_full_name() or obj.user.username
        return None

    def get_email(self, obj: Profile):
        if obj.user:
            return obj.user.email
        return None

class BlogPostSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogPost
        fields = "__all__"


class ContactSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    email = serializers.EmailField()
    message = serializers.CharField(max_length=2000, allow_blank=False)


class KnowledgeDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnowledgeDocument
        fields = "__all__"


class ChatLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatLog
        fields = "__all__"


class ChatAskSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(choices=[("google", "google"), ("groq", "groq")])
    model = serializers.CharField(max_length=100, required=False, allow_blank=True)
    question = serializers.CharField(max_length=4000)
    max_tokens = serializers.IntegerField(required=False)
    structured = serializers.BooleanField(required=False, default=True)
    top_n = serializers.IntegerField(required=False, min_value=1, max_value=20, default=6)

class KnowledgeSourcesSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    counts = serializers.DictField(child=serializers.IntegerField())
    github_code_samples = serializers.ListField(child=serializers.CharField())


class KnowledgeIngestRequestSerializer(serializers.Serializer):
    # Either provide explicit repos (owner/name) or set username/include_private
    repos = serializers.ListField(child=serializers.CharField(), required=False)
    username = serializers.CharField(required=False, allow_blank=True)
    include_private = serializers.BooleanField(required=False, default=False)


class KnowledgeIngestResponseSerializer(serializers.Serializer):
    ingested = KnowledgeDocumentSerializer(many=True)
    ingested_count = serializers.IntegerField()
    skipped = serializers.IntegerField()