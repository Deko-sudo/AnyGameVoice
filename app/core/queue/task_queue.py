"""Threaded task queue with priorities (Phase 7).

Batch TTS generation runs here: hundreds of lines are queued,
workers synthesize in parallel, progress is reported per task.
Single worker by default (deterministic order); configurable.
"""

import itertools
import queue
import threading
import time
import traceback

from .priority import Priority

__all__ = ["TaskQueue", "TaskStatus"]


class TaskStatus:
    """Status constants."""

    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    TIMEOUT = "timeout"


class TaskQueue:
    """Priority task queue backed by worker threads."""

    def __init__(self, workers: int = 1) -> None:
        self._pq: queue.PriorityQueue = queue.PriorityQueue()
        self._counter = itertools.count()
        self._tasks: dict = {}
        self._lock = threading.Lock()
        self._closed = False
        self._deadline: float | None = None
        self._threads = [
            threading.Thread(target=self._worker, daemon=True, name=f"agv-worker-{i}")
            for i in range(max(1, workers))
        ]
        for t in self._threads:
            t.start()

    def submit(self, func, *args, priority: Priority = Priority.NORMAL, name: str = "", **kwargs) -> int:
        """Queue a callable. Returns task id."""
        with self._lock:
            if self._closed:
                raise RuntimeError("Task queue has been shut down")
            task_id = next(self._counter)
            self._tasks[task_id] = {
                "id": task_id,
                "name": name or getattr(func, "__name__", str(task_id)),
                "priority": Priority(priority),
                "status": TaskStatus.PENDING,
                "result": None,
                "error": None,
                "enqueued_at": time.time(),
            }
            # PriorityQueue is a min-heap: negate priority so HIGH runs first.
            self._pq.put((-int(priority), task_id, func, args, kwargs))
        return task_id

    def _worker(self) -> None:
        while True:
            _neg, task_id, func, args, kwargs = self._pq.get()
            if task_id == -1:
                self._pq.task_done()
                return
            with self._lock:
                task = self._tasks[task_id]
                if self._deadline is not None and time.monotonic() >= self._deadline:
                    task["status"] = TaskStatus.TIMEOUT
                    self._pq.task_done()
                    continue
                task["status"] = TaskStatus.RUNNING
            try:
                result = func(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - errors are task results
                outcome = {"status": TaskStatus.FAILED, "error": f"{exc}\n{traceback.format_exc(limit=3)}"}
            else:
                outcome = {"status": TaskStatus.DONE, "result": result}
            finally:
                self._pq.task_done()
            with self._lock:
                if self._deadline is not None and time.monotonic() >= self._deadline:
                    task["status"] = TaskStatus.TIMEOUT
                elif task["status"] == TaskStatus.RUNNING:
                    task.update(outcome)

    def status(self, task_id: int) -> dict:
        """Snapshot of a task. Raises KeyError for unknown ids."""
        with self._lock:
            return dict(self._tasks[task_id])

    def wait(self, task_id: int, timeout: float = 60) -> dict:
        """Block until a task finishes. Raises TimeoutError on timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            snap = self.status(task_id)
            if snap["status"] in (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.TIMEOUT):
                return snap
            time.sleep(0.01)
        raise TimeoutError(f"task {task_id} did not finish in {timeout}s")

    def wait_all(self, timeout: float = 300) -> list:
        """Block until the queue drains. Returns snapshots in submit order."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                pending = [t for t in self._tasks.values() if t["status"] in (TaskStatus.PENDING, TaskStatus.RUNNING)]
            if not pending:
                break
            time.sleep(0.01)
        with self._lock:
            return [dict(self._tasks[k]) for k in sorted(self._tasks)]

    def shutdown(self, wait: bool = False, timeout: float | None = None) -> None:
        """Close submissions. A bounded wait lets queued work drain until the deadline."""
        deadline = time.monotonic() + timeout if wait and timeout is not None else None
        with self._lock:
            if deadline is not None and (self._deadline is None or deadline < self._deadline):
                self._deadline = deadline
            if not self._closed:
                self._closed = True
                # Bounded drain: stop markers follow queued tasks. Otherwise keep
                # the original immediate stop, allowing only active calls to finish.
                priority = float("inf") if deadline is not None else float("-inf")
                for _ in self._threads:
                    self._pq.put((priority, -1, None, (), {}))
        if wait:
            for thread in self._threads:
                remaining = None if deadline is None else max(0, deadline - time.monotonic())
                thread.join(remaining)
        if deadline is not None:
            with self._lock:
                for task in self._tasks.values():
                    if task["status"] in (TaskStatus.PENDING, TaskStatus.RUNNING):
                        task["status"] = TaskStatus.TIMEOUT
