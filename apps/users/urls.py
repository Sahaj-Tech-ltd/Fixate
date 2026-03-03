from django.urls import path
from apps.users.views import HomeView, DashboardView, SettingsView

urlpatterns = [
    path("", HomeView, name="home"),
    path("dashboard/", DashboardView, name="dashboard"),
    path("settings/", SettingsView.as_view(), name="settings"),
]
