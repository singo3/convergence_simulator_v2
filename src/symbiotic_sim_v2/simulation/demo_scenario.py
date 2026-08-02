"""Twenty-second diagnostic scenario for the Stage 1 time foundation only."""

from __future__ import annotations

from dataclasses import dataclass

from symbiotic_sim_v2.domain.event_priorities import SIMULATION_COMPLETE_EVENT_PRIORITY
from symbiotic_sim_v2.domain.event_types import SIMULATION_COMPLETE_EVENT_TYPE
from symbiotic_sim_v2.simulation.scheduler import EventScheduler
from symbiotic_sim_v2.simulation.time_utils import MICROSECONDS_PER_SECOND

DEMO_DURATION_US = 20 * MICROSECONDS_PER_SECOND
TICK_PRIORITY = 10
SAME_TIME_A_PRIORITY = 20
SAME_TIME_B_PRIORITY = 30
MARKER_PRIORITY = 40
COMPLETION_PRIORITY = SIMULATION_COMPLETE_EVENT_PRIORITY
DEMO_SOURCE = "stage_01_diagnostic"


@dataclass(frozen=True, slots=True)
class DemoScenario:
    """A deterministic diagnostic schedule, not a physiological system model."""

    start_time_us: int = 0
    end_time_us: int = DEMO_DURATION_US

    def schedule(self, scheduler: EventScheduler) -> None:
        """Populate all 26 diagnostic events in a reproducible registration order."""

        for second in range(21):
            scheduler.schedule_at(
                second * MICROSECONDS_PER_SECOND,
                "clock_tick",
                source=DEMO_SOURCE,
                priority=TICK_PRIORITY,
                payload={"diagnostic_only": True, "tick_index": second},
            )

        scheduler.schedule_at(
            2_500_000,
            "demo_marker",
            source=DEMO_SOURCE,
            priority=MARKER_PRIORITY,
            payload={"label": "2.5秒マーカー"},
        )

        # Register B first on purpose: A still executes first because priority wins.
        scheduler.schedule_at(
            7_300_000,
            "demo_same_time_b",
            source=DEMO_SOURCE,
            priority=SAME_TIME_B_PRIORITY,
            payload={"label": "同時刻B", "registration": "first"},
        )
        scheduler.schedule_at(
            7_300_000,
            "demo_same_time_a",
            source=DEMO_SOURCE,
            priority=SAME_TIME_A_PRIORITY,
            payload={"label": "同時刻A", "registration": "second"},
        )

        scheduler.schedule_at(
            12_750_000,
            "demo_marker",
            source=DEMO_SOURCE,
            priority=MARKER_PRIORITY,
            payload={"label": "12.75秒マーカー"},
        )
        scheduler.schedule_at(
            DEMO_DURATION_US,
            SIMULATION_COMPLETE_EVENT_TYPE,
            source=DEMO_SOURCE,
            priority=COMPLETION_PRIORITY,
            payload={"diagnostic_only": True, "status": "complete"},
        )


def create_demo_engine():
    """Create a freshly loaded engine without importing any GUI dependency."""

    from symbiotic_sim_v2.simulation.engine import SimulationEngine

    return SimulationEngine(DemoScenario())
