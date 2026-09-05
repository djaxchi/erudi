"""No periodic beacon to a third party while the app is open.

The connectivity pill used to be coloured by a ``HEAD https://huggingface.co``
that the frontend triggered every 45 seconds. It carried no data, but it handed
huggingface.co a per-machine, per-second record of when Erudi runs, and nothing
in the app could turn it off. The renderer now reads connectivity from the
operating system, so the probe, its endpoint and its response schema are gone.

These pin the removal: a route that comes back would resume the traffic without
anyone noticing, and so would a helper that quietly re-adds the request.
"""

from pathlib import Path

import pytest

from src.core import config

pytestmark = pytest.mark.unit


class TestConnectivityEndpointIsGone:
    def test_the_startup_router_exposes_no_connectivity_probe(self, client):
        response = client.get("/erudi/startup/connection-status")
        assert response.status_code == 404

    def test_the_welcome_popup_endpoint_still_works(self, client):
        # The rest of the startup domain must survive the removal.
        assert client.get("/erudi/startup/welcome-popup").status_code == 200

    def test_no_connection_status_schema_is_left_behind(self):
        from src.domains.startup import schemas

        assert not hasattr(schemas, "ConnectionStatusResponse")


class TestSeedMakesNoConnectivityRequest:
    def test_seed_declares_no_reachability_probe(self):
        from src.database import seed

        assert not hasattr(seed, "is_online")

    def test_seed_source_contains_no_bare_reachability_request(self):
        source = (Path(config.ROOT_DIR) / "src" / "database" / "seed.py").read_text(
            encoding="utf-8"
        )
        assert "requests.head" not in source
