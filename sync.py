#!/usr/bin/env python3
"""Import configured GitHub release APKs, then sign and publish an F-Droid index."""

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


def verify_download(path, asset):
    digest = asset.get("digest", "") or ""
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        raise ValueError("GitHub asset must provide a SHA-256 digest")
    if path.stat().st_size != asset["size"] or "sha256:" + sha256(path) != digest:
        raise ValueError("APK size or SHA-256 does not match the GitHub release")


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


def main():
    WORK.joinpath("repo").mkdir(parents=True, exist_ok=True)
    apps = json.loads(SOURCE.joinpath("apps.json").read_text())
    for app in apps:
        with fetch(f"https://api.github.com/repos/{app['github']}/releases/latest") as response:
            release = json.load(response)
        asset = select_asset(release, app)
        expected_prefix = f"https://github.com/{app['github']}/releases/download/"
        if not asset["browser_download_url"].startswith(expected_prefix):
            raise ValueError("APK download URL does not belong to configured repository")
        cached = None
        for path in WORK.joinpath("repo").glob(app["package"] + "_*.apk"):
            if "sha256:" + sha256(path) == asset.get("digest"):
                cached = path
                break
        if cached:
            verify_download(cached, asset)
            inspect_apk(cached, app)
            print(f"Already imported {app['package']} {release['tag_name']}", flush=True)
        else:
            with tempfile.TemporaryDirectory(dir=WORK) as directory:
                incoming = Path(directory) / "download.apk"
                with fetch(asset["browser_download_url"]) as response, incoming.open("wb") as output:
                    shutil.copyfileobj(response, output)
                verify_download(incoming, asset)
                version = inspect_apk(incoming, app)
                filename = f"{app['package']}_{version}.apk"
                store_apk(incoming, WORK / "repo" / filename, WORK / "retired" / filename)
                print(f"Imported {app['package']} {release['tag_name']}", flush=True)

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


if __name__ == "__main__":
    main()
