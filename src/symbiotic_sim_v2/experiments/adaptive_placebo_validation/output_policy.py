"""Deterministic yoke mapping and RMSSD-independent random light output."""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from symbiotic_sim_v2.digital_life.config import digital_life_config_for_role
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.job import sha256_canonical
from symbiotic_sim_v2.garden.light_mapper.config import GardenLightMapperConfig
from symbiotic_sim_v2.garden.light_mapper.mapping import map_active_b_to_light

from .config import RANDOM_OUTPUT_VERSION, YOKE_MAPPING_VERSION, ValidationParticipant

LIFE_ROLES = ("red", "green", "blue")
LIFE_IDS = tuple(digital_life_config_for_role(role).digital_life_id for role in LIFE_ROLES)


def _hash_bytes(*parts: object) -> bytes:
    return hashlib.sha256(":".join(str(part) for part in parts).encode("utf-8")).digest()


def _hash01(*parts: object) -> float:
    return int.from_bytes(_hash_bytes(*parts)[:8], "big") / float(1 << 64)


def _uint32(*parts: object) -> int:
    return int.from_bytes(_hash_bytes(*parts)[:4], "big", signed=False)


@dataclass(frozen=True, slots=True)
class YokeAssignment:
    target_participant_id: str
    donor_participant_id: str
    user_type_id: str
    hidden_donor: bool
    version: str = YOKE_MAPPING_VERSION

    def __post_init__(self) -> None:
        for name in (
            "target_participant_id",
            "donor_participant_id",
            "user_type_id",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string")
        if self.target_participant_id == self.donor_participant_id:
            raise ValueError("yoked donor must differ from target")
        if not isinstance(self.hidden_donor, bool):
            raise TypeError("hidden_donor must be boolean")
        if self.version != YOKE_MAPPING_VERSION:
            raise ValueError(f"version must be {YOKE_MAPPING_VERSION}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def cyclic_yoke_map(
    participants: Sequence[ValidationParticipant],
) -> tuple[YokeAssignment, ...]:
    values = tuple(sorted(participants, key=lambda item: item.participant_id))
    if not values:
        raise ValueError("cyclic yoke mapping requires at least one participant")
    if len({item.user_type_id for item in values}) != 1:
        raise ValueError("cyclic yoke mapping is scoped to exactly one user type")
    if len(values) == 1:
        target = values[0]
        return (
            YokeAssignment(
                target_participant_id=target.participant_id,
                donor_participant_id=f"{target.participant_id}__hidden_donor",
                user_type_id=target.user_type_id,
                hidden_donor=True,
            ),
        )
    return tuple(
        YokeAssignment(
            target_participant_id=target.participant_id,
            donor_participant_id=values[(index + 1) % len(values)].participant_id,
            user_type_id=target.user_type_id,
            hidden_donor=False,
        )
        for index, target in enumerate(values)
    )


@dataclass(frozen=True, slots=True)
class RandomBundleOutput:
    participant_id: str
    session_index: int
    bundle_index: int
    displayed_life_id: str
    displayed_role: str
    b: tuple[float, float, float, float]
    hue_degree: float
    blink_bpm: float
    output_seed: int
    version: str = RANDOM_OUTPUT_VERSION

    def __post_init__(self) -> None:
        if self.displayed_role not in LIFE_ROLES:
            raise ValueError("displayed_role must be red, green, or blue")
        if self.displayed_life_id != digital_life_config_for_role(
            self.displayed_role
        ).digital_life_id:
            raise ValueError("displayed life ID and role differ")
        if len(self.b) != 4 or any(
            not math.isfinite(value) or not 0.0 <= value <= 1.0 for value in self.b
        ):
            raise ValueError("random B must contain four finite unit axes")
        if not 0.0 <= self.hue_degree <= 360.0:
            raise ValueError("random Hue is outside [0,360]")
        if not 10.0 <= self.blink_bpm <= 165.0:
            raise ValueError("random BPM is outside [10,165]")
        if self.version != RANDOM_OUTPUT_VERSION:
            raise ValueError(f"version must be {RANDOM_OUTPUT_VERSION}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def deterministic_random_session_outputs(
    *,
    validation_master_seed: int,
    participant_id: str,
    session_index: int,
) -> tuple[RandomBundleOutput, RandomBundleOutput, RandomBundleOutput]:
    """Create one holder and three B values without physiology or condition inputs."""

    holder_u = _hash01(
        validation_master_seed,
        participant_id,
        session_index,
        "random-output",
        "holder",
    )
    role = LIFE_ROLES[min(int(holder_u * len(LIFE_ROLES)), len(LIFE_ROLES) - 1)]
    life_config = digital_life_config_for_role(role)
    mapper = GardenLightMapperConfig()
    outputs: list[RandomBundleOutput] = []
    for bundle_index in range(3):
        key = (
            validation_master_seed,
            participant_id,
            session_index,
            bundle_index,
            "random-output",
        )
        f = life_config.f_min + (life_config.f_max - life_config.f_min) * _hash01(
            *key, "hue"
        )
        t = _hash01(*key, "bpm")
        b = (f, life_config.a_fixed, t, life_config.d_fixed)
        mapped = map_active_b_to_light(b, mapper)
        assert mapped.hue_degree is not None
        assert mapped.blink_bpm is not None
        outputs.append(
            RandomBundleOutput(
                participant_id=participant_id,
                session_index=session_index,
                bundle_index=bundle_index,
                displayed_life_id=life_config.digital_life_id,
                displayed_role=role,
                b=b,
                hue_degree=mapped.hue_degree,
                blink_bpm=mapped.blink_bpm,
                output_seed=_uint32(*key, "seed"),
            )
        )
    return tuple(outputs)  # type: ignore[return-value]


def output_sequence_checksum(values: Sequence[Mapping[str, Any] | Any]) -> str:
    payload = [value.to_dict() if hasattr(value, "to_dict") else dict(value) for value in values]
    return sha256_canonical(payload)


__all__ = [
    "LIFE_IDS",
    "LIFE_ROLES",
    "RandomBundleOutput",
    "YokeAssignment",
    "cyclic_yoke_map",
    "deterministic_random_session_outputs",
    "output_sequence_checksum",
]
