"""Asset lookup for the importer; runs without the source document."""

from pathlib import Path

import pytest

from app.importer.run import media_index, resolve_asset


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


def test_images_are_found_in_sub_folders_by_name(tmp_path: Path):
    nested = tmp_path / "media" / "sefiller"
    nested.mkdir(parents=True)
    (nested / "sefillerpic1.svg").write_bytes(b"a")
    (tmp_path / "media" / "logo").mkdir()
    (tmp_path / "media" / "logo" / "baysahnelogo1.png").write_bytes(b"b")
    (tmp_path / "notes.txt").write_text("not an image")

    assert resolve_asset(tmp_path, "sefillerpic1.svg") == nested / "sefillerpic1.svg"
    assert resolve_asset(tmp_path, "baysahnelogo1.svg") == tmp_path / "media" / "logo" / "baysahnelogo1.png"
    assert set(media_index(tmp_path)) == {"sefillerpic1.svg", "baysahnelogo1.png"}


def test_two_images_with_the_same_name_are_refused(tmp_path: Path):
    for folder in ("antigone", "sefiller"):
        (tmp_path / folder).mkdir()
        (tmp_path / folder / "pic1.svg").write_bytes(b"x")
    with pytest.raises(ValueError, match="pic1.svg"):
        media_index(tmp_path)
