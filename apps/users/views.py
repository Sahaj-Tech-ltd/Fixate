from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

from apps.documents.models import Document
from apps.reader.models import UserPreferences


class HomeView(TemplateView):
    template_name = "home.html"


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['documents'] = Document.objects.filter(user=self.request.user)
        context['quota_used'] = self.request.user.textract_uploads_used
        context['quota_max'] = 10 if self.request.user.tier == 'free' else None
        context['is_pro'] = self.request.user.tier == 'pro'
        return context


class SettingsView(LoginRequiredMixin, TemplateView):
    template_name = "settings.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['preferences'], _ = UserPreferences.objects.get_or_create(user=self.request.user)
        return context
