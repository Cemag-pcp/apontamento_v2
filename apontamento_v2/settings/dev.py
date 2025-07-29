from .base import *

# Configurações específicas de desenvolvimento
DEBUG = env.bool('DEBUG', default=True)
ALLOWED_HOSTS = ['127.0.0.1', 'localhost','apontamento-v2-testes.onrender.com', '192.168.3.3', '192.168.3.18']
CSRF_TRUSTED_ORIGINS = [
    'https://apontamentousinagem.onrender.com',
    'http://127.0.0.1:8000',
    'http://localhost:8000',
    'https://apontamento-v2-testes.onrender.com',
    'http://192.168.3.18:8084'
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': env('DB_NAME'),
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST'),
        'PORT': env('DB_PORT'),
        'OPTIONS': {
            'options': '-c search_path='+env('BASE_TESTE'),
        },
    }
}

# STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
# Configurações adicionais para desenvolvimento (opcional)
# STATIC_URL = '/static/'
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
# STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

# daphne -b 127.0.0.1 -p 8000 apontamento_v2.asgi:application