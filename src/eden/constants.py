from __future__ import annotations

from enum import Enum, IntEnum


class Terrain(IntEnum):
    WATER = 0
    FERTILE = 1
    DRY = 2
    ROCK = 3


class Weather(str, Enum):
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAIN = "rain"
    DROUGHT = "drought"
    HEATWAVE = "heatwave"
    COLD = "cold period"


SEASONS = ("spring", "summer", "autumn", "winter")

ACTION_NAMES = (
    "move",
    "turn left",
    "turn right",
    "eat",
    "drink",
    "rest",
    "reproduce",
    "signal",
)

INPUT_COUNT = 16
HIDDEN_COUNT = 10
OUTPUT_COUNT = len(ACTION_NAMES)

