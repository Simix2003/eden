from __future__ import annotations

from dataclasses import dataclass
import pygame

from eden.rendering.palette import ACCENT, INK, MUTED, PANEL_ALT, WARNING


@dataclass(slots=True)
class Button:
    key: str
    label: str
    rect: pygame.Rect
    active: bool = False
    danger: bool = False
    enabled: bool = True

    def draw(self, surface: pygame.Surface, font: pygame.font.Font) -> None:
        if self.active:
            background = (54, 70, 48)
            border = ACCENT
            color = INK
        elif self.danger:
            background = (61, 34, 27)
            border = WARNING
            color = (239, 197, 172)
        else:
            background = PANEL_ALT
            border = (55, 67, 61)
            color = INK if self.enabled else MUTED
        pygame.draw.rect(surface, background, self.rect, border_radius=7)
        pygame.draw.rect(surface, border, self.rect, 1, border_radius=7)
        text = font.render(self.label, True, color)
        surface.blit(text, text.get_rect(center=self.rect.center))


def button_at(buttons: list[Button], position: tuple[int, int]) -> str | None:
    for button in buttons:
        if button.enabled and button.rect.collidepoint(position):
            return button.key
    return None

