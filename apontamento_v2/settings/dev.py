from .base import *

# Configurações específicas de desenvolvimento
DEBUG = env.bool('DEBUG', default=True)
ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

# Banco de dados para desenvolvimento
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Configurações adicionais para desenvolvimento (opcional)
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
