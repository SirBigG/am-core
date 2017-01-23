from social_core.pipeline.partial import partial

from django.http import HttpResponseRedirect
from django.urls import reverse
from django.contrib.auth import get_user_model

USER_FIELDS = ['email', 'phone1']


@partial
def add_user_extra_data(strategy, backend, request, details, *args, **kwargs):
    # If social user created not write extra data to session
    if kwargs.get('user', None):
        return
    # For existing users association
    if backend.strategy.session_get('user_pk'):
        return
    if not backend.strategy.session_get('social_form_data'):
        # For adding extra data for new user creation
        return HttpResponseRedirect(redirect_to=reverse('pro_auth:social-register', args=(backend.name,)))
    return


def create_user(strategy, details, backend, user=None, *args, **kwargs):
    _user_pk = backend.strategy.session_pop('user_pk')
    if _user_pk:
        return {'is_new': False, 'user': get_user_model().objects.get(pk=_user_pk)}
    if user:
        return {'is_new': False}
    fields = dict((name, kwargs.get(name, details.get(name)))
                  for name in backend.setting('USER_FIELDS', USER_FIELDS))

    _user_data = backend.strategy.session_pop('social_form_data')
    if _user_data:
        fields.update(_user_data)

    if not fields:
        return

    return {
        'is_new': True,
        'user': strategy.create_user(**fields)
    }
