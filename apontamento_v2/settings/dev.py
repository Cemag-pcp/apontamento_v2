from .base import *

# Configurações específicas de desenvolvimento
DEBUG = env.bool('DEBUG', default=True)
ALLOWED_HOSTS = ['127.0.0.1', 'localhost','apontamento-v2-testes.onrender.com', '91a4-177-19-132-134.ngrok-free.app']
CSRF_TRUSTED_ORIGINS = [
    'https://apontamentousinagem.onrender.com',
    'http://127.0.0.1',
    'https://apontamento-v2-testes.onrender.com',
    'https://91a4-177-19-132-134.ngrok-free.app'
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
            'options': '-c search_path=apontamento_v2_testes',
        },
    }
}

# STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
# Configurações adicionais para desenvolvimento (opcional)
# STATIC_URL = '/static/'
# STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
