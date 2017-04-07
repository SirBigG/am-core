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
