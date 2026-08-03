from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

from apps.documents.models import Document
from apps.reader.models import UserPreferences


class HomeView(TemplateView):
    template_name = "flocus.html"

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['documents'] = Document.objects.filter(user=self.request.user)
        context['quota_used'] = self.request.user.textract_uploads_used
        context['quota_max'] = None
        context['is_pro'] = True
        return context

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response


class FlocusView(LoginRequiredMixin, TemplateView):
    template_name = "flocus.html"

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response


class SettingsView(LoginRequiredMixin, TemplateView):
    template_name = "settings.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['preferences'], _ = UserPreferences.objects.get_or_create(user=self.request.user)
        return context
