from social_core.pipeline.partial import partial

from django.contrib.auth import get_user_model

USER_FIELDS = ['email']


@partial
def add_user_extra_data(strategy, backend, request, details, *args, **kwargs):
    return


def create_user(strategy, details, backend, user=None, *args, **kwargs):
    _user_pk = backend.strategy.session_pop('user_pk')
    if _user_pk:
        return {'is_new': False, 'user': get_user_model().objects.get(pk=_user_pk)}
    if user:
        return {'is_new': False}
    fields = dict((name, kwargs.get(name, details.get(name)))
                  for name in backend.setting('USER_FIELDS', USER_FIELDS))

    fields.update({'details': details})
    # _user_data = backend.strategy.session_pop('social_form_data')
    # if _user_data:
    #    fields.update(_user_data)

    if not fields:
        return

    return {
        'is_new': True,
        'user': strategy.create_user(**fields)
    }
