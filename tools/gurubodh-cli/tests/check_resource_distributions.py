"""Verify that every runtime-owned JSON/script resource ships unchanged."""

from pathlib import Path, PurePosixPath
import sys
import tarfile
import zipfile


def expected_resources(cli_root: Path) -> dict[str, bytes]:
    paths = [
        *sorted((cli_root / "config/jobs").glob("*.schema.json")),
        *sorted((cli_root / "config/artifacts").glob("*.schema.json")),
        *sorted((cli_root / "config/policies").glob("*.json")),
        *sorted((cli_root / "config/job-components").rglob("*.json")),
        cli_root / "scripts/legacy_font_convert.js",
        *sorted((cli_root / "scripts/vendor").glob("*.js")),
    ]
    return {
        path.relative_to(cli_root).as_posix(): path.read_bytes() for path in paths
    }


def archive_matches(name: str, relative: str) -> bool:
    parts = PurePosixPath(name).parts
    expected = PurePosixPath(relative).parts
    return parts[-len(expected) :] == expected


def main():
    cli_root, sdist, wheel = map(Path, sys.argv[1:])
    expected = expected_resources(cli_root)
    assert "scripts/vendor/hindietools_aps_prakash_to_unicode.js" in expected

    with tarfile.open(sdist) as archive:
        files = [entry for entry in archive.getmembers() if entry.isfile()]
        for relative, content in expected.items():
            matches = [entry for entry in files if archive_matches(entry.name, relative)]
            assert len(matches) == 1, (relative, [entry.name for entry in matches])
            assert archive.extractfile(matches[0]).read() == content, relative

    with zipfile.ZipFile(wheel) as archive:
        files = [name for name in archive.namelist() if not name.endswith("/")]
        for relative, content in expected.items():
            matches = [name for name in files if archive_matches(name, relative)]
            assert len(matches) == 1, (relative, matches)
            assert archive.read(matches[0]) == content, relative

    print(f"All {len(expected)} runtime-owned resources match checkout bytes in sdist and wheel.")


if __name__ == "__main__":
    main()
