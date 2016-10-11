from agro_portal.settings import *  # noqa

ALLOWED_HOSTS = ['localhost:8000', 'localhost']

DEBUG = True

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}