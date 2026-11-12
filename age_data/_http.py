"""Use the central retry and cache-revalidation policy for all age-data requests."""

from europe_data._http import get_json

__all__ = ["get_json"]
