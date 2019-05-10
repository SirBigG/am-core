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

# CACHES = {
#     'default': {
#         'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
#     }
# }

STATIC_ROOT = '/static'
MEDIA_ROOT = '/media'

CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOW_CREDENTIALS = True

INSTALLED_APPS = ["corsheaders"] + INSTALLED_APPS
MIDDLEWARE = ('corsheaders.middleware.CorsMiddleware', ) + MIDDLEWARE
