"""Verify sdist/wheel component inventories and exact independently owned bytes."""

from pathlib import Path
import sys
import tarfile
import zipfile


def main():
    schema_dir, sdist, wheel = map(Path, sys.argv[1:])
    expected = {path.name: path.read_bytes() for path in schema_dir.glob("*.schema.json")}
    assert len(expected) == 7, sorted(expected)
    suffix = "config/job-components/schemas/"
    with tarfile.open(sdist) as archive:
        names = [entry.name for entry in archive.getmembers()
                 if entry.isfile() and suffix in entry.name]
        assert len(names) == len(expected), names
        actual = {name.split(suffix, 1)[1]: archive.extractfile(name).read() for name in names}
        assert actual == expected, "sdist schema inventory/content differs from checkout"
    with zipfile.ZipFile(wheel) as archive:
        names = [name for name in archive.namelist() if suffix in name and not name.endswith("/")]
        assert len(names) == len(expected), names
        actual = {name.split(suffix, 1)[1]: archive.read(name) for name in names}
        assert actual == expected, "wheel schema inventory/content differs from checkout"
    print("All seven independently owned component schemas match checkout bytes in sdist and wheel.")


if __name__ == "__main__":
    main()
