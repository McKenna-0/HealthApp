from functools import lru_cache

from ..config import settings
from .base import DataSource


@lru_cache(maxsize=1)
def get_data_source() -> DataSource:
    if settings.data_source == "garmin":
        from .garmin_source import GarminSource

        return GarminSource()
    from .mock_source import MockSource

    return MockSource()
