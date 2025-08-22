from django.contrib import admin
from .models import Profile, Project, Experience, Skill, BlogPost
from .models import KnowledgeDocument, ChatLog

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "title", "email")
    search_fields = ("full_name", "title", "email")

@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name", "level")
    list_filter = ("level",)

@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("title", "featured", "image_url")
    list_filter = ("featured",)
    search_fields = ("title", "description")

@admin.register(Experience)
class ExperienceAdmin(admin.ModelAdmin):
    list_display = ("role", "company", "start_date", "end_date")
    list_filter = ("company",)

@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ("title", "slug", "published_at", "cover_image_url")
    search_fields = ("title", "slug", "summary")
    prepopulated_fields = {"slug": ("title",)}

@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    list_display = ("source", "title", "updated_at")
    search_fields = ("source", "title", "content")

@admin.register(ChatLog)
class ChatLogAdmin(admin.ModelAdmin):
    list_display = ("provider", "model", "status", "latency_ms", "created_at")
    search_fields = ("question", "answer", "error")
