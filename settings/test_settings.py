from settings.settings import *  # noqa

HOST = "localhost:8000"

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

"""DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': 'testdb',
    },
}"""


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': "test_db",
        'USER': os.getenv('POSTGRES_USER'),  # noqa
        'PASSWORD': os.getenv('POSTGRES_PASSWORD'),  # noqa
        'HOST': os.getenv('POSTGRES_HOST'),  # noqa
        'PORT': os.getenv('POSTGRES_PORT'),  # noqa
    }
}

MEDIA_ROOT = os.path.join(BASE_DIR, 'media/test')  # noqa
