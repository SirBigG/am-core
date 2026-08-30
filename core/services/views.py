from django.http import Http404, HttpResponse, HttpResponseForbidden, JsonResponse
from django.template.loader import render_to_string
from django.views.generic import FormView, ListView, View

from core.classifier.models import Category
from core.services.forms import FeedbackForm
from core.services.models import Reviews


class FeedbackView(FormView):
    form_class = FeedbackForm
    template_name = "services/feedback.html"

    def form_valid(self, form):
        form.save()
        render = render_to_string("services/success.html", request=self.request)
        return HttpResponse(render)


class ReviewInfoView(View):
    def get(self, request):
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            if not request.user.is_authenticated:
                return HttpResponseForbidden()
            if request.GET.get("slug", None):
                is_valid = 0
                is_reviewed = 0
                try:
                    category = Category.objects.select_related("parent").get(slug=request.GET.get("slug"))
                    parent = category.parent
                    if parent and parent.is_for_user:
                        is_valid = 1
                        if Reviews.objects.filter(object_id=category.pk, user=request.user).exists():
                            is_reviewed = 1
                except Category.DoesNotExist:
                    pass
                return JsonResponse({"is-valid": is_valid, "is-reviewed": is_reviewed})
        raise Http404


class ReviewsList(ListView):
    paginate_by = 20
    template_name = "services/reviews/list.html"
    ordering = "-date"

    def get_queryset(self):
        qs = Reviews.objects.all()
        if self.kwargs.get("category", None):
            qs = qs.filter(content_type__model=self.kwargs.get("category"))
        if self.kwargs.get("object_id", None):
            qs = qs.filter(object_id=self.kwargs.get("object_id"))
        return qs
