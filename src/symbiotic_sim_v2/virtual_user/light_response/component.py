"""GUI-independent Stage 7 light-responsive virtual-user component."""

from __future__ import annotations

import hashlib
import json
from bisect import bisect_right
from dataclasses import asdict, dataclass

from symbiotic_sim_v2.devices.virtual_light.events import (
    parse_light_stimulus_state_event,
)
from symbiotic_sim_v2.domain.event_priorities import (
    HEARTBEAT_EVENT_PRIORITY,
    SIMULATION_COMPLETE_EVENT_PRIORITY,
)
from symbiotic_sim_v2.domain.event_types import (
    HEARTBEAT_EVENT_TYPE,
    SIMULATION_COMPLETE_EVENT_TYPE,
)
from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.simulation.engine import SimulationEngine
from symbiotic_sim_v2.simulation.scheduler import EventScheduler
from symbiotic_sim_v2.simulation.time_utils import us_to_seconds
from symbiotic_sim_v2.virtual_user.component import (
    HEARTBEAT_EVENT_SOURCE,
    VirtualUserComponent,
)
from symbiotic_sim_v2.virtual_user.config import VirtualUserConfig
from symbiotic_sim_v2.virtual_user.light_response.config import LightResponseConfig
from symbiotic_sim_v2.virtual_user.light_response.dynamics import (
    first_order_response_at,
    transition_time_constant_seconds,
)
from symbiotic_sim_v2.virtual_user.light_response.physical_projection import (
    PhysicalLightStimulus,
    inactive_physical_light_stimulus,
    project_physical_light_stimulus,
)
from symbiotic_sim_v2.virtual_user.light_response.physiology import (
    LightResponsiveRriComputation,
    calculate_light_responsive_next_rri,
    effective_physiology,
)
from symbiotic_sim_v2.virtual_user.light_response.preference import (
    LightPreferenceMatch,
    evaluate_light_preference,
    response_target_for,
)
from symbiotic_sim_v2.virtual_user.light_response.records import (
    LightResponseSample,
    LightResponseSegment,
    LightResponsiveHeartbeatRecord,
    LightStimulusReceiptRecord,
)
from symbiotic_sim_v2.virtual_user.light_response.state import (
    LightResponsiveVirtualUserSnapshot,
)


@dataclass(frozen=True, slots=True)
class _ResponseEpoch:
    start_time_us: int
    response_at_start: float
    response_target: float
    time_constant_seconds: float | None
    stimulus: PhysicalLightStimulus
    preference: LightPreferenceMatch


@dataclass(frozen=True, slots=True)
class _PendingLightComputation:
    sample_time_us: int
    stimulus: PhysicalLightStimulus
    preference: LightPreferenceMatch
    response_target: float
    responsive: LightResponsiveRriComputation


