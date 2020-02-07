#!/usr/bin/env python3
# pylint: disable=locally-disabled, missing-docstring, import-error, invalid-name

from secrets import token_hex
import json
from flask import Flask, jsonify, request, abort, make_response
from waitress import serve
import uwsgi
from lib.main import execute_tests
from lib.config import get_config_options

app = Flask(__name__)

CONFIG = get_config_options()


@app.before_request
def check_auth_header():
    """Authenticate the client's API request."""
    if "authorization" in request.headers:
        token = request.headers.get("authorization")
    elif "Authorization" in request.headers:
        token = request.headers.get("Authorization")
    else:
        return abort(403)
    if token != CONFIG["api_secret"]:
        return abort(403)
    return None


@app.route("/api/v1.0/tests", methods=["POST"])
def create_tests():
    """Execute tests upon successful POST."""
    payload = request.get_json()
    if payload is None:
        return make_response(jsonify({"error": "Valid request payload not found."}), 400)
    test_count = 0
    for tests in payload.values():
        test_count += len(tests)
    if test_count > CONFIG["max_test_count"]:
        return make_response(
            jsonify(
                {"error": f"Provided number of tests is too high. Max: {CONFIG['max_test_count']}"}
            ),
            400,
        )
    # Generate the client's receipt and pass the test payload to a background thread to be executed.
    receipt = token_hex(16)
    uwsgi.cache_set(receipt, "{}", 600, "receipts")
    execute_tests(receipt, payload, CONFIG["max_process_count"])
    return jsonify({"receipt": receipt})


@app.route("/api/v1.0/tests", methods=["GET"])
def get_tests():
    """Retrieve test execution status upon successful GET."""
    if "receipt" not in request.args:
        return make_response(jsonify({"error": "Required 'receipt' parameter not found."}), 400)
    receipt = request.args.get("receipt")
    if not receipt:
        return make_response(
            jsonify({"error": "Required 'receipt' parameter found with an empty value."}), 400
        )
    test_status = uwsgi.cache_get(receipt, "receipts")
    if test_status is None:
        return make_response(jsonify({"error": "Provided 'receipt' not found."}), 404)
    return jsonify(json.loads(test_status))


@app.route("/api/v1.0/tests", methods=["DELETE"])
def delete_tests():
    """Delete test data from cache upon successful DELETE."""
    if "receipt" not in request.args:
        return make_response(jsonify({"error": "Required 'receipt' parameter not found."}), 400)
    receipt = request.args.get("receipt")
    if not uwsgi.cache_del(receipt, "receipts"):
        return make_response(jsonify({"error": "Provided 'receipt' not found."}), 404)
    return jsonify({"message": "Provided 'receipt' has been successfully deleted."})


@app.route("/api/v1.0/status", methods=["GET"])
def get_status():
    """Retrieve API specific stats upon successful GET."""
    status = {"worker_status": []}
    for worker in uwsgi.workers():
        del worker["apps"]
        worker["status"] = worker["status"].decode("utf-8")
        status["worker_status"].append(worker)
    status["total_requests"] = uwsgi.total_requests()
    return jsonify(status)


if __name__ == "__main__":
    serve(app, listen="*:8000")
