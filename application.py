import os

from blacklist_service import create_app

application = create_app()
application.config["APP_VERSION"] = os.getenv("APP_VERSION", "exp04-immutable")
