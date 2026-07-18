from __future__ import annotations

import logging
from pathlib import Path
import time
import pygame

from eden.config import Settings, project_root
from eden.persistence.repository import WorldRepository, perform_offline_catchup
from eden.rendering.camera import Camera
from eden.rendering.palette import ACCENT, BACKGROUND, INK, MUTED, PANEL, PANEL_ALT, WARNING
from eden.rendering.renderer import WorldRenderer
from eden.simulation.world import World
from eden.ui.controls import Button, button_at
from eden.ui.god_panel import draw_god_panel
from eden.ui.history_panel import draw_history
from eden.ui.inspector import draw_inspector
from eden.ui.layout import calculate_layout

LOGGER = logging.getLogger(__name__)
SPEEDS = (0, 1, 5, 20, 100)


class EdenApp:
    """Main-thread Pygame host with separately scheduled simulation and render loops."""

    def __init__(self, settings: Settings, world: World, repository: WorldRepository, fullscreen: bool = False) -> None:
        pygame.init()
        pygame.display.set_caption("EDEN / Persistent Artificial World")
        self.settings = settings
        self.world = world
        self.repository = repository
        self.fullscreen = fullscreen
        self.screen = self._create_display()
        self.clock = pygame.time.Clock()
        self.running = True
        self.speed = 1
        self.previous_speed = 1
        self.accumulator = 0.0
        self.selected_id: int | None = None
        self.selected_cell: tuple[int, int] | None = None
        self.selected_tool: str | None = None
        self.god_panel_open = False
        self.history_open = True
        self.help_open = False
        self.reset_pending = False
        self.follow_selected = False
        self.dragging = False
        self.drag_last = (0, 0)
        self.last_save = time.monotonic()
        self.layout = calculate_layout(self.screen.get_size(), self.history_open)
        self.camera = Camera(world.shape[1], world.shape[0], self.layout.world)
        self.renderer = WorldRenderer(settings.ui.performance_mode)
        self.font = self._font(21, bold=True)
        self.small = self._font(15)
        self.tiny = self._font(12)
        self.large = self._font(38, bold=True)
        self.top_buttons: list[Button] = []
        self.panel_buttons: list[Button] = []

    def _font(self, size: int, bold: bool = False) -> pygame.font.Font:
        return pygame.font.SysFont("segoeui,dejavusans", max(10, int(size * self.settings.ui.ui_scale)), bold=bold)

    def _create_display(self) -> pygame.Surface:
        if self.fullscreen:
            return pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.DOUBLEBUF)
        return pygame.display.set_mode(
            (self.settings.ui.width, self.settings.ui.height), pygame.RESIZABLE | pygame.DOUBLEBUF
        )

    def run(self, catch_up: bool = True) -> int:
        if catch_up and self.world.last_saved_at is not None:
            self._catch_up_splash()
        try:
            while self.running:
                real_dt = min(0.2, self.clock.tick(self.settings.ui.render_fps) / 1000.0)
                self._handle_events()
                self._advance_simulation(real_dt)
                self._draw()
                if time.monotonic() - self.last_save >= self.settings.persistence.save_interval_seconds:
                    self._save()
            return 0
        finally:
            try:
                self._save()
            except Exception:
                LOGGER.exception("Final save failed")
            pygame.quit()

    def _catch_up_splash(self) -> None:
        def progress(current: int, total: int) -> None:
            for event in pygame.event.get((pygame.QUIT,)):
                if event.type == pygame.QUIT:
                    self.running = False
                    return
            self.screen.fill(BACKGROUND)
            title = self.large.render("EDEN IS REMEMBERING", True, INK)
            self.screen.blit(title, title.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() // 2 - 50)))
            message = self.small.render("Reconstructing the time that passed beyond the glass…", True, MUTED)
            self.screen.blit(message, message.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() // 2 + 3)))
            bar = pygame.Rect(self.screen.get_width() // 2 - 180, self.screen.get_height() // 2 + 42, 360, 8)
            pygame.draw.rect(self.screen, PANEL_ALT, bar, border_radius=4)
            fill = bar.copy()
            fill.width = int(bar.width * current / max(1, total))
            pygame.draw.rect(self.screen, ACCENT, fill, border_radius=4)
            pygame.display.flip()

        result = perform_offline_catchup(self.world, progress=progress)
        if result.steps:
            LOGGER.info("Offline catch-up advanced %.1f seconds in %d steps", result.simulated_seconds, result.steps)

    def _advance_simulation(self, real_dt: float) -> None:
        if self.speed == 0:
            return
        base_step = 1.0 / self.settings.simulation.tick_rate
        # At 100x, five seconds of ecological time are integrated per fixed quantum.
        # This is the documented reduced-fidelity fast-forward path used to protect the Pi UI.
        coarse = 5.0 if self.speed == 100 else 1.0
        scheduled_speed = 20 if self.speed == 100 else self.speed
        self.accumulator += real_dt * scheduled_speed
        steps = 0
        while self.accumulator >= base_step and steps < 40:
            self.world.step(base_step * coarse)
            self.accumulator -= base_step
            steps += 1
        if steps == 40:
            self.accumulator = min(self.accumulator, base_step * 40)
        if self.follow_selected and self.selected_id in self.world.organisms:
            organism = self.world.organisms[self.selected_id]
            self.camera.follow(organism.x, organism.y)
        if self.selected_id is not None and self.selected_id not in self.world.organisms:
            self.selected_id = None
            self.follow_selected = False

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.VIDEORESIZE and not self.fullscreen:
                self.screen = pygame.display.set_mode(event.size, pygame.RESIZABLE | pygame.DOUBLEBUF)
                self._update_layout()
            elif event.type == pygame.KEYDOWN:
                self._handle_key(event)
            elif event.type == pygame.MOUSEWHEEL:
                self.camera.zoom_at(1.18 if event.y > 0 else 1 / 1.18, pygame.mouse.get_pos())
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    self._handle_press(event.pos)
                elif event.button in (2, 3):
                    self.dragging = True
                    self.drag_last = event.pos
            elif event.type == pygame.MOUSEBUTTONUP and event.button in (1, 2, 3):
                self.dragging = False
            elif event.type == pygame.MOUSEMOTION and self.dragging:
                dx = event.pos[0] - self.drag_last[0]
                dy = event.pos[1] - self.drag_last[1]
                self.camera.pan_pixels(dx, dy)
                self.drag_last = event.pos
            elif event.type == pygame.FINGERDOWN:
                position = (int(event.x * self.screen.get_width()), int(event.y * self.screen.get_height()))
                self._handle_press(position)

    def _handle_key(self, event: pygame.event.Event) -> None:
        if self.reset_pending:
            if event.key == pygame.K_RETURN:
                self._confirm_reset()
            elif event.key == pygame.K_ESCAPE:
                self.reset_pending = False
            return
        if event.key == pygame.K_ESCAPE:
            if self.help_open:
                self.help_open = False
            elif self.selected_tool:
                self.selected_tool = None
            elif self.god_panel_open:
                self.god_panel_open = False
            else:
                self.running = False
        elif event.key == pygame.K_SPACE:
            if self.speed == 0:
                self.speed = self.previous_speed or 1
            else:
                self.previous_speed, self.speed = self.speed, 0
        elif pygame.K_1 <= event.key <= pygame.K_5:
            self.speed = SPEEDS[event.key - pygame.K_1]
            if self.speed:
                self.previous_speed = self.speed
        elif event.key == pygame.K_g:
            self.god_panel_open = not self.god_panel_open
        elif event.key == pygame.K_h:
            self.help_open = not self.help_open
        elif event.key == pygame.K_e:
            self.history_open = not self.history_open
            self._update_layout()
        elif event.key == pygame.K_F11:
            self.fullscreen = not self.fullscreen
            self.screen = self._create_display()
            self._update_layout()
        elif event.key == pygame.K_F12:
            self._take_screenshot()
        elif event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
            self.camera.zoom_at(1.2, self.layout.world.center)
        elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.camera.zoom_at(1 / 1.2, self.layout.world.center)
        elif event.key == pygame.K_LEFT:
            self.camera.pan_pixels(35, 0)
        elif event.key == pygame.K_RIGHT:
            self.camera.pan_pixels(-35, 0)
        elif event.key == pygame.K_UP:
            self.camera.pan_pixels(0, 35)
        elif event.key == pygame.K_DOWN:
            self.camera.pan_pixels(0, -35)
        elif event.key == pygame.K_n and event.mod & pygame.KMOD_CTRL and event.mod & pygame.KMOD_SHIFT:
            self.reset_pending = True

    def _handle_press(self, position: tuple[int, int]) -> None:
        top_key = button_at(self.top_buttons, position)
        if top_key:
            if top_key.startswith("speed:"):
                self.speed = int(top_key.split(":", 1)[1])
                if self.speed:
                    self.previous_speed = self.speed
            elif top_key == "god":
                self.god_panel_open = not self.god_panel_open
            elif top_key == "history":
                self.history_open = not self.history_open
                self._update_layout()
            elif top_key == "help":
                self.help_open = not self.help_open
            return
        panel_key = button_at(self.panel_buttons, position)
        if panel_key:
            self._handle_panel_action(panel_key)
            return
        if not self.layout.world.collidepoint(position):
            return
        wx, wy = self.camera.screen_to_world(*position)
        if not (0 <= wx < self.world.shape[1] and 0 <= wy < self.world.shape[0]):
            return
        if self.selected_tool:
            if self.world.apply_intervention(self.selected_tool, wx, wy):
                self.selected_cell = (int(wx), int(wy))
            return
        nearest_id = self._nearest_organism(position)
        if nearest_id is not None:
            self.selected_id = nearest_id
            self.selected_cell = None
            self.god_panel_open = False
        else:
            self.selected_id = None
            self.follow_selected = False
            self.selected_cell = (int(wx), int(wy))

    def _handle_panel_action(self, key: str) -> None:
        if key in {"rain", "drought", "plants", "fire", "extinguish", "water", "spawn", "smite", "heat", "cold"}:
            self.selected_tool = None if self.selected_tool == key else key
        elif key == "reset":
            self.reset_pending = True
        elif self.selected_id in self.world.organisms:
            organism = self.world.organisms[self.selected_id]
            if key == "choose":
                self.world.choose(self.selected_id)
            elif key == "bless":
                self.world.bless(self.selected_id, not organism.protected)
            elif key == "mutate":
                self.world.mutate_organism(self.selected_id)
            elif key == "follow":
                self.follow_selected = not self.follow_selected
                if self.follow_selected:
                    self.camera.zoom = max(2.0, self.camera.zoom)
                    self.camera.follow(organism.x, organism.y)
            elif key == "close":
                self.selected_id = None
                self.follow_selected = False

    def _nearest_organism(self, position: tuple[int, int]) -> int | None:
        best: tuple[float, int] | None = None
        for organism in self.world.organisms.values():
            sx, sy = self.camera.world_to_screen(organism.x, organism.y)
            distance = (sx - position[0]) ** 2 + (sy - position[1]) ** 2
            if distance <= 18**2 and (best is None or distance < best[0]):
                best = (distance, organism.organism_id)
        return best[1] if best else None

    def _draw(self) -> None:
        preview = None
        mouse = pygame.mouse.get_pos()
        if self.selected_tool and self.layout.world.collidepoint(mouse):
            wx, wy = self.camera.screen_to_world(*mouse)
            preview = (wx, wy, float(self.settings.interventions.radius))
        self.renderer.draw(self.screen, self.world, self.camera, selected_id=self.selected_id, preview=preview)
        self._draw_top()
        organism = self.world.organisms.get(self.selected_id) if self.selected_id is not None else None
        if self.god_panel_open:
            self.panel_buttons = draw_god_panel(
                self.screen, self.layout.side, self.font, self.small, self.selected_tool
            )
        else:
            self.panel_buttons = draw_inspector(
                self.screen,
                self.layout.side,
                self.world,
                organism,
                self.selected_cell,
                self.font,
                self.small,
                self.tiny,
            )
        if self.history_open:
            draw_history(self.screen, self.layout.history, self.world, self.small, self.tiny)
        if self.help_open:
            self._draw_help()
        if self.reset_pending:
            self._draw_reset_confirmation()
        pygame.display.flip()

    def _draw_top(self) -> None:
        rect = self.layout.top
        pygame.draw.rect(self.screen, PANEL, rect, border_radius=8)
        pygame.draw.rect(self.screen, (48, 59, 53), rect, 1, border_radius=8)
        self.screen.blit(self.font.render("EDEN", True, INK), (rect.x + 15, rect.y + 9))
        save_word = "ERROR" if "failed" in self.world.save_status else ("NEW" if self.world.save_status == "new world" else "SAVED")
        subtitle = self.tiny.render(f"WORLD {self.world.seed}  /  DAY {self.world.age_days:07.2f}  /  {save_word}", True, MUTED)
        self.screen.blit(subtitle, (rect.x + 15, rect.y + 39))
        counts = Counter(item.lineage_id for item in self.world.organisms.values())
        dominant = counts.most_common(1)[0][0] if counts else 0
        chosen = self.world.organisms.get(self.world.chosen_id) if self.world.chosen_id else None
        metrics = [
            ("LIFE", str(len(self.world.organisms))),
            ("SPECIES", str(len(counts))),
            ("BIRTH / DEATH", f"{self.world.total_births} / {self.world.total_deaths}"),
            ("DOMINANT", f"L-{dominant:03d}" if dominant else "—"),
            ("CLIMATE", f"{self.world.season[:3]} / {self.world.weather.value[:5]}"),
            ("CHOSEN", chosen.short_name if chosen else "none"),
        ]
        x = rect.x + 218
        available_right = rect.right - 470
        item_width = max(82, (available_right - x) // len(metrics))
        for label, value in metrics:
            self.screen.blit(self.tiny.render(label, True, MUTED), (x, rect.y + 9))
            self.screen.blit(self.small.render(value.upper(), True, INK), (x, rect.y + 31))
            x += item_width
        self.top_buttons = []
        button_x = rect.right - 453
        for speed in SPEEDS:
            button = Button(
                f"speed:{speed}",
                "II" if speed == 0 else f"{speed}×",
                pygame.Rect(button_x, rect.y + 11, 48, 43),
                active=self.speed == speed,
            )
            button.draw(self.screen, self.small)
            self.top_buttons.append(button)
            button_x += 53
        for key, label in (("god", "GOD"), ("history", "LOG"), ("help", "?")):
            width = 61 if key != "help" else 43
            button = Button(
                key,
                label,
                pygame.Rect(button_x, rect.y + 11, width, 43),
                active=(key == "god" and self.god_panel_open) or (key == "history" and self.history_open),
            )
            button.draw(self.screen, self.small)
            self.top_buttons.append(button)
            button_x += width + 7

    def _draw_help(self) -> None:
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((3, 6, 5, 218))
        panel = pygame.Rect(0, 0, min(720, self.screen.get_width() - 70), min(570, self.screen.get_height() - 70))
        panel.center = overlay.get_rect().center
        pygame.draw.rect(overlay, (18, 24, 21, 250), panel, border_radius=14)
        pygame.draw.rect(overlay, (*ACCENT, 170), panel, 1, border_radius=14)
        overlay.blit(self.large.render("HOW TO OBSERVE EDEN", True, INK), (panel.x + 38, panel.y + 31))
        lines = (
            "TOUCH / CLICK   Inspect a creature or terrain cell",
            "RIGHT DRAG      Pan the world     ·     WHEEL / + −   Zoom",
            "G               Divine instruments and intervention preview",
            "SPACE           Pause / resume   ·     1–5   Select time speed",
            "E               Toggle field notes history",
            "F11             Toggle fullscreen",
            "F12             Save a screenshot",
            "CTRL+SHIFT+N    Begin the deliberate new-world confirmation",
            "ESC             Cancel a tool, close this guide, or leave EDEN",
            "",
            "At 100×, EDEN uses bounded reduced-fidelity integration so the display",
            "remains responsive. Every intervention and notable event enters history.",
        )
        for index, line in enumerate(lines):
            overlay.blit(self.small.render(line, True, INK if index < 9 else MUTED), (panel.x + 40, panel.y + 105 + index * 31))
        close = self.small.render("PRESS H OR ESC TO CLOSE", True, ACCENT)
        overlay.blit(close, (panel.centerx - close.get_width() // 2, panel.bottom - 42))
        self.screen.blit(overlay, (0, 0))

    def _draw_reset_confirmation(self) -> None:
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((9, 3, 2, 220))
        panel = pygame.Rect(0, 0, 620, 220)
        panel.center = overlay.get_rect().center
        pygame.draw.rect(overlay, (49, 24, 19), panel, border_radius=12)
        pygame.draw.rect(overlay, (*WARNING, 210), panel, 2, border_radius=12)
        title = self.font.render("CREATE A NEW WORLD?", True, WARNING)
        overlay.blit(title, title.get_rect(center=(panel.centerx, panel.y + 49)))
        message = self.small.render("The current database will be archived, not erased.", True, INK)
        overlay.blit(message, message.get_rect(center=(panel.centerx, panel.y + 95)))
        prompt = self.small.render("ENTER TO CONFIRM   ·   ESC TO CANCEL", True, ACCENT)
        overlay.blit(prompt, prompt.get_rect(center=(panel.centerx, panel.y + 157)))
        self.screen.blit(overlay, (0, 0))

    def _confirm_reset(self) -> None:
        self._save()
        archived = self.repository.archive_for_new_world()
        LOGGER.warning("World reset confirmed; previous database archived at %s", archived)
        self.world = World(self.settings)
        self.selected_id = None
        self.selected_cell = None
        self.selected_tool = None
        self.reset_pending = False
        self.follow_selected = False
        self.camera = Camera(self.world.shape[1], self.world.shape[0], self.layout.world)
        self._save()

    def _save(self) -> None:
        try:
            self.repository.save(self.world)
            self.last_save = time.monotonic()
        except Exception:
            LOGGER.exception("EDEN could not save the current world")

    def _take_screenshot(self) -> None:
        directory = project_root() / "data" / "screenshots"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / time.strftime("eden-%Y%m%d-%H%M%S.png", time.localtime())
        pygame.image.save(self.screen, path)
        screenshots = sorted(directory.glob("eden-*.png"), key=lambda item: item.stat().st_mtime)
        for old in screenshots[:-40]:
            old.unlink(missing_ok=True)
        self.world.save_status = f"screenshot {path.name}"

    def _update_layout(self) -> None:
        previous_center = (float(self.camera.center_x), float(self.camera.center_y))
        previous_zoom = self.camera.zoom
        self.layout = calculate_layout(self.screen.get_size(), self.history_open)
        self.camera = Camera(
            self.world.shape[1], self.world.shape[0], self.layout.world, previous_center[0], previous_center[1], previous_zoom
        )
        self.camera.clamp()


# Local import avoids paying for collections in headless mode before Pygame starts.
from collections import Counter
