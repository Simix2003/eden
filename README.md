# EDEN

**EDEN is a persistent artificial world for a Raspberry Pi 5 or desktop computer.** It is a deterministic ecosystem rather than a scripted animation: terrain, water, weather, plants, fire, organisms, tiny inherited neural controllers, mutation, lineages, and divine interventions all share one mechanical world.

Leave it running as a living home artifact. Close it normally—or recover after an abrupt stop—and the latest verified SQLite snapshot resumes. Time missed while the display was off is simulated in bounded reduced-fidelity batches.

Version: **0.1.0**

## What is alive in v0.1

- Deterministic 128×128 procedural world with lakes, fertile zones, dry land, and rock.
- Spatial sunlight, temperature, soil moisture, water, fertility, plant biomass, signals, ash, and fire.
- Seasonal and daily cycles plus clear, cloudy, rain, drought, heatwave, and cold-period weather.
- 110 initial organisms using 16 sensors, a 10-neuron hidden layer, and 8 possible actions.
- Movement, turning, feeding, drinking, rest, reproduction, signaling, environmental avoidance, aging, and five mechanical death paths.
- Bounded genomes for physiology, color, and neural weights; asexual inheritance, mutation, lineage divergence, and extinction.
- Structured event history for births, deaths, disasters, records, population changes, migrations, dominance, recovery, and The Chosen.
- Transaction-safe compressed SQLite snapshots with checksums, schema versioning, retention, fallback to older valid saves, and exact RNG restoration.
- Offline catch-up capped by configuration, with progress and a historical event.
- Touch-friendly Pygame interface, camera pan/zoom, cell and organism inspection, field notes, fullscreen, help, and screenshots.
- God instruments for rain, drought, plants, fire, extinguishing, water, spawning life, smiting, and temporary heat/cold.
- One mortal Chosen organism, a modest survival advantage, a visible mark, protected descendants, succession, blessing, and directed mutation.
- Normal, headless, benchmark, safe, seeded, and deliberate new-world modes.

Audio and predation are intentionally not part of v0.1.

## Quick start

EDEN requires a **64-bit Python 3.11 or newer**. Python 3.12 is used for the current release validation.

### Windows

```powershell
cd E:\Simix\Projects\Eden\eden
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\verify_installation.py
.\.venv\Scripts\python.exe run.py
```

After setup, `run_eden.bat` launches the display.

### Raspberry Pi OS / Linux

```bash
cd ~/eden
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/verify_installation.py
./run_eden.sh --fullscreen
```

If the shell launcher lost its executable bit after copying, run `chmod +x run_eden.sh` once. Complete Pi packages, autostart, service, backup, and display instructions are in [docs/RASPBERRY_PI_SETUP.md](docs/RASPBERRY_PI_SETUP.md).

## Launch modes

All of these options are implemented:

```bash
python run.py                         # windowed living display, restoring the latest world
python run.py --fullscreen            # fullscreen artifact display
python run.py --headless              # continuous simulation; Ctrl+C saves and exits
python run.py --headless --steps 1000 # finite headless run for maintenance or validation
python run.py --new-world             # archive the current database and make a fresh world
python run.py --seed 12345            # archive the current database and make this seeded world
python run.py --benchmark             # simulation + SDL software-render benchmark
python run.py --safe-mode             # 20 FPS cap and low-cost scaling
```

`--new-world` and `--seed` are deliberate reset actions. The old database is renamed with a timestamp; it is not erased. In the UI, use **Reset World** or `Ctrl+Shift+N`, then press Enter on the explicit confirmation screen.

## Controls

| Action | Mouse / touch | Keyboard |
|---|---|---|
| Inspect life or terrain | Tap/click | — |
| Pan | Right/middle drag | Arrow keys |
| Zoom | Wheel | `+` / `-` |
| Pause / resume | Top `II` / `1×` | Space |
| Time speed | Top `1×`, `5×`, `20×`, `100×` | `1`–`5` (`1` means pause) |
| Divine instruments | `GOD` | `G` |
| Apply a divine force | Select tool, preview radius, tap world | — |
| Field notes | `LOG` | `E` |
| Help | `?` | `H` |
| Fullscreen | — | `F11` |
| Screenshot | — | `F12` |
| Cancel tool / close overlay | — | `Esc` |
| Deliberate reset prompt | `RESET WORLD` | `Ctrl+Shift+N` |

The organism inspector exposes energy, hydration, health, age, ancestry, position, visible traits, current action, status, and a compact trait signature. Its actions choose, bless/unbless, mutate, follow, and close.

At `100×`, EDEN schedules the same bounded number of controller decisions as `20×` but integrates five times more ecological time per decision. This documented reduced-fidelity mode protects responsiveness on low-power hardware.

## Persistence and recovery

The default save is `data/saves/eden.db`. A snapshot is captured only at a completed simulation tick, compressed without pickle, checksummed, inserted incomplete, and marked complete in one SQLite transaction. The newest five complete snapshots are retained by default. Loading verifies checksums, array names, shapes, value ranges, neural-controller shapes, and schema versions; a damaged newest snapshot falls back to the next valid generation.

