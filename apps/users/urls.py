from django.urls import path, reverse_lazy
from django.contrib.auth.views import LogoutView
from apps.users.views import HomeView, DashboardView, SettingsView, FlocusView

urlpatterns = [
    path("", HomeView.as_view(), name="home"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("flocus/", FlocusView.as_view(), name="flocus"),
    path("settings/", SettingsView.as_view(), name="settings"),
    path("logout/", LogoutView.as_view(next_page=reverse_lazy("home")), name="logout"),
]
