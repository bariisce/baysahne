"""Asset lookup for the importer; runs without the source document."""

from pathlib import Path

from app.importer.run import resolve_asset


def test_exact_name_is_preferred(tmp_path: Path):
    (tmp_path / "poster.svg").write_bytes(b"a")
    (tmp_path / "poster.jpg").write_bytes(b"b")
    assert resolve_asset(tmp_path, "poster.svg") == tmp_path / "poster.svg"


def test_file_renamed_to_its_real_extension_is_found(tmp_path: Path):
    (tmp_path / "bygrbaysahne.jpeg").write_bytes(b"x")
    assert resolve_asset(tmp_path, "bygrbaysahne.svg") == tmp_path / "bygrbaysahne.jpeg"


def test_absent_file_is_reported_missing(tmp_path: Path):
    (tmp_path / "other.jpg").write_bytes(b"x")
    assert resolve_asset(tmp_path, "r&jpic2.svg") is None
