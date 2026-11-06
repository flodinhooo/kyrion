"""Readiness checks on the Pi loopback proxy; never print device credentials.

This does not validate public DNS/TLS, SMTP delivery or browser authentication.
The device-grant check creates one short-lived unapproved device request.
"""

import json
import urllib.error
import urllib.parse
import urllib.request


def request(path, data=None, headers=None):
    req = urllib.request.Request(
        "http://127.0.0.1:18890" + path, data=data, headers=headers or {}
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def main():
    issuer = "https://auth.kyrion.ch/realms/kyrion"
    status, body = request(
        "/realms/kyrion/.well-known/openid-configuration",
        headers={"Host": "attacker.invalid", "X-Forwarded-Host": "attacker.invalid"},
    )
    assert status == 200, "Discovery unavailable"
    discovery = json.loads(body)
    assert discovery["issuer"] == issuer, "Issuer mismatch"
    assert "S256" in discovery["code_challenge_methods_supported"], "PKCE missing"
    assert (
        discovery["device_authorization_endpoint"]
        == issuer + "/protocol/openid-connect/auth/device"
    )
    for path in (
        "/",
        "/admin/",
        "/admin/master/console/",
        "/realms/master",
        "/health",
        "/metrics",
    ):
        assert request(path)[0] == 404, "Administrative route exposed"
    status, body = request("/realms/kyrion/protocol/openid-connect/certs")
    assert status == 200 and json.loads(body)["keys"], "Signing keys unavailable"
    status, body = request(
        "/realms/kyrion/protocol/openid-connect/auth/device",
        urllib.parse.urlencode(
            {"client_id": "kyrion-local", "scope": "openid"}
        ).encode(),
        {"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert status == 200, "Public device grant unavailable"
    grant = json.loads(body)
    assert grant.get("device_code") and grant.get("user_code"), "Device proof missing"
    assert grant["verification_uri"].startswith(issuer + "/"), (
        "Unexpected authorization origin"
    )
    assert 0 < grant["expires_in"] <= 300, "Device expiry outside policy"
    print(
        "PASS: fixed HTTPS issuer, S256, JWKS, six blocked paths, public device grant"
    )


if __name__ == "__main__":
    try:
        main()
    except AssertionError as error:
        raise SystemExit("Pilot readiness failed: " + str(error)) from None
    except (OSError, ValueError, KeyError, TypeError):
        raise SystemExit(
            "Pilot transport failed; no response bodies or credentials printed"
        ) from None
