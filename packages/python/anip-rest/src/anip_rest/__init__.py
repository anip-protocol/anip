"""ANIP REST bindings — expose ANIPService capabilities as RESTful API endpoints."""
from .routes import mount_anip_rest

__all__ = ["mount_anip_rest"]
