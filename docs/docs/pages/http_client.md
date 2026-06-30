# HTTP Client

`OSRM_HTTP` provides the same routing interface as the native `OSRM` class but connects to a
remote `osrm-routed` server over HTTP. Useful for cloud deployments, shared infrastructure,
or when you want to avoid managing local `.osrm` files.

::: osrm.OSRM_HTTP
    options:
      show_root_heading: true
      members:
        - Route
        - Table
        - Nearest
        - Match
        - Trip
        - Tile
        - Metadata

---

## Server metadata

Some OSRM servers expose a custom `/metadata` endpoint reporting when the underlying
OSM data was sourced and when each routing profile was processed. `OSRM_HTTP` can both
fetch this on demand and surface it automatically.

### Querying it explicitly

`Metadata()` returns the raw dict and caches it on the client, so it only hits the
server on the first call:

```python
import osrm

client = osrm.OSRM_HTTP("http://your-osrm-server:5000")

meta = client.Metadata()
# {'generated_at': '2026-05-18T22:07:35Z',
#  'profiles': {'car': {...}, 'bicycle': {...}, 'foot': {...}}}

print(meta["generated_at"])
print(meta["profiles"]["car"]["osm_data_timestamp"])   # when the OSM data is from
print(meta["profiles"]["car"]["processed_at"])          # when it was built
```

Pass `refresh=True` to bypass the cache if the server may have been updated mid-session:

```python
meta = client.Metadata(refresh=True)
```

### Automatic one-time reporting

By default (`report_metadata=True`), the **first** routing request logs a one-line
metadata summary at `INFO` level on the `osrm` logger. Because INFO is off by default,
you must enable it to see the message:

```python
import logging, osrm

logging.basicConfig(level=logging.INFO)   # or: logging.getLogger("osrm").setLevel(logging.INFO)

client = osrm.OSRM_HTTP("http://your-osrm-server:5000")
client.Route([(7.41337, 43.72956), (7.41546, 43.73077)])
# INFO:osrm:OSRM server metadata (generated 2026-05-18T22:07:35Z): car: osm_data=..., processed=...; ...

client.Route([...])   # no second log line — reported once per client
```

This covers `Route`, `Table`, `Nearest`, `Match`, `Trip`, `Tile`, and the bulk helpers.
The auto-log reuses the same cached fetch, so it adds no extra round-trip. Disable it
with `OSRM_HTTP(..., report_metadata=False)`. If the server doesn't implement `/metadata`,
the failure is swallowed and routing is unaffected (an explicit `Metadata()` call raises
`RuntimeError`).

### Common patterns

Check data freshness and warn on staleness:

```python
from datetime import datetime, timezone

meta = client.Metadata()
built = datetime.fromisoformat(meta["profiles"]["car"]["processed_at"].replace("Z", "+00:00"))
age_days = (datetime.now(timezone.utc) - built).days
if age_days > 30:
    print(f"⚠ car routing data is {age_days} days old")
```

Record provenance alongside results:

```python
meta = client.Metadata()
result = {
    "routes": client.Route(coords),
    "data_version": meta["generated_at"],
}
```
