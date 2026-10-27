"""One-time reconstruction of the user's already-verified game archive.

Only GitHub blob contents are downloaded. The archive is never extracted or run.
The final publication uses a regular fast-forward push to v1.0, never main.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request


REPOSITORY = "qqzj1071/Magicians-"
BRANCH_REF = "refs/heads/v1.0"
FILENAME = "Magicians-v1.0-Windows-x64.zip"
EXPECTED_SIZE = 84_795_845
EXPECTED_SHA256 = "9044bf02480964b6c67a29c738a3a2055a7d7adc66ccdc9188630f0128ae921e"
MAX_CHUNK_BYTES = 16 * 1024 * 1024
MAX_CHUNKS = 256
MANIFEST = Path("releases/windows-v1.0/upload-manifest.json")
OUTPUT = MANIFEST.parent / FILENAME
HELPERS = [MANIFEST, Path(".github/scripts/assemble-v1.0.py")]


def git(*arguments: str, capture: bool = False) -> str:
    result = subprocess.run(["git", *arguments], check=True, text=True,
                            stdout=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else ""


def read_manifest() -> dict:
    if MANIFEST.stat().st_size > 256 * 1024:
        raise ValueError("The upload manifest is unexpectedly large")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if (manifest.get("filename") != FILENAME or manifest.get("size") != EXPECTED_SIZE
            or manifest.get("sha256") != EXPECTED_SHA256):
        raise ValueError("Manifest does not identify the approved package")
    chunks = manifest.get("chunks")
    if not isinstance(chunks, list) or not 1 <= len(chunks) <= MAX_CHUNKS:
        raise ValueError("Manifest has an invalid chunk list")
    total = 0
    for chunk in chunks:
        if (not isinstance(chunk, dict) or not isinstance(chunk.get("sha"), str)
                or not re.fullmatch(r"[0-9a-f]{40}", chunk["sha"])
                or type(chunk.get("size")) is not int
                or not 0 < chunk["size"] <= MAX_CHUNK_BYTES):
            raise ValueError("Manifest has an invalid Git blob entry")
        total += chunk["size"]
    if total != EXPECTED_SIZE:
        raise ValueError("Manifest chunk sizes do not sum to the approved file size")
    return manifest


def fetch_blob(token: str, chunk: dict) -> bytes:
    url = f"https://api.github.com/repos/{REPOSITORY}/git/blobs/{chunk['sha']}"
    request = urllib.request.Request(url, headers={
        "User-Agent": "Magicians-v1.0-Assembly",
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    for attempt in range(3):
        try:
            # Base64 plus line wrapping and JSON metadata stay below this bound.
            limit = chunk["size"] * 3 // 2 + 64 * 1024
            with urllib.request.urlopen(request, timeout=45) as response:
                raw = response.read(limit + 1)
            if len(raw) > limit:
                raise ValueError("Blob response exceeds the approved chunk size")
            blob = json.loads(raw)
            if (blob.get("sha") != chunk["sha"] or blob.get("size") != chunk["size"]
                    or blob.get("encoding") != "base64" or not isinstance(blob.get("content"), str)):
                raise ValueError("GitHub blob metadata does not match the manifest")
            encoded = "".join(blob["content"].split())
            payload = base64.b64decode(encoded, validate=True)
            if len(payload) != chunk["size"]:
                raise ValueError("Decoded blob has the wrong size")
            git_digest = hashlib.sha1(b"blob " + str(len(payload)).encode("ascii") + b"\0" + payload).hexdigest()
            if git_digest != chunk["sha"]:
                raise ValueError("Decoded blob does not match its Git SHA")
            return payload
        except urllib.error.HTTPError as error:
            if attempt == 2 or error.code not in (429, 500, 502, 503, 504):
                raise RuntimeError(f"Blob download failed with HTTP {error.code}") from None
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise RuntimeError("Blob download failed after three network attempts") from None
        time.sleep(2 ** attempt)
    raise AssertionError("unreachable")


def main() -> None:
    if os.environ.get("GITHUB_REPOSITORY") != REPOSITORY or os.environ.get("GITHUB_REF") != BRANCH_REF:
        raise RuntimeError("This one-time publication is restricted to the approved repository and branch")
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise RuntimeError("The workflow token is not available")
    root = Path(git("rev-parse", "--show-toplevel", capture=True)).resolve()
    os.chdir(root)
    head = git("rev-parse", "HEAD", capture=True)
    for helper in HELPERS:
        if not helper.is_file() or helper.is_symlink():
            raise ValueError("A required one-time publication file is absent or is a symlink")
    if OUTPUT.exists():
        raise RuntimeError("A package already exists at the destination; refusing to replace it")
    manifest = read_manifest()
    descriptor, temporary = tempfile.mkstemp(prefix=".assemble-", suffix=".zip", dir=OUTPUT.parent)
    digest = hashlib.sha256()
    total = 0
    try:
        with os.fdopen(descriptor, "wb") as stream:
            for index, chunk in enumerate(manifest["chunks"], 1):
                payload = fetch_blob(token, chunk)
                stream.write(payload)
                digest.update(payload)
                total += len(payload)
                print(f"Verified chunk {index}/{len(manifest['chunks'])}", flush=True)
        if total != EXPECTED_SIZE or digest.hexdigest() != EXPECTED_SHA256:
            raise ValueError("Reconstructed archive does not match the approved size and SHA-256")
        # Do not silently include or overwrite a collaborator's concurrent work.
        git("fetch", "--no-tags", "--depth=1", "origin", BRANCH_REF)
        if git("rev-parse", "FETCH_HEAD", capture=True) != head:
            raise RuntimeError("The v1.0 branch changed during assembly; no commit or push was performed")
        Path(temporary).replace(OUTPUT)
        git("config", "user.name", "github-actions[bot]")
        git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")
        git("add", "--", OUTPUT.as_posix())
        git("rm", "--", *(path.as_posix() for path in HELPERS))
        changed = set(git("diff", "--cached", "--name-only", capture=True).splitlines())
        expected = {OUTPUT.as_posix(), *(path.as_posix() for path in HELPERS)}
        if changed != expected:
            raise RuntimeError("Unexpected staged files; publication was not committed")
        git("diff", "--cached", "--check")
        git("commit", "-m", "Publish verified v1.0 Windows portable game archive")
        # No --force: a concurrent remote update will be safely rejected.
        git("push", "origin", f"HEAD:{BRANCH_REF}")
        print(f"Published {FILENAME}: {EXPECTED_SIZE} bytes, SHA-256 {EXPECTED_SHA256}", flush=True)
    finally:
        Path(temporary).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
