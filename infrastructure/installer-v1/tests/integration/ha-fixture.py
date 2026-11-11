"""Synthetic HA-compatible API, only for the isolated developer network.

No upstream provider, USB device or physical device is accessed.
"""

import datetime
import http.server
import json

state = {"on": False, "removed": False, "posts": 0}


class Handler(http.server.BaseHTTPRequestHandler):
    def reply(self, value, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(value).encode())

    def do_GET(self):
        if self.path == "/fixture/status":
            self.reply(state)
        elif self.headers.get("Authorization") != "Bearer synthetic-ha-fixture":
            self.reply({}, 401)
        elif self.path == "/api/states/light.fixture":
            self.reply(
                {
                    "entity_id": "light.fixture",
                    "state": "on" if state["on"] else "off",
                    "last_updated": self.now(),
                }
            )
        else:
            self.reply({}, 404)

    def do_POST(self):
        raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if self.path == "/fixture/remove":
            state["removed"] = True
            return self.reply(state)
        if self.path == "/fixture/reset":
            state.update(on=False, removed=False, posts=0)
            return self.reply(state)
        if self.headers.get("Authorization") != "Bearer synthetic-ha-fixture":
            return self.reply({}, 401)
        if self.path == "/api/template":
            rows = (
                []
                if state["removed"]
                else [
                    self.row("a", "light.fixture", "on" if state["on"] else "off"),
                    self.row("a", "sensor.temperature", "21", "temperature"),
                ]
            )
            return self.reply([*rows, self.row("b", "switch.excluded", "off")])
        if self.path in {"/api/services/light/turn_on", "/api/services/light/turn_off"}:
            if json.loads(raw) != {"entity_id": "light.fixture"} or state["removed"]:
                return self.reply({}, 400)
            state["posts"] += 1
            state["on"] = self.path.endswith("turn_on")
            return self.reply([])
        return self.reply({}, 404)

    @staticmethod
    def now():
        return datetime.datetime.now(datetime.UTC).isoformat()

    def row(self, identifier, entity, value, kind=None):
        return {
            "id": identifier * 32,
            "entity": entity,
            "entityName": entity.split(".")[1],
            "name": "Synthetic " + identifier,
            "area": "Fixture room",
            "state": value,
            "class": kind,
            "unit": "°C" if kind else None,
            "updated": self.now(),
        }

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    http.server.ThreadingHTTPServer(("0.0.0.0", 8123), Handler).serve_forever()
