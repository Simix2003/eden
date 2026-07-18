from __future__ import annotations

import pygame

from eden.rendering.palette import INK, MUTED, PANEL


def draw_history(surface: pygame.Surface, rect: pygame.Rect, world: object, font: pygame.font.Font, small: pygame.font.Font) -> None:
    pygame.draw.rect(surface, PANEL, rect, border_radius=8)
    pygame.draw.rect(surface, (47, 58, 53), rect, 1, border_radius=8)
    title = font.render("FIELD NOTES  /  RECENT EVENTS", True, INK)
    surface.blit(title, (rect.x + 14, rect.y + 8))
    events = world.events.events[-2:]
    for index, event in enumerate(reversed(events)):
        color = (230, 157, 104) if event.severity in ("warning", "major") else MUTED
        text = small.render(f"T+{event.tick:06d}  {event.title.upper()} — {event.description}", True, color)
        clipped = text.subsurface((0, 0, min(text.get_width(), rect.width - 28), text.get_height()))
        surface.blit(clipped, (rect.x + 14, rect.y + 35 + index * 23))

