from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.conf.urls.static import static
from django.views.generic import TemplateView


class FrontendView(TemplateView):
    """Single-page frontend shell.

    Sends no-cache headers so browsers never serve a stale
    copy of the HTML (e.g. an older version whose map
    libraries pointed at a CDN that no longer resolves).
    Static assets (CSS/JS) are fingerprinted by their URLs
    and keep normal caching.

    Also injects the server-side map tile configuration so
    the tile provider (and any API key) can be changed via
    environment variables without touching the frontend.
    """

    template_name = "index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["map_tile_url"] = settings.MAP_TILE_URL
        context["map_tile_attribution"] = settings.MAP_TILE_ATTRIBUTION
        context["map_tile_api_key"] = settings.MAP_TILE_API_KEY
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
