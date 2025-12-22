from pathlib import Path
import os
import environ
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

SECRET_KEY = env('SECRET_KEY')

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'cadastro',
    'usuario',
    'core',
    'inspecao',
    'sucata',

    'cadastro_almox',
    'core_almox',
    'solicitacao_almox',

    'apontamento_serra',
    'apontamento_usinagem',
    'apontamento_corte',
    'apontamento_prod_especiais',
    'apontamento_estamparia',
    'apontamento_pintura',
    'apontamento_montagem',
    'apontamento_solda',
    'apontamento_exped',
    'cargas',
    'storages',

    'channels',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # 'whitenoise.middleware.WhiteNoiseMiddleware', # temporario em dev

    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.middleware.common.BrokenLinkEmailsMiddleware',

    # middleware personalizado para perfis de usuário
    'core.middleware.RotaAccessMiddleware', 
    
]

ROOT_URLCONF = 'apontamento_v2.urls'

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
            ],
        },
    },
]

WSGI_APPLICATION = 'apontamento_v2.wsgi.application'
ASGI_APPLICATION = 'apontamento_v2.asgi.application'

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Static files
STATIC_URL = 'static/'
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static/'),
    
    os.path.join(BASE_DIR, 'apontamento_serra/static'),
    os.path.join(BASE_DIR, 'apontamento_usinagem/static'),
    os.path.join(BASE_DIR, 'apontamento_corte/static'),
    os.path.join(BASE_DIR, 'apontamento_prod_especiais/static'),
    os.path.join(BASE_DIR, 'apontamento_estamparia/static'),
    os.path.join(BASE_DIR, 'apontamento_montagem/static'),
    os.path.join(BASE_DIR, 'apontamento_solda/static'),
    os.path.join(BASE_DIR, 'apontamento_pintura/static'),
    os.path.join(BASE_DIR, 'apontamento_exped/static'),

    os.path.join(BASE_DIR, 'cargas/static'),
    os.path.join(BASE_DIR, 'sucata/static'),
    os.path.join(BASE_DIR, 'inspecao/static'),
    os.path.join(BASE_DIR, 'cadastro/static'),
]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = env('AWS_S3_REGION_NAME')

DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'

MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/'

# Define o diretório onde os arquivos de mídia serão armazenados
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

RPA_API_KEY = env('RPA_API_KEY')

LOGIN_URL = '/core/login/'
LOGIN_REDIRECT_URL = '/core/'  
LOGOUT_REDIRECT_URL = '/core/login/'  

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": ["redis://default:AWbmAbD4G2CfZPb3RxwuWQ4RfY7JOmxS@redis-19210.c262.us-east-1-3.ec2.redns.redis-cloud.com:19210"],
        },
    },
}