No entity action writes to disk. Automatic saves happen every 30 seconds and at graceful exit. Logs rotate at 2 MB with three backups. Event, metric, death, intervention, snapshot, screenshot, and population counts are all bounded.

Offline elapsed time is clamped to one hour by default and at most 2,400 catch-up steps. A progress screen remains visible during graphical recovery. Negative clock changes produce no catch-up.

## Configuration

Edit `config/default.toml` before creating a world. Existing saves retain their ecological settings so a configuration edit cannot silently change a running experiment.

Major controls include:

- seed, dimensions, initial and maximum population;
- simulation rate, day and season length, plant rates, metabolism, history limits;
- mutation, divergence, reproduction, Chosen advantage and optional immortality;
- database path, save interval, retained snapshots, catch-up cap and step budget;
- resolution, render FPS, fullscreen, UI scale, audio flag, and performance mode;
- intervention radius and strength.

Configuration is validated on startup. Dimensions are limited to 32–512 cells per side and population to 2,000.

## Tests and validation

Run the complete test suite:

```bash
python -m pytest
```

Run the installation smoke test:

```bash
python scripts/verify_installation.py
```

Run a repeatable 10,000-tick invariant soak:

```bash
python scripts/long_run.py --steps 10000 --seed 314159
```

Run the release benchmark:

```bash
python run.py --benchmark --seed 314159
```

The suite covers procedural determinism, environmental bounds, plant growth/stress, rain/drought, fire spread/expiry, real resource consumption, terrain avoidance, reproduction, death causes, population caps, mutation bounds, lineage divergence/extinction, snapshot equivalence, deterministic resume, corrupt-save fallback, incomplete-save rejection, catch-up caps, ordered-intervention determinism, long-run invariants, core performance, and a real Pygame render frame through SDL.

Current development-computer results are stored in:

- `data/logs/benchmark_results.json`
- `data/logs/long_run_results.json`

The measured numbers in those files are Windows development evidence, **not Raspberry Pi claims**. Perform the same commands on the target Pi before treating its thermal, touch, display, or 24/7 behavior as certified.

## Screenshots

Press `F12` while EDEN is running. Screenshots are written to `data/screenshots/` and the newest 40 are retained. Runtime images are intentionally ignored by Git.

## Architecture

```text
TOML + PCG64 RNG
        ↓
compact world arrays → environment rules
        ↓
organism sensors → tiny brain → actions
        ↓
inheritance + lineages + structured events
        ↓
versioned snapshot codec → SQLite generations
        ↓
Pygame camera + world renderer + touch UI
```

The simulation is entirely independent of Pygame. The graphical host schedules a fixed simulation accumulator and a separately capped render loop on Pygame's main thread. Headless mode calls the same `World.step()` API. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/SIMULATION_RULES.md](docs/SIMULATION_RULES.md) for the actual state model and formulas.

## Project map

```text
config/                 validated TOML defaults
data/                   saves, screenshots, bounded logs, validation results
docs/                   architecture, rules, Pi operation, roadmap
scripts/                benchmark, demo world, soak, install verifier, service template
src/eden/simulation/    grids, environment, brains, organisms, evolution, events, metrics
src/eden/persistence/   migrations, SQLite connection, snapshot codec, catch-up
src/eden/rendering/     camera, palette, effects, world renderer
src/eden/ui/            layout, controls, inspector, God panel, history
tests/                  deterministic headless and SDL render validation
run.py                  CLI and application entry point
```

## Troubleshooting

- **Python is older than 3.11 or 32-bit:** install a current 64-bit Python and recreate `.venv`. `scripts/verify_installation.py` reports both gates.
- **`pygame` cannot open a display:** confirm the desktop session is active and install the SDL packages listed in the Pi guide. Use `--headless` to keep the ecosystem running without a display.
- **The newest save is corrupt:** EDEN automatically tries older complete snapshots. The log identifies skipped generations.
- **The UI is slow:** use `--safe-mode`, lower `render_fps`, or set `performance_mode = "low"`.
- **No audio:** v0.1 intentionally ships silent; the configuration flag is reserved and defaults off.
- **The world was closed for a long time:** catch-up is deliberately capped; the event log reports the simulated duration.

## Known limitations

- Pi 5 FPS, power-loss behavior, touch accuracy, temperature, and multi-day stability still require on-device validation.
- `100×` and offline catch-up use documented reduced-fidelity integration; they are deterministic for the same saved state and explicit elapsed input, but not tick-for-tick equivalent to uninterrupted `1×` time.
- Determinism is verified within the supported Python/NumPy build. Bitwise equality between x86 and ARM transcendental implementations is not promised.
- Organisms are herbivorous and reproduce asexually. There are no predators, sexual reproduction, audio, civilization, language, buildings, cloud services, or network requirement.
- SQLite generations protect against partial snapshots but are not a substitute for copying the database to another device.

Future work is separated from implemented v0.1 in [docs/ROADMAP.md](docs/ROADMAP.md).
