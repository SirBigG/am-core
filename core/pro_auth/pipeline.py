from social_core.pipeline.partial import partial

from django.http import HttpResponseRedirect
from django.urls import reverse

USER_FIELDS = ['email', 'phone1']


@partial
def add_user_extra_data(strategy, backend, request, details, *args, **kwargs):
    phone1 = backend.strategy.session.get('phone1', None)
    email = backend.strategy.session.get('email', None)
    if not phone1 or not email:
        return HttpResponseRedirect(redirect_to=reverse('pro_auth:social-register', args=(backend.name,)))
    return


def create_user(strategy, details, backend, user=None, *args, **kwargs):
    if user:
        return {'is_new': False}
    fields = dict((name, kwargs.get(name, details.get(name)))
                  for name in backend.setting('USER_FIELDS', USER_FIELDS))
    if not fields:
        return

    fields.update({'phone1': strategy.session_get('phone1'),
                   'email': strategy.session_get('email')})

    return {
        'is_new': True,
        'user': strategy.create_user(**fields)
    }
