# Tailscale on the laptop (interim setup until the Raspberry Pi arrives)

Result: the app is reachable from your iPhone **anywhere** at
`https://<laptop-name>.<tailnet>.ts.net` — while the laptop is awake. HTTPS means the
camera barcode scanner works and Add to Home Screen installs the full PWA.
Nothing is exposed to the public internet; only devices on your Tailscale account can connect.

When the Pi arrives, follow `deploy-pi.md` — this setup carries over (same Tailscale
account, just a different machine serving).

## 1. Install Tailscale (once)

```powershell
winget install --id tailscale.tailscale
```

Open the Tailscale tray app and log in (browser opens). Tailscale installs a Windows
**service** that starts at boot, so the tailnet connection itself survives reboots.

In the admin console at https://login.tailscale.com/admin:
- **DNS tab → enable MagicDNS**
- **Enable HTTPS Certificates** (same DNS tab)

Do this BEFORE the next step or `tailscale serve` will fail with a certificate error.

Install the Tailscale app on your iPhone and log in with the same account.

## 2. Reverse-proxy the app with HTTPS (once)

Open a **new** terminal (so `tailscale.exe` is on PATH; it lives in
`C:\Program Files\Tailscale\` if not):

```powershell
tailscale serve --bg --https=443 http://127.0.0.1:8000
tailscale serve status     # shows your https://<laptop>.<tailnet>.ts.net URL
```

`--bg` stores the config in the Tailscale service, so it survives reboots.
The first HTTPS request can take ~30 seconds while the certificate is provisioned.

## 3. Auto-start the backend at logon (once)

1. Press Win+R → `shell:startup` → Enter.
2. Right-click → New → Shortcut → browse to `C:\Users\conor\Health app\deploy\start-app.bat`.

The backend now starts minimized whenever you log in, logging to
`%LOCALAPPDATA%\health-app\uvicorn.log`.

Alternative (no startup folder): a scheduled task —

```powershell
schtasks /Create /TN "HealthApp" /SC ONLOGON /TR "\"C:\Users\conor\Health app\deploy\start-app.bat\"" /RL LIMITED
```

## 4. iPhone

1. Tailscale app ON.
2. Safari → `https://<laptop>.<tailnet>.ts.net`.
3. Share → **Add to Home Screen** — full PWA (standalone, cached shell, camera scanner).

Replace your old `http://<lan-ip>:8000` bookmark; the ts.net URL works both at home and away.

## Notes & troubleshooting

- **App unreachable?** Laptop asleep or backend not running. Check
  `%LOCALAPPDATA%\health-app\uvicorn.log`; check the phone's Tailscale toggle is on.
- **`tailscale serve` error about certificates** → enable HTTPS Certificates in the
  admin console first (step 1).
- The bat binds `0.0.0.0` so plain LAN access (`http://<lan-ip>:8000`) keeps working
  alongside Tailscale. If you want Tailscale-only, change `--host 0.0.0.0` to
  `--host 127.0.0.1` in `start-app.bat`.
- Laptop renamed → the ts.net URL changes (it's based on the machine name).
