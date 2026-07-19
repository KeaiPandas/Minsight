#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/minsight}"
ENV_DIR="${ENV_DIR:-/etc/minsight}"
SERVICE_USER="${SERVICE_USER:-minsight}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run as root: sudo bash Deploy/scripts/bootstrap_aliyun.sh" >&2
  exit 1
fi

apt-get update
apt-get install -y python3 python3-venv python3-pip nginx

if ! id "${SERVICE_USER}" >/dev/null 2>&1; then
  useradd --system --create-home --shell /usr/sbin/nologin "${SERVICE_USER}"
fi

mkdir -p "${APP_DIR}" "${ENV_DIR}" /var/lib/minsight
python3 -m venv "${APP_DIR}/.venv"
"${APP_DIR}/.venv/bin/pip" install --upgrade pip
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/Deploy/requirements.txt"

if [[ ! -f "${ENV_DIR}/minsight.env" ]]; then
  cp "${APP_DIR}/Deploy/.env.production.example" "${ENV_DIR}/minsight.env"
  chmod 600 "${ENV_DIR}/minsight.env"
  echo "Created ${ENV_DIR}/minsight.env. Fill real model secrets before starting the service."
fi

cp "${APP_DIR}/Deploy/ops/minsight.service" /etc/systemd/system/minsight.service
cp "${APP_DIR}/Deploy/ops/nginx.minsight.conf" /etc/nginx/sites-available/minsight.conf
ln -sf /etc/nginx/sites-available/minsight.conf /etc/nginx/sites-enabled/minsight.conf
rm -f /etc/nginx/sites-enabled/default

chown -R "${SERVICE_USER}:${SERVICE_USER}" "${APP_DIR}" /var/lib/minsight
systemctl daemon-reload
nginx -t

echo "Bootstrap complete."
echo "Next:"
echo "1. Edit ${ENV_DIR}/minsight.env"
echo "2. Run: systemctl enable --now minsight"
echo "3. Run: systemctl reload nginx"
