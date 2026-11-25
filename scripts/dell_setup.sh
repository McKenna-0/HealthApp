#!/usr/bin/env bash
# One-time hardening for the Dell. Idempotent - safe to re-run.
#
#   ssh -t conor@100.95.44.32 'sudo bash ~/health-app/scripts/dell_setup.sh'
#
# Written after the 2026-11-24/25 outages:
#   * eduroam dropped the Dell at 04:00 and NetworkManager gave up after its
#     default 4 retries - offline for ~9h until someone reconnected it by hand.
#   * deploy.sh / the poller launched uvicorn with nohup beside
#     health-app.service; the stray held port 8000 and the unit crash-looped
#     every 7s for days (each restart also attempting a Garmin login).
#   * a desktop autostart entry ran a second copy of the poller.
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "run with sudo" >&2; exit 1; }
APP_USER=conor
APP_HOME=/home/$APP_USER
WIFI_CONN=eduroam

echo "==> sudoers: let $APP_USER restart the app units without a password"
cat > /etc/sudoers.d/health-app <<EOF
$APP_USER ALL=(root) NOPASSWD: /usr/bin/systemctl restart health-app.service, /usr/bin/systemctl restart health-poller.service
EOF
chmod 440 /etc/sudoers.d/health-app
visudo -cf /etc/sudoers.d/health-app

echo "==> health-app.service: restart on any exit, with backoff"
# Restart=always so a plain kill also comes back. RestartSteps/MaxDelay
# (systemd >= 254) stretch a crash loop out to one attempt per 5 min instead
# of hammering the disk and Garmin's SSO every few seconds.
mkdir -p /etc/systemd/system/health-app.service.d
cat > /etc/systemd/system/health-app.service.d/resilience.conf <<'EOF'
[Unit]
StartLimitIntervalSec=0

[Service]
Restart=always
RestartSec=5
RestartSteps=6
RestartMaxDelaySec=300
EOF

echo "==> wifi: retry '$WIFI_CONN' forever, no power saving"
nmcli connection modify "$WIFI_CONN" connection.autoconnect yes \
  connection.autoconnect-retries 0 802-11-wireless.powersave 2

echo "==> wifi watchdog: every 2 min, bring the connection back if it is down"
cat > /usr/local/sbin/wifi-watchdog <<EOF
#!/usr/bin/env bash
# Healthy = default route exists and the internet answers ping OR http, so a
# network that filters one of them can't trigger needless reconnects.
if ip route show default | grep -q . && { ping -c1 -W5 1.1.1.1 >/dev/null 2>&1 \\
     || curl -fsS -m 8 -o /dev/null http://connectivity-check.ubuntu.com/; }; then
  rm -f /run/wifi-watchdog.fails
  exit 0
fi
fails=\$(( \$(cat /run/wifi-watchdog.fails 2>/dev/null || echo 0) + 1 ))
echo "\$fails" > /run/wifi-watchdog.fails
logger -t wifi-watchdog "offline (strike \$fails) - reconnecting $WIFI_CONN"
if [ "\$fails" -ge 3 ]; then
  # nmcli alone has not been enough; wpa_supplicant can wedge too.
  systemctl restart NetworkManager
  echo 0 > /run/wifi-watchdog.fails
else
  nmcli radio wifi on
  nmcli connection up "$WIFI_CONN" || true
fi
EOF
chmod 755 /usr/local/sbin/wifi-watchdog

cat > /etc/systemd/system/wifi-watchdog.service <<'EOF'
[Unit]
Description=Reconnect wifi if the Dell has lost the network

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/wifi-watchdog
EOF
cat > /etc/systemd/system/wifi-watchdog.timer <<'EOF'
[Unit]
Description=Check wifi every 2 minutes

[Timer]
OnBootSec=3min
OnUnitActiveSec=2min

[Install]
WantedBy=timers.target
EOF

echo "==> never suspend (lid closed or idle)"
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target >/dev/null
mkdir -p /etc/systemd/logind.conf.d
cat > /etc/systemd/logind.conf.d/no-sleep.conf <<'EOF'
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
IdleAction=ignore
EOF

echo "==> poller: only the systemd unit, not a desktop autostart copy"
AUTOSTART=$APP_HOME/.config/autostart/github-poller.desktop
if [ -f "$AUTOSTART" ]; then
  mv "$AUTOSTART" "$AUTOSTART.disabled"
fi

systemctl daemon-reload
systemctl enable --now wifi-watchdog.timer

echo "==> replacing stray (non-systemd) app and poller processes"
pkill -f "uvicorn app[.]main" || true
pkill -f "github_poller[.]py" || true
sleep 2
systemctl restart health-app.service health-poller.service
sleep 5
systemctl is-active health-app.service health-poller.service wifi-watchdog.timer
pgrep -c -f "github_poller[.]py" | xargs echo "poller processes (want 1):"
curl -fsS --max-time 10 http://127.0.0.1:8000/api/health && echo
echo "Done. logind changes take effect after the next reboot."
