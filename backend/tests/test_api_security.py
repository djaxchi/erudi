"""Localhost API hardening (#89): CORS allowlist + host pinning.

The desktop threat model: the API binds 127.0.0.1 without auth, so the browser
is the only wall between a malicious website and the user's conversations/KB.
Two findings from the security audit are pinned here:

- Permissive CORS (``allow_origins=["*"]`` + credentials) let ANY website read
  API responses cross-origin. The allowlist now covers exactly the two real
  renderer origins: the webpack dev server (http://localhost:3000) and the
  packaged ``file://`` renderer (which serializes to the literal origin
  ``null``). Credentials are off — nothing uses cookies.
- No host pinning meant DNS rebinding (attacker domain resolving to 127.0.0.1)
  bypassed CORS entirely. ``TrustedHostMiddleware`` now rejects any Host that
  is not local.

Documented residual: sandboxed iframes also send ``Origin: null``; Chromium's
private-network-access blocks public->local fetches, other browsers may not.
The full fix (per-session token minted by the Electron main) is tracked in #89.
"""


def _get(client, path="/erudi/health", **headers):
    return client.get(path, headers=headers)


class TestCorsAllowlist:
    def test_foreign_website_origin_is_not_allowed(self, client):
        r = _get(client, Origin="https://evil.example")
        assert r.status_code == 200  # same-machine request itself still works
        assert "access-control-allow-origin" not in r.headers

    def test_packaged_renderer_null_origin_is_allowed(self, client):
        r = _get(client, Origin="null")
        assert r.headers.get("access-control-allow-origin") == "null"

    def test_dev_renderer_origin_is_allowed(self, client):
        r = _get(client, Origin="http://localhost:3000")
        assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"

    def test_credentials_are_never_offered(self, client):
        for origin in ("null", "http://localhost:3000", "https://evil.example"):
            r = _get(client, Origin=origin)
            assert "access-control-allow-credentials" not in r.headers

    def test_preflight_from_foreign_origin_is_rejected(self, client):
        r = client.options(
            "/erudi/health",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert "access-control-allow-origin" not in r.headers

    def test_request_id_stays_exposed_to_the_renderer(self, client):
        # The fe-/be- correlation contract (#172) must survive the tightening.
        r = _get(client, Origin="http://localhost:3000")
        assert "X-Request-ID" in r.headers.get("access-control-expose-headers", "")


class TestHostPinning:
    def test_rebound_host_is_rejected(self, client):
        r = _get(client, Host="attacker.example")
        assert r.status_code == 400

    def test_local_hosts_are_accepted(self, client):
        for host in ("127.0.0.1", "localhost", "127.0.0.1:27182"):
            assert _get(client, Host=host).status_code == 200
