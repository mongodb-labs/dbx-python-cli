from django.views.generic import TemplateView


class HomeView(TemplateView):
    template_name = "default_urlconf.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            from wagtail.models import Site

            site = Site.find_for_request(self.request)
            if site:
                context["wagtail_site"] = site
                context["wagtail_menu_items"] = (
                    site.root_page.get_children()
                    .filter(show_in_menus=True, live=True)
                    .specific()
                )
        except Exception:
            pass
        return context
