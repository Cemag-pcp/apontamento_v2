from pathlib import Path
import json
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
    'compras',
    'comercial',
    'storages',
    'reuniao',

    'channels',
    'corsheaders',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # 'whitenoise.middleware.WhiteNoiseMiddleware', # temporario em dev

    'corsheaders.middleware.CorsMiddleware',
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

# E-mail / SMTP
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = env('EMAIL_DEFAULT_FROM', default=EMAIL_HOST_USER)

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
    os.path.join(BASE_DIR, 'compras/static'),
    os.path.join(BASE_DIR, 'comercial/static'),
]
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

AWS_ACCESS_KEY_ID = env('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = env('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = env('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = env('AWS_S3_REGION_NAME')

DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

# Desativa o upload multipart concorrente (boto3 usa threads lendo o mesmo
# file-like object do Django em offsets diferentes, corrompendo arquivos
# acima do limite de multipart quando varias threads leem simultaneamente).
AWS_S3_USE_THREADS = False

AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'

MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/'

# Define o diretório onde os arquivos de mídia serão armazenados
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

RPA_API_KEY = env('RPA_API_KEY')

LOGIN_URL = '/core/login/'
LOGIN_REDIRECT_URL = '/core/'  
LOGOUT_REDIRECT_URL = '/core/login/'  

# Google Sheets - Compras
GSHEETS_SERVICE_ACCOUNT_INFO = {
    'type': env('type', default=''),
    'project_id': env('project_id', default=''),
    'private_key': env('private_key', default=''),
    'private_key_id': env('private_key_id', default=''),
    'client_email': env('client_email', default=''),
    'client_id': env('client_id', default=''),
    'auth_uri': env('auth_uri', default=''),
    'token_uri': env('token_uri', default=''),
    'auth_provider_x509_cert_url': env('auth_provider_x509_cert_url', default=''),
    'client_x509_cert_url': env('client_x509_cert_url', default=''),
    'universe_domain': env('universe_domain', default=''),
}

if not GSHEETS_SERVICE_ACCOUNT_INFO['private_key']:
    GSHEETS_SERVICE_ACCOUNT_INFO = json.loads(
        env('GSHEETS_SERVICE_ACCOUNT_JSON', default='{}')
    )

if GSHEETS_SERVICE_ACCOUNT_INFO.get('private_key') and "\\n" in GSHEETS_SERVICE_ACCOUNT_INFO['private_key']:
    GSHEETS_SERVICE_ACCOUNT_INFO['private_key'] = GSHEETS_SERVICE_ACCOUNT_INFO['private_key'].replace("\\n", "\n")

GSHEETS_COMPRAS_SPREADSHEET_NAME = env('GSHEETS_COMPRAS_SPREADSHEET_NAME', default='Análise Previsão de Consumo (CMM / NTP ) DEE')

GSHEETS_ESTOQUE_SPREADSHEET_ID = env('GSHEETS_ESTOQUE_SPREADSHEET_ID', default='1u2Iza-ocp6ROUBXG9GpfHvEJwLHuW7F2uiO583qqLIE')

GSHEETS_MAT_INDIRETO_SPREADSHEET_ID = env('GSHEETS_MAT_INDIRETO_SPREADSHEET_ID', default='1s6w-B4kqHiSOk6l9m8jA67-43b6l_ejWN-E2SWavoOs')

PLOOMES_USER_KEY = env('PLOOMES_USER_KEY', default='')

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": ["redis://default:AWbmAbD4G2CfZPb3RxwuWQ4RfY7JOmxS@redis-19210.c262.us-east-1-3.ec2.redns.redis-cloud.com:19210"],
        },
    },
}
