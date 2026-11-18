from django.views.generic import TemplateView


class HomeView(TemplateView):
    template_name = "default_urlconf.html"
