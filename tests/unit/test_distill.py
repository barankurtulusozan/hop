import json
import pytest

from src.distill.harvester import TrajectoryHarvester


def test_trajectory_harvester():
    harvester = TrajectoryHarvester(min_score_threshold=0.85)

    # High score trajectory -> recorded
    rec1 = harvester.record_trajectory(
        input_prompt="Explain RAG",
        completion_output="RAG combines dense vector retrieval with LLM generation.",
        eval_score=0.95,
    )
    assert rec1 is not None

    # Low score trajectory -> discarded
    rec2 = harvester.record_trajectory(
        input_prompt="Bad query",
        completion_output="Incorrect output",
        eval_score=0.50,
    )
    assert rec2 is None

    records = harvester.get_records()
    assert len(records) == 1

    jsonl_output = harvester.export_jsonl()
    assert "messages" in jsonl_output
    parsed = json.loads(jsonl_output)
    assert parsed["messages"][1]["content"] == "Explain RAG"
