from django.urls import path

from .views import HomeView, DashboardView

urlpatterns = [
    path("", HomeView, name="home"),
    path("dashboard/", DashboardView, name="dashboard"),
]
