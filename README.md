# SerrebiFdroid

Developer-signed Android APK releases, served through a signed F-Droid repository.

## Add to F-Droid

In F-Droid, open **Settings > Repositories**, choose **Add repository**, and paste:

https://fdroid.serrebiradio.com/fdroid/repo?fingerprint=BC713B224BF39316356FB7D035AB6983298234CC3F56ACEB01B77F906268857B

Repository certificate SHA-256:

```text
BC713B224BF39316356FB7D035AB6983298234CC3F56ACEB01B77F906268857B
```

The public site is https://fdroid.serrebiradio.com/. The `/repo/` path also works.

## Apps

- **Accessible IPTV**: https://github.com/serrebidev/Accessible-IPTV-Client-Android
- **BlindPilot**: https://github.com/serrebidev/BlindPilot-Android
- **BlindRSS**: https://github.com/serrebidev/BlindRSS-Android

Apps without published APK releases are not imported.
This is an independent repository, separate from f-droid.org's
main catalogue. Accessible IPTV includes optional Google Cast dependencies,
declared through F-Droid's `NonFreeDep` metadata.

## Publishing

The server checks the configured GitHub repositories approximately hourly. Only
stable releases and explicitly matching APK assets are imported. The importer
checks the GitHub asset's SHA-256 and size, the Android package ID, and the pinned
APK signing certificate. A published package/version cannot be replaced with
different bytes. APKs retain their original developer signatures, so existing
installations signed with the same certificate can update normally.

The standard Debian `fdroidserver` package creates and signs legacy, v1, and v2
indexes. APKs are published before indexes. Previous APKs for listed apps remain available.
The repository signature is renewed each run; clients reject indexes older than
14 days. A failed import or index build leaves the last published repository
available. Monitor the service if updates stop.

To add another app, add its GitHub repository, exact Android package ID,
asset-name pattern, and certificate SHA-256 to `apps.json`. Add its metadata file
under `metadata/`, including the same `AllowedAPKSigningKeys` certificate.
Review and deploy these changes explicitly; there is no automatic app discovery.
Removing an app from `apps.json` removes it from the next signed index and then
removes its public APK downloads. Its APKs are preserved privately in the working
state's `retired/` directory.

## Server setup

The live server uses Debian 13, YunoHost, nginx, and systemd. DNS already resolves
through the domain's wildcard. The YunoHost domain and Let's Encrypt certificate
must exist before running setup:

```sh
yunohost domain add fdroid.serrebiradio.com
yunohost domain cert install fdroid.serrebiradio.com --no-checks
git clone https://github.com/serrebidev/SerrebiFdroid.git /opt/serrebifdroid
cd /opt/serrebifdroid
sh deploy/setup.sh
```

Skip domain creation if it already exists. Setup preserves any existing signing
key and its generated passwords. A fresh installation creates a new repository
identity: restore the existing private signing backup when rebuilding this repo.

- Source: `/opt/serrebifdroid` (root-owned).
- Private working state: `/var/lib/serrebifdroid/repository` (service user only).
- Private signing material: `config.yml` and `keystore.p12` inside that state.
- Public files only: `/var/www/serrebifdroid/fdroid/repo`.
- nginx: `/etc/nginx/conf.d/fdroid.serrebiradio.com.d/repository.conf`.
- Public YunoHost permission: `custom_serrebifdroid.main` in the persistent SSO configuration.
- Timer: `serrebifdroid.timer`; signing/import service: `serrebifdroid.service`.

Deploy source or metadata changes:

```sh
git -C /opt/serrebifdroid pull --ff-only
systemctl start serrebifdroid.service
journalctl -u serrebifdroid.service -n 30 --no-pager
systemctl list-timers serrebifdroid.timer
```

After changing deployment files, rerun `sh deploy/setup.sh` from the source directory.
The service runs as an unprivileged account with access to its private state and
public output only. Online signing enables unattended updates; protect the
server and keep an independent private backup of the config and keystore.
Neither file belongs in Git, GitHub artifacts, or the web root.

## Checks

```sh
python -m unittest discover -s tests -v
sh -n deploy/setup.sh
```

GitHub Actions runs these checks. End-to-end publication requires the Debian
F-Droid tools. On the server, verify public signatures, APKs, and private-file isolation:

```sh
cd /var/lib/serrebifdroid/repository
runuser -u serrebifdroid -- python3 /opt/serrebifdroid/verify_live.py
```

See the upstream [repository setup guide](https://f-droid.org/en/docs/Setup_an_F-Droid_App_Repo/).
