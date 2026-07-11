# Deploying to a Raspberry Pi (always-on, reachable anywhere via Tailscale)

Target: Raspberry Pi 4/5 (2GB+ RAM), Raspberry Pi OS **Lite 64-bit**, powered on 24/7.
Result: the app runs at `https://<pi-name>.<tailnet>.ts.net` from your iPhone anywhere,
with automatic Garmin syncs, weekly AI reports, HTTPS (which enables the camera barcode
scanner and full PWA install), and nightly backups. Nothing is exposed to the public internet.

## 1. Prepare the Pi

```bash
# flash Raspberry Pi OS Lite 64-bit with the Raspberry Pi Imager (enable SSH in settings)
ssh pi@raspberrypi.local

sudo apt update && sudo apt install -y sqlite3 rsync
curl -LsSf https://astral.sh/uv/install.sh | sh          # installs to ~/.local/bin
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up                                        # log in with your Tailscale account
```

In the Tailscale admin console (https://login.tailscale.com/admin/dns):
- Enable **MagicDNS**
- Enable **HTTPS certificates**

Install the Tailscale app on your iPhone and log in with the same account.

## 2. Migrate the app from the laptop

On the **laptop** (Git Bash). Never raw-copy a live WAL database — take a snapshot:

```bash
cd "/c/Users/conor/Health app"
bash scripts/build_frontend.sh                # build UI on the laptop, not the Pi

cd backend
uv run python -c "import sqlite3; sqlite3.connect('data/health.db').backup(sqlite3.connect('health-snap.db')); print('snapshot ok')"

# copy everything the Pi needs (adjust host name)
rsync -av --exclude .venv --exclude data --exclude node_modules --exclude .git \
  ../ pi@raspberrypi.local:/home/pi/health-app/
rsync -av health-snap.db pi@raspberrypi.local:/home/pi/health-app/backend/data/health.db
rsync -av ../.env pi@raspberrypi.local:/home/pi/health-app/.env
rsync -av .garmin_tokens/ pi@raspberrypi.local:/home/pi/health-app/backend/.garmin_tokens/
rm health-snap.db
```

On the **Pi**:

```bash
cd /home/pi/health-app/backend && ~/.local/bin/uv sync
```

## 3. Run as a service

```bash
sudo cp /home/pi/health-app/deploy/health-app.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now health-app
systemctl status health-app          # should be active (running)
curl localhost:8000/api/health       # {"status":"ok",...}
```

## 4. HTTPS via Tailscale

```bash
sudo tailscale serve --bg https / http://127.0.0.1:8000
tailscale serve status               # shows your https://<pi>.<tailnet>.ts.net URL
```

`tailscale serve` provisions and auto-renews the certificate and survives reboots
(`--bg` persists the config). The app is now reachable from any of your Tailscale
devices — and nothing else.

## 5. iPhone

1. Tailscale app on and connected.
2. Safari → `https://<pi>.<tailnet>.ts.net`.
3. Share → **Add to Home Screen**. Because it's HTTPS, this is a full PWA: standalone
   app, cached shell, and the camera barcode scanner works.

## 6. Nightly backups

```bash
chmod +x /home/pi/health-app/deploy/backup.sh
sudo cp /home/pi/health-app/deploy/backup.service /etc/systemd/system/
sudo cp /home/pi/health-app/deploy/backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now backup.timer
sudo systemctl start backup.service && ls /home/pi/health-app/backups/   # test now
```

Optional off-Pi copy: from the laptop, occasionally run
`rsync -av pi@<pi>:/home/pi/health-app/backups/ ~/health-backups/` (works over Tailscale too).

## 7. Updating the app later

On the laptop after making changes:

```bash
bash scripts/build_frontend.sh
rsync -av --exclude .venv --exclude data --exclude node_modules --exclude .git \
  ./ pi@<pi>:/home/pi/health-app/
ssh pi@<pi> "cd health-app/backend && ~/.local/bin/uv sync && sudo systemctl restart health-app"
```

Schema changes apply automatically on restart (the app adds missing tables/columns itself).

## Troubleshooting

- **Service won't start**: `journalctl -u health-app -n 50`
- **Garmin auth broken after migration**: delete `backend/.garmin_tokens/` on the Pi and
  restart — it re-logs-in with the .env credentials.
- **ts.net URL unreachable**: check `tailscale status` on both Pi and iPhone; both must be
  on the same tailnet.
- **Clock drift breaks sync scheduling**: Pi has no RTC; ensure `timedatectl` shows NTP sync.
