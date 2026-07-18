from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
import hashlib
import json
import logging
from pathlib import Path
import shutil
import time
from typing import Callable
import zipfile
import numpy as np

from eden.config import Settings, project_root, settings_from_dict
from eden.persistence.database import connect
from eden.simulation.world import ARRAY_NAMES, World

LOGGER = logging.getLogger(__name__)
MAX_SNAPSHOT_BYTES = 256 * 1024 * 1024


def _resolve_database_path(settings: Settings, root: Path | None = None) -> Path:
    configured = Path(settings.persistence.database_path)
    if configured.is_absolute():
        return configured
    base = root or project_root()
    resolved = (base / configured).resolve()
    if base.resolve() not in resolved.parents and resolved != base.resolve():
        raise ValueError("database_path must remain inside the project root")
    return resolved


def _encode(world: World, saved_at: float) -> bytes:
    world.last_saved_at = saved_at
    metadata = world.metadata(include_clock=True)
    text = json.dumps(metadata, sort_keys=True, separators=(",", ":"), allow_nan=False)
    payload: dict[str, np.ndarray] = {name: np.ascontiguousarray(getattr(world, name)) for name in ARRAY_NAMES}
    payload["__metadata__"] = np.asarray(text)
    buffer = BytesIO()
    np.savez_compressed(buffer, **payload)
    encoded = buffer.getvalue()
    if len(encoded) > MAX_SNAPSHOT_BYTES:
        raise ValueError("snapshot exceeds the 256 MB safety limit")
    return encoded


def _decode(settings: Settings, payload: bytes) -> World:
    if not payload or len(payload) > MAX_SNAPSHOT_BYTES:
        raise ValueError("invalid snapshot size")
    with zipfile.ZipFile(BytesIO(payload)) as container:
        if sum(item.file_size for item in container.infolist()) > MAX_SNAPSHOT_BYTES * 2:
            raise ValueError("snapshot expands beyond the safety limit")
    with np.load(BytesIO(payload), allow_pickle=False) as archive:
        names = set(archive.files)
        required = set(ARRAY_NAMES) | {"__metadata__"}
        if names != required:
            raise ValueError(f"snapshot fields do not match schema: {sorted(names ^ required)}")
        metadata_text = str(np.asarray(archive["__metadata__"]).item())
        if len(metadata_text) > 64 * 1024 * 1024:
            raise ValueError("snapshot metadata is unexpectedly large")
        metadata = json.loads(metadata_text)
        arrays = {name: np.asarray(archive[name]).copy() for name in ARRAY_NAMES}
    snapshot_settings = settings_from_dict(metadata["settings"], settings.source_path)
    return World.from_snapshot(snapshot_settings, metadata, arrays)


