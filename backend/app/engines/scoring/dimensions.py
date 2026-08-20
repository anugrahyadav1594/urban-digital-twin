"""The ten scoring dimensions. Product report §2.

The report is explicit that "the exact weights and scoring formula should
remain configurable until the final scoring framework is approved". So the
dimensions are declared as data here and aggregated through the existing
MCDA ScoringProfile, exactly like site suitability. Changing planning
priorities is a profile edit, never a code change.

Each dimension declares how its raw measurement maps onto 0..100:

    floor    the raw value scoring 0
    target   the raw value scoring 100
    direction 'benefit' (higher raw is better) or 'cost' (lower is better)

Values between floor and target interpolate linearly; values outside clamp.
The floor/target pairs are policy assumptions, not measurements, so they are
surfaced in the API response and in Provenance.assumptions rather than being
buried in the code.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from ..planning.mcda import Criterion, ScoringProfile

Direction = Literal["benefit", "cost"]

PROFILE_VERSION = "city-score-1.0.0"


@dataclass(frozen=True)
class Dimension:
    """One measurable axis of urban development quality."""

    key: str
    label: str
    unit: str
    floor: float
    target: float
    direction: Direction = "benefit"
    weight: float = 1.0
    description: str = ""
    # Which repository layers must be non-empty for this to be measurable.
    requires: tuple[str, ...] = ()

    def normalise(self, raw: float | None) -> float | None:
        """Map a raw measurement onto 0..100, or None when unmeasurable."""
        if raw is None:
            return None
        lo, hi = self.floor, self.target
        if hi == lo:
            return 100.0 if self.direction == "benefit" else 0.0
        frac = (raw - lo) / (hi - lo)
        pct = frac * 100.0
        return max(0.0, min(100.0, pct))


@dataclass
class DimensionScore:
    """Scored dimension, retaining the raw value so the UI can explain it."""

    key: str
    label: str
    unit: str
    raw: float | None
    score: float | None
    weight: float
    measurable: bool
    note: str = ""
    contribution: float = 0.0
    benchmark_raw: float | None = None
    benchmark_score: float | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "unit": self.unit,
            "raw": self.raw,
            "score": self.score,
            "weight": self.weight,
            "measurable": self.measurable,
            "note": self.note,
            "contribution": self.contribution,
            "benchmarkRaw": self.benchmark_raw,
            "benchmarkScore": self.benchmark_score,
            "gap": (None if self.score is None or self.benchmark_score is None
                    else round(self.benchmark_score - self.score, 1)),
            "evidence": self.evidence,
        }


# ---------------------------------------------------------------------------
# The ten dimensions of the report, in its order.
#
# Floors and targets are calibrated against widely used planning norms
# (UDPFI / URDPFI service-level benchmarks, WHO green-space guidance) so the
# numbers mean something outside this codebase. They remain overridable.
# ---------------------------------------------------------------------------

DIMENSIONS: tuple[Dimension, ...] = (
    Dimension(
        key="mobility",
        label="Mobility & connectivity",
        unit="km/km²",
        floor=2.0, target=12.0, weight=1.2,
        description="Road network density. Denser networks give shorter, "
                    "more redundant journeys.",
        requires=("roads",),
    ),
    Dimension(
        key="facility_access",
        label="Public facility accessibility",
        unit="% within 15 min",
        floor=20.0, target=95.0, weight=1.2,
        description="Share of residents within a 15-minute network journey of "
                    "any public facility.",
        requires=("roads", "facilities", "population_zones"),
    ),
    Dimension(
        key="healthcare",
        label="Healthcare & emergency coverage",
        unit="beds-equivalent/1000",
        floor=0.0, target=2.0, weight=1.3,
        description="Healthcare facility provision per 1,000 residents.",
        requires=("facilities", "population_zones"),
    ),
    Dimension(
        key="education",
        label="Education coverage",
        unit="schools/1000",
        floor=0.0, target=1.0, weight=1.0,
        description="School provision per 1,000 residents.",
        requires=("facilities", "population_zones"),
    ),
    Dimension(
        key="green_space",
        label="Green / open space",
        unit="m²/person",
        floor=0.0, target=9.0, weight=1.0,
        description="Open space per resident. WHO recommends a minimum of "
                    "9 m² per person.",
        requires=("parcels", "population_zones"),
    ),
    Dimension(
        key="recreation",
        label="Recreation & public amenities",
        unit="per 10k people",
        floor=0.0, target=5.0, weight=0.8,
        description="Higher-order amenities: sports, community and cultural "
                    "facilities.",
        requires=("facilities", "population_zones"),
    ),
    Dimension(
        key="landuse",
        label="Land-use efficiency & structure",
        unit="index",
        floor=0.0, target=1.0, weight=0.9,
        description="Mix and structural regularity of the land-use pattern.",
        requires=("parcels",),
    ),
    Dimension(
        key="infrastructure",
        label="Infrastructure readiness",
        unit="% serviced",
        floor=0.0, target=100.0, weight=1.0,
        description="Share of developed land with road frontage and "
                    "utility access.",
        requires=("parcels", "roads"),
    ),
    Dimension(
        key="resilience",
        label="Disaster resilience & emergency routing",
        unit="index",
        floor=0.0, target=100.0, weight=1.3,
        description="Network redundancy and emergency reach under "
                    "disruption.",
        requires=("roads", "facilities"),
    ),
    Dimension(
        key="constraints",
        label="Environmental & development constraints",
        unit="% unconstrained",
        floor=0.0, target=100.0, weight=0.8,
        description="Share of land free of flood, slope and protection "
                    "constraints.",
        requires=("parcels",),
    ),
)

_BY_KEY = {d.key: d for d in DIMENSIONS}


def dimension_by_key(key: str) -> Dimension | None:
    return _BY_KEY.get(key)


def _profile() -> ScoringProfile:
    """Express the dimensions as an MCDA profile.

    Every dimension is normalised to 0..100 before aggregation, so all
    criteria are 'benefit' at this point regardless of their raw direction.
    """
    return ScoringProfile(
        name="city-development-score",
        version=PROFILE_VERSION,
        criteria=tuple(
            Criterion(name=d.key, weight=d.weight, direction="benefit",
                      unit=d.unit, floor=0.0, ceiling=100.0)
            for d in DIMENSIONS
        ),
        aggregation="weighted_sum",
        normalization="minmax",
    )


DEFAULT_SCORING_PROFILE = _profile()


def profile_from_weights(weights: dict[str, float] | None) -> ScoringProfile:
    """Rebuild the profile with caller-supplied weights (report §2).

    Unknown keys are ignored; omitted dimensions keep their default weight.
    """
    if not weights:
        return DEFAULT_SCORING_PROFILE
    return ScoringProfile(
        name="city-development-score",
        version=f"{PROFILE_VERSION}+custom",
        criteria=tuple(
            Criterion(name=d.key,
                      weight=float(weights.get(d.key, d.weight)),
                      direction="benefit", unit=d.unit,
                      floor=0.0, ceiling=100.0)
            for d in DIMENSIONS
        ),
        aggregation="weighted_sum",
        normalization="minmax",
    )