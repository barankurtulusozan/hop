import asyncio
import pytest

from src.domain.queue import TaskPriority, TaskStatus
from src.queue.engine import AsyncTaskQueue


@pytest.mark.asyncio
async def test_async_task_queue_priority_processing():
    queue = AsyncTaskQueue()
    execution_order: list[str] = []

    def task_handler(payload: dict) -> str:
        name = payload["item"]
        execution_order.append(name)
        return f"Processed {name}"

    queue.register_handler("job", task_handler)

    # Enqueue low priority first, then critical priority
    t_low = await queue.enqueue("job", {"item": "low_job"}, priority=TaskPriority.LOW)
    t_crit = await queue.enqueue("job", {"item": "critical_job"}, priority=TaskPriority.CRITICAL)

    queue.start_workers(num_workers=1)
    await asyncio.sleep(0.1)
    await queue.stop_workers()

    assert execution_order == ["critical_job", "low_job"]
    res_crit = await queue.get_task(t_crit.task_id)
    assert res_crit is not None
    assert res_crit.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_async_task_queue_dlq_dead_lettering():
    queue = AsyncTaskQueue()
    attempt_counter = 0

    def failing_handler(payload: dict):
        nonlocal attempt_counter
        attempt_counter += 1
        raise ValueError("Permanent job failure")

    queue.register_handler("fail_job", failing_handler)

    task = await queue.enqueue("fail_job", {"data": "test"}, max_retries=2)
    queue.start_workers(num_workers=1)

    await asyncio.sleep(0.2)
    await queue.stop_workers()

    assert attempt_counter == 2
    dlq = await queue.get_dlq_tasks()
    assert len(dlq) == 1
    assert dlq[0].task_id == task.task_id
    assert dlq[0].status == TaskStatus.DEAD_LETTERED
    assert "Permanent job failure" in dlq[0].error
