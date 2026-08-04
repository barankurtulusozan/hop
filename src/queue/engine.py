from __future__ import annotations

import asyncio
import inspect
import logging
import time
import uuid
from typing import Any, Awaitable, Callable

from src.domain.exceptions import QueueException
from src.domain.queue import QueueTask, TaskPriority, TaskStatus

logger = logging.getLogger("llm_orchestrator.queue")


class AsyncTaskQueue:
    """Prioritized asynchronous task queue with worker pool processing and Dead Letter Queue (DLQ) isolation."""

    def __init__(self):
        # PriorityQueue stores tuple (-priority_value, timestamp, task_id)
        self._queue: asyncio.PriorityQueue[tuple[int, float, str]] = asyncio.PriorityQueue()
        self._tasks: dict[str, QueueTask] = {}
        self._dlq: dict[str, QueueTask] = {}
        self._handlers: dict[str, Callable[..., Any]] = {}
        self._workers: list[asyncio.Task[None]] = []
        self._lock = asyncio.Lock()
        self._running = False

    def register_handler(self, name: str, handler: Callable[..., Any]) -> None:
        self._handlers[name] = handler

    async def enqueue(
        self,
        name: str,
        payload: dict[str, Any],
        priority: TaskPriority = TaskPriority.NORMAL,
        max_retries: int = 3,
    ) -> QueueTask:
        if name not in self._handlers:
            raise QueueException(f"No handler registered for task name '{name}'")

        task_id = f"task_{uuid.uuid4().hex[:10]}"
        now = time.time()
        task = QueueTask(
            task_id=task_id,
            name=name,
            payload=payload,
            priority=priority,
            status=TaskStatus.QUEUED,
            attempts=0,
            max_retries=max_retries,
            created_at=now,
            updated_at=now,
        )

        async with self._lock:
            self._tasks[task_id] = task
            # Negate priority value so higher priority (e.g. CRITICAL=4) comes out first
            await self._queue.put((-int(priority), now, task_id))

        logger.info(f"Task '{task_id}' ({name}, priority={priority.name}) enqueued")
        return task

    async def get_task(self, task_id: str) -> QueueTask | None:
        async with self._lock:
            return self._tasks.get(task_id) or self._dlq.get(task_id)

    async def get_dlq_tasks(self) -> list[QueueTask]:
        async with self._lock:
            return list(self._dlq.values())

    async def _worker_loop(self, worker_id: int) -> None:
        while self._running:
            try:
                # Timeout allows worker loop to check self._running periodically
                _, _, task_id = await asyncio.wait_for(self._queue.get(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            async with self._lock:
                task = self._tasks.get(task_id)
                if not task:
                    self._queue.task_done()
                    continue

                attempts = task.attempts + 1
                updated_task = QueueTask(
                    task_id=task.task_id,
                    name=task.name,
                    payload=task.payload,
                    priority=task.priority,
                    status=TaskStatus.PROCESSING,
                    attempts=attempts,
                    max_retries=task.max_retries,
                    created_at=task.created_at,
                    updated_at=time.time(),
                )
                self._tasks[task_id] = updated_task

            handler = self._handlers[task.name]
            try:
                res = handler(updated_task.payload)
                if inspect.isawaitable(res):
                    res = await res

                async with self._lock:
                    completed_task = QueueTask(
                        task_id=task.task_id,
                        name=task.name,
                        payload=task.payload,
                        priority=task.priority,
                        status=TaskStatus.COMPLETED,
                        attempts=attempts,
                        max_retries=task.max_retries,
                        result=res,
                        created_at=task.created_at,
                        updated_at=time.time(),
                    )
                    self._tasks[task_id] = completed_task
                logger.info(f"Task '{task_id}' completed successfully by worker-{worker_id}")

            except Exception as exc:
                logger.warning(f"Task '{task_id}' attempt {attempts}/{task.max_retries} failed: {exc}")
                async with self._lock:
                    if attempts < task.max_retries:
                        # Re-enqueue task for retry
                        retry_task = QueueTask(
                            task_id=task.task_id,
                            name=task.name,
                            payload=task.payload,
                            priority=task.priority,
                            status=TaskStatus.QUEUED,
                            attempts=attempts,
                            max_retries=task.max_retries,
                            error=str(exc),
                            created_at=task.created_at,
                            updated_at=time.time(),
                        )
                        self._tasks[task_id] = retry_task
                        await self._queue.put((-int(task.priority), time.time(), task_id))
                    else:
                        # Max retries exhausted: move to Dead Letter Queue (DLQ)
                        dlq_task = QueueTask(
                            task_id=task.task_id,
                            name=task.name,
                            payload=task.payload,
                            priority=task.priority,
                            status=TaskStatus.DEAD_LETTERED,
                            attempts=attempts,
                            max_retries=task.max_retries,
                            error=f"Dead lettered after {attempts} attempts: {exc}",
                            created_at=task.created_at,
                            updated_at=time.time(),
                        )
                        self._dlq[task_id] = dlq_task
                        del self._tasks[task_id]
                        logger.error(f"Task '{task_id}' moved to Dead Letter Queue (DLQ)")

            finally:
                self._queue.task_done()

    def start_workers(self, num_workers: int = 2) -> None:
        if self._running:
            return
        self._running = True
        for i in range(num_workers):
            task = asyncio.create_task(self._worker_loop(i + 1))
            self._workers.append(task)

    async def stop_workers(self) -> None:
        self._running = False
        for w in self._workers:
            w.cancel()
        if self._workers:
            await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
