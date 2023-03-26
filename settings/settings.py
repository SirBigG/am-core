"""
Django settings for golub_portal project.

Generated by 'django-admin startproject' using Django 1.8.4.

For more information on this file, see
https://docs.djangoproject.com/en/1.8/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/1.8/ref/settings/
"""

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
from django.utils.translation import gettext_lazy as _

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/1.8/howto/deployment/checklist/

SECRET_KEY = os.getenv("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

HOST = os.getenv("HOST") or 'localhost:8000'

ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS").split(",") if os.getenv('ALLOWED_HOSTS') else ['localhost:8000']

CSRF_TRUSTED_ORIGINS = [
    'https://*.agromega.in.ua',
    'http://localhost:8000',
]

WSGI_APPLICATION = 'settings.wsgi.application'

ADMIN_HASH = os.getenv("ADMIN_HASH", "")

# https settings
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
# SECURE_SSL_REDIRECT = True
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True
# Application definition

INSTALLED_APPS = [
    # Autocomplete field. https://github.com/yourlabs/django-autocomplete-light.
    'dal',
    'dal_select2',
    # Standard django apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.flatpages',
    'django.contrib.postgres',

    # Package for project api: http://www.django-rest-framework.org/
    'rest_framework',

    # project apps
    'core.classifier',
    'core.pro_auth',
    'core.posts',
    'core.services',
    'core.events',
    'core.news',
    'core.adverts',
    'core.diary',

    # Third part packages
    # Translation plugin http://django-rosetta.readthedocs.org/en/latest/index.html
    'rosetta',
    # Package for category tree realization https://github.com/django-mptt/django-mptt
    'mptt',
    # For nice working with text https://github.com/django-ckeditor/django-ckeditor
    'ckeditor',
    # For social authentication: https://github.com/python-social-auth/social-app-django
    'social_django',
    # Simple tags https://github.com/jazzband/django-taggit
    'taggit',
    # http2 support https://github.com/ricardochaves/django_http2_push
    "django_http2_push",
    # https://github.com/praekelt/django-recaptcha
    'captcha',
    # https://github.com/radi85/Comment
    'comment',

    # additional apps
    # Package for testing falling data in models https://github.com/rbarrois/factory_boy
    'factory',
]

MIDDLEWARE = (
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    "django_http2_push.middleware.PushHttp2Middleware",
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # 'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
)

ROOT_URLCONF = 'settings.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'social_django.context_processors.backends',
                'social_django.context_processors.login_redirect'
            ],
        },
    },
]

LOGGING = {
    'version': 1,
    'filters': {
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        }
    },
    'loggers': {
        'django.db.backends': {
            'level': 'DEBUG',
            'filters': ['require_debug_true'],
            'handlers': ['console'],
        },
        'django': {
            'level': 'INFO',
            'handlers': ['console'],
        },
    }
}

# Database
# https://docs.djangoproject.com/en/1.8/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': os.getenv('POSTGRES_DB'),
        'USER': os.getenv('POSTGRES_USER'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD'),
        'HOST': os.getenv('POSTGRES_HOST'),
        'PORT': os.getenv('POSTGRES_PORT'),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# ========================================================================================
# Authentication settings
# ========================================================================================

# Project authentication model
AUTH_USER_MODEL = 'pro_auth.User'

# Project authentication backend
AUTHENTICATION_BACKENDS = [
    'social_core.backends.open_id.OpenIdAuth',
    'social_core.backends.facebook.FacebookOAuth2',
    'social_core.backends.google.GoogleOAuth2',
    'core.pro_auth.backends.AuthBackend',
]

SOCIAL_AUTH_FIELDS_STORED_IN_SESSION = []  # ['state', ]
SESSION_COOKIE_SECURE = False
SESSION_COOKIE_AGE = 60 * 60 * 24 * 180

SOCIAL_AUTH_PIPELINE = (
    'social_core.pipeline.social_auth.social_details',
    'social_core.pipeline.social_auth.social_uid',
    'social_core.pipeline.social_auth.auth_allowed',
    'social_core.pipeline.social_auth.social_user',
    'core.pro_auth.pipeline.add_user_extra_data',
    'core.pro_auth.pipeline.create_user',
    'social_core.pipeline.social_auth.associate_user',
    'social_core.pipeline.social_auth.load_extra_data',
    'social_core.pipeline.user.user_details',
)

SOCIAL_AUTH_FACEBOOK_KEY = os.getenv("SOCIAL_AUTH_FACEBOOK_KEY")
SOCIAL_AUTH_FACEBOOK_SECRET = os.getenv("SOCIAL_AUTH_FACEBOOK_SECRET")

SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = os.getenv("SOCIAL_AUTH_GOOGLE_OAUTH2_KEY")
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = os.getenv("SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET")

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'

# ========================================================================================
# Internationalization
# https://docs.djangoproject.com/en/1.8/topics/i18n/
# ========================================================================================

LANGUAGE_CODE = 'uk-Uk'

LANGUAGES = [
    ('uk-Uk', _('Ukrainian')),
    ('en', _('English')),
]

LOCALE_PATHS = [os.path.join(BASE_DIR, 'locale'), ]

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.8/howto/static-files/

STATIC_URL = '/static/'

STATICFILES_FINDERS = [
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
]

STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'pwa')
]

STATIC_ROOT = os.getenv("STATIC_ROOT", BASE_DIR + '/static/')
STATICFILES_STORAGE = "core.utils.storage.VersionedStaticFilesStorage"

# Media files (uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.getenv("MEDIA_ROOT", os.path.join(BASE_DIR, 'media'))

CKEDITOR_UPLOAD_PATH = '/media/ckeditor/'

CKEDITOR_CONFIGS = {
    'default': {
        'width': '100%',
    },
    "public": {
        'width': '100%',
        'toolbar_Full': [
            ['Format', 'Bold', 'Italic', 'Underline', 'Strike', 'SpellChecker', 'Undo', 'Redo',
             '-', 'NumberedList', 'BulletedList'],
            ['Table'],
            ['TextColor', 'BGColor'],
            ['SpecialChar'],
        ],
        'bodyClass': "col-12"
    }

}

# Multillect translator secrets
MULTILLECT_ACCOUNT_ID = os.getenv("MULTILLECT_ACCOUNT_ID")
MULTILLECT_SECRET_KEY = os.getenv("MULTILLECT_SECRET_KEY")

# EMAIL_HOST = os.getenv("EMAIL_HOST")
# EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
# EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
# EMAIL_PORT = int(os.getenv("EMAIL_PORT")) if os.getenv("EMAIL_PORT") else None
# EMAIL_USE_TLS = True
#
# SERVER_EMAIL = os.getenv("SERVER_EMAIL")
# ADMINS = [i.split(",") for i in os.getenv("ADMINS").split(":")] if os.getenv("ADMINS") else []

# Media version for browser cache refresh
MEDIA_VERSION = os.getenv("MEDIA_VERSION")

API_HOST = os.getenv('API_HOST')

# SESSION_ENGINE = "django.contrib.sessions.backends.cache"

RECAPTCHA_PUBLIC_KEY = os.getenv("RECAPTCHA_PUBLIC_KEY", "")
RECAPTCHA_PRIVATE_KEY = os.getenv("RECAPTCHA_PRIVATE_KEY", "")
