import os
from pathlib import Path
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file
load_dotenv(BASE_DIR / '.env')

SECRET_KEY = os.getenv('SECRET_KEY', 'bakery-default-secret-key-change-in-production-2026')
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 't', 'yes')

ALLOWED_HOSTS = [h.strip() for h in os.getenv('ALLOWED_HOSTS', '*').split(',') if h.strip()]

# Multiport CSRF Trusted Origins (Dev: 8008, 8009, 8010 | Prod: 9008, 9009, 9010)
CSRF_TRUSTED_ORIGINS = [
    # Development Ports
    'http://localhost:8008',
    'http://127.0.0.1:8008',
    'http://0.0.0.0:8008',
    'http://localhost:8009',
    'http://127.0.0.1:8009',
    'http://0.0.0.0:8009',
    'http://localhost:8010',
    'http://127.0.0.1:8010',
    'http://0.0.0.0:8010',
    # Production Ports
    'http://localhost:9008',
    'http://127.0.0.1:9008',
    'http://0.0.0.0:9008',
    'http://localhost:9009',
    'http://127.0.0.1:9009',
    'http://0.0.0.0:9009',
    'http://localhost:9010',
    'http://127.0.0.1:9010',
    'http://0.0.0.0:9010',
    # Internal Direct
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    # Domain & Cloudflare Tunnel Origins
    'https://example-trusted-bakery.org',
    'http://example-trusted-bakery.org',
    'https://*.example-trusted-bakery.org',
    'http://*.example-trusted-bakery.org',
]
extra_origins = os.getenv('CSRF_TRUSTED_ORIGINS', '')
if extra_origins:
    CSRF_TRUSTED_ORIGINS.extend([origin.strip() for origin in extra_origins.split(',') if origin.strip()])



# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Custom apps
    'apps.authentication',
    'apps.products',
    'apps.pos',
    'apps.custom_orders',
    'apps.kitchen_bom',
    'apps.inventory',
    'apps.dashboard',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'apps.dashboard.middleware.PortalAccessMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.dashboard.context_processors.store_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Database MySQL 8.0 configuration
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.getenv('DB_NAME', 'bakery_db'),
        'USER': os.getenv('DB_USER', 'bakery_user'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'bakery_pass123'),
        'HOST': os.getenv('DB_HOST', 'db'),
        'PORT': os.getenv('DB_PORT', '3306'),
        'OPTIONS': {
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        }
    }
}

# Custom User Model
AUTH_USER_MODEL = 'authentication.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Security Hardening Settings
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True

# Reverse proxy SSL header (essential for HTTPS via Cloudflare Tunnel, Nginx, etc.)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

if not DEBUG:
    if os.getenv('SECURE_SSL_REDIRECT', 'False').lower() in ('true', '1'):
        SECURE_SSL_REDIRECT = True
        SESSION_COOKIE_SECURE = True
        CSRF_COOKIE_SECURE = True


# Internationalization
LANGUAGE_CODE = 'vi'
TIME_ZONE = 'Asia/Ho_Chi_Minh'
USE_I18N = True
USE_TZ = True

from django.utils.translation import gettext_lazy as _
LANGUAGES = (
    ('vi', _('Tiếng Việt')),
    ('en', _('English')),
)
LOCALE_PATHS = [BASE_DIR / 'locale']
USE_X_FORWARDED_PORT = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

if not DEBUG:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/auth/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/auth/login/'

# Business Rules Constants
DEFAULT_SHIPPING_FEE = int(os.getenv('DEFAULT_SHIPPING_FEE', 30000))
LOYALTY_POINT_EARN_RATE = float(os.getenv('LOYALTY_POINT_EARN_RATE', 0.10)) # 10%
POINT_TO_VND_RATE = int(os.getenv('POINT_TO_VND_RATE', 1000)) # 1 pt = 1000 VND
MIN_CUSTOM_CAKE_DEPOSIT_RATE = float(os.getenv('MIN_CUSTOM_CAKE_DEPOSIT_RATE', 0.30)) # 30%
BOM_STANDARD_WASTE_RATE = float(os.getenv('BOM_STANDARD_WASTE_RATE', 0.05)) # 5%
