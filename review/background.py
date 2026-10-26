import hashlib
import json
import logging
import time

from django.core.cache import caches

from provider import tasks

logger = logging.getLogger("radar.review")


def result_key(course_id, operation, arguments):
    digest = hashlib.sha256(
        json.dumps([course_id, operation, arguments], sort_keys=True).encode()
    ).hexdigest()
    return "radar_background:v2:" + digest


def store_background_state(store, key, state, timeout):
    store.set(key, state, timeout)
    # Expire the small status marker before its separately stored result.
    store.set(key + ":status", public_status(state), max(1, timeout - 1))


def background_result(request, course, operation, arguments):
    store = caches["course_report_progress"]
    locks = caches["default"]
    key = result_key(course.pk, operation, [arguments, request.GET.get("run", "")])
    polling = request.GET.get("background") == "1"
    state = store.get(key + ":status")
    if state and state["status"] == "ready" and not polling:
        state = store.get(key)
        if state is None:
            store.delete(key + ":status")
    if state and state["status"] == "pending" and time.time() - state["started"] > 660:
        state = {"status": "failed", "message": "Background loading timed out. Check the Celery worker."}
        store_background_state(store, key, state, 600)
    if request.method == "POST" and polling:
        if request.POST.get("retry") == "1" and state and state["status"] == "failed":
            store.delete_many([key, key + ":status"])
            locks.delete(key + ":lock")
            state = None
        if state is None:
            pending = {"status": "pending", "started": time.time()}
            if locks.add(key + ":lock", pending, 900):
                store_background_state(store, key, pending, 900)
                try:
                    tasks.load_radar_page_data.apply_async(
                        args=[course.pk, operation, arguments, key],
                        queue="radar_background", retry=False, expires=600,
                    )
                except Exception:
                    logger.exception(
                        "Could not queue Radar background loading course=%s operation=%s", course.pk, operation,
                    )
                    state = {
                        "status": "failed", "message": "Could not queue background loading. Check the task queue.",
                    }
                    store_background_state(store, key, state, 600)
                    locks.delete(key + ":lock")
                else:
                    state = pending
            else:
                state = store.get(key + ":status") or locks.get(key + ":lock")
    return state or {"status": "idle"}


def public_status(state):
    return {key: value for key, value in state.items() if key != "result"}