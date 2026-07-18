from __future__ import annotations

import pygame

from eden.rendering.palette import INK, MUTED, PANEL
from eden.ui.controls import Button

TOOLS = (
    ("rain", "RAIN"),
    ("drought", "DROUGHT"),
    ("plants", "SEED LIFE"),
    ("fire", "IGNITE"),
    ("extinguish", "QUENCH"),
    ("water", "MAKE WATER"),
    ("spawn", "CALL LIFE"),
    ("smite", "SMITE"),
    ("heat", "WARM"),
    ("cold", "COOL"),
)


def draw_god_panel(
    surface: pygame.Surface,
    rect: pygame.Rect,
    font: pygame.font.Font,
    small: pygame.font.Font,
    selected_tool: str | None,
) -> list[Button]:
    pygame.draw.rect(surface, PANEL, rect, border_radius=9)
    pygame.draw.rect(surface, (50, 63, 56), rect, 1, border_radius=9)
    surface.blit(font.render("DIVINE INSTRUMENTS", True, INK), (rect.x + 18, rect.y + 17))
    surface.blit(small.render("Choose a force, then touch the world.", True, MUTED), (rect.x + 18, rect.y + 45))
    buttons: list[Button] = []
    gap = 8
    button_width = (rect.width - 36 - gap) // 2
    for index, (key, label) in enumerate(TOOLS):
        col, row = index % 2, index // 2
        button = Button(
            key,
            label,
            pygame.Rect(rect.x + 18 + col * (button_width + gap), rect.y + 76 + row * 49, button_width, 41),
            active=selected_tool == key,
            danger=key in ("fire", "drought", "smite"),
        )
        button.draw(surface, small)
        buttons.append(button)
    reset = Button("reset", "RESET WORLD", pygame.Rect(rect.x + 18, rect.bottom - 54, rect.width - 36, 37), danger=True)
    reset.draw(surface, small)
    buttons.append(reset)
    return buttons

