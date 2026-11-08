from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from flask import Flask, jsonify, request
from sqlalchemy import DateTime, ForeignKey, String, URL, create_engine, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from werkzeug.exceptions import RequestEntityTooLarge

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_DOCUMENTS = {
    ".jpg": (b"\xff\xd8\xff", "image/jpeg"),
    ".jpeg": (b"\xff\xd8\xff", "image/jpeg"),
    ".png": (b"\x89PNG\r\n\x1a\n", "image/png"),
    ".pdf": (b"%PDF-", "application/pdf"),
}


class Base(DeclarativeBase):
    pass


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    bio: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="awaiting_upload")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    object_key: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    media_type: Mapped[str] = mapped_column(String(40), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


def create_app(test_config: dict[str, Any] | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(
        DATABASE_URL=os.environ.get("DATABASE_URL"),
        DB_HOST=os.environ.get("DB_HOST", "postgres"),
        DB_PORT=os.environ.get("DB_PORT", "5432"),
        DB_NAME=os.environ.get("DB_NAME"),
        DB_USER=os.environ.get("DB_USER"),
        DB_PASSWORD=os.environ.get("DB_PASSWORD"),
        S3_BUCKET=os.environ.get("S3_BUCKET", ""),
        AWS_REGION=os.environ.get("AWS_REGION", "ap-south-1"),
        MAX_CONTENT_LENGTH=MAX_UPLOAD_BYTES + 64 * 1024,
        MAX_UPLOAD_BYTES=MAX_UPLOAD_BYTES,
    )
    if test_config:
        app.config.update(test_config)

    database_url = app.config.get("DATABASE_URL")
    if not database_url:
        if all(app.config.get(key) for key in ("DB_NAME", "DB_USER", "DB_PASSWORD")):
            database_url = URL.create(
                drivername="postgresql+psycopg",
                username=app.config["DB_USER"],
                password=app.config["DB_PASSWORD"],
                host=app.config["DB_HOST"],
                port=int(app.config["DB_PORT"]),
                database=app.config["DB_NAME"],
            )
        else:
            database_url = "sqlite:///instance/application.sqlite3"
    if (
        isinstance(database_url, str)
        and database_url.startswith("sqlite:///")
        and database_url != "sqlite:///:memory:"
    ):
        database_path = Path(database_url.removeprefix("sqlite:///"))
        database_path.parent.mkdir(parents=True, exist_ok=True)

    engine_options: dict[str, Any] = {"pool_pre_ping": True}
    if isinstance(database_url, str) and database_url.startswith("sqlite:"):
        engine_options["connect_args"] = {"check_same_thread": False}
    engine = create_engine(database_url, **engine_options)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)

    s3_client = app.config.get("S3_CLIENT") or boto3.client(
        "s3", region_name=app.config["AWS_REGION"]
    )
    app.extensions["database_engine"] = engine
    app.extensions["database_session_factory"] = session_factory
    app.extensions["s3_client"] = s3_client

    @app.after_request
    def add_security_headers(response: Any) -> Any:
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        )
        return response

    @app.errorhandler(RequestEntityTooLarge)
    def handle_large_upload(_: RequestEntityTooLarge) -> tuple[Any, int]:
        return jsonify(error="File is too large. Maximum upload size is 5 MB."), 413

    @app.get("/healthz")
    def healthcheck() -> tuple[Any, int]:
        session = session_factory()
        try:
            session.execute(select(1))
        except SQLAlchemyError:
            app.logger.exception("Database health check failed")
            return jsonify(status="unhealthy"), 503
        finally:
            session.close()
        return jsonify(status="ok"), 200

    @app.post("/api/profiles")
    def create_profile() -> tuple[Any, int]:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify(error="Send profile details as JSON."), 400

        name = payload.get("name")
        bio = payload.get("bio", "")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
            return jsonify(error="Name must be 1 to 80 characters."), 400
        if not isinstance(bio, str) or len(bio.strip()) > 500:
            return jsonify(error="Bio must be 500 characters or fewer."), 400
        if payload.get("consent") is not True:
            return jsonify(error="Confirm that profile data will be stored for this demo."), 400

        profile_id = str(uuid.uuid4())
        session = session_factory()
        try:
            profile = Profile(
                id=profile_id,
                name=name.strip(),
                bio=bio.strip(),
                status="awaiting_upload",
                created_at=_utc_now(),
            )
            session.add(profile)
            session.commit()
        except SQLAlchemyError:
            session.rollback()
            app.logger.exception("Could not save profile")
            return jsonify(error="Profile could not be saved. Please try again."), 500
        finally:
            session.close()
        return jsonify(id=profile_id, name=name.strip(), status="awaiting_upload"), 201

    @app.get("/api/profiles/<profile_id>")
    def get_profile(profile_id: str) -> tuple[Any, int]:
        session = session_factory()
        try:
            profile = session.get(Profile, profile_id)
            if profile is None:
                return jsonify(error="Profile not found."), 404
            return jsonify(id=profile.id, name=profile.name, status=profile.status), 200
        except SQLAlchemyError:
            app.logger.exception("Could not read profile")
            return jsonify(error="Profile could not be loaded. Please try again."), 500
        finally:
            session.close()

    @app.post("/api/profiles/<profile_id>/document")
    def upload_document(profile_id: str) -> tuple[Any, int]:
        if not app.config["S3_BUCKET"]:
            app.logger.error("S3_BUCKET is not configured")
            return jsonify(error="Document storage is not configured."), 503
        if request.form.get("consent") != "yes":
            return jsonify(error="Confirm that you are authorized to upload this document."), 400

        uploaded_file = request.files.get("document")
        if uploaded_file is None or not uploaded_file.filename:
            return jsonify(error="Choose a JPG, PNG, or PDF file."), 400

        extension = Path(uploaded_file.filename).suffix.lower()
        file_config = ALLOWED_DOCUMENTS.get(extension)
        if file_config is None:
            return jsonify(error="Use a JPG, PNG, or PDF file."), 400
        file_bytes = uploaded_file.stream.read(app.config["MAX_UPLOAD_BYTES"] + 1)
        if not file_bytes:
            return jsonify(error="The selected file is empty."), 400
        if len(file_bytes) > app.config["MAX_UPLOAD_BYTES"]:
            return jsonify(error="Choose a file smaller than 5 MB."), 400
        signature, media_type = file_config
        if not file_bytes.startswith(signature):
            return jsonify(error="File contents do not match a valid JPG, PNG, or PDF."), 400

        session = session_factory()
        object_key = f"profile-documents/{profile_id}/{uuid.uuid4().hex}{extension}"
        object_saved = False
        try:
            profile = session.get(Profile, profile_id)
            if profile is None:
                return jsonify(error="Profile not found."), 404
            if profile.status == "complete":
                return jsonify(error="A document has already been uploaded for this profile."), 409

            app.extensions["s3_client"].put_object(
                Bucket=app.config["S3_BUCKET"],
                Key=object_key,
                Body=file_bytes,
                ContentType=media_type,
                ServerSideEncryption="AES256",
            )
            object_saved = True
            profile.status = "complete"
            session.add(
                Document(
                    profile_id=profile_id,
                    object_key=object_key,
                    media_type=media_type,
                    uploaded_at=_utc_now(),
                )
            )
            session.commit()
        except (ClientError, BotoCoreError):
            session.rollback()
            app.logger.exception("S3 upload failed")
            return jsonify(error="Document could not be uploaded to storage."), 502
        except IntegrityError:
            session.rollback()
            _delete_s3_object(app, object_key, object_saved)
            return jsonify(error="A document has already been uploaded for this profile."), 409
        except SQLAlchemyError:
            session.rollback()
            _delete_s3_object(app, object_key, object_saved)
            app.logger.exception("Could not save document metadata")
            return jsonify(error="Document upload could not be recorded. Please try again."), 500
        finally:
            session.close()

        return jsonify(status="complete"), 201

    return app


def _delete_s3_object(app: Flask, object_key: str, object_saved: bool) -> None:
    if not object_saved:
        return
    try:
        app.extensions["s3_client"].delete_object(
            Bucket=app.config["S3_BUCKET"], Key=object_key
        )
    except (ClientError, BotoCoreError):
        app.logger.exception("Could not clean up uploaded S3 object %s", object_key)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


app = create_app()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    app.run(host="0.0.0.0", port=8000, debug=False)
