from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from scripts.verify_geoid_reference_artifact import (
    ReferenceArtifactError,
    verify_and_extract,
)


def write_artifact(path: Path, rows: list[str]) -> None:
    with gzip.open(path, "wt", encoding="ascii", newline="") as stream:
        stream.write("# synthetic test fixture; not geoid reference data\n")
        stream.write("\n".join(rows) + "\n")


def test_verifier_checks_digest_and_extracts_stable_model_column(tmp_path):
    artifact = tmp_path / "small.gz"
    write_artifact(
        artifact,
        [
            "0 0 1.0 2.0 3.0",
            "10 20 4.0 5.0 6.0",
            "-10 30 7.0 8.0 9.0",
        ],
    )
    import hashlib

    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    result = verify_and_extract(
        artifact,
        expected_sha256=digest,
        expected_rows=3,
        sample_rows=(0, 2),
        model="EGM96",
    )
    assert result["verified_row_count"] == 3
    assert result["model_column"] == "EGM96"
    assert result["samples"]["0"]["geoid_height_m"] == 2.0
    assert result["samples"]["2"]["latitude_degrees"] == -10.0


def test_verifier_rejects_digest_mismatch_before_parsing(tmp_path):
    artifact = tmp_path / "small.gz"
    write_artifact(artifact, ["0 0 1 2 3"])
    with pytest.raises(ReferenceArtifactError, match="SHA-256 mismatch"):
        verify_and_extract(
            artifact,
            expected_sha256="0" * 64,
            expected_rows=1,
            sample_rows=(0,),
        )


def test_verifier_rejects_wrong_column_count(tmp_path):
    artifact = tmp_path / "small.gz"
    write_artifact(artifact, ["0 0 1 2"])
    import hashlib

    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    with pytest.raises(ReferenceArtifactError, match="expected 5"):
        verify_and_extract(
            artifact,
            expected_sha256=digest,
            expected_rows=1,
            sample_rows=(0,),
        )


def test_verifier_rejects_row_count_mismatch(tmp_path):
    artifact = tmp_path / "small.gz"
    write_artifact(artifact, ["0 0 1 2 3"])
    import hashlib

    digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
    with pytest.raises(ReferenceArtifactError, match="row count mismatch"):
        verify_and_extract(
            artifact,
            expected_sha256=digest,
            expected_rows=2,
            sample_rows=(0,),
        )
