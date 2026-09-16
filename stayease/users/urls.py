from django.urls import path

from .views import owner_dashboard_view
from .views import tenant_dashboard_view
from .views import user_detail_view
from .views import user_profile_view
from .views import user_redirect_view
from .views import user_update_view

app_name = "users"
urlpatterns = [
    path("~redirect/", view=user_redirect_view, name="redirect"),
    path("profile/", view=user_profile_view, name="profile"),
    path("~update/", view=user_update_view, name="update"),
    path("<int:pk>/", view=user_detail_view, name="detail"),
    path("dashboard/owner/", view=owner_dashboard_view, name="dashboard_owner"),
    path("dashboard/tenant/", view=tenant_dashboard_view, name="dashboard_tenant"),
]

