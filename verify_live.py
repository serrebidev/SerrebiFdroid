#!/usr/bin/env python3
"""Check public indexes, repository signatures, APKs, and private-file isolation."""

import json
from pathlib import Path
import shutil
import tempfile
import urllib.error
import urllib.request

from fdroidserver import common, index
import sync


BASE = "https://fdroid.serrebiradio.com"
FINGERPRINT = "BC713B224BF39316356FB7D035AB6983298234CC3F56ACEB01B77F906268857B"


def main():
    common.read_config()
    url = BASE + "/fdroid/repo?fingerprint=" + FINGERPRINT
    v1, _ = index.download_repo_index_v1(url)
    v2, _ = index.download_repo_index_v2(url)
    apps = {app["package"]: app for app in json.loads(sync.SOURCE.joinpath("apps.json").read_text())}
    assert set(v1["packages"]) == set(apps), "Unexpected apps in v1 index"
    assert set(v2["packages"]) == set(apps), "Unexpected apps in v2 index"
    for package, app in apps.items():
        versions = v2["packages"][package]["versions"]
        assert versions, f"No published versions for {package}"
        latest = max(versions.values(), key=lambda v: v["manifest"]["versionCode"])
        file = latest["file"]
        with tempfile.TemporaryDirectory() as directory:
            apk = Path(directory) / "app.apk"
            with sync.fetch(BASE + "/fdroid/repo" + file["name"]) as response, apk.open("wb") as output:
                shutil.copyfileobj(response, output)
            sync.verify_download(apk, {"size": file["size"], "digest": "sha256:" + file["sha256"]})
            version = sync.inspect_apk(apk, app)
            assert version == latest["manifest"]["versionCode"]
            print(f"Verified public APK: {package}, versionCode {version}")
    for path in ("/config.yml", "/keystore.p12", "/fdroid/config.yml",
                 "/fdroid/keystore.p12", "/.git/config", "/fdroid/repo/config.yml"):
        try:
            with urllib.request.urlopen(BASE + path, timeout=30) as response:
                raise AssertionError(f"Private path returned HTTP {response.status}: {path}")
        except urllib.error.HTTPError as error:
            assert error.code == 404, f"Expected 404 for {path}, got {error.code}"
    print("Verified v1/v2 signatures, app allowlist, HTTPS downloads, and private-file isolation")


if __name__ == "__main__":
    main()
