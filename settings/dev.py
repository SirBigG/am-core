import os

from settings.settings import *  # noqa


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': "postgres",
        'USER': 'postgres',
        'HOST': 'db',
        'PORT': '5432',
    }
}

ALLOWED_HOSTS = ['*']

SECRET_KEY = 'adrfgnlkjbh25687ywdrgn45wrth$#%#&356'

DEBUG = True

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
    }
}

STATIC_ROOT = '/static'
MEDIA_ROOT = '/media'


FIXTURE_DIRS = [
    os.path.join(BASE_DIR, 'core/classifier/fixtures/test_data.json'),
    os.path.join(BASE_DIR, 'core/posts/fixtures/test_data.json'),
    os.path.join(BASE_DIR, 'core/pro_auth/fixtures/test_data.json'),
    os.path.join(BASE_DIR, 'core/services/fixtures/test_data.json'),
]
