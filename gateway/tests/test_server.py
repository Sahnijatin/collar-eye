"""Gateway HTTP routes: device upload, tokens, /status, /camera, /eye.

Run from gateway/:  python -m pytest tests
"""
import io
import os
import sys

import pytest
from PIL import Image

KEY = "test-device-key-123"
os.environ["DEVICE_KEY"] = KEY
os.environ["GATEWAY_TOKEN"] = ""
sys.argv = ["server.py"]

from fastapi.testclient import TestClient  # noqa: E402

import server  # noqa: E402
from eye import EyeHub  # noqa: E402

AUTH = {"X-Gateway-Token": KEY}


@pytest.fixture
def client(monkeypatch):
    hub = EyeHub()
    monkeypatch.setattr(server, "hub", hub)
    # server.py loads gateway/.env with override=True; pin the keys for the test
    monkeypatch.setattr(server, "DEVICE_KEY", KEY)
    monkeypatch.setattr(server, "GATEWAY_TOKEN", KEY)
    return TestClient(server.app)


def _jpeg():
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), "red").save(buf, "JPEG")
    return buf.getvalue()


def _upload(client, key=KEY):
    return client.post("/device/frame", content=_jpeg(), headers={"X-Device-Key": key, "X-Device-Id": "aabbccddeeff"})


def test_device_frame_needs_the_device_key(client):
    assert _upload(client, key="wrong").status_code == 401
    assert _upload(client).status_code == 200


def test_device_frame_rejects_non_jpeg(client):
    h = {"X-Device-Key": KEY}
    assert client.post("/device/frame", content=b"not a jpeg" * 20, headers=h).status_code == 400
    assert client.post("/device/frame", content=b"\xff\xd8" + b"x" * 200, headers=h).status_code == 400


def test_device_gets_only_explicit_camera_settings(client):
    assert _upload(client).json() == {}
    assert client.post("/camera", json={"fps": 3}, headers=AUTH).status_code == 200
    assert _upload(client).json() == {"fps": 3}


def test_frame_jpg_needs_token_in_header_not_url(client):
    _upload(client)
    assert client.get("/frame.jpg").status_code == 401
    assert client.get(f"/frame.jpg?token={KEY}").status_code == 401
    r = client.get("/frame.jpg", headers=AUTH)
    assert r.status_code == 200 and r.content[:2] == b"\xff\xd8"


def test_status_hides_device_details_without_token(client):
    _upload(client)
    public = client.get("/status").json()
    assert public["connected"] and "device_id" not in public and "camera" not in public
    assert client.get("/status", headers=AUTH).json()["device_id"] == "aabbccddeeff"


@pytest.mark.parametrize("body", [[1], "fps", {"fps": "3"}, {"fps": 99}, {"quality": 12.5},
                                  {"vflip": 1}, {"framesize": "4K"}, {"zoom": 2}, {"fps": None}])
def test_camera_rejects_bad_settings(client, body):
    assert client.post("/camera", json=body, headers=AUTH).status_code == 400


def test_camera_accepts_good_settings(client):
    r = client.post("/camera", json={"fps": 0.5, "framesize": "HD", "quality": 12, "vflip": True}, headers=AUTH)
    assert r.status_code == 200
    assert r.json() == {"fps": 0.5, "framesize": "HD", "quality": 12, "vflip": True}
    assert client.post("/camera", json={"fps": 1}).status_code == 401


def test_eye_page_does_not_reflect_the_request(client):
    r = client.get("/eye?token=%3C/script%3E%3Cscript%3Ealert(1)%3C/script%3E")
    assert r.status_code == 200
    assert "alert(1)" not in r.text