class WorldRepository:
    def __init__(self, settings: Settings, root: Path | None = None) -> None:
        self.settings = settings
        self.path = _resolve_database_path(settings, root)

    def has_save(self) -> bool:
        if not self.path.exists():
            return False
        try:
            with connect(self.path) as connection:
                return connection.execute("SELECT 1 FROM snapshots WHERE complete = 1 LIMIT 1").fetchone() is not None
        except Exception:
            LOGGER.exception("Could not inspect save database")
            return False

    def save(self, world: World, now: float | None = None) -> int:
        saved_at = time.time() if now is None else float(now)
        payload = _encode(world, saved_at)
        checksum = hashlib.sha256(payload).hexdigest()
        connection = connect(self.path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "INSERT INTO snapshots(created_at, tick, checksum, payload, complete) VALUES (?, ?, ?, ?, 0)",
                (saved_at, world.tick, checksum, payload),
            )
            snapshot_id = int(cursor.lastrowid)
            connection.execute("UPDATE snapshots SET complete = 1 WHERE id = ?", (snapshot_id,))
            connection.commit()
            row = connection.execute("SELECT checksum, payload FROM snapshots WHERE id = ? AND complete = 1", (snapshot_id,)).fetchone()
            if row is None or row[0] != checksum or hashlib.sha256(row[1]).hexdigest() != checksum:
                raise IOError("snapshot verification failed after commit")
            keep = self.settings.persistence.retained_snapshots
            connection.execute(
                "DELETE FROM snapshots WHERE id NOT IN (SELECT id FROM snapshots WHERE complete = 1 ORDER BY id DESC LIMIT ?)",
                (keep,),
            )
            connection.commit()
            connection.execute("PRAGMA wal_checkpoint(PASSIVE)")
            world.save_status = f"saved at tick {world.tick}"
            return snapshot_id
        except Exception:
            connection.rollback()
            world.save_status = "save failed"
            raise
        finally:
            connection.close()

    def load_latest(self) -> World:
        connection = connect(self.path)
        try:
            rows = connection.execute(
                "SELECT id, checksum, payload FROM snapshots WHERE complete = 1 ORDER BY id DESC"
            ).fetchall()
        finally:
            connection.close()
        errors: list[str] = []
        for snapshot_id, checksum, payload in rows:
            try:
                actual = hashlib.sha256(payload).hexdigest()
                if actual != checksum:
                    raise ValueError("checksum mismatch")
                world = _decode(self.settings, payload)
                world.save_status = f"restored snapshot {snapshot_id}"
                return world
            except Exception as exc:
                errors.append(f"snapshot {snapshot_id}: {exc}")
                LOGGER.warning("Skipping invalid EDEN snapshot %s: %s", snapshot_id, exc)
        detail = "; ".join(errors) if errors else "database contains no complete snapshots"
        raise RuntimeError(f"no valid EDEN snapshot found ({detail})")

    def archive_for_new_world(self) -> Path | None:
        if not self.path.exists():
            return None
        try:
            connection = connect(self.path)
            connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            connection.close()
        except Exception:
            LOGGER.exception("Could not checkpoint the database before archiving; preserving all available files")
        stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime())
        archive = self.path.with_name(f"{self.path.stem}.reset-{stamp}{self.path.suffix}")
        counter = 1
        while archive.exists():
            archive = self.path.with_name(f"{self.path.stem}.reset-{stamp}-{counter}{self.path.suffix}")
            counter += 1
        shutil.move(str(self.path), str(archive))
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(self.path) + suffix)
            if sidecar.exists():
                sidecar.unlink()
        return archive


@dataclass(slots=True)
class CatchupResult:
    elapsed_seconds: float
    simulated_seconds: float
    steps: int
    capped: bool


def perform_offline_catchup(
    world: World,
    *,
    now: float | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> CatchupResult:
    if world.last_saved_at is None:
        return CatchupResult(0.0, 0.0, 0, False)
    current = time.time() if now is None else float(now)
    raw_elapsed = max(0.0, current - float(world.last_saved_at))
    cap = float(world.settings.persistence.offline_catchup_cap_seconds)
    elapsed = min(raw_elapsed, cap)
    capped = raw_elapsed > cap
    if elapsed < 1.0:
        return CatchupResult(raw_elapsed, 0.0, 0, capped)
    natural_steps = max(1, int(round(elapsed * world.settings.simulation.tick_rate)))
    steps = min(natural_steps, world.settings.persistence.offline_catchup_max_steps)
    dt = elapsed / steps
    world.run(steps, progress=progress, dt=dt)
    world.events.add(
        world.tick,
        "world",
        "info",
        "Time passed beyond the glass",
        f"EDEN advanced {elapsed / 60.0:.1f} minutes while the display was closed"
        + (" (the configured safety cap was reached)." if capped else "."),
        key=f"offline-catchup:{world.tick}",
        data={"elapsed_seconds": raw_elapsed, "simulated_seconds": elapsed, "steps": steps, "capped": int(capped)},
    )
    return CatchupResult(raw_elapsed, elapsed, steps, capped)
