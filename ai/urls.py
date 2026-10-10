from django.urls import path

from . import views

app_name = "ai"

urlpatterns = [
    path("ai/chat/", views.ChatView.as_view(), name="chat"),
]
