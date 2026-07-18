# EDEN v0.1 simulation rules

These are the rules implemented by the current code. Values are configurable where noted.

## Time

- Default controller/environment rate: 8 ticks per second.
- Default day: 480 ticks (60 seconds at 1×).
- Default season: 7,200 ticks; spring, summer, autumn, and winter repeat.
- Weather lasts 320–1,100 ticks, selected by deterministic weighted sampling with seasonal adjustments.
- Pause, 1×, 5×, and 20× use 0.125-second ecological quanta. 100× and offline catch-up use bounded reduced-fidelity quanta.

## Initial world

Two deterministic coherent-noise fields combine into elevation and wetness. The bottom 19% elevation quantile becomes connected lowland water. High elevated detail becomes rock. Low wetness becomes dry soil; other traversable cells become fertile soil.

Water depth is based on distance below the water line. Moisture combines wetness and water, then five inexpensive neighbor-dilation passes create wet shores. Fertility combines wetness and inverse elevation, with penalties for dry soil and rock. Initial plants are fertility × moisture × local detail and are removed from water/rock.

## Light, temperature, seasons, and weather

Daylight is `max(0.04, sin(day_phase × π))`. Cloud and rain multiply it by 0.68.

Base cell temperature is:

```text
18 − elevation × 11 + seasonal shift + weather shift + divine modifier
```

The seasonal shift is a sine wave with amplitude 7.5. Heatwaves add 8.5; cold periods subtract 9. A divine modifier lasts 60 default seconds.

Rain raises traversable moisture by `0.030 × dt` and lake water by `0.014 × dt`. Drought lowers moisture by `0.006 × dt` and water by `0.0015 × dt`. Other weather evaporates moisture at a small season-adjusted rate. Each tick, local and orthogonal-neighbor water provides a smaller moisture influence.

## Plants

Temperature comfort is `clip(1 − |temperature − 19| / 24, 0, 1)`.

Plant suitability is:

```text
sunlight × moisture × fertility × temperature comfort
```

Growth is logistic:

```text
plant_growth_rate × suitability × plants × (1 − plants) × dt
```

Four-neighbor plant mean drives configured spread. A very small suitability-scaled seed bank permits regrowth from zero after favorable conditions return. Suitability below 0.14 causes bounded stress loss. Plants remain in [0, 1] and cannot grow in water or rock.

Eating removes real local biomass. Energy gained is consumed biomass × 24, limited by the genome's food-efficiency trait and maximum energy.

## Fire and recovery

Fire can be ignited only where fuel exists and the cell is not water. Orthogonal neighbor intensity, fuel, dryness, `dt`, and a deterministic random draw control spread. Burning consumes `fire × 0.22 × dt` biomass and produces ash. Fire decays from a base loss plus additional loss when fuel is gone or moisture is high. It expires naturally at zero. Ash fades slowly, and the seed bank/spread allow later plant recovery.

Fire at an organism's cell removes up to `fire × 24 × dt` health before protection. Fire can be extinguished mechanically by rain over time or immediately by the divine quench tool.

## Organism controller

Every organism has 16 normalized inputs:

1. energy ratio;
2. hydration;
3. age/lifespan;
4. health;
5. local temperature comfort;
6. plants underfoot;
7. plants ahead;
8. water underfoot;
9. nearby water;
10. obstacle ahead;
11. local organism density;
12. local signal;
13–14. two memory values;
15. orientation sine;
16. deterministic noise.

The controller applies `tanh(inputs × W1 + b1)`, then `tanh(hidden × W2 + b2)`. The highest of eight outputs selects move, left, right, eat, drink, rest, reproduce, or signal.

Bounded survival reflex biases keep the tiny random initial brains viable: available food is favored when energy is low, drinking is favored when dehydrated beside water, obstacles favor a deterministic-random turn, and physiologically ready organisms favor reproduction. The neural outputs still determine choices outside these urgent conditions and are inherited/mutated.

Movement is continuous in logical-cell coordinates and uses genome speed. Water and rock reject entry. Eating and drinking require actual plant/water arrays. A signal raises the local field, which decays every environment tick. Rest gives a very small energy recovery.

## Physiology and death

Traits include speed, size, maximum energy, lifespan, vision, preferred temperature, metabolism, reproductive cost, food efficiency, hue, and mutation rate. Every mutation is clipped to documented bounds in `genome.py`; neural values are clipped to [-3, 3].

Energy cost per second is:

```text
base_metabolism × metabolism trait × size × dt
```

Hydration cost is `(0.18 + metabolism × 0.08) × dt`. Movement and signaling add small energy costs. Energy and hydration stop at zero; continued deficit removes health. Temperature outside a nine-degree comfort band removes health. Old age, starvation, dehydration, temperature stress, and fire record explicit causes.

The Chosen or a blessed organism receives the configured 8% reduction to vital damage/cost, applied once even if both. Health can slowly recover. The Chosen remains subject to age and disaster unless `chosen_immortal` is explicitly enabled.

## Reproduction and evolution

Reproduction requires minimum age, cooldown completion, free traversable space, available population capacity, and enough energy for both the genome's reproductive cost and an energy ratio threshold.

The threshold is density-sensitive:

```text
base ratio + 0.20 × (population / maximum population)²
```

and is capped at 0.90. This creates pressure before the hard population cap rather than allowing unchecked exponential birth.

The parent pays reproductive energy and enters cooldown. A child receives a new monotonic ID, parent ID, next generation, reduced starting energy, inherited lineage, inherited Chosen ancestry, and a mutated genome.

Each trait and neural value has a deterministic mutation mask. The effective mask rate averages global and inherited mutation rates. Trait changes scale to each legal range. Genome distance combines normalized trait distance (70%) and neural distance (30%). Distance beyond the configured lineage baseline threshold creates a new lineage and event.

## Events and bounded history

Events are generated from state, not invented prose. Each stores tick, category, severity, title, description, relevant IDs, and numeric evidence. Keys and cooldowns suppress duplicates.

Implemented detectors cover world awakening, first birth/death, age records, population milestones/crash, lineage emergence/extinction/dominance, migration, severe drought, major fire, fire recovery, divine actions, offline catch-up, Chosen selection/death, and marked descendants.

The event list defaults to 300, metrics to 720, death summaries to 300, interventions to 200, snapshots to five, screenshots to 40, and living population to 260.

## Divine interventions

- **Rain:** raises regional moisture and lake water.
- **Drought:** removes regional moisture and water.
- **Seed Life:** raises plant biomass and fertility on soil.
- **Ignite:** starts fire only where fuel exists.
- **Quench:** removes fire and adds moisture.
- **Make Water:** converts non-rock cells to water, clears plants, and relocates stranded organisms if space exists.
- **Call Life:** creates a new founder genome and lineage when capacity/space allows.
- **Smite:** removes 82% of regional plants and 58 health from organisms, but does not bypass the one-health safety floor immediately.
- **Warm/Cool:** applies a global ± configured temperature modifier for 60 seconds.
- **Choose/Bless/Mutate:** operate on an inspected organism and enter event history.

