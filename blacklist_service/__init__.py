import os
from datetime import timedelta

import click
from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_jwt_extended import create_access_token
from flask_restful import Api
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.middleware.proxy_fix import ProxyFix

from .extensions import db, jwt, ma, migrate


def create_app(test_config=None):
    load_dotenv()
    app = Flask(__name__)
    app.config.from_mapping(
        SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URL"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        JWT_SECRET_KEY=os.getenv("JWT_SECRET_KEY"),
        JWT_ACCESS_TOKEN_EXPIRES=timedelta(days=7),
        APP_VERSION=os.getenv("APP_VERSION", "local"),
        TRUSTED_PROXY_HOPS=int(os.getenv("TRUSTED_PROXY_HOPS", "0")),
    )
    if test_config:
        app.config.update(test_config)
    if not app.config["SQLALCHEMY_DATABASE_URI"]:
        raise RuntimeError("Configure DATABASE_URL antes de iniciar la aplicacion.")
    secret = app.config["JWT_SECRET_KEY"]
    if not secret or len(secret.encode("utf-8")) < 32:
        raise RuntimeError("Configure JWT_SECRET_KEY con al menos 32 bytes.")

    db.init_app(app)
    ma.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)

    from .resources import BlacklistResource, BlacklistsResource, HealthResource

    # Flask-JWT-Extended registers its error handlers on Flask.
    # Disable RESTful's interception so these handlers also cover Resources.
    class ApplicationApi(Api):
        def error_router(self, original_handler, error):
            return original_handler(error)

    api = ApplicationApi(app)
    api.add_resource(BlacklistsResource, "/blacklists")
    api.add_resource(BlacklistResource, "/blacklists/<string:email>")
    api.add_resource(HealthResource, "/health")

    hops = app.config["TRUSTED_PROXY_HOPS"]
    if hops < 0:
        raise RuntimeError("TRUSTED_PROXY_HOPS no puede ser negativo.")
    if hops:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops)

    @jwt.unauthorized_loader
    def missing_token(reason):
        return jsonify(message="Se requiere un Bearer Token valido."), 401

    @jwt.invalid_token_loader
    def invalid_token(reason):
        return jsonify(message="Token invalido."), 401

    @jwt.expired_token_loader
    def expired_token(header, payload):
        return jsonify(message="Token expirado."), 401

    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        db.session.rollback()
        app.logger.exception("Database operation failed")
        return jsonify(message="No fue posible completar la operacion."), 503

    @app.cli.command("issue-token")
    @click.option("--identity", default="postman", show_default=True)
    def issue_token(identity):
        """Genera un token predefinido valido por siete dias; no lo versione."""
        click.echo(create_access_token(identity=identity))

    return app
