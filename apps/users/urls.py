from django.urls import path
from apps.users.views import HomeView, DashboardView, SettingsView

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("settings/", SettingsView.as_view(), name="settings"),
]
