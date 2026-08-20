"""Reference cities for benchmarking. Product report §2.

The report fixes the pairings:

    Adivali / NAINA  -> Chandigarh  (planning benchmark)
    JNPT / Navi Mumbai -> Rotterdam (infrastructure and logistics benchmark)

Two sources of benchmark values are supported, in order of preference:

  1. MEASURED. If the region's tables are populated, the same scoring engine
     runs over the benchmark city, so both sides of the comparison are
     computed identically. This is the honest comparison.

  2. PUBLISHED. If the benchmark has no extracted data, these documented
     reference values are used instead and the result is flagged
     `benchmarkSource: "published"` so nobody mistakes it for a measurement.

Published values are order-of-magnitude planning figures for the reference
sectors, not survey data; they exist so the UI degrades gracefully rather
than showing an empty comparison.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Benchmark:
    key: str
    label: str
    rationale: str
    # dimension key -> raw value in that dimension's unit
    published: dict[str, float]


BENCHMARKS: dict[str, Benchmark] = {
    "chandigarh": Benchmark(
        key="chandigarh",
        label="Chandigarh (Sector 17)",
        rationale="Planning benchmark: organised sector grid, designed "
                  "walkable accessibility and distributed public amenities.",
        published={
            "mobility": 11.5,
            "facility_access": 88.0,
            "healthcare": 1.6,
            "education": 0.9,
            "green_space": 15.0,
            "recreation": 4.2,
            "landuse": 0.86,
            "infrastructure": 92.0,
            "resilience": 74.0,
            "constraints": 88.0,
        },
    ),
    "rotterdam": Benchmark(
        key="rotterdam",
        label="Rotterdam",
        rationale="Infrastructure and logistics benchmark: modern port "
                  "systems, multimodal mobility and resilient water "
                  "management.",
        published={
            "mobility": 13.2,
            "facility_access": 92.0,
            "healthcare": 1.8,
            "education": 0.95,
            "green_space": 12.0,
            "recreation": 5.4,
            "landuse": 0.82,
            "infrastructure": 96.0,
            "resilience": 88.0,
            "constraints": 71.0,
        },
    ),
}

# Which benchmark each study area is judged against (report §2).
PAIRING: dict[str, str] = {
    "adivali_devad": "chandigarh",
    "jnpt_port": "rotterdam",
    # A benchmark compared with itself is meaningless, so pair the two
    # references with each other for symmetry.
    "chandigarh": "rotterdam",
    "rotterdam": "chandigarh",
}


def benchmark_for(region: str) -> Benchmark | None:
    """The reference city for a study area, or None if unpaired."""
    key = PAIRING.get((region or "").lower().strip())
    return BENCHMARKS.get(key) if key else None


def reference_values(region: str) -> dict[str, float]:
    """Published raw values for the benchmark paired with `region`."""
    b = benchmark_for(region)
    return dict(b.published) if b else {}


def describe(region: str) -> dict[str, Any]:
    b = benchmark_for(region)
    if not b:
        return {"key": None, "label": None, "rationale": None}
    return {"key": b.key, "label": b.label, "rationale": b.rationale}