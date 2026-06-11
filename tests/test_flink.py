"""
Unit tests for flink.py.

All HTTP calls are mocked with the ``responses`` library so no network
connection is required.
"""

import logging
import re
import sys
import pytest
import responses as resp_lib
from unittest.mock import MagicMock

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import flink as flink_module
from flink import Flink, FlinkLogHandler, format_time

BASE_URL = "http://flink.example.com"
API_KEY = "test-api-key"
DEVICE_ID = "ZEK-001"

MOCK_CODES = {
    "1": ["8200", "1001", "8392"],
    "2": ["5149", "1002", "1794"],
    "3": ["2805", "1003", "1330"],
}


@pytest.fixture
def flink(requests_mock=None):
    return Flink(DEVICE_ID, BASE_URL, API_KEY)


# ---------------------------------------------------------------------------
# format_time
# ---------------------------------------------------------------------------

def test_format_time_matches_pattern():
    """format_time() returns a string like YYYY-MM-DD_HH-MM-SS."""
    result = format_time()
    assert re.match(r"^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}$", result), (
        f"format_time() returned unexpected format: {result!r}"
    )


# ---------------------------------------------------------------------------
# Flink.put_status
# ---------------------------------------------------------------------------

@resp_lib.activate
def test_put_status_success(flink):
    resp_lib.add(
        resp_lib.PUT,
        f"{BASE_URL}/{DEVICE_ID}/status",
        json={},
        status=200,
    )
    code = flink.put_status(uptime=123.4, SN="SN-001", version="2.0.0", comps=10, large_comps=2)
    assert code == 200

    # Verify Authorization header was sent
    assert len(resp_lib.calls) == 1
    assert resp_lib.calls[0].request.headers["Authorization"] == API_KEY


@resp_lib.activate
def test_put_status_sends_correct_json(flink):
    resp_lib.add(resp_lib.PUT, f"{BASE_URL}/{DEVICE_ID}/status", json={}, status=200)
    flink.put_status(uptime=500.0, SN="SN-002", version="2.0.0-beta5", comps=20, large_comps=4)

    import json
    body = json.loads(resp_lib.calls[0].request.body)
    assert body["serial"] == "SN-002"
    assert body["version"] == "2.0.0-beta5"
    assert body["compartments"] == "20"
    assert body["large_compartments"] == "4"
    assert "time" in body
    assert "uptime" in body


@resp_lib.activate
def test_put_status_non_200_returns_status_code(flink):
    resp_lib.add(resp_lib.PUT, f"{BASE_URL}/{DEVICE_ID}/status", json={}, status=503)
    code = flink.put_status(0, "", "", 0, 0)
    assert code == 503


@resp_lib.activate
def test_put_status_network_error_returns_exception(flink):
    resp_lib.add(
        resp_lib.PUT,
        f"{BASE_URL}/{DEVICE_ID}/status",
        body=ConnectionError("network down"),
    )
    result = flink.put_status(0, "", "", 0, 0)
    assert isinstance(result, Exception)


# ---------------------------------------------------------------------------
# Flink.get_codes
# ---------------------------------------------------------------------------

@resp_lib.activate
def test_get_codes_success(flink):
    resp_lib.add(resp_lib.GET, f"{BASE_URL}/{DEVICE_ID}/codes", json=MOCK_CODES, status=200)
    status, codes = flink.get_codes()
    assert status == 200
    assert codes == MOCK_CODES


@resp_lib.activate
def test_get_codes_non_200(flink):
    resp_lib.add(resp_lib.GET, f"{BASE_URL}/{DEVICE_ID}/codes", json={}, status=404)
    status, codes = flink.get_codes()
    assert status == 404
    assert codes == {}


@resp_lib.activate
def test_get_codes_network_error(flink):
    resp_lib.add(
        resp_lib.GET,
        f"{BASE_URL}/{DEVICE_ID}/codes",
        body=ConnectionError("timeout"),
    )
    status, codes = flink.get_codes()
    assert isinstance(status, Exception)
    assert codes is None


# ---------------------------------------------------------------------------
# Flink.check_code
# ---------------------------------------------------------------------------

@resp_lib.activate
def test_check_code_valid(flink):
    resp_lib.add(resp_lib.GET, f"{BASE_URL}/{DEVICE_ID}/codes", json=MOCK_CODES, status=200)
    comp, status = flink.check_code("1001")
    assert comp == "1"
    assert status == "valid"


