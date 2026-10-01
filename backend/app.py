"""Flask application factory for the RAG backend."""

from __future__ import annotations

import logging
import os

from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from config import Config
from routes.chat import chat_bp
from routes.documents import documents_bp


def create_app() -> Flask:
    Config.ensure_dirs()

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    )

    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["MAX_CONTENT_LENGTH"] = Config.MAX_CONTENT_LENGTH
    app.json.sort_keys = False

    CORS(app, resources={r"/api/*": {"origins": Config.CORS_ORIGINS}})

    app.register_blueprint(documents_bp)
    app.register_blueprint(chat_bp)

    @app.get("/api")
    def index():
        return jsonify(
            {
                "service": "rag-backend",
                "endpoints": [
                    "GET    /api/health",
                    "GET    /api/models",
                    "GET    /api/documents",
                    "POST   /api/documents      (multipart field: file)",
                    "DELETE /api/documents/<id>",
                    "POST   /api/chat           (SSE stream)",
                ],
            }
        )

    @app.errorhandler(RequestEntityTooLarge)
    def too_large(_exc):
        limit_mb = Config.MAX_CONTENT_LENGTH // (1024 * 1024)
        return jsonify({"error": f"File is too large. The limit is {limit_mb} MB."}), 413

    @app.errorhandler(HTTPException)
    def http_error(exc: HTTPException):
        return jsonify({"error": exc.description}), exc.code

    @app.errorhandler(Exception)
    def unexpected(exc: Exception):
        app.logger.exception("Unhandled error")
        return jsonify({"error": f"Unexpected server error: {exc}"}), 500

    @app.after_request
    def log_request(response):
        if request.path.startswith("/api") and not request.path.endswith("/chat"):
            app.logger.info("%s %s -> %s", request.method, request.path, response.status_code)
        return response

    return app


app = create_app()

if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "0") in {"1", "true", "yes"},
        threaded=True,
    )
