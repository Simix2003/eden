# Raspberry Pi 5 setup and operation

## Supported target

- Raspberry Pi 5, 4 GB or 8 GB.
- Raspberry Pi OS 64-bit Bookworm or newer.
- Python 3.11+ 64-bit.
- 10–13 inch HDMI or DSI touchscreen, normally 1280×720 or 1920×1080.
- No dedicated GPU, network, cloud account, root runtime, or audio device is required.

EDEN has been validated on the development Windows computer. Complete the benchmark and soak sections below on the real Pi before permanent installation.

## System packages

From a normal sudo-enabled setup account:

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-dev \
  libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-ttf-2.0-0 \
  libgl1 libegl1
```

The application itself must run as the desktop user, never root.

## Install

```bash
cd /home/pi
git clone https://github.com/Simix2003/eden.git
cd eden
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/verify_installation.py
chmod +x run_eden.sh
```

After packages are installed, EDEN's core operation is offline.

## First launch and target validation

```bash
./run_eden.sh --fullscreen --new-world
```

Use `F11` if the window manager does not honor the initial fullscreen request. Confirm touch selection, God-tool preview, organism inspector, pan/zoom, `F12` screenshots, and graceful exit.

Then run:

```bash
.venv/bin/python -m pytest
.venv/bin/python run.py --benchmark --seed 314159
.venv/bin/python scripts/long_run.py --steps 10000 --seed 314159
```

Inspect `data/logs/benchmark_results.json` and `data/logs/long_run_results.json`. During a longer 24–72 hour acceptance soak, also monitor:

```bash
htop
vcgencmd measure_temp
vcgencmd get_throttled
du -sh data
```

The development target is average RSS below 500 MB, a sustained 30 FPS display where possible, and base simulation work comfortably above 8 ticks/s. Thermal throttling, disk growth, and touch accuracy are Pi-specific release gates.

## Desktop fullscreen autostart (recommended)

Pygame needs the active desktop session for a visible artifact. Desktop autostart is more reliable than a system service for the fullscreen window.

```bash
mkdir -p ~/.config/autostart
nano ~/.config/autostart/eden.desktop
```

Paste:

```ini
[Desktop Entry]
Type=Application
Name=EDEN
Exec=/home/pi/eden/run_eden.sh --fullscreen
Path=/home/pi/eden
Terminal=false
X-GNOME-Autostart-enabled=true
```

Adjust `/home/pi` if your username differs. Reboot and confirm the display starts after desktop login.

## Optional headless systemd service

Use headless service mode when the desktop should be stopped or restarted independently while the ecosystem continues. Stop the fullscreen instance first; do not run two writers against one world database.

Edit `scripts/eden.service` so `User`, `WorkingDirectory`, and `ExecStart` match your account and checkout, then:

```bash
sudo cp scripts/eden.service /etc/systemd/system/eden.service
sudo systemctl daemon-reload
sudo systemctl enable --now eden.service
systemctl status eden.service
```

The supplied service uses `--headless`, restarts after failure with a five-second delay, sends `SIGTERM`, and gives EDEN 30 seconds to save. Stop it before starting the visible desktop application:

```bash
sudo systemctl stop eden.service
```

## Disable screen blanking

On Raspberry Pi OS desktop, use **Preferences → Raspberry Pi Configuration → Display → Screen Blanking: Off**. For an X11 session, the equivalent startup commands are:

```bash
xset s off
xset -dpms
xset s noblank
```

Do not disable display power management globally unless this Pi is dedicated to the artifact.

## Performance mode

Start conservatively:

```bash
./run_eden.sh --fullscreen --safe-mode
```

Safe mode caps drawing at 20 FPS and uses inexpensive scaling. Or edit:

```toml
[ui]
render_fps = 20
performance_mode = "low"
```

Create a new world after changing ecological settings such as world size. Rendering-only changes can be applied immediately by restarting.

## Graceful shutdown and crash recovery

Normal window close, `Esc`, Ctrl+C in headless mode, `SIGINT`, and `SIGTERM` cause a final save. Automatic saves happen independently every 30 seconds.

After power loss, SQLite ignores incomplete transactions. EDEN validates the newest complete generation and falls back through older checksummed snapshots. Do not delete `-wal`/`-shm` files while EDEN is running.

For a physical shutdown button, configure the OS to call `systemctl poweroff`; do not wire a script that kills Python without allowing SIGTERM.

## Backup and restore

Stop all EDEN processes, then copy the database and configuration:

```bash
sudo systemctl stop eden.service 2>/dev/null || true
cp data/saves/eden.db /media/pi/BACKUP/eden-$(date +%F).db
cp config/default.toml /media/pi/BACKUP/eden-config-$(date +%F).toml
```

Restore only while EDEN is stopped. Keep backups off the Pi; retained generations inside one SQLite file do not protect against SD-card loss.

## Logs and disk use

- `data/logs/eden.log`: rotating, 2 MB × four files total.
- `data/saves/eden.db`: newest configured snapshot generations.
- `data/screenshots/`: newest 40 screenshots.
- `data/logs/*_results.json`: validation evidence.

Review monthly with `du -sh data/*`. Copy old screenshots elsewhere rather than expanding the in-app retention without considering SD-card space.

## Display and audio failures

- If SDL reports no video device, run from the logged-in desktop, not SSH, or use `--headless`.
- If HDMI is blank, confirm the OS desktop works before debugging EDEN.
- EDEN v0.1 does not initialize audio and functions normally with no sound hardware.
- If touch generates no mouse-compatible events, verify the panel with `libinput debug-events`; Pygame handles both finger-down and mouse events.

