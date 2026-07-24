// Aponta pro backend Django. Em dev, defina EXPO_PUBLIC_API_BASE_URL com o
// IP de LAN do PC rodando `python manage.py runserver` (ex: http://192.168.3.18:8000),
// já que "localhost" no celular aponta pro proprio celular, nao pro PC.
export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL || 'http://192.168.3.18:8000';

export const API_MOBILE_PREFIX = '/expedicao/api/mobile';
