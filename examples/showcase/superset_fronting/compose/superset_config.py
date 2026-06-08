import os

SECRET_KEY = os.environ.get("SUPERSET_SECRET_KEY", "anip-local-superset-secret-key")
SQLALCHEMY_DATABASE_URI = "sqlite:////app/superset_home/superset.db"

FEATURE_FLAGS = {
    "ENABLE_TEMPLATE_PROCESSING": True,
}

TALISMAN_ENABLED = False
WTF_CSRF_ENABLED = False
