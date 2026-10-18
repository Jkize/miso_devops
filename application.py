from blacklist_service import create_app

application = create_app()
application.config["APP_VERSION"] = "exp02-rolling"
