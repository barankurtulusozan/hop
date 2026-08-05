from __future__ import annotations

import json
import logging
import time
import uuid

from src.domain.distill import TrajectoryRecord

logger = logging.getLogger("llm_orchestrator.distill")


class TrajectoryHarvester:
    """Trajectory harvester for continuous online model distillation dataset generation."""

    def __init__(self, min_score_threshold: float = 0.9):
        self.min_score_threshold = min_score_threshold
        self._harvested_records: list[TrajectoryRecord] = []

    def record_trajectory(
        self,
        input_prompt: str,
        completion_output: str,
        system_prompt: str = "You are a helpful assistant.",
        eval_score: float = 1.0,
    ) -> TrajectoryRecord | None:
        if eval_score < self.min_score_threshold:
            logger.info(f"Discarding trajectory (score={eval_score:.2f} < threshold={self.min_score_threshold})")
            return None

        rec = TrajectoryRecord(
            trajectory_id=f"traj_{uuid.uuid4().hex[:10]}",
            input_prompt=input_prompt,
            system_prompt=system_prompt,
            completion_output=completion_output,
            eval_score=eval_score,
            created_at=time.time(),
        )
        self._harvested_records.append(rec)
        logger.info(f"Harvested high-quality trajectory '{rec.trajectory_id}' (eval_score={eval_score})")
        return rec

    def get_records(self) -> list[TrajectoryRecord]:
        return list(self._harvested_records)

    def export_jsonl(self) -> str:
        lines: list[str] = []
        for rec in self._harvested_records:
            entry = {
                "messages": [
                    {"role": "system", "content": rec.system_prompt},
                    {"role": "user", "content": rec.input_prompt},
                    {"role": "assistant", "content": rec.completion_output},
                ]
            }
            lines.append(json.dumps(entry))
        return "\n".join(lines)
