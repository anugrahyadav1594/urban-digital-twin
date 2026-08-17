"""Planning / site suitability engine. ARCHITECTURE §14."""
from .mcda import (
    Criterion,
    ScoringProfile,
    normalize,
    score_candidates,
    DEFAULT_PROFILES,
)
from .filters import SiteRequirements, hard_filter
from .candidates import Candidate, generate_candidates
from .ranking import rank_candidates, site_suitability
from .road_design import validate_alignment, road_from_alignment

__all__ = [
    "Criterion", "ScoringProfile", "normalize", "score_candidates",
    "DEFAULT_PROFILES", "SiteRequirements", "hard_filter",
    "Candidate", "generate_candidates", "rank_candidates", "site_suitability",
    "validate_alignment", "road_from_alignment",
]
