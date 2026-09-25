"""HTTP client for PokeMac telemetry on port 9777."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from jev_player.snapshot import snapshot_identity


class SnapshotTimeout(TimeoutError):
    pass


class Clock:
    def monotonic(self):
        return time.monotonic()

    def sleep(self, seconds):
        if seconds > 0:
            time.sleep(seconds)


class UrllibTransport:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")

    def get_json(self, path):
        with urllib.request.urlopen(self.base_url + path, timeout=5) as response:
            return json.load(response)

    def post_json(self, path, body):
        payload = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"POST {path} failed: {error.code} {detail}") from error


class TelemetryClient:
    def __init__(self, base_url="http://127.0.0.1:9777", transport=None, clock=None, timeout=8.0, poll_interval=0.05):
        self.transport = transport or UrllibTransport(base_url)
        self.clock = clock or Clock()
        self.timeout = timeout
        self.poll_interval = poll_interval

    def latest(self):
        return self.transport.get_json("/telemetry/latest")

    def press(self, button):
        return self.transport.post_json("/input", {"button": button})

    def wait_until_ready(self):
        deadline = self.clock.monotonic() + self.timeout
        while True:
            snapshot = self.latest()
            if snapshot.get("inputReady"):
                return snapshot
            if self.clock.monotonic() >= deadline:
                raise SnapshotTimeout("snapshot stayed input-locked")
            self.clock.sleep(self.poll_interval)

    def press_and_wait(self, button, before):
        before_identity = snapshot_identity(before)
        self.press(button)
        deadline = self.clock.monotonic() + self.timeout
        while True:
            snapshot = self.latest()
            changed = snapshot_identity(snapshot) != before_identity
            if changed and snapshot.get("inputReady"):
                return snapshot
            if self.clock.monotonic() >= deadline:
                raise SnapshotTimeout(f"snapshot did not advance after {button}")
            self.clock.sleep(self.poll_interval)
