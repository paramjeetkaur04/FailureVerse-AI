"""Deliberately small target application. Failure injection starts in Phase 4."""

from datetime import datetime, timezone
from time import monotonic

from flask import Flask, jsonify

app = Flask(__name__)
started = monotonic()


@app.get("/")
def index():
    return jsonify(
        service="failureverse-demo",
        message="FailureVerse test application. No failure injection is enabled in Phase 1.",
    )


@app.get("/health")
def health():
    return jsonify(
        service="failureverse-demo", status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        uptime_seconds=round(monotonic() - started, 3),
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False)
