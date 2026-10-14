from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.conf.urls.static import static
from django.views.generic import TemplateView


class FrontendView(TemplateView):
    """Single-page frontend shell.

    Sends no-cache headers so browsers never serve a stale
    copy of the HTML. Static assets (CSS/JS) get a
    content version query string so a stale browser cache
    cannot keep an old build alive after a change.
    """

    template_name = "index.html"

    @staticmethod
    def asset_version():
        """Short token derived from the newest asset mtime."""
        latest = 0
        for name in ("style.css", "script.js"):
            try:
                latest = max(latest, int((settings.BASE_DIR / "frontend" / name).stat().st_mtime))
            except OSError:
                continue
        return latest or 1

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["asset_version"] = self.asset_version()
        return context

    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        response["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0"
        )
        response["Pragma"] = "no-cache"
        return response


urlpatterns = [
    path("admin/", admin.site.urls),
    # API endpoints, each app's urls are rooted at /api/
    path("api/", include("accounts.urls")),
    path("api/", include("properties.urls")),
    path("api/", include("reviews.urls")),
    path("api/", include("landlords.urls")),
    path("api/", include("ai.urls")),
    path("api/", include("payments.urls")),
    # Single-page frontend served by Django (no CORS needed in local dev)
    path("", FrontendView.as_view(), name="home"),
]

# Serve user-uploaded media during local development only.
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
