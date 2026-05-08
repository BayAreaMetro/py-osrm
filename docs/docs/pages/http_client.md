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
