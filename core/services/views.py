from django.views.generic import FormView, View, ListView
from django.http import HttpResponse, JsonResponse, Http404, HttpResponseForbidden
from django.template.loader import render_to_string

from core.services.forms import FeedbackForm
from core.services.models import Reviews

from core.classifier.models import Category


class FeedbackView(FormView):
    form_class = FeedbackForm
    template_name = 'services/feedback.html'

    def form_valid(self, form):
        form.save()
        render = render_to_string('services/success.html')
        return HttpResponse(render)


class IsReviewedView(View):
    def get(self, request):
        if request.is_ajax():
            if not request.user.is_authenticated:
                return HttpResponseForbidden()
            if request.GET.get('slug', None):
                try:
                    Reviews.objects.get(object_id=Category.objects.get(slug=request.GET.get('slug')).pk,
                                        user=request.user)
                    return JsonResponse({'is-reviewed': 1})
                except Reviews.DoesNotExist:
                    return JsonResponse({'is-reviewed': 0})
        raise Http404


class ReviewsList(ListView):
    paginate_by = 20
    template_name = 'services/reviews/list.html'
    ordering = '-date'

    def get_queryset(self):
        qs = Reviews.objects.all()
        if self.kwargs.get('category', None):
            qs = qs.filter(content_type__model=self.kwargs.get('category'))
        if self.kwargs.get('object_id', None):
            qs = qs.filter(object_id=self.kwargs.get('object_id'))
        return qs