class LightResponsiveVirtualUserComponent(VirtualUserComponent):
    """Emit only formal heartbeats while light modifies future interval physiology."""

    def __init__(
        self,
        virtual_user_config: VirtualUserConfig,
        light_response_config: LightResponseConfig,
    ) -> None:
        if not isinstance(virtual_user_config, VirtualUserConfig):
            raise TypeError("virtual_user_config must be a VirtualUserConfig")
        if not isinstance(light_response_config, LightResponseConfig):
            raise TypeError("light_response_config must be a LightResponseConfig")
        super().__init__(virtual_user_config)
        self.virtual_user_config = virtual_user_config
        self.light_response_config = light_response_config
        self.reset()

    def reset(self) -> None:
        """Restore baseline physiology and every light-response diagnostic history."""

        super().reset()
        initial_stimulus = inactive_physical_light_stimulus()
        initial_preference = evaluate_light_preference(
            initial_stimulus,
            self.light_response_config,
        )
        self._responsive_records: list[LightResponsiveHeartbeatRecord] = []
        self._light_receipts: list[LightStimulusReceiptRecord] = []
        self._response_segments: list[LightResponseSegment] = []
        self._physical_history: list[PhysicalLightStimulus] = []
        self._physical_times_us: list[int] = []
        self._response_epochs: list[_ResponseEpoch] = [
            _ResponseEpoch(
                start_time_us=0,
                response_at_start=0.0,
                response_target=0.0,
                time_constant_seconds=None,
                stimulus=initial_stimulus,
                preference=initial_preference,
            )
        ]
        self._response_epoch_times_us: list[int] = [0]
        self._pending_light_computation: _PendingLightComputation | None = None
        self._seen_source_signal_indices: set[int] = set()
        self._response_target_change_count = 0
        self._latest_observed_time_us = 0
        self._completed = False

    def schedule_initial(self, scheduler: EventScheduler) -> SimulationEvent:
        """Schedule the unchanged formal beat-zero boundary."""

        return super().schedule_initial(scheduler)

    def handle_heartbeat(self, event: SimulationEvent, engine: SimulationEngine) -> None:
        """Retain causal diagnostics around the shared Stage 2 heartbeat handler."""

        if self._completed:
            raise RuntimeError("completed light-responsive user cannot accept heartbeats")
        if event.scheduled_time_us < self._latest_observed_time_us:
            raise RuntimeError("heartbeat time cannot move backwards")
        pending_for_arriving_interval = self._pending_light_computation
        super().handle_heartbeat(event, engine)
        base_record = self._records[-1]
        if pending_for_arriving_interval is None:
            sample_time_us = event.scheduled_time_us
            stimulus = self._physical_at(sample_time_us)
            preference = evaluate_light_preference(stimulus, self.light_response_config)
            target = response_target_for(
                stimulus,
                preference,
                self.light_response_config,
            )
            response = self.response_at(sample_time_us)
            physiology_values = effective_physiology(
                self.virtual_user_config,
                self.light_response_config,
                response,
            )
        else:
            sample_time_us = pending_for_arriving_interval.sample_time_us
            stimulus = pending_for_arriving_interval.stimulus
            preference = pending_for_arriving_interval.preference
            target = pending_for_arriving_interval.response_target
            response = pending_for_arriving_interval.responsive.response_level
            responsive = pending_for_arriving_interval.responsive
            physiology_values = (
                responsive.base_mean_rri_ms,
                responsive.effective_mean_rri_ms,
                responsive.mean_rri_increase_ms,
                responsive.base_respiratory_amplitude_ms,
                responsive.effective_respiratory_amplitude_ms,
                responsive.respiratory_amplitude_gain_ms,
            )
        (
            base_mean,
            effective_mean,
            mean_increase,
            base_amplitude,
            effective_amplitude,
            amplitude_gain,
        ) = physiology_values
        self._responsive_records.append(
            LightResponsiveHeartbeatRecord(
                **base_record.to_dict(),
                response_sample_time_us=sample_time_us,
                light_active_at_heartbeat=stimulus.active,
                perceived_render_hue_degree=stimulus.render_hue_degree,
                perceived_blink_bpm=stimulus.blink_bpm,
                hue_match=preference.hue_match,
                bpm_match=preference.bpm_match,
                preference_match=preference.preference_match,
                response_target=target,
                response_level=response,
                base_mean_rri_ms=base_mean,
                effective_mean_rri_ms=effective_mean,
                mean_rri_increase_ms=mean_increase,
                base_respiratory_amplitude_ms=base_amplitude,
                effective_respiratory_amplitude_ms=effective_amplitude,
                respiratory_amplitude_gain_ms=amplitude_gain,
                heartbeat_causality_policy_version=(
                    self.light_response_config.heartbeat_causality_policy_version
                ),
                schema_version=self.light_response_config.responsive_heartbeat_schema_version,
            )
        )
        self._latest_observed_time_us = event.scheduled_time_us

    def handle_light_stimulus_state(
        self,
        event: SimulationEvent,
        _engine: SimulationEngine,
    ) -> None:
        """Validate one formal Stage 6 state without touching a pending heartbeat."""

        if self._completed:
            raise RuntimeError("completed light-responsive user cannot accept light input")
        state = parse_light_stimulus_state_event(event)
        if state.schema_version != self.light_response_config.input_schema_version:
            raise ValueError("light state schema differs from light-response config")
        if state.effective_time_us > self.light_response_config.simulation_end_time_us:
            raise ValueError("light input exceeds the Stage 7 simulation end")
        if (
            self._light_receipts
            and state.effective_time_us <= self._light_receipts[-1].event_time_us
        ):
            raise ValueError("light input times must be strictly increasing")
        if state.effective_time_us < self._latest_observed_time_us:
            raise ValueError("light input time cannot move component time backwards")
        if state.source_signal_index in self._seen_source_signal_indices:
            raise ValueError("duplicate light source signal index")

        stimulus = project_physical_light_stimulus(state)
        preference = evaluate_light_preference(stimulus, self.light_response_config)
        target = response_target_for(stimulus, preference, self.light_response_config)
        response_before = self.response_at(state.effective_time_us)
        current_epoch = self._response_epochs[-1]
        target_changed = target != current_epoch.response_target
        if target_changed:
            self._close_current_segment(state.effective_time_us)
            new_epoch = _ResponseEpoch(
                start_time_us=state.effective_time_us,
                response_at_start=response_before,
                response_target=target,
                time_constant_seconds=transition_time_constant_seconds(
                    response_before,
                    target,
                    self.light_response_config,
                ),
                stimulus=stimulus,
                preference=preference,
            )
            self._response_epochs.append(new_epoch)
            self._response_epoch_times_us.append(state.effective_time_us)
            self._response_target_change_count += 1

        response_after = self.response_at(state.effective_time_us)
        if response_after != response_before:
            raise RuntimeError("light input caused a discontinuous response jump")
        self._physical_history.append(stimulus)
        self._physical_times_us.append(state.effective_time_us)
        self._seen_source_signal_indices.add(state.source_signal_index)
        self._light_receipts.append(
            LightStimulusReceiptRecord(
                receipt_index=len(self._light_receipts),
                event_time_us=state.effective_time_us,
                source_signal_index=state.source_signal_index,
                active=state.active,
                qualification_holder_id=state.qualification_holder_id,
                source_b=state.source_b,
                physical_stimulus=stimulus,
                hue_match=preference.hue_match,
                bpm_match=preference.bpm_match,
                preference_match=preference.preference_match,
                response_target=target,
                target_changed=target_changed,
                response_before=response_before,
                response_after_at_same_time=response_after,
                provenance_used_by_physiology=False,
                physical_projection_version=(
                    self.light_response_config.physical_projection_version
                ),
                preference_model_version=self.light_response_config.preference_model_version,
                input_schema_version=self.light_response_config.input_schema_version,
            )
        )
        self._latest_observed_time_us = state.effective_time_us

    def handle_simulation_complete(
        self,
        event: SimulationEvent,
        _engine: SimulationEngine,
    ) -> None:
        """Close the last positive-duration response interval exactly once."""

        if event.event_type != SIMULATION_COMPLETE_EVENT_TYPE:
            raise ValueError("completion handler received the wrong event type")
        if event.priority != SIMULATION_COMPLETE_EVENT_PRIORITY:
            raise ValueError("completion priority does not match the stable boundary")
        if event.scheduled_time_us != self.light_response_config.simulation_end_time_us:
            raise ValueError("completion time does not match simulation_end_time_us")
        if self._completed:
            raise RuntimeError("light-responsive user is already completed")
        if event.scheduled_time_us < self._latest_observed_time_us:
            raise RuntimeError("completion time cannot move backwards")
        self._close_current_segment(event.scheduled_time_us)
        self._validate_response_segments()
        self._latest_observed_time_us = event.scheduled_time_us
        self._completed = True

    def response_at(self, time_us: int) -> float:
        """Evaluate historical or current latent response analytically."""

        if isinstance(time_us, bool) or not isinstance(time_us, int):
            raise TypeError("time_us must be an integer")
        if not 0 <= time_us <= self.light_response_config.simulation_end_time_us:
            raise ValueError("time_us must be within the Stage 7 simulation interval")
        epoch_index = bisect_right(self._response_epoch_times_us, time_us) - 1
        epoch = self._response_epochs[epoch_index]
        return first_order_response_at(
            time_us,
            start_time_us=epoch.start_time_us,
            response_at_start=epoch.response_at_start,
            target=epoch.response_target,
            time_constant_seconds=epoch.time_constant_seconds,
        )

    def snapshot(self) -> LightResponsiveVirtualUserSnapshot:
        """Return a frozen read model without exposing mutable histories."""

        latest = self._records[-1] if self._records else None
        time_us = self._latest_observed_time_us
        stimulus = self._physical_at(time_us)
        preference = evaluate_light_preference(stimulus, self.light_response_config)
        target = response_target_for(stimulus, preference, self.light_response_config)
        response = self.response_at(time_us)
        (
            base_mean,
            effective_mean,
            mean_increase,
            base_amplitude,
            effective_amplitude,
            amplitude_gain,
        ) = effective_physiology(
            self.virtual_user_config,
            self.light_response_config,
            response,
        )
        return LightResponsiveVirtualUserSnapshot(
            user_id=self.config.user_id,
            base_model_version=self.config.model_version,
            light_response_model_version=self.light_response_config.model_version,
            heartbeat_count=len(self._records),
            current_heartbeat_time_us=(latest.heartbeat_time_us if latest else None),
            latest_true_rri_ms=(latest.true_rri_ms if latest else None),
            latest_instantaneous_hr_bpm=(
                latest.instantaneous_hr_bpm if latest else None
            ),
            current_light_active=stimulus.active,
            current_render_hue_degree=stimulus.render_hue_degree,
            current_blink_bpm=stimulus.blink_bpm,
            current_hue_match=preference.hue_match,
            current_bpm_match=preference.bpm_match,
            current_preference_match=preference.preference_match,
            current_response_target=target,
            current_response_level=response,
            base_respiratory_amplitude_ms=base_amplitude,
            effective_respiratory_amplitude_ms=effective_amplitude,
            current_respiratory_gain_ms=amplitude_gain,
            base_mean_rri_ms=base_mean,
            effective_mean_rri_ms=effective_mean,
            current_mean_rri_increase_ms=mean_increase,
            light_input_count=len(self._light_receipts),
            response_target_change_count=self._response_target_change_count,
            response_segment_count=self._visible_response_segment_count(),
            clamped_beat_count=self._clamped_beat_count,
            completed=self._completed,
        )

    def responsive_heartbeat_records(self) -> tuple[LightResponsiveHeartbeatRecord, ...]:
        return tuple(self._responsive_records)

    def light_receipt_records(self) -> tuple[LightStimulusReceiptRecord, ...]:
        return tuple(self._light_receipts)

    def response_segments(self) -> tuple[LightResponseSegment, ...]:
        return tuple(self._response_segments)

    def response_samples(self) -> tuple[LightResponseSample, ...]:
        """Return the required 0..240 s grid only after formal completion."""

        if not self._completed:
            raise RuntimeError("response samples require a completed simulation")
        return self.response_samples_through(self.light_response_config.simulation_end_time_us)

    def response_samples_through(self, time_us: int) -> tuple[LightResponseSample, ...]:
        """Derive a diagnostic grid through an observed time without engine events."""

        if isinstance(time_us, bool) or not isinstance(time_us, int):
            raise TypeError("time_us must be an integer")
        if not 0 <= time_us <= self._latest_observed_time_us:
            raise ValueError("time_us must be within observed response history")
        interval_us = self.light_response_config.diagnostic_sample_interval_us
        return tuple(
            self._sample_at(sample_index, sample_index * interval_us)
            for sample_index in range(time_us // interval_us + 1)
        )

    def responsive_diagnostic_digest(self) -> str:
        return self._digest([record.to_dict() for record in self._responsive_records])

    def light_receipt_digest(self) -> str:
        return self._digest(
            [
                {
                    "event_time_us": record.event_time_us,
                    "physical_stimulus": asdict(record.physical_stimulus),
                    "hue_match": record.hue_match,
                    "bpm_match": record.bpm_match,
                    "preference_match": record.preference_match,
                    "response_target": record.response_target,
                    "target_changed": record.target_changed,
                    "response_before": record.response_before,
                    "provenance_used_by_physiology": (
                        record.provenance_used_by_physiology
                    ),
                    "physical_projection_version": record.physical_projection_version,
                    "preference_model_version": record.preference_model_version,
                }
                for record in self._light_receipts
            ]
        )

    def response_segment_digest(self) -> str:
        return self._digest([record.to_dict() for record in self._response_segments])

    def response_sample_digest(self) -> str:
        return self._digest([record.to_dict() for record in self.response_samples()])

    def _schedule_next_if_in_bounds(
        self,
        event: SimulationEvent,
        engine: SimulationEngine,
    ) -> None:
        if event.scheduled_time_us >= engine.clock.end_time_us:
            self._pending_light_computation = None
            return
        sample_time_us = event.scheduled_time_us
        stimulus = self._physical_at(sample_time_us)
        preference = evaluate_light_preference(stimulus, self.light_response_config)
        target = response_target_for(stimulus, preference, self.light_response_config)
        responsive = calculate_light_responsive_next_rri(
            self.virtual_user_config,
            self.light_response_config,
            sample_time_us,
            len(self._records) - 1,
            self._correlated_state,
            self.response_at(sample_time_us),
        )
        next_time_us = sample_time_us + responsive.computation.rri_us
        if next_time_us > engine.clock.end_time_us:
            self._pending_computation = None
            self._pending_light_computation = None
            return
        self._correlated_state = responsive.computation.next_correlated_state
        self._pending_computation = responsive.computation
        self._pending_light_computation = _PendingLightComputation(
            sample_time_us=sample_time_us,
            stimulus=stimulus,
            preference=preference,
            response_target=target,
            responsive=responsive,
        )
        engine.schedule_at(
            next_time_us,
            HEARTBEAT_EVENT_TYPE,
            source=HEARTBEAT_EVENT_SOURCE,
            priority=HEARTBEAT_EVENT_PRIORITY,
            payload={"user_id": self.config.user_id, "beat_index": len(self._records)},
        )

    def _close_current_segment(self, end_time_us: int) -> None:
        epoch = self._response_epochs[-1]
        if end_time_us < epoch.start_time_us:
            raise RuntimeError("response segment end precedes its start")
        if end_time_us == epoch.start_time_us:
            return
        self._response_segments.append(
            LightResponseSegment(
                segment_index=len(self._response_segments),
                start_time_us=epoch.start_time_us,
                end_time_us=end_time_us,
                duration_us=end_time_us - epoch.start_time_us,
                light_active=epoch.stimulus.active,
                render_hue_degree=epoch.stimulus.render_hue_degree,
                blink_bpm=epoch.stimulus.blink_bpm,
                hue_match=epoch.preference.hue_match,
                bpm_match=epoch.preference.bpm_match,
                preference_match=epoch.preference.preference_match,
                response_target=epoch.response_target,
                response_at_start=epoch.response_at_start,
                response_at_end=self.response_at(end_time_us),
                time_constant_seconds=epoch.time_constant_seconds,
                preference_model_version=self.light_response_config.preference_model_version,
                response_dynamics_version=self.light_response_config.response_dynamics_version,
                schema_version=self.light_response_config.response_segment_schema_version,
            )
        )

    def _physical_at(self, time_us: int) -> PhysicalLightStimulus:
        physical_index = bisect_right(self._physical_times_us, time_us) - 1
        if physical_index < 0:
            return inactive_physical_light_stimulus()
        return self._physical_history[physical_index]

    def _sample_at(self, sample_index: int, time_us: int) -> LightResponseSample:
        stimulus = self._physical_at(time_us)
        preference = evaluate_light_preference(stimulus, self.light_response_config)
        target = response_target_for(stimulus, preference, self.light_response_config)
        response = self.response_at(time_us)
        (
            _base_mean,
            effective_mean,
            _mean_increase,
            _base_amplitude,
            effective_amplitude,
            _amplitude_gain,
        ) = effective_physiology(
            self.virtual_user_config,
            self.light_response_config,
            response,
        )
        return LightResponseSample(
            sample_index=sample_index,
            time_us=time_us,
            time_seconds=us_to_seconds(time_us),
            light_active=stimulus.active,
            render_hue_degree=stimulus.render_hue_degree,
            blink_bpm=stimulus.blink_bpm,
            preference_match=preference.preference_match,
            response_target=target,
            response_level=response,
            effective_respiratory_amplitude_ms=effective_amplitude,
            effective_mean_rri_ms=effective_mean,
        )

    def _validate_response_segments(self) -> None:
        previous_end = 0
        previous_response: float | None = None
        for index, segment in enumerate(self._response_segments):
            if segment.segment_index != index:
                raise RuntimeError("response segment indices are not contiguous")
            if segment.start_time_us != previous_end or segment.end_time_us <= previous_end:
                raise RuntimeError("response segments have a gap, overlap, or empty interval")
            if (
                previous_response is not None
                and segment.response_at_start != previous_response
            ):
                raise RuntimeError("response segments are discontinuous")
            previous_end = segment.end_time_us
            previous_response = segment.response_at_end
        if previous_end != self.light_response_config.simulation_end_time_us:
            raise RuntimeError("response segments do not cover the complete simulation")

    def _visible_response_segment_count(self) -> int:
        if self._completed:
            return len(self._response_segments)
        current = self._response_epochs[-1]
        return len(self._response_segments) + int(
            self._latest_observed_time_us > current.start_time_us
            or current.start_time_us == 0
        )

    @staticmethod
    def _digest(records: list[dict[str, object]]) -> str:
        encoded = json.dumps(
            records,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
