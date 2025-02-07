from .base import *

import os

# Configurações específicas de produção
DEBUG = False
ALLOWED_HOSTS = ['apontamentousinagem.onrender.com', 'apontamento-v2-testes.onrender.com']
CSRF_TRUSTED_ORIGINS = [
    'https://apontamentousinagem.onrender.com',
    'http://127.0.0.1',
    'https://apontamento-v2-testes.onrender.com'
    
]

# Banco de dados para produção
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

# Configurações para servir arquivos estáticos
# STATIC_URL = '/static/'
# STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_ROOT = str(BASE_DIR.joinpath('staticfiles'))
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Middleware adicional para produção
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

# Configuração para forçar atualização de arquivos estáticos
WHITENOISE_MAX_AGE = 0

# Configurações de segurança para produção (certifique-se de ajustar essas conforme necessário)
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
}
