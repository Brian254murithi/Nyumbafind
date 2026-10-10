from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("payments/stk-push/", views.StkPushView.as_view(), name="stk-push"),
    path(
        "payments/<str:reference>/status/",
        views.PaymentStatusView.as_view(),
        name="payment-status",
    ),
    path(
        "payments/history/",
        views.PaymentHistoryView.as_view(),
        name="payment-history",
    ),
    path(
        "payments/callback/",
        views.PaymentCallbackView.as_view(),
        name="payment-callback",
    ),
    path(
        "payments/config/",
        views.PaymentConfigView.as_view(),
        name="payment-config",
    ),
    path(
        "payments/reconcile/",
        views.ReconcileView.as_view(),
        name="payment-reconcile",
    ),
]
