# Changelog

## v0.1.0 — 2026-05-08

Initial release as an independently maintained fork of [nick-fournier/py-osrm](https://github.com/nick-fournier/py-osrm), a continuation of the archived [nilsnolde/osrm-bindings](https://github.com/nilsnolde/osrm-bindings).

### Added
- Native Python bindings to **OSRM v6.0.0** backend via [nanobind](https://github.com/wjakob/nanobind)
- Routing services: `Route`, `Table`, `Nearest`, `Match`, `Trip`, `Tile`
- Bulk parallel processing: `bulk_route`, `bulk_nearest`, `bulk_match` (Polars DataFrame + dict-of-lists)
- HTTP client `OSRM_HTTP` — same interface as native engine, connects to `osrm-routed` servers
- Preprocessing pipeline: `extract`, `contract`, `partition`, `customize`
- CLI: `python -m osrm extract|contract|partition|customize|datastore`
- Bundled routing profiles: `car`, `bicycle`, `foot`
- Pre-built wheels for Linux, macOS, and Windows (CPython 3.9+)
