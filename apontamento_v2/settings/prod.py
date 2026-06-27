from .base import *

import os

# Configurações específicas de produção
DEBUG = False
ALLOWED_HOSTS = ['apontamentousinagem.onrender.com', 'apontamento-v2-testes.onrender.com', 'www.cmgprod.com.br', 'cmgprod.com.br']
CSRF_TRUSTED_ORIGINS = [
    'https://apontamentousinagem.onrender.com',
    'http://127.0.0.1',
    'https://apontamento-v2-testes.onrender.com',
    'https://cmgprod.com.br',
    'https://www.cmgprod.com.br',
]

CORS_ALLOW_ALL_ORIGINS = True

# Banco de dados para produção
DATABASES = {
    'default': {
        'ENGINE': 'dj_db_conn_pool.backends.postgresql',
        'NAME': env('DB_NAME'),
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST'),
        'PORT': env('DB_PORT'),
        'CONN_MAX_AGE': 0,
        'POOL_OPTIONS': {
            # Pool maior e timeout de espera mais curto: o RDS fica em
            # us-east-1 e o app roda em oregon, entao instabilidades de rede
            # entre as regioes derrubam varias conexoes ao mesmo tempo.
            # Esperar 30s por uma vaga prende a thread da requisicao (e o
            # worker do daphne) por muito tempo durante essas rajadas; com
            # timeout curto a requisicao falha rapido e o
            # DBConnectionRetryMiddleware tenta de novo.
            'POOL_SIZE': 15,
            'MAX_OVERFLOW': 25,
            'RECYCLE': 300,
            'TIMEOUT': 10,
            'PRE_PING': True,
        },
        'OPTIONS': {
            'options': '-c search_path=' + env('BASE_PROD'),
            'connect_timeout': 10,
        },
    }
}
# Configurações para servir arquivos estáticos
# STATIC_URL = '/static/'
# STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATIC_ROOT = str(BASE_DIR.joinpath('staticfiles'))

# Hash do conteudo no nome do arquivo (ex: app.a69c0a5335c5.js): a URL muda
# sozinha sempre que o conteudo muda, sem precisar editar nenhuma versao
# manual em templates. Substitui a tentativa anterior de forcar atualizacao
# via WHITENOISE_MAX_AGE=0, que so evitava cache para requisicoes novas e
# nao resolvia navegadores que ja tinham cacheado a URL antiga.
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Middleware adicional para produção
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

# Como a URL e imutavel por conteudo, pode cachear de forma agressiva
# (1 ano) sem risco de servir versao desatualizada.
WHITENOISE_MAX_AGE = 31536000

# Configurações de segurança para produção (certifique-se de ajustar essas conforme necessário)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
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
    'loggers': {
        'cargas.views': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'cargas.utils': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
