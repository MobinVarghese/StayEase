from django.urls import path

from .views import admin_dashboard_view
from .views import approve_password_reset
from .views import forgot_password_request_view
from .views import forgot_password_success_view
from .views import owner_dashboard_view
from .views import reject_password_reset
from .views import tenant_dashboard_view
from .views import user_change_password_view
from .views import user_detail_view
from .views import user_profile_view
from .views import user_redirect_view
from .views import user_update_view

app_name = "users"
urlpatterns = [
    path("~redirect/", view=user_redirect_view, name="redirect"),
    path("profile/", view=user_profile_view, name="profile"),
    path("profile/change-password/", view=user_change_password_view, name="change_password"),
    path("~update/", view=user_update_view, name="update"),
    path("<int:pk>/", view=user_detail_view, name="detail"),
    path("dashboard/owner/", view=owner_dashboard_view, name="dashboard_owner"),
    path("dashboard/tenant/", view=tenant_dashboard_view, name="dashboard_tenant"),
    path("dashboard/admin/", view=admin_dashboard_view, name="dashboard_admin"),
    path("forgot-password/", view=forgot_password_request_view, name="forgot_password"),
    path("forgot-password/done/", view=forgot_password_success_view, name="forgot_password_done"),
    path("reset/<int:request_id>/approve/", view=approve_password_reset, name="approve_password_reset"),
    path("reset/<int:request_id>/reject/", view=reject_password_reset, name="reject_password_reset"),
]

