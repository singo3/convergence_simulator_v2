"""Independent fixed-vector tests for normative Stage 5A Hash01."""

from __future__ import annotations

import ast
import dataclasses
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from symbiotic_sim_v2.digital_life.config import digital_life_config_for_role
from symbiotic_sim_v2.digital_life.hash01 import HASH01_DENOMINATOR, hash01
from symbiotic_sim_v2.digital_life.intrinsic import derive_intrinsic_profile

PROJECT_ROOT = Path(__file__).parents[2]
VECTOR_PATH = PROJECT_ROOT / "docs" / "conformance" / "stage-05a-reference-vectors.json"
GENERATOR_PATH = PROJECT_ROOT / "tools" / "generate_stage_05a_reference_vectors.py"


def reference_vectors() -> dict[str, Any]:
    return json.loads(VECTOR_PATH.read_text(encoding="utf-8"))


def test_committed_vectors_are_exactly_reproduced_by_the_independent_generator() -> None:
    completed = subprocess.run(
        [sys.executable, str(GENERATOR_PATH), "--stdout"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stderr == ""
    assert completed.stdout == VECTOR_PATH.read_text(encoding="utf-8")


def test_reference_generator_has_no_product_import_or_dynamic_import() -> None:
    source = GENERATOR_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )

    assert "symbiotic_sim_v2" not in source
    assert all(not name.startswith("symbiotic_sim_v2") for name in imported_modules)
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "__import__"
        for node in ast.walk(tree)
    )


def test_fixed_hash_vectors_cover_colon_join_utf8_sha256_u48_and_denominator() -> None:
    vectors = reference_vectors()["normative_vectors"]["hash01"]
    by_name = {item["name"]: item for item in vectors["vectors"]}
    red = by_name["red_handle_distance"]
    unicode_vector = by_name["unicode_colon_join"]

    assert vectors["denominator"] == HASH01_DENOMINATOR == 281_474_976_710_655
    assert red["joined_text"] == "life-red:handle-distance"
    assert red["utf8_hex"] == "6c6966652d7265643a68616e646c652d64697374616e6365"
    assert red["sha256_hex"] == (
        "d05908577cfa520a098b6d24d35114ec31455585a8be3d160f0b50aa1d614775"
    )
    assert red["prefix48_hex"] == "d05908577cfa"
    assert red["numerator"] == 229_080_810_618_106
    assert unicode_vector["joined_text"] == "生命:赤:距離"
    assert unicode_vector["utf8_hex"] == "e7949fe591bd3ae8b5a43ae8b79de99ba2"
    assert unicode_vector["sha256_hex"] == (
        "e1cef9f3401f29be96b940ac8b42239b578db3879d39034e1aa47f39b2eddfc9"
    )
    assert unicode_vector["numerator"] == 248_279_072_981_023


def test_product_hash01_matches_every_fixed_binary64_vector_exactly() -> None:
    vectors = reference_vectors()["normative_vectors"]["hash01"]["vectors"]

    for vector in vectors:
        actual = hash01(*vector["parts"])
        assert actual == vector["expected"], vector["name"]
        assert actual.hex() == vector["expected_binary64_hex"], vector["name"]
        assert 0.0 <= actual <= 1.0


def test_hash01_changes_when_argument_value_or_position_changes() -> None:
    canonical = hash01("life-green", "handle-distance")

    assert hash01("life-blue", "handle-distance") != canonical
    assert hash01("life-green", "birth-phase") != canonical
    assert hash01("handle-distance", "life-green") != canonical
    assert hash01("life-green:handle-distance") == canonical


def test_hash01_rejects_an_empty_argument_list() -> None:
    with pytest.raises(ValueError, match="at least one"):
        hash01()


def test_product_hash01_source_never_calls_python_builtin_hash() -> None:
    module = importlib.import_module("symbiotic_sim_v2.digital_life.hash01")
    source = Path(module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "hash"
        for node in ast.walk(tree)
    )


def test_hash01_is_process_independent_across_python_hash_seeds() -> None:
    code = (
        "from symbiotic_sim_v2.digital_life.hash01 import hash01;"
        "print(hash01('life-green','handle-distance').hex())"
    )
    outputs = []
    for seed in ("0", "1", "8675309", "random"):
        environment = dict(os.environ)
        environment["PYTHONHASHSEED"] = seed
        completed = subprocess.run(
            [sys.executable, "-c", code],
            check=True,
            capture_output=True,
            text=True,
            env=environment,
            cwd=PROJECT_ROOT,
        )
        assert completed.stderr == ""
        outputs.append(completed.stdout.strip())

    assert outputs == ["0x1.8e9768d022c99p-3"] * 4


@pytest.mark.parametrize("role", ("red", "green", "blue"))
def test_intrinsic_p_and_birth_phase_match_fixed_id_vectors(role: str) -> None:
    normative = reference_vectors()["normative_vectors"]
    expected_p = next(item for item in normative["p_intrinsic"] if item["role"] == role)
    expected_birth = next(item for item in normative["birth_phase"] if item["role"] == role)

    profile = derive_intrinsic_profile(digital_life_config_for_role(role))

    assert profile.p_intrinsic == expected_p["expected"]
    assert profile.p_intrinsic.hex() == expected_p["expected_binary64_hex"]
    assert 0.35 <= profile.p_intrinsic <= 0.65
    assert profile.birth_phase == expected_birth["expected"]
    assert profile.birth_phase.hex() == expected_birth["expected_binary64_hex"]
    assert 0.0 <= profile.birth_phase <= 0.000001


def test_intrinsic_p_depends_on_id_not_role_and_is_repeatable() -> None:
    red = digital_life_config_for_role("red")
    same_id_as_green = dataclasses.replace(red, digital_life_id="life-green")
    green = digital_life_config_for_role("green")

    first = derive_intrinsic_profile(same_id_as_green)
    second = derive_intrinsic_profile(same_id_as_green)

    assert first.p_intrinsic == derive_intrinsic_profile(green).p_intrinsic
    assert first.birth_phase == derive_intrinsic_profile(green).birth_phase
    assert first == second
