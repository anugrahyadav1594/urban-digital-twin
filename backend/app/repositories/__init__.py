"""Data access layer. ARCHITECTURE §5.3 - queries only, no business logic."""
from .results_repo import ResultsRepository, ScenarioRepository
from .spatial_repo import SpatialRepository

__all__ = ["SpatialRepository", "ResultsRepository", "ScenarioRepository"]

# RegionRepository is re-exported for convenience, but a failure to import it
# must not take down the entire application. It is a newer module, so a tree
# where only part of a patch landed would otherwise fail at
# `from .region_repo import RegionRepository` and break every route, not just
# scoring. Consumers that need it import app.repositories.region_repo
# directly and get a clear error naming the real missing file.
try:
    from .region_repo import RegionRepository
except ImportError:                                          # pragma: no cover
    pass
else:
    __all__.append("RegionRepository")