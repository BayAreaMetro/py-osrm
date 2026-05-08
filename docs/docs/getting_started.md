# Getting Started

## Installation

!!! warning "C++ extension — pre-built wheels strongly recommended"
    py-osrm wraps the [OSRM C++ backend](https://github.com/Project-OSRM/osrm-backend).
    Installing from source (e.g. `uv sync`, `pip install .`, or `pip install git+...`) requires
    a full C++ toolchain including a recent compiler (GCC/Clang), CMake, Boost, libtbb, and Lua,
    and **takes 5–10 minutes to compile**. Toolchain mismatches are common and will cause the build
    to fail silently or with cryptic errors.

    **Use the pre-built wheels below** unless you explicitly need to modify the C++ source.

py-osrm is distributed as pre-built wheels via [GitHub Releases](https://github.com/BayAreaMetro/py-osrm/releases).
No C++ compiler required.

=== "Linux / macOS"

    ```bash
    pip install https://github.com/BayAreaMetro/py-osrm/releases/latest/download/py_osrm-cp39-abi3-linux_x86_64.whl
    ```

=== "Windows"

    Download the appropriate `.whl` from the [Releases page](https://github.com/BayAreaMetro/py-osrm/releases) and install:

    ```bash
    pip install py_osrm-<version>-cp39-abi3-win_amd64.whl
    ```

!!! tip "Bulk processing support"
    Install [Polars](https://pola.rs/) and [tqdm](https://tqdm.github.io/) to use the bulk processing functions with progress reporting:
    ```bash
    pip install polars tqdm
    ```

---

## Preprocessing

Before routing, you must preprocess OpenStreetMap (OSM) data into OSRM's internal format.
Built-in profiles are `car`, `bicycle`, and `foot`.

### CH (Contraction Hierarchies) — recommended for most use cases

```python
import osrm

# Step 1 — extract the road network from an OSM file
osrm.extract("region.osm.pbf", profile="car", output_path="region")

# Step 2 — build the CH routing graph
osrm.contract("region")

# Ready to route
engine = osrm.OSRM("region.osrm")
```

### MLD (Multi-Level Dijkstra) — better for large datasets / dynamic weights

```python
import osrm

osrm.extract("region.osm.pbf", profile="car", output_path="region")
osrm.partition("region")
osrm.customize("region")

engine = osrm.OSRM("region.osrm", algorithm="mld")
```

### CLI equivalent

```bash
python -m osrm extract region.osm.pbf --profile car
python -m osrm contract region
```

See [Preprocessing](pages/preprocessing.md) for full API reference and custom profile support.

---

## Routing

### Single route

```python
import osrm

engine = osrm.OSRM("region.osrm")

result = engine.Route(
    coordinates=[(7.41337, 43.72956), (7.41546, 43.73077)],
    steps=True,
    geometries="geojson",
)

route = result["routes"][0]
print(f"Distance: {route['distance']:.1f} m")
print(f"Duration: {route['duration']:.1f} s")
```

### Distance / duration matrix

```python
coords = [
    (7.41337, 43.72956),
    (7.41546, 43.73077),
    (7.41862, 43.73216),
]

result = engine.Table(coordinates=coords, annotations=["distance", "duration"])
print(result["durations"])   # 3×3 matrix
print(result["distances"])   # 3×3 matrix
```

### Nearest road segment

```python
result = engine.Nearest(coordinates=[(7.41337, 43.72956)], number=3)
for waypoint in result["waypoints"]:
    print(waypoint["name"], waypoint["distance"])
```

---

## HTTP Client

Use `OSRM_HTTP` when connecting to a remote `osrm-routed` server instead of loading data locally.
The interface is identical to the native `OSRM` class.

```python
import osrm

# Public demo server (rate-limited — use for testing only)
client = osrm.OSRM_HTTP("http://router.project-osrm.org")

result = client.Route(
    coordinates=[(7.41337, 43.72956), (7.41546, 43.73077)]
)
print(result["routes"][0]["distance"])
```

See [HTTP Client](pages/http_client.md) for full reference.

---

## Bulk Processing

Process large origin-destination matrices in parallel using a Polars DataFrame.

```python
import polars as pl
import osrm

engine = osrm.OSRM("region.osrm")

df = pl.DataFrame({
    "origin_lon":  [7.41337, 7.41862, 7.42150],
    "origin_lat":  [43.72956, 43.73216, 43.73400],
    "dest_lon":    [7.41546, 7.42000, 7.42300],
    "dest_lat":    [43.73077, 43.73300, 43.73500],
})

results = osrm.bulk_route(engine, df, geometries="geojson")
print(results.select(["distance", "duration", "success"]))
```

See [Bulk Processing](pages/bulk.md) for full reference including `bulk_nearest` and `bulk_match`.
