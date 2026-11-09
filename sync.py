#!/usr/bin/env python3
"""Import configured Forgejo release APKs, then sign and publish an F-Droid index."""

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.request


SOURCE = Path(__file__).resolve().parent
WORK = Path("/var/lib/serrebifdroid/repository")
PUBLIC = Path("/var/www/serrebifdroid/fdroid/repo")
FORGEJO_API = "https://git.serrebiradio.com/api/v1"
FORGEJO_WEB = "https://git.serrebiradio.com"


def run(*args):
    return subprocess.run(args, check=True, text=True, stdout=subprocess.PIPE).stdout


def select_asset(release, app):
    if release.get("draft") or release.get("prerelease"):
        raise ValueError("Only stable, published releases may be imported")
    assets = [asset for asset in release["assets"]
              if re.fullmatch(app["asset_pattern"], asset["name"])]
    if len(assets) != 1:
        raise ValueError(f"Expected one matching APK, found {len(assets)}")
    return assets[0]


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def sidecar_asset(release, asset):
    """Return the "<apk>.sha256" sidecar asset, if the release carries one."""
    target = asset["name"] + ".sha256"
    for candidate in release.get("assets", []):
        if candidate["name"] == target:
            return candidate
    return None


def parse_sha256_sidecar(data: bytes):
    match = re.search(rb"\b[0-9a-f]{64}\b", data)
    if not match:
        raise ValueError("Release SHA-256 sidecar is malformed")
    return match.group(0).decode("ascii")


def verify_download(path, asset, expected_sha256=None):
    # Forgejo assets carry no digest field, so the caller passes the SHA-256
    # parsed from a ".sha256" sidecar asset when the release provides one.
    # A digest embedded in the asset itself is still honoured when present.
    if expected_sha256 is None:
        digest = asset.get("digest", "") or ""
        if re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
            expected_sha256 = digest[len("sha256:"):]
    if path.stat().st_size != asset["size"]:
        raise ValueError("APK size does not match the release asset")
    if expected_sha256 is not None and sha256(path) != expected_sha256:
        raise ValueError("APK SHA-256 does not match the release asset")


def inspect_apk(path, app):
    certificate = run("apksigner", "verify", "--print-certs", str(path))
    signers = re.findall(r"Signer #\d+ certificate SHA-256 digest: ([0-9a-f]{64})", certificate)
    if signers != [app["signer_sha256"]]:
        raise ValueError("APK signing certificate changed; refusing import")
    badging = run("aapt", "dump", "badging", str(path))
    package = re.search(r"^package: name='([^']+)' versionCode='(\d+)'", badging)
    if not package or package[1] != app["package"]:
        raise ValueError("APK package does not match configured application")
    return int(package[2])


def store_apk(incoming, destination, retired=None):
    for previous in (destination, retired):
        if previous is not None and previous.exists() and sha256(incoming) != sha256(previous):
            raise ValueError(f"Refusing to replace published APK: {destination.name}")
    if not destination.exists():
        incoming.chmod(0o644)
        incoming.replace(destination)


def retire_unlisted(work, allowed):
    for metadata in work.joinpath("metadata").glob("*.yml"):
        if metadata.stem not in allowed:
            metadata.unlink()
    for apk in work.joinpath("repo").glob("*.apk"):
        if apk.stem.rsplit("_", 1)[0] not in allowed:
            retired = work / "retired"
            retired.mkdir(exist_ok=True)
            store_apk(apk, retired / apk.name)
            apk.unlink(missing_ok=True)


def fetch(url):
    if not url.startswith("https://"):
        raise ValueError("HTTPS is required")
    request = urllib.request.Request(url, headers={"User-Agent": "SerrebiFdroid/1.0"})
    return urllib.request.urlopen(request, timeout=120)


def import_app(app):
    with fetch(f"{FORGEJO_API}/repos/{app['forgejo']}/releases/latest") as response:
        release = json.load(response)
    asset = select_asset(release, app)
    expected_prefix = f"{FORGEJO_WEB}/{app['forgejo']}/releases/download/"
    if not asset["browser_download_url"].startswith(expected_prefix):
        raise ValueError("APK download URL does not belong to configured repository")
    expected_sha256 = None
    sidecar = sidecar_asset(release, asset)
    if sidecar is not None:
        if not sidecar["browser_download_url"].startswith(expected_prefix):
            raise ValueError("Checksum download URL does not belong to configured repository")
        with fetch(sidecar["browser_download_url"]) as response:
            expected_sha256 = parse_sha256_sidecar(response.read())
    cached = None
    for path in WORK.joinpath("repo").glob(app["package"] + "_*.apk"):
        if expected_sha256 is not None:
            if sha256(path) == expected_sha256:
                cached = path
                break
        elif path.stat().st_size == asset["size"]:
            cached = path
            break
    if cached:
        verify_download(cached, asset, expected_sha256)
        inspect_apk(cached, app)
        print(f"Already imported {app['package']} {release['tag_name']}", flush=True)
    else:
        with tempfile.TemporaryDirectory(dir=WORK) as directory:
            incoming = Path(directory) / "download.apk"
            with fetch(asset["browser_download_url"]) as response, incoming.open("wb") as output:
                shutil.copyfileobj(response, output)
            verify_download(incoming, asset, expected_sha256)
            version = inspect_apk(incoming, app)
            filename = f"{app['package']}_{version}.apk"
            store_apk(incoming, WORK / "repo" / filename, WORK / "retired" / filename)
            print(f"Imported {app['package']} {release['tag_name']}", flush=True)


def publish(apps):
    shutil.copytree(SOURCE / "metadata", WORK / "metadata", dirs_exist_ok=True)
    retire_unlisted(WORK, {app["package"] for app in apps})
    shutil.copyfile(SOURCE / "icon.png", WORK / "icon.png")
    subprocess.run(["fdroid", "update", "--pretty", "-W", "error"], cwd=WORK, check=True)
    PUBLIC.mkdir(parents=True, exist_ok=True)
    # Publish APKs before indexes so an index never points at an unfinished download.
    run("rsync", "-rt", "--chmod=D755,F644", "--exclude=index*", "--exclude=entry*",
        str(WORK / "repo") + "/", str(PUBLIC) + "/")
    run("rsync", "-rt", "--delay-updates", "--chmod=D755,F644", "--include=*/",
        "--include=index*", "--include=entry*", "--exclude=*",
        str(WORK / "repo") + "/", str(PUBLIC) + "/")
    for apk in PUBLIC.glob("*.apk"):
        if not WORK.joinpath("repo", apk.name).exists():
            apk.unlink()
    print("Signed repository published", flush=True)


def main():
    WORK.joinpath("repo").mkdir(parents=True, exist_ok=True)
    apps = json.loads(SOURCE.joinpath("apps.json").read_text())
    failed = []
    for app in apps:
        # One app's broken or missing release must not stop the index re-signing:
        # clients reject indexes older than 14 days, which would drop every app.
        try:
            import_app(app)
        except Exception as error:
            print(f"Import failed for {app['package']}: {error!r}", flush=True)
            failed.append(app["package"])
    publish(apps)
    if failed:
        raise SystemExit(f"Import failed for: {', '.join(failed)}")


if __name__ == "__main__":
    main()
