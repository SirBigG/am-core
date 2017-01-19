from social_core.pipeline.partial import partial

from django.http import HttpResponseRedirect
from django.urls import reverse

USER_FIELDS = ['email', 'phone1']


@partial
def add_user_extra_data(strategy, backend, request, details, *args, **kwargs):
    # If social user created not write extra data to session
    if kwargs.get('user', None):
        return
    _form_data = backend.strategy.session.get('social_form_data', None)
    if not _form_data:
        # For adding extra data for new user creation
        return HttpResponseRedirect(redirect_to=reverse('pro_auth:social-register', args=(backend.name,)))
    return


def create_user(strategy, details, backend, user=None, *args, **kwargs):
    if user:
        return {'is_new': False}
    fields = dict((name, kwargs.get(name, details.get(name)))
                  for name in backend.setting('USER_FIELDS', USER_FIELDS))
    if not fields:
        return

    fields.update(strategy.session_get('social_form_data'))

    return {
        'is_new': True,
        'user': strategy.create_user(**fields)
    }
