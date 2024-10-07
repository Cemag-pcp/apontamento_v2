import os

environment = os.getenv('DJANGO_ENV', 'dev')

if environment == 'prod':
    from .prod import *
else:
    from .dev import *
