# py-osrm

[![Build Wheels](https://github.com/BayAreaMetro/py-osrm/actions/workflows/build_wheels.yml/badge.svg)](https://github.com/BayAreaMetro/py-osrm/actions/workflows/build_wheels.yml)
[![Docs](https://github.com/BayAreaMetro/py-osrm/actions/workflows/gh-pages.yml/badge.svg)](https://bayareametro.github.io/py-osrm/)

**py-osrm provides Python bindings to [osrm-backend](https://github.com/Project-OSRM/osrm-backend) using [nanobind](https://github.com/wjakob/nanobind).**

> This project is a fork of [nick-fournier/py-osrm](https://github.com/nick-fournier/py-osrm), itself a continuation of the archived [gis-ops/py-osrm](https://github.com/gis-ops/py-osrm).

This package binds to **OSRM v6.0.0** backend and includes preprocessing functionality.

---

## Supported Platforms
Platform | Arch
---|---
Linux | x86_64
MacOS | x86_64
Windows | x86_64
---

## Installation
py-osrm is supported on **CPython 3.9+**.

> [!WARNING]
> **py-osrm wraps a C++ library and must be compiled from source if not using a pre-built wheel.**
> Running `uv sync`, `pip install .`, or `pip install git+...` requires a full C++ toolchain
> (compiler, CMake, Boost, libtbb, Lua) and takes **5–10 minutes**. Toolchain mismatches are
> common and will cause hard-to-diagnose build failures. **Use the pre-built wheels below.**

**Install from GitHub Releases (recommended — no compilation required):**

```bash
# Linux
pip install https://github.com/BayAreaMetro/py-osrm/releases/latest/download/py_osrm-cp39-abi3-linux_x86_64.whl

# macOS
pip install https://github.com/BayAreaMetro/py-osrm/releases/latest/download/py_osrm-cp39-abi3-macosx_15_0_x86_64.whl

# Windows
pip install https://github.com/BayAreaMetro/py-osrm/releases/latest/download/py_osrm-cp39-abi3-win_amd64.whl
```

Or browse all wheels on the [Releases page](https://github.com/BayAreaMetro/py-osrm/releases).

**From source (requires C++ compiler, CMake, ~5-10 min):**
```bash
git clone https://github.com/BayAreaMetro/py-osrm.git
cd py-osrm
pip install .
```

## Quick Start

```python
import osrm

# Load preprocessed data
py_osrm = osrm.OSRM("path/to/data.osrm")

# Calculate route - pass coordinates directly!
result = py_osrm.Route([(7.41337, 43.72956), (7.41546, 43.73077)])
print(result["routes"][0]["distance"])  # Distance in meters
```

## Usage

### Routing Services

**Route** - Calculate routes between coordinates:
```python
result = py_osrm.Route(
    coordinates=[(7.41337, 43.72956), (7.41546, 43.73077)],
    steps=True,
    geometries="geojson",
    annotations=["speed", "distance"]
)
```

**Table** - Calculate distance/duration matrices:
```python
result = py_osrm.Table(
    coordinates=[(7.41337, 43.72956), (7.41546, 43.73077), (7.41862, 43.73216)],
    annotations=["distance", "duration"]
)
# Access via result["distances"] and result["durations"]
```

**Nearest** - Find nearest road segment:
```python
result = py_osrm.Nearest(
    coordinates=[(7.41337, 43.72956)],
    number=3
)
```

See the [documentation](https://bayareametro.github.io/py-osrm/) for Trip, Match, and Tile services.

### Bulk Processing (Concurrent)

Process multiple routes in parallel using ThreadPoolExecutor for significant speedup:

```python
import polars as pl
import osrm

# Initialize OSRM instance
py_osrm = osrm.OSRM("path/to/data.osrm")

# Create DataFrame with origin-destination pairs
df = pl.DataFrame({
    "origin_lon": [7.41337, 7.41862, 7.42150],
    "origin_lat": [43.72956, 43.73216, 43.73400],
    "dest_lon": [7.41546, 7.42000, 7.42300],
    "dest_lat": [43.73077, 43.73300, 43.73500]
})

# Process all routes concurrently (releases GIL for true parallelism)
results = osrm.bulk_route(py_osrm, df, steps=True, geometries="geojson")

# Results DataFrame includes: distance, duration, geometry, success, error
print(results.select(["distance", "duration", "success"]))
```

**Optional dependencies for bulk processing:**
```bash
pip install polars          # DataFrame support
pip install polars tqdm     # DataFrame support + progress bar
```

**Key features:**
- True parallel execution (GIL released in C++)
- Works with Polars DataFrames or dict-of-lists
- Per-row parameter customization
- Automatic error handling with `fail_fast` option
- Progress tracking with `show_progress=True`
- Typically 3-4x faster than sequential processing on 4+ cores

### Preprocessing

Before routing, you must preprocess OpenStreetMap data. Built-in profiles include `car`, `bicycle`, and `foot`:

**CH (Contraction Hierarchies) - Fastest queries:**
```python
import osrm

# Extract road network from OSM data
osrm.extract("data.osm.pbf", profile="car", output_path="data")

# Build routing graph (CH)
osrm.contract("data")

# Ready to use
py_osrm = osrm.OSRM("data.osrm")
```

**Using a custom profile:**
```python
osrm.extract("data.osm.pbf", profile="/path/to/custom.lua", output_path="data")
```

**CLI usage:**
```bash
python -m osrm extract data.osm.pbf --profile car
python -m osrm contract data
```

For **MLD (Multi-Level Dijkstra)** on larger datasets, see [preprocessing documentation](https://bayareametro.github.io/py-osrm/pages/preprocessing/).

## Advanced Usage

### Legacy Parameter Objects

<details>
<summary>Alternative usage with parameter objects (click to expand)</summary>

Parameter objects are still supported for backwards compatibility:

```python
# Create parameter object
route_params = osrm.RouteParameters(
    coordinates=[(7.41337, 43.72956), (7.41546, 43.73077)]
)

# Pass to Route method
result = py_osrm.Route(route_params)
```

This pattern is useful when constructing parameters programmatically or reusing them across multiple requests. However, the direct keyword argument pattern shown above is now recommended for most use cases.

</details>

---

## HTTP Client

Route against a remote `osrm-routed` server — same API as the native `OSRM` class:

```python
import osrm

client = osrm.OSRM_HTTP("http://localhost:5000")
result = client.Route([(7.41337, 43.72956), (7.41546, 43.73077)])
print(result["routes"][0]["distance"])

# Works identically with bulk_route
results = osrm.bulk_route(client, df)
```

---

## Documentation

[https://bayareametro.github.io/py-osrm/](https://bayareametro.github.io/py-osrm/)

## Acknowledgments
This project is a fork of [nick-fournier/py-osrm](https://github.com/nick-fournier/py-osrm), which continues the original work from the archived [gis-ops/py-osrm](https://github.com/gis-ops/py-osrm). Thanks to all prior authors for their foundational contributions.
