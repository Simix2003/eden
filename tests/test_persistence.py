from __future__ import annotations

import sqlite3

from eden.persistence.repository import WorldRepository, perform_offline_catchup
from eden.simulation.world import World


def repository(settings, tmp_path) -> WorldRepository:
    settings.persistence.database_path = "eden-test.db"
    return WorldRepository(settings, tmp_path)


def test_save_restore_matches_exact_state(settings, tmp_path) -> None:
    repo = repository(settings, tmp_path)
    world = World(settings, seed=17)
    world.run(75)
    expected = world.state_hash()
    repo.save(world, now=1000.0)
    restored = repo.load_latest()
    assert restored.state_hash() == expected


def test_save_load_continuation_matches_uninterrupted(settings, tmp_path) -> None:
    repo = repository(settings, tmp_path)
    uninterrupted = World(settings, seed=18)
    resumed = World(settings, seed=18)
    uninterrupted.run(120)
    resumed.run(60)
    repo.save(resumed, now=1000.0)
    resumed = repo.load_latest()
    resumed.run(60)
    assert resumed.state_hash() == uninterrupted.state_hash()


def test_corrupt_latest_snapshot_falls_back_safely(settings, tmp_path) -> None:
    repo = repository(settings, tmp_path)
    world = World(settings, seed=19)
    world.run(10)
    repo.save(world, now=1000.0)
    expected = world.state_hash()
    world.run(10)
    latest_id = repo.save(world, now=1001.0)
    with sqlite3.connect(repo.path) as connection:
        connection.execute("UPDATE snapshots SET payload = ? WHERE id = ?", (b"corrupt", latest_id))
        connection.commit()
    restored = repo.load_latest()
    assert restored.state_hash() == expected


def test_incomplete_snapshot_is_ignored(settings, tmp_path) -> None:
    repo = repository(settings, tmp_path)
    world = World(settings, seed=20)
    repo.save(world, now=1000.0)
    with sqlite3.connect(repo.path) as connection:
        connection.execute(
            "INSERT INTO snapshots(created_at, tick, checksum, payload, complete) VALUES (?, ?, ?, ?, 0)",
            (1001.0, 99, "bad", b"partial"),
        )
        connection.commit()
    assert repo.load_latest().state_hash() == world.state_hash()


def test_offline_catchup_is_capped_and_bounded(settings) -> None:
    world = World(settings, seed=21)
    world.last_saved_at = 1000.0
    result = perform_offline_catchup(world, now=10_000.0)
    assert result.capped
    assert result.simulated_seconds == settings.persistence.offline_catchup_cap_seconds
    assert result.steps <= settings.persistence.offline_catchup_max_steps
    assert any(event.title == "Time passed beyond the glass" for event in world.events.events)

