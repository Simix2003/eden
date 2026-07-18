from __future__ import annotations

import math
import pygame

from eden.constants import Weather


def draw_weather(screen: pygame.Surface, viewport: pygame.Rect, weather: Weather, frame: int) -> None:
    if weather == Weather.RAIN:
        overlay = pygame.Surface(viewport.size, pygame.SRCALPHA)
        for index in range(42):
            x = (index * 97 + frame * 9) % max(1, viewport.width)
            y = (index * 53 + frame * 15) % max(1, viewport.height)
            pygame.draw.line(overlay, (139, 190, 203, 80), (x, y), (x - 4, y + 11), 1)
        screen.blit(overlay, viewport.topleft)
    elif weather in (Weather.HEATWAVE, Weather.COLD):
        tint = (155, 74, 28, 18) if weather == Weather.HEATWAVE else (80, 145, 174, 18)
        overlay = pygame.Surface(viewport.size, pygame.SRCALPHA)
        overlay.fill(tint)
        screen.blit(overlay, viewport.topleft)

    # A restrained animated scan line gives the display an instrument-like depth.
    scan_y = viewport.top + int((math.sin(frame * 0.015) * 0.5 + 0.5) * viewport.height)
    pygame.draw.line(screen, (47, 61, 50), (viewport.left, scan_y), (viewport.right, scan_y), 1)
