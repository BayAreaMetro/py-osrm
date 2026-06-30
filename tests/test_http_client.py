"""Tests for OSRM_HTTP, focused on the /metadata helper and one-time reporting.

These tests avoid a live server (and any HTTP-mocking dependency) by injecting a
fake ``requests.Session`` whose ``.get()`` returns canned responses. The fake is
also used for the connectivity check the constructor performs.
"""
import logging
from unittest.mock import MagicMock

import pytest
import requests

import osrm
import constants

two_test_coordinates = constants.two_test_coordinates


@pytest.fixture(scope="session", autouse=True)
def osrm_datastore():
    """Override the conftest datastore fixture — these tests use a fake session
    and never touch a real engine or shared memory."""
    yield

SAMPLE_METADATA = {
    "generated_at": "2026-05-18T22:07:35Z",
    "profiles": {
        "car": {
            "osm_data_timestamp": "2026-05-01T20:21:00Z",
            "processed_at": "2026-05-18T22:07:35Z",
        },
        "bicycle": {
            "osm_data_timestamp": "2026-05-01T20:21:00Z",
            "processed_at": "2026-05-01T23:48:38Z",
        },
        "foot": {
            "osm_data_timestamp": "2026-05-01T20:21:00Z",
            "processed_at": "2026-05-02T00:01:12Z",
        },
    },
}

ROUTE_RESPONSE = {
    "code": "Ok",
    "waypoints": [{}, {}],
    "routes": [{"distance": 123.4, "duration": 45.6, "geometry": "abc"}],
}


def _make_response(json_data):
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


class FakeSession:
    """Minimal requests.Session stand-in dispatching on URL path.

    ``metadata_error`` makes /metadata raise a RequestException, simulating a
    server that does not implement the endpoint.
    """

    def __init__(self, metadata_error=False):
        self.metadata_error = metadata_error
        self.calls = []  # list of requested URLs

    def mount(self, *args, **kwargs):  # constructor never calls this (session given)
        pass

    def get(self, url, params=None, timeout=None):
        self.calls.append(url)
        if url.endswith("/metadata"):
            if self.metadata_error:
                raise requests.exceptions.RequestException("metadata unavailable")
            return _make_response(SAMPLE_METADATA)
        # Connectivity check (root) and routing requests
        return _make_response(ROUTE_RESPONSE)

    def metadata_call_count(self):
        return sum(1 for u in self.calls if u.endswith("/metadata"))


def _client(metadata_error=False, report_metadata=True):
    session = FakeSession(metadata_error=metadata_error)
    client = osrm.OSRM_HTTP(
        "http://testserver:5000",
        session=session,
        report_metadata=report_metadata,
    )
    return client, session


def test_metadata_returns_and_caches():
    client, session = _client()
    assert client.Metadata() == SAMPLE_METADATA
    assert session.metadata_call_count() == 1
    # Cached: a second call does not hit the server again
    assert client.Metadata() == SAMPLE_METADATA
    assert session.metadata_call_count() == 1
    # refresh=True forces a re-fetch
    client.Metadata(refresh=True)
    assert session.metadata_call_count() == 2


def test_metadata_logged_once_on_first_request(caplog):
    client, session = _client()
    with caplog.at_level(logging.INFO, logger="osrm"):
        client.Route(two_test_coordinates)
        client.Route(two_test_coordinates)
    records = [r for r in caplog.records if "OSRM server metadata" in r.getMessage()]
    assert len(records) == 1
    assert "generated 2026-05-18T22:07:35Z" in records[0].getMessage()
    assert "car:" in records[0].getMessage()
    # /metadata fetched exactly once despite two routing calls
    assert session.metadata_call_count() == 1


def test_report_metadata_disabled(caplog):
    client, session = _client(report_metadata=False)
    with caplog.at_level(logging.INFO, logger="osrm"):
        client.Route(two_test_coordinates)
    assert not any(
        "OSRM server metadata" in r.getMessage() for r in caplog.records
    )
    assert session.metadata_call_count() == 0


def test_metadata_failure_does_not_break_routing(caplog):
    client, session = _client(metadata_error=True)
    with caplog.at_level(logging.INFO, logger="osrm"):
        res = client.Route(two_test_coordinates)
    # Routing still succeeds
    assert res["routes"][0]["distance"] == 123.4
    # No metadata line was logged
    assert not any(
        "OSRM server metadata" in r.getMessage() for r in caplog.records
    )
    # And the failed attempt is not retried on the next request
    client.Route(two_test_coordinates)
    assert session.metadata_call_count() == 1


def test_metadata_explicit_failure_raises():
    client, _ = _client(metadata_error=True)
    with pytest.raises(RuntimeError):
        client.Metadata()
