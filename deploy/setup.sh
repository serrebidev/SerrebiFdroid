#!/bin/sh
set -eu

# Run as root from the checked-out repository on the YunoHost server.
export DEBIAN_FRONTEND=noninteractive
apt-get install -y --no-install-recommends fdroidserver rsync
chmod -R a+rX metadata
install -d -m 700 /root/backups
id serrebifdroid >/dev/null 2>&1 || useradd --system --create-home \
    --home-dir /var/lib/serrebifdroid --shell /usr/sbin/nologin serrebifdroid
install -d -o serrebifdroid -g serrebifdroid -m 700 /var/lib/serrebifdroid/repository
install -d -o serrebifdroid -g serrebifdroid -m 755 /var/www/serrebifdroid/fdroid/repo
if [ ! -f /var/lib/serrebifdroid/repository/config.yml ]; then
    runuser -u serrebifdroid -- sh -c 'cd /var/lib/serrebifdroid/repository && ANDROID_HOME=/usr/lib/android-sdk fdroid init --no-prompt --repo-keyalias serrebifdroid --distinguished-name CN=SerrebiFdroid'
fi
python3 - <<'PY'
from pathlib import Path
import json
import shutil
import time
import yaml

config = Path('/var/lib/serrebifdroid/repository/config.yml')
settings = yaml.safe_load(config.read_text())
settings.update(yaml.safe_load(Path('config.example.yml').read_text()))
config.write_text(yaml.safe_dump(settings))
config.chmod(0o600)

permissions = Path('/etc/ssowat/conf.json.persistent')
shutil.copy2(permissions, '/root/backups/ssowat-before-fdroid-' + str(time.time_ns()) + '.json')
data = json.loads(permissions.read_text())
data.setdefault('permissions', {})['custom_serrebifdroid.main'] = {
    'users': [], 'label': 'SerrebiFdroid', 'show_tile': False,
    'auth_header': False, 'public': True, 'uris': ['fdroid.serrebiradio.com/']
}
permissions.write_text(json.dumps(data, indent=2) + '\n')
PY
install -m 644 deploy/serrebifdroid.service /etc/systemd/system/
install -m 644 deploy/serrebifdroid.timer /etc/systemd/system/
yunohost app ssowatconf
systemctl daemon-reload
systemctl start serrebifdroid.service
python3 - <<'PY'
from pathlib import Path
import hashlib
import zipfile
from fdroidserver import common

with zipfile.ZipFile('/var/lib/serrebifdroid/repository/repo/entry.jar') as jar:
    name = next(n for n in jar.namelist() if common.SIGNATURE_BLOCK_FILE_REGEX.match(n))
    fingerprint = hashlib.sha256(common.get_certificate(jar.read(name))).hexdigest().upper()
Path('/var/www/serrebifdroid/fingerprint.txt').write_text(fingerprint + '\n')
nginx = Path('deploy/nginx.conf').read_text().replace('REPOSITORY_FINGERPRINT', fingerprint)
Path('/etc/nginx/conf.d/fdroid.serrebiradio.com.d/repository.conf').write_text(nginx)
print('Repository fingerprint:', fingerprint)
PY
nginx -t
systemctl reload nginx
systemctl enable --now serrebifdroid.timer
