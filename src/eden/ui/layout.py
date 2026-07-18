from __future__ import annotations

from dataclasses import dataclass
import pygame


@dataclass(slots=True)
class Layout:
    top: pygame.Rect
    world: pygame.Rect
    side: pygame.Rect
    history: pygame.Rect


def calculate_layout(size: tuple[int, int], show_history: bool = True) -> Layout:
    width, height = size
    margin = max(12, int(min(width, height) * 0.016))
    top_height = max(74, int(height * 0.09))
    side_width = min(354, max(300, int(width * 0.235)))
    history_height = max(92, int(height * 0.12)) if show_history else 0
    top = pygame.Rect(margin, margin, width - margin * 2, top_height - margin)
    world = pygame.Rect(margin, top_height, width - side_width - margin * 3, height - top_height - history_height - margin)
    side = pygame.Rect(world.right + margin, top_height, side_width, height - top_height - margin)
    history = pygame.Rect(margin, world.bottom + margin, world.width, max(0, history_height - margin * 2))
    return Layout(top, world, side, history)

