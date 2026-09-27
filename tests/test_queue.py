"""Queue tests."""

import time


def test_priority_order():
    from app.core.queue.priority import Priority
    from app.core.queue.task_queue import TaskQueue

    q = TaskQueue(workers=1)
    started = []

    def make(tag, prio):
        def _run():
            started.append(prio)

        _run.__name__ = tag
        return _run

    # Burst of mixed priorities. The worker may grab the very first task
    # before the rest is queued (race), but everything after that must
    # come out strictly HIGH -> NORMAL -> LOW.
    q.submit(make("l1", 0), priority=Priority.LOW)
    q.submit(make("h1", 2), priority=Priority.HIGH)
    q.submit(make("n1", 1), priority=Priority.NORMAL)
    q.submit(make("h2", 2), priority=Priority.HIGH)
    q.submit(make("l2", 0), priority=Priority.LOW)
    q.submit(make("n2", 1), priority=Priority.NORMAL)
    snaps = q.wait_all()
    q.shutdown()
    assert all(s["status"] == "done" for s in snaps)
    assert len(started) == 6
    tail = started[1:]
    assert tail == sorted(tail, reverse=True)


def test_result_and_error():
    from app.core.queue.task_queue import TaskQueue

    q = TaskQueue(workers=2)

    def boom():
        raise ValueError("bad")

    ok_id = q.submit(lambda a, b: a + b, 2, 3, name="add")
    fail_id = q.submit(boom, name="boom")
    ok = q.wait(ok_id)
    fail = q.wait(fail_id)
    q.shutdown()
    assert ok["status"] == "done" and ok["result"] == 5
    assert fail["status"] == "failed" and "bad" in fail["error"]


def test_wait_timeout():
    import pytest

    from app.core.queue.task_queue import TaskQueue

    q = TaskQueue(workers=1)
    tid = q.submit(lambda: time.sleep(5), name="slow")
    with pytest.raises(TimeoutError):
        q.wait(tid, timeout=0.1)
    q.shutdown()
