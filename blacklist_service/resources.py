from flask import current_app, request
from flask_jwt_extended import jwt_required
from flask_restful import Resource
from marshmallow import ValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from .extensions import db
from .models import BlacklistEntry
from .schemas import BlacklistSchema, EmailQuerySchema


class BlacklistsResource(Resource):
    @jwt_required()
    def post(self):
        if not request.is_json:
            return {"message": "Se requiere un cuerpo JSON."}, 400
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return {"message": "El cuerpo debe ser un objeto JSON."}, 400
        try:
            data = BlacklistSchema().load(payload)
        except ValidationError as error:
            return {"message": "Datos invalidos.", "errors": error.messages}, 400

        entry = BlacklistEntry(**data, source_ip=request.remote_addr or "unknown")
        db.session.add(entry)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            # Only classify an actual duplicate as 409; other constraints are errors.
            exists = db.session.scalar(db.select(BlacklistEntry.id).filter_by(email=data["email"]))
            if exists is not None:
                return {"message": "El correo ya esta en la lista negra."}, 409
            raise
        return {"message": "Correo agregado a la lista negra."}, 201


class BlacklistResource(Resource):
    @jwt_required()
    def get(self, email):
        email = email.strip().lower()
        try:
            EmailQuerySchema().load({"email": email})
        except ValidationError as error:
            return {"message": "Correo invalido.", "errors": error.messages}, 400
        entry = db.session.scalar(db.select(BlacklistEntry).filter_by(email=email))
        return {
            "blacklisted": entry is not None,
            "blocked_reason": entry.blocked_reason if entry else None,
        }, 200


class HealthResource(Resource):
    def get(self):
        try:
            db.session.execute(db.text("SELECT 1"))
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Database health check failed")
            return {"status": "unavailable"}, 503
        return {"status": "ok", "version": current_app.config["APP_VERSION"]}, 200
