from __future__ import annotations

import math
import pygame

from eden.rendering.camera import Camera
from eden.rendering.effects import draw_weather
from eden.rendering.palette import ACCENT, BACKGROUND, WARNING, world_rgb


class WorldRenderer:
    def __init__(self, performance_mode: str = "balanced") -> None:
        self.performance_mode = performance_mode
        self.frame = 0

    def draw(
        self,
        screen: pygame.Surface,
        world: object,
        camera: Camera,
        *,
        selected_id: int | None,
        preview: tuple[float, float, float] | None,
    ) -> None:
        self.frame += 1
        screen.fill(BACKGROUND)
        rgb = world_rgb(world)
        base = pygame.surfarray.make_surface(rgb.swapaxes(0, 1))
        scale = camera.scale
        width = max(1, int(world.shape[1] * scale))
        height = max(1, int(world.shape[0] * scale))
        if self.performance_mode == "low":
            map_surface = pygame.transform.scale(base, (width, height))
        else:
            map_surface = pygame.transform.smoothscale(base, (width, height))
        origin = camera.origin
        old_clip = screen.get_clip()
        screen.set_clip(camera.viewport)
        screen.blit(map_surface, (int(origin[0]), int(origin[1])))

        for organism in world.organisms.values():
            sx, sy = camera.world_to_screen(organism.x, organism.y)
            if not camera.viewport.collidepoint(sx, sy):
                continue
            radius = max(2, int((2.0 + organism.genome.traits["size"] * 1.7) * min(1.8, camera.zoom**0.35)))
            pygame.draw.circle(screen, (7, 11, 9), (sx + 1, sy + 2), radius + 1)
            pygame.draw.circle(screen, organism.color, (sx, sy), radius)
            direction = (
                sx + int(math.cos(organism.orientation) * radius * 1.8),
                sy + int(math.sin(organism.orientation) * radius * 1.8),
            )
            pygame.draw.line(screen, (229, 239, 221), (sx, sy), direction, 1)
            if organism.protected:
                pygame.draw.circle(screen, (122, 188, 196), (sx, sy), radius + 3, 1)
            if organism.organism_id == world.chosen_id:
                pulse = radius + 5 + int((math.sin(self.frame * 0.08) + 1.0) * 1.5)
                pygame.draw.circle(screen, ACCENT, (sx, sy), pulse, 2)
                pygame.draw.line(screen, ACCENT, (sx, sy - pulse - 5), (sx, sy - pulse - 1), 2)
            if organism.organism_id == selected_id:
                pygame.draw.circle(screen, (245, 247, 236), (sx, sy), radius + 5, 1)

        if preview is not None:
            px, py = camera.world_to_screen(preview[0], preview[1])
            radius = max(2, int(preview[2] * scale))
            overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            pygame.draw.circle(overlay, (*WARNING, 35), (px, py), radius)
            pygame.draw.circle(overlay, (*WARNING, 190), (px, py), radius, 2)
            screen.blit(overlay, (0, 0))
        draw_weather(screen, camera.viewport, world.weather, self.frame)
        screen.set_clip(old_clip)
        pygame.draw.rect(screen, (49, 60, 55), camera.viewport, 1, border_radius=3)

