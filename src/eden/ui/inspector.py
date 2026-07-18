from __future__ import annotations

import pygame

from eden.rendering.palette import ACCENT, INK, MUTED, PANEL
from eden.ui.controls import Button


def _bar(surface: pygame.Surface, rect: pygame.Rect, fraction: float, color: tuple[int, int, int]) -> None:
    pygame.draw.rect(surface, (34, 42, 38), rect, border_radius=4)
    fill = rect.copy()
    fill.width = int(rect.width * max(0.0, min(1.0, fraction)))
    pygame.draw.rect(surface, color, fill, border_radius=4)


def draw_inspector(
    surface: pygame.Surface,
    rect: pygame.Rect,
    world: object,
    organism: object | None,
    selected_cell: tuple[int, int] | None,
    font: pygame.font.Font,
    small: pygame.font.Font,
    tiny: pygame.font.Font,
) -> list[Button]:
    pygame.draw.rect(surface, PANEL, rect, border_radius=9)
    pygame.draw.rect(surface, (50, 63, 56), rect, 1, border_radius=9)
    buttons: list[Button] = []
    if organism is None:
        surface.blit(font.render("OBSERVATION", True, INK), (rect.x + 18, rect.y + 17))
        if selected_cell is None:
            lines = ["Touch a creature to follow its life.", "Touch terrain to read local conditions.", "Press G to open divine instruments."]
            for index, line in enumerate(lines):
                surface.blit(small.render(line, True, MUTED), (rect.x + 18, rect.y + 58 + index * 27))
        else:
            x, y = selected_cell
            terrain_names = ("water", "fertile soil", "dry soil", "rock")
            values = [
                ("CELL", f"{x:03d}, {y:03d}"),
                ("TERRAIN", terrain_names[int(world.terrain[y, x])]),
                ("PLANT BIOMASS", f"{world.plants[y, x]:.2f}"),
                ("MOISTURE", f"{world.moisture[y, x]:.2f}"),
                ("FERTILITY", f"{world.fertility[y, x]:.2f}"),
                ("TEMPERATURE", f"{world.temperature[y, x]:.1f}°C"),
                ("WATER", f"{world.water[y, x]:.2f}"),
                ("FIRE", f"{world.fire[y, x]:.2f}"),
            ]
            for index, (label, value) in enumerate(values):
                surface.blit(tiny.render(label, True, MUTED), (rect.x + 18, rect.y + 58 + index * 31))
                text = small.render(value, True, INK)
                surface.blit(text, (rect.right - 18 - text.get_width(), rect.y + 54 + index * 31))
        return buttons

    surface.blit(font.render(organism.short_name, True, INK), (rect.x + 18, rect.y + 16))
    subtitle = f"LINEAGE {organism.lineage_id:03d}  ·  GENERATION {organism.generation}  ·  {organism.current_action.upper()}"
    surface.blit(tiny.render(subtitle, True, ACCENT), (rect.x + 18, rect.y + 45))
    stats = (
        ("ENERGY", organism.energy / organism.genome.traits["max_energy"], (184, 214, 112)),
        ("HYDRATION", organism.hydration / 100.0, (91, 171, 191)),
        ("HEALTH", organism.health / 100.0, (219, 123, 99)),
    )
    y = rect.y + 77
    for label, fraction, color in stats:
        surface.blit(tiny.render(label, True, MUTED), (rect.x + 18, y))
        _bar(surface, pygame.Rect(rect.x + 102, y + 1, rect.width - 122, 10), fraction, color)
        y += 27
    details = (
        ("AGE", f"{organism.age:.1f}s / {organism.genome.traits['lifespan']:.0f}s"),
        ("CHILDREN", str(organism.children_count)),
        ("PARENT", f"#{organism.parent_id}" if organism.parent_id else "founder"),
        ("POSITION", f"{organism.x:.1f}, {organism.y:.1f}"),
        ("SPEED / SIZE", f"{organism.genome.traits['speed']:.2f} / {organism.genome.traits['size']:.2f}"),
        ("METABOLISM", f"{organism.genome.traits['metabolism']:.2f}"),
        ("TEMPERATURE", f"prefers {organism.genome.traits['preferred_temperature']:.1f}°C"),
        ("STATUS", "THE CHOSEN" if organism.organism_id == world.chosen_id else ("blessed" if organism.protected else "mortal")),
    )
    for label, value in details:
        surface.blit(tiny.render(label, True, MUTED), (rect.x + 18, y))
        rendered = tiny.render(value, True, INK)
        surface.blit(rendered, (rect.right - 18 - rendered.get_width(), y))
        y += 23

    # Compact trait signature: eleven bars, intentionally excluding raw neural weights.
    signature_y = y + 8
    surface.blit(tiny.render("GENOME SIGNATURE", True, MUTED), (rect.x + 18, signature_y))
    values = list(organism.genome.traits.values())
    for index, value in enumerate(values):
        normalized = (abs(float(value)) * (0.17 + index * 0.037)) % 1.0
        bar = pygame.Rect(rect.x + 18 + index * 23, signature_y + 19, 15, 12 + int(normalized * 27))
        pygame.draw.rect(surface, organism.color, bar, border_radius=2)

    bottom = rect.bottom - 112
    labels = (("choose", "CHOOSE"), ("bless", "BLESS" if not organism.protected else "UNBLESS"), ("mutate", "MUTATE"))
    button_width = (rect.width - 52) // 3
    for index, (key, label) in enumerate(labels):
        button = Button(key, label, pygame.Rect(rect.x + 18 + index * (button_width + 8), bottom, button_width, 39), active=key == "choose" and organism.organism_id == world.chosen_id)
        button.draw(surface, tiny)
        buttons.append(button)
    follow = Button("follow", "FOLLOW WITH CAMERA", pygame.Rect(rect.x + 18, bottom + 48, rect.width - 80, 39))
    close = Button("close", "×", pygame.Rect(rect.right - 53, bottom + 48, 35, 39))
    follow.draw(surface, tiny)
    close.draw(surface, font)
    buttons.extend((follow, close))
    return buttons

