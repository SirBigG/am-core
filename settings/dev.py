from settings.settings import *  # noqa

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.postgresql_psycopg2',
#         'NAME': "postgres",
#         'USER': 'postgres',
#         'PASSWORD': 'postgres',
#         'HOST': 'db',
#         'PORT': '5432',
#     }
# }

"""
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'mydatabase',
    }
}
"""

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

# MIDDLEWARE = ['corsheaders.middleware.CorsMiddleware'] + MIDDLEWARE
#
# CORS_ORIGIN_ALLOW_ALL = True
# CORS_ORIGIN_WHITELIST = []

SITE_ID = 1

INSTALLED_APPS += [
    'silk',
]
MIDDLEWARE += ['silk.middleware.SilkyMiddleware', ]
SILKY_PYTHON_PROFILER = True