@resp_lib.activate
def test_check_code_valid_second_compartment(flink):
    resp_lib.add(resp_lib.GET, f"{BASE_URL}/{DEVICE_ID}/codes", json=MOCK_CODES, status=200)
    comp, status = flink.check_code("1002")
    assert comp == "2"
    assert status == "valid"


@resp_lib.activate
def test_check_code_invalid_4digit(flink):
    resp_lib.add(resp_lib.GET, f"{BASE_URL}/{DEVICE_ID}/codes", json=MOCK_CODES, status=200)
    comp, status = flink.check_code("9999")
    assert comp is None
    assert status == "invalid"


def test_check_code_wrong_length_short(flink):
    comp, status = flink.check_code("123")
    assert comp is None
    assert status == "invalid"


def test_check_code_wrong_length_long(flink):
    comp, status = flink.check_code("12345")
    assert comp is None
    assert status == "invalid"


def test_check_code_empty(flink):
    comp, status = flink.check_code("")
    assert comp is None
    assert status == "invalid"


@resp_lib.activate
def test_check_code_api_error_returns_error_status(flink):
    resp_lib.add(resp_lib.GET, f"{BASE_URL}/{DEVICE_ID}/codes", json={}, status=500)
    comp, status = flink.check_code("1001")
    assert comp is None
    assert status == "error"


# ---------------------------------------------------------------------------
# Flink.post_code_log
# ---------------------------------------------------------------------------

@resp_lib.activate
def test_post_code_log_known_compartment(flink):
    resp_lib.add(resp_lib.POST, f"{BASE_URL}/{DEVICE_ID}/code_log", json={}, status=200)

    mock_comp = MagicMock()
    mock_comp.content_status = "present"
    mock_comp.door_status = "closed"
    compartments = {"1": mock_comp}

    code = flink.post_code_log("1001", compartments, "1")
    assert code == 200

    import json
    body = json.loads(resp_lib.calls[0].request.body)
    assert body["content"] == "present"
    assert body["door"] == "closed"
    assert body["compartment"] == "1"
    assert body["code_entered"] == "1001"


@resp_lib.activate
def test_post_code_log_unknown_compartment_sends_none(flink):
    resp_lib.add(resp_lib.POST, f"{BASE_URL}/{DEVICE_ID}/code_log", json={}, status=200)

    flink.post_code_log("9999", {}, None)

    import json
    body = json.loads(resp_lib.calls[0].request.body)
    assert body["content"] is None
    assert body["door"] is None


@resp_lib.activate
def test_post_code_log_compartment_index_not_in_dict(flink):
    resp_lib.add(resp_lib.POST, f"{BASE_URL}/{DEVICE_ID}/code_log", json={}, status=200)
    flink.post_code_log("1001", {}, "5")

    import json
    body = json.loads(resp_lib.calls[0].request.body)
    assert body["content"] is None
    assert body["door"] is None


# ---------------------------------------------------------------------------
# FlinkLogHandler
# ---------------------------------------------------------------------------

@resp_lib.activate
def test_flink_log_handler_emit_posts_error_log():
    resp_lib.add(resp_lib.POST, f"{BASE_URL}/{DEVICE_ID}/error_log", json={}, status=200)

    handler = FlinkLogHandler(logging.ERROR, DEVICE_ID, BASE_URL, API_KEY)

    record = logging.LogRecord(
        name="test",
        level=logging.ERROR,
        pathname="",
        lineno=0,
        msg="Something went wrong",
        args=(),
        exc_info=None,
    )
    handler.emit(record)

    assert len(resp_lib.calls) == 1
    assert f"{DEVICE_ID}/error_log" in resp_lib.calls[0].request.url

    import json
    body = json.loads(resp_lib.calls[0].request.body)
    assert body["level"] == "ERROR"
    assert "Something went wrong" in body["message"]


@resp_lib.activate
def test_flink_log_handler_does_not_raise_on_network_error():
    """If the HTTP call fails, emit() must not raise (it just prints)."""
    resp_lib.add(
        resp_lib.POST,
        f"{BASE_URL}/{DEVICE_ID}/error_log",
        body=ConnectionError("down"),
    )
    handler = FlinkLogHandler(logging.ERROR, DEVICE_ID, BASE_URL, API_KEY)
    record = logging.LogRecord("test", logging.ERROR, "", 0, "msg", (), None)
    handler.emit(record)  # must not raise
