from __future__ import annotations

from dataclasses import dataclass
import pygame


@dataclass(slots=True)
class Camera:
    world_width: int
    world_height: int
    viewport: pygame.Rect
    center_x: float | None = None
    center_y: float | None = None
    zoom: float = 1.0

    def __post_init__(self) -> None:
        self.center_x = self.world_width / 2 if self.center_x is None else self.center_x
        self.center_y = self.world_height / 2 if self.center_y is None else self.center_y

    @property
    def scale(self) -> float:
        return min(self.viewport.width / self.world_width, self.viewport.height / self.world_height) * self.zoom

    @property
    def origin(self) -> tuple[float, float]:
        return (
            self.viewport.centerx - float(self.center_x) * self.scale,
            self.viewport.centery - float(self.center_y) * self.scale,
        )

    def world_to_screen(self, x: float, y: float) -> tuple[int, int]:
        ox, oy = self.origin
        return int(ox + x * self.scale), int(oy + y * self.scale)

    def screen_to_world(self, x: float, y: float) -> tuple[float, float]:
        ox, oy = self.origin
        return (x - ox) / self.scale, (y - oy) / self.scale

    def zoom_at(self, factor: float, screen_position: tuple[int, int]) -> None:
        before = self.screen_to_world(*screen_position)
        self.zoom = max(0.85, min(8.0, self.zoom * factor))
        after = self.screen_to_world(*screen_position)
        self.center_x = float(self.center_x) + before[0] - after[0]
        self.center_y = float(self.center_y) + before[1] - after[1]
        self.clamp()

    def pan_pixels(self, dx: float, dy: float) -> None:
        self.center_x = float(self.center_x) - dx / self.scale
        self.center_y = float(self.center_y) - dy / self.scale
        self.clamp()

    def follow(self, x: float, y: float) -> None:
        self.center_x, self.center_y = x, y
        self.clamp()

    def clamp(self) -> None:
        half_visible_x = self.viewport.width / (2 * self.scale)
        half_visible_y = self.viewport.height / (2 * self.scale)
        if half_visible_x >= self.world_width / 2:
            self.center_x = self.world_width / 2
        else:
            self.center_x = max(half_visible_x, min(self.world_width - half_visible_x, float(self.center_x)))
        if half_visible_y >= self.world_height / 2:
            self.center_y = self.world_height / 2
        else:
            self.center_y = max(half_visible_y, min(self.world_height - half_visible_y, float(self.center_y)))

