"""
URL configuration for seud_portfolio_backend project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
import os
from rest_framework import routers
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from portfolio import views as portfolio_views
from django.conf import settings
from django.conf.urls.static import static

router = routers.DefaultRouter()
router.register(r'profiles', portfolio_views.ProfileViewSet, basename='profile')
router.register(r'projects', portfolio_views.ProjectViewSet)
router.register(r'experiences', portfolio_views.ExperienceViewSet)
router.register(r'skills', portfolio_views.SkillViewSet)
router.register(r'blogposts', portfolio_views.BlogPostViewSet)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health", lambda request: JsonResponse({"status": "ok"})),
    path(
        "api/info",
        lambda request: JsonResponse(
            {
                "app": "portfolio-backend",
                "env": os.environ.get("DJANGO_ENV", "dev"),
                "debug": os.environ.get("DEBUG", "True"),
                "version": "1.0.0",
            }
        ),
    ),
    path("api/", include(router.urls)),
    path("api/contact", portfolio_views.ContactView.as_view(), name="contact"),
    path("api/knowledge/refresh", portfolio_views.KnowledgeRefreshView.as_view(), name="knowledge-refresh"),
    path("api/chat/ask", portfolio_views.ChatAskView.as_view(), name="chat-ask"),
    path("api/knowledge/ingest_code", portfolio_views.KnowledgeIngestCodeView.as_view(), name="knowledge-ingest-code"),
    path("api/knowledge/sources", portfolio_views.KnowledgeSourcesView.as_view(), name="knowledge-sources"),
    path("api/github/repos.json", portfolio_views.GitHubReposJSONView.as_view(), name="github-repos-json"),
    path("test/github-repos", portfolio_views.GitHubReposHTMLView.as_view(), name="github-repos-html"),
    path("api/auth/jwt/create", TokenObtainPairView.as_view(), name="jwt-create"),
    path("api/auth/jwt/refresh", TokenRefreshView.as_view(), name="jwt-refresh"),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

