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


class TaskQueue:
    """Priority task queue backed by worker threads."""

    def __init__(self, workers: int = 1) -> None:
        self._pq: queue.PriorityQueue = queue.PriorityQueue()
        self._counter = itertools.count()
        self._tasks: dict = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._threads = [
            threading.Thread(target=self._worker, daemon=True, name=f"agv-worker-{i}")
            for i in range(max(1, workers))
        ]
        for t in self._threads:
            t.start()

    def submit(self, func, *args, priority: Priority = Priority.NORMAL, name: str = "", **kwargs) -> int:
        """Queue a callable. Returns task id."""
        task_id = next(self._counter)
        with self._lock:
            self._tasks[task_id] = {
                "id": task_id,
                "name": name or getattr(func, "__name__", str(task_id)),
                "priority": Priority(priority),
                "status": TaskStatus.PENDING,
                "result": None,
                "error": None,
                "enqueued_at": time.time(),
            }
        # PriorityQueue is a min-heap: negate priority so HIGH runs first
        self._pq.put((-int(priority), task_id, func, args, kwargs))
        return task_id

    def _worker(self) -> None:
        while not self._stop.is_set():
            try:
                _neg, task_id, func, args, kwargs = self._pq.get(timeout=0.1)
            except queue.Empty:
                continue
            with self._lock:
                task = self._tasks.get(task_id)
                if task is None:
                    self._pq.task_done()
                    continue
                task["status"] = TaskStatus.RUNNING
            try:
                result = func(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - errors are task results
                with self._lock:
                    task["status"] = TaskStatus.FAILED
                    task["error"] = f"{exc}\n{traceback.format_exc(limit=3)}"
            else:
                with self._lock:
                    task["status"] = TaskStatus.DONE
                    task["result"] = result
            finally:
                self._pq.task_done()

    def status(self, task_id: int) -> dict:
        """Snapshot of a task. Raises KeyError for unknown ids."""
        with self._lock:
            return dict(self._tasks[task_id])

    def wait(self, task_id: int, timeout: float = 60) -> dict:
        """Block until a task finishes. Raises TimeoutError on timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            snap = self.status(task_id)
            if snap["status"] in (TaskStatus.DONE, TaskStatus.FAILED):
                return snap
            time.sleep(0.01)
        raise TimeoutError(f"task {task_id} did not finish in {timeout}s")

    def wait_all(self, timeout: float = 300) -> list:
        """Block until the queue drains. Returns snapshots in submit order."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._lock:
                pending = [t for t in self._tasks.values() if t["status"] in (TaskStatus.PENDING, TaskStatus.RUNNING)]
            if not pending and self._pq.empty():
                break
            time.sleep(0.01)
        with self._lock:
            return [dict(self._tasks[k]) for k in sorted(self._tasks)]

    def shutdown(self) -> None:
        """Stop workers (daemon threads also die with the process)."""
        self._stop.set()
