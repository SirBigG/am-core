from django.views.generic import FormView
from django.http import JsonResponse

from .forms import CommentsForm
from .models import Comments


class CommentValidate(FormView):
    """
    Save comments.
    Return event status and errors in JSON.
    """
    form_class = CommentsForm
    model = Comments

    def form_invalid(self, form):
        data = {
            'status': 'false',
            'errors': form.errors,
        }
        return JsonResponse(data, status=400)

    def form_valid(self, form):
        form.save()
        status = 'success'
        return JsonResponse(status)
