"""HTTP client adapter for OSRM that provides the same interface as native bindings."""

import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("osrm")


class OSRM_HTTP:
    """
    HTTP client for OSRM that mimics the native OSRM interface.
    
    This allows using a remote OSRM server (osrm-routed) instead of loading
    data locally. Useful for cloud deployments, shared infrastructure, or when
    you don't want to manage local .osrm files.
    
    Args:
        base_url: Base URL of the OSRM server (e.g., "http://localhost:5000" or 
                  "http://router.project-osrm.org")
        profile: Routing profile to use (default: "driving"). Common options are
                 "driving", "car", "bike", "foot", "walking"
        timeout: Request timeout in seconds (default: 30)
        session: Optional requests.Session object for connection pooling
        report_metadata: When True (default), the first routing request logs a
                 one-time summary of the server's /metadata (OSM data and profile
                 processing timestamps) at INFO level on the "osrm" logger. Set
                 False to disable. Note: enable INFO logging to see it, e.g.
                 logging.basicConfig(level=logging.INFO).

    Examples:
        >>> import logging, osrm
        >>> logging.basicConfig(level=logging.INFO)  # required to see metadata report
        >>>
        >>> # Connect to local OSRM server
        >>> client = osrm.OSRM_HTTP("http://localhost:5000")
        >>>
        >>> # Or use the public demo instance
        >>> client = osrm.OSRM_HTTP("http://router.project-osrm.org")
        >>>
        >>> # Inspect the server's data vintage on demand
        >>> client.Metadata()
        {'generated_at': '2026-05-18T22:07:35Z', 'profiles': {...}}
        >>>
        >>> # Same API as native OSRM; first request also logs the metadata once
        >>> result = client.Route([(7.41337, 43.72956), (7.41546, 43.73077)])
        >>> print(result["routes"][0]["distance"])
        >>>
        >>> # Works with bulk processing
        >>> import polars as pl
        >>> df = pl.DataFrame({
        ...     "origin_lon": [7.41337, 7.41862],
        ...     "origin_lat": [43.72956, 43.73216],
        ...     "dest_lon": [7.41546, 7.42000],
        ...     "dest_lat": [43.73077, 43.73300]
        ... })
        >>> results = osrm.bulk_route(client, df)
    """
    
    def __init__(
        self,
        base_url: str = "http://localhost:5000",
        profile: str = "driving",
        timeout: float = 30.0,
        session: Optional[Any] = None,
        report_metadata: bool = True,
        pool_connections: int = 16,
        pool_maxsize: int = 16,
    ):
        import requests
        from requests.adapters import HTTPAdapter
        self._requests = requests

        self.base_url = base_url.rstrip('/')
        self.profile = profile
        self.timeout = timeout

        # Metadata reporting state
        self.report_metadata = report_metadata
        self._metadata_cache: Optional[Dict[str, Any]] = None
        self._metadata_reported = False

        if session is not None:
            self.session = session
        else:
            self.session = requests.Session()
            # Increase connection pool for concurrent bulk_route usage
            adapter = HTTPAdapter(
                pool_connections=pool_connections,
                pool_maxsize=pool_maxsize,
            )
            self.session.mount('http://', adapter)
            self.session.mount('https://', adapter)
        
        # Verify server is accessible (OSRM returns 400/404 for root, that's fine)
        try:
            self.session.get(f"{self.base_url}/", timeout=5)
        except self._requests.exceptions.ConnectionError as e:
            raise ConnectionError(
                f"Failed to connect to OSRM server at {self.base_url}: {e}"
            )
    
    def _format_coordinates(self, coordinates: List[tuple]) -> str:
        """Format coordinates as lon,lat;lon,lat string."""
        return ';'.join([f"{lon},{lat}" for lon, lat in coordinates])
    
    def _format_bool_param(self, value: bool) -> str:
        """Format boolean as 'true' or 'false' string."""
        return 'true' if value else 'false'
    
    def _build_request(
        self,
        service: str,
        coordinates: List[tuple],
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Build HTTP request parameters."""
        coords_str = self._format_coordinates(coordinates)
        url = f"{self.base_url}/{service}/v1/{self.profile}/{coords_str}"
        
        # Convert parameters to query string format
        query_params = {}
        
        for key, value in params.items():
            if value is None:
                continue
            
            # Handle different parameter types
            if isinstance(value, bool):
                query_params[key] = self._format_bool_param(value)
            elif isinstance(value, list):
                # Lists are formatted as semicolon-separated values
                if key in ['radiuses', 'bearings', 'approaches']:
                    query_params[key] = ';'.join([str(v) if v is not None else '' for v in value])
                elif key == 'exclude':
                    query_params[key] = ','.join(value)
                elif key == 'sources' or key == 'destinations':
                    query_params[key] = ';'.join([str(v) for v in value])
                elif key == 'annotations':
                    # Annotations can be a list
                    query_params[key] = ','.join(value) if isinstance(value, list) else value
                else:
                    query_params[key] = str(value)
            elif key == 'geometries':
                # Map internal format to OSRM API format
                query_params[key] = value
            elif key == 'overview':
                query_params[key] = value
            elif key == 'annotations':
                query_params[key] = value if isinstance(value, str) else ','.join(value)
            else:
                query_params[key] = str(value)
        
        return {'url': url, 'params': query_params}
    
    def Metadata(self, refresh: bool = False) -> Dict[str, Any]:
        """Fetch server metadata (OSM data + profile processing timestamps).

        Hits the server's custom ``/metadata`` endpoint, which reports when the
        underlying OSM data was sourced and when each routing profile was
        processed. The result is cached on the client; pass ``refresh=True`` to
        force a re-fetch.

        Returns:
            Metadata dict, e.g.
            ``{"generated_at": ..., "profiles": {"car": {...}, ...}}``.

        Raises:
            RuntimeError: If the ``/metadata`` endpoint is unreachable or returns
                an error (e.g. the server does not implement it).
        """
        if self._metadata_cache is not None and not refresh:
            return self._metadata_cache
        try:
            response = self.session.get(f"{self.base_url}/metadata", timeout=self.timeout)
            response.raise_for_status()
            self._metadata_cache = response.json()
        except self._requests.exceptions.RequestException as e:
            raise RuntimeError(
                f"Failed to fetch metadata from {self.base_url}/metadata: {e}"
            )
        return self._metadata_cache

    @staticmethod
    def _format_metadata(meta: Dict[str, Any]) -> str:
        """Render metadata as a single human-readable log line."""
        generated = meta.get("generated_at", "unknown")
        parts = []
        for name, info in (meta.get("profiles") or {}).items():
            parts.append(
                f"{name}: osm_data={info.get('osm_data_timestamp', '?')}, "
                f"processed={info.get('processed_at', '?')}"
            )
        profiles = "; ".join(parts) if parts else "no profile info"
        return f"OSRM server metadata (generated {generated}): {profiles}"

    def _report_metadata_once(self) -> None:
        """Log the server metadata a single time per client (if enabled)."""
        if not self.report_metadata or self._metadata_reported:
            return
        self._metadata_reported = True  # set first: don't retry on failure / spam
        try:
            meta = self.Metadata()
        except RuntimeError:
            return  # metadata endpoint missing/unreachable must not break routing
        logger.info(self._format_metadata(meta))

    def _make_request(self, service: str, coordinates: List[tuple], **kwargs) -> Dict[str, Any]:
        """Make HTTP request to OSRM server."""
        self._report_metadata_once()
        request_data = self._build_request(service, coordinates, kwargs)
        
        try:
            response = self.session.get(
                request_data['url'],
                params=request_data['params'],
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()
            
            # Check for OSRM-specific errors
            if result.get('code') != 'Ok':
                raise RuntimeError(f"{result.get('code', 'Error')} - {result.get('message', 'Unknown error')}")
            
            return result
        
        except self._requests.exceptions.Timeout:
            raise TimeoutError(f"Request to OSRM server timed out after {self.timeout}s")
        except self._requests.exceptions.RequestException as e:
            raise RuntimeError(f"HTTP request failed: {e}")
    
    def Route(self, coordinates: Optional[List[tuple]] = None, **kwargs) -> Dict[str, Any]:
        """
        Calculate route between coordinates.
        
        See OSRM API documentation: http://project-osrm.org/docs/v5.24.0/api/#route-service
        
        Args:
            coordinates: List of (lon, lat) tuples
            steps: Return route steps (default: False)
            alternatives: Search for alternative routes (default: False)
            geometries: Geometry format: 'polyline', 'polyline6', 'geojson'
            overview: Overview detail: 'simplified', 'full', 'false'
            continue_straight: Force straight at waypoints
            annotations: Annotation types (list or string)
            Other OSRM route parameters...
        
        Returns:
            Route result as dict
        """
        if coordinates is None:
            raise ValueError("coordinates parameter is required")
        if len(coordinates) < 2:
            raise ValueError("At least 2 coordinates are required for routing")
        
        return self._make_request('route', coordinates, **kwargs)
    
    def Nearest(self, coordinates: Optional[List[tuple]] = None, **kwargs) -> Dict[str, Any]:
        """
        Find nearest road segment to coordinates.
        
        Args:
            coordinates: List of (lon, lat) tuples (typically just one)
            number: Number of nearest segments to return (default: 1)
            Other OSRM nearest parameters...
        
        Returns:
            Nearest result as dict
        """
        if coordinates is None:
            raise ValueError("coordinates parameter is required")
        
        return self._make_request('nearest', coordinates, **kwargs)
    
    def Match(self, coordinates: Optional[List[tuple]] = None, **kwargs) -> Dict[str, Any]:
        """
        Match GPS trace to road network.
        
        Args:
            coordinates: List of (lon, lat) tuples for GPS trace
            timestamps: Timestamps for each coordinate
            steps: Return route steps
            geometries: Geometry format
            overview: Overview detail
            annotations: Annotation types
            gaps: Gap handling: 'split' or 'ignore'
            tidy: Clean up trace
            Other OSRM match parameters...
        
        Returns:
            Match result as dict
        """
        if coordinates is None:
            raise ValueError("coordinates parameter is required")
        if len(coordinates) < 2:
            raise ValueError("At least 2 coordinates are required for matching")
        
        return self._make_request('match', coordinates, **kwargs)
    
    def Table(self, coordinates: Optional[List[tuple]] = None, **kwargs) -> Dict[str, Any]:
        """
        Compute distance/duration table between coordinates.
        
        Args:
            coordinates: List of (lon, lat) tuples
            sources: Indices of source coordinates
            destinations: Indices of destination coordinates
            annotations: 'duration', 'distance', or both
            Other OSRM table parameters...
        
        Returns:
            Table result as dict
        """
        if coordinates is None:
            raise ValueError("coordinates parameter is required")
        
        return self._make_request('table', coordinates, **kwargs)
    
    def Trip(self, coordinates: Optional[List[tuple]] = None, **kwargs) -> Dict[str, Any]:
        """
        Solve traveling salesman problem.
        
        Args:
            coordinates: List of (lon, lat) tuples
            roundtrip: Return to start point (default: True)
            source: Source constraint: 'any' or 'first'
            destination: Destination constraint: 'any' or 'last'
            steps: Return route steps
            geometries: Geometry format
            overview: Overview detail
            annotations: Annotation types
            Other OSRM trip parameters...
        
        Returns:
            Trip result as dict
        """
        if coordinates is None:
            raise ValueError("coordinates parameter is required")
        if len(coordinates) < 2:
            raise ValueError("At least 2 coordinates are required for trip")
        
        return self._make_request('trip', coordinates, **kwargs)
    
    def Tile(self, x: int, y: int, z: int) -> bytes:
        """
        Get vector tile data.
        
        Args:
            x: Tile X coordinate
            y: Tile Y coordinate
            z: Tile zoom level
        
        Returns:
            Tile data as bytes
        """
        self._report_metadata_once()
        url = f"{self.base_url}/tile/v1/{self.profile}/tile({x},{y},{z}).mvt"

        try:
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.content
        except self._requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to fetch tile: {e}")
    
    def __repr__(self) -> str:
        return f"OSRM_HTTP(base_url='{self.base_url}', profile='{self.profile}')"
