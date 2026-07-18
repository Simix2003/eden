# EDEN v0.1 architecture

This document describes the code that is present in v0.1. It does not describe roadmap features.

## Runtime boundaries

EDEN has one authoritative mutable object: `simulation.world.World`. It owns simulation time, the PCG64 random generator, environment arrays, living entities, lineage registry, counters, bounded histories, and the current Chosen ID.

The dependency direction is intentionally one-way:

```text
config + constants + deterministic RNG
                 ↓
environment arrays and update functions
                 ↓
genomes → sensors → neural controller → organism actions
                 ↓
lineages, structured events, aggregate metrics
                 ↓
versioned snapshot codec and SQLite repository
                 ↓
camera, renderer, panels, and application host
```

Simulation modules never import Pygame. Headless runs, tests, offline catch-up, and the visual application therefore execute the same ecological rules.

## State model

The default 128×128 world stores one compact NumPy array per spatial field:

| Field | Meaning |
|---|---|
| `terrain` | `uint8` water, fertile, dry, or rock code |
| `elevation` | normalized static height |
| `water` | available surface water |
| `moisture` | local soil moisture |
| `fertility` | soil productivity |
| `temperature` | current °C-like local value |
| `sunlight` | current normalized daylight |
| `plants` | consumable biomass |
| `signal` | short-lived organism signal |
| `fire` | active fire intensity |
| `ash` | temporary burn degradation |

Dynamic normalized arrays use `float32`. Vectorized environment rules avoid 16,384 per-cell Python objects.

Each living organism is a slotted dataclass keyed by a monotonic integer ID. Its genome contains eleven bounded traits and four small `float32` neural arrays. A 16×10 input layer and 10×8 output layer remain small enough for the Pi target. The living collection is capped by configuration; death summaries are retained separately in a bounded list.

Lineages keep a founder, emergence/extinction tick, name, and baseline genome. Species identity is deliberately lightweight rather than a claim of biological taxonomy.

## Simulation and render loops

`World.step()` is the sole ecological time transition. At the default 8 Hz it receives a 0.125-second quantum. It advances tick/time, weather, the environment, organisms in stable ID order, event detection, decimated metrics, and invariants.

`EdenApp` runs on Pygame's required main thread. It maintains a real-time accumulator for simulation work and draws at a separately capped FPS. Pause, 1×, 5×, and 20× retain the base ecological quantum. The 100× mode schedules 20× controller decisions and integrates five base quanta in each decision; work is capped at 40 transitions per frame to keep events responsive.

Rendering only reads state. Terrain is composed into an RGB array, converted to a Pygame surface, scaled through a camera, and decorated with organisms, direction marks, protection rings, The Chosen, fire/weather effects, and intervention previews. Visual animation uses frame counters only and never consumes the simulation RNG.

Headless mode repeatedly calls `World.run()` and saves on interval or signal. No SDL display is initialized because the graphical app import is lazy.

## Determinism contract

Determinism is scoped to the same supported Python/NumPy environment, seed, saved settings, initial state, and ordered interventions.

- One explicitly seeded NumPy `PCG64` generator owns all ecological random draws.
- The full bit-generator state is persisted and restored.
- IDs and lineage IDs are monotonic integers rather than random UUIDs.
- Organisms update in sorted ID order.
- Genome mutation iterates a fixed trait schema, not serialized dictionary order.
- Simulation time comes from ticks and supplied `dt`; wall time never enters ecology except as an explicit catch-up input.
- Rendering does not call the world RNG.
- `state_hash()` canonicalizes metadata and hashes every array's name, dtype, and contiguous bytes.

Tests prove same-seed/action equality and uninterrupted-versus-save/resume equality. Cross-architecture bitwise equality is not claimed because NumPy transcendental implementations may vary between x86 and ARM.

## Persistence boundary

A save occurs synchronously after a complete tick. `World.metadata()` serializes entities, genomes, lineages, RNG state, histories, counters, persisted settings, and the last wall-clock save time. Named arrays plus UTF-8 JSON metadata are encoded with `numpy.savez_compressed`; pickle is disabled on load.

SQLite holds snapshot generations rather than mutable entity tables. Saving performs:

1. encode one complete state;
2. compute SHA-256;
3. begin an immediate transaction;
4. insert the snapshot as incomplete;
5. mark it complete;
6. commit;
7. read back and verify checksum;
8. retain the newest configured generations;
9. request a passive WAL checkpoint.

Loading examines complete generations newest-first. It rejects bad checksums, unknown archive members, excessive sizes, unsupported schema versions, invalid shapes, non-finite grids, out-of-range normalized fields, and malformed neural shapes. A corrupt newest generation therefore falls back without mutating it.

The SQLite database schema and the world payload each have explicit version 1 identifiers. `migrations.py` owns ordered database migration.

## Offline catch-up

The repository records an epoch timestamp only as snapshot metadata. On reopening, elapsed time is clamped to non-negative and then to the configured one-hour cap. Natural missed ticks are bounded to 2,400 steps. If more ecological time must be covered, `dt = elapsed / steps` creates a deterministic reduced-fidelity batch. Graphical catch-up pumps quit events and renders progress. Completion produces a structured event; saving afterward prevents the same interval from being applied again.

## UI flow

The layout consists of a compact status instrument, central camera viewport, right contextual panel, and bounded field-notes strip. The right panel switches between terrain/life observation and divine instruments so the world stays dominant.

Mouse and Pygame finger events share hit testing. Camera mapping converts between screen and logical cells. Regional interventions are previewed with the configured logical radius before the same coordinates reach `World.apply_intervention()`.

Reset is a two-stage action. The UI or explicit CLI flag archives the previous database with a timestamp before a new world is saved.

## Performance and operational strategy

- Compact fixed-shape arrays and bounded entity/history counts.
- Vectorized plant, water, temperature, signal, and fire rules.
- No database writes for entity actions.
- Decimated metrics and event detector cadence.
- Snapshot and log retention.
- Screenshot retention of 40 images.
- Low-quality nearest-neighbor scaling and 20 FPS safe mode.
- Headless mode for background operation.
- Main-thread scheduling avoids Pygame/thread races and cross-thread SQLite connections.

Measured results are generated into `data/logs/`. They must be rerun on the target Raspberry Pi rather than extrapolated from Windows.

