
from pathlib import Path
import os
import sys

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# StartWise-integration/ (parent of backend/) must be on sys.path so that
# the `finagents` and `a2a_bus` packages sitting next to backend/ are importable.
_SW_ROOT = str(BASE_DIR.parent)
if _SW_ROOT not in sys.path:
    sys.path.insert(0, _SW_ROOT)

# Force CWD to the project root (finAgent/) so all relative paths —
# chroma_db/, data/ — resolve correctly regardless of where Django is launched from.
_PROJECT_ROOT = str(BASE_DIR.parent.parent)
os.chdir(_PROJECT_ROOT)

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-zq&ypcr445e2b1*)s7pua%9-+2kzrh=6!+@7l$$h8%*rm4c5dr')

DEBUG = True

ALLOWED_HOSTS = ['*']

# ── CORS — accepte le Vite (5173) et le Next.js (3000) ──────────────────────
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
    "x-session-id",  # used by CFO and agents session management
]

# ── Applications ─────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    'corsheaders',
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'channels',
    # CFO Agent — Financial viability analysis
    'cfo',
    # StartWise agents (LangGraph + WebSocket)
    'agents',
    # Ideation module (ADK A2A — Q&A flow)
    'ideation',
    # Product Audit module (Gemini + Qdrant)
    'product_audit',
    # Legal Advisor — RAG juridique tunisien (ChromaDB + Llama)
    'legal_advisor',
]

# ── Legal Advisor config ──────────────────────────────────────────────────────
LLM_API_KEY  = os.getenv("LLM_API_KEY",  "sk-af700b35e54c4b98a460eb42d2f6064c")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://tokenfactory.esprit.tn/api")
LLM_MODEL    = os.getenv("LLM_MODEL",    "hosted_vllm/Llama-3.1-70B-Instruct")
CHROMA_PATH  = os.getenv("CHROMA_PATH",  str(BASE_DIR / "chroma_db"))
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "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")

# Expose the shared API key under the names used by the CFO and agents modules
os.environ.setdefault("ESPRIT_API_KEY", LLM_API_KEY)
os.environ.setdefault("TOKEN_FACTORY_API_KEY", LLM_API_KEY)

# ── Middleware ────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# No trailing-slash redirects (ideation frontend POSTs without slash)
APPEND_SLASH = False

ROOT_URLCONF = 'startwise.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'startwise.wsgi.application'

ASGI_APPLICATION = 'startwise.asgi.application'

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
        "CONFIG": {
            "capacity": 1500,
            "expiry": 900,
        },
    },
}

DATA_UPLOAD_MAX_MEMORY_SIZE = 100 * 1024 * 1024  # 100MB


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


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


LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


STATIC_URL = 'static/'
