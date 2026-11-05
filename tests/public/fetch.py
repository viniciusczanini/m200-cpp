#!/usr/bin/env python3
"""Opt-in local fetch of pinned public originals. Never modifies their contents."""

import argparse
import hashlib
import json
import tempfile
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_CORPUS = HERE.parents[1] / "research/downloads/public-projects"


def verified_bytes(path, source):
    """Check both file identity and the GitHub blob identity before XML parsing."""
    path = Path(path)
    if path.stat().st_size != source["bytes"]:
        raise ValueError("original size mismatch: " + source["file"])
    data = path.read_bytes()
    blob = b"blob " + str(len(data)).encode("ascii") + b"\0" + data
    if hashlib.sha256(data).hexdigest() != source["sha256"]:
        raise ValueError("original SHA-256 mismatch: " + source["file"])
    if hashlib.sha1(blob).hexdigest() != source["git_blob"]:
        raise ValueError("original Git blob mismatch: " + source["file"])
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--manifest", type=Path, default=HERE / "manifest.json")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    args.corpus.mkdir(parents=True, exist_ok=True)
    for source in manifest["sources"]:
        destination = args.corpus / source["file"]
        if destination.exists():
            verified_bytes(destination, source)
            print("verified existing " + source["file"], flush=True)
            continue
        with urllib.request.urlopen(source["raw_url"], timeout=30) as response:
            data = response.read(source["bytes"] + 1)
        # Verify the temporary file before publishing an immutable original name.
        with tempfile.NamedTemporaryFile(dir=args.corpus, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(data)
        try:
            verified_bytes(temporary, source)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
        print("downloaded and verified " + source["file"], flush=True)


if __name__ == "__main__":
    main()
