import hashlib
import json
import time

from django.core.cache import caches


def result_key(course_id, operation, arguments):
    digest = hashlib.sha256(
        json.dumps([course_id, operation, arguments], sort_keys=True).encode()
    ).hexdigest()
    return "radar_background:" + digest


def background_result(request, course, operation, arguments):
    from provider.tasks import load_radar_page_data

    store = caches["course_report_progress"]
    locks = caches["default"]
    key = result_key(course.pk, operation, [arguments, request.GET.get("run", "")])
    state = store.get(key)
    if state and state["status"] == "pending" and time.time() - state["started"] > 660:
        state = {"status": "failed", "message": "Background loading timed out. Check the Celery worker."}
        store.set(key, state, 600)
    if request.method == "POST" and request.GET.get("background") == "1":
        if request.POST.get("retry") == "1" and state and state["status"] == "failed":
            store.delete(key)
            locks.delete(key + ":lock")
            state = None
        if state is None:
            pending = {"status": "pending", "started": time.time()}
            if locks.add(key + ":lock", pending, 900):
                store.set(key, pending, 900)
                try:
                    load_radar_page_data.apply_async(
                        args=[course.pk, operation, arguments, key],
                        queue="radar_background", retry=False, expires=600,
                    )
                except Exception:
                    state = {"status": "failed", "message": "Could not queue background loading. Check the task queue."}
                    store.set(key, state, 600)
                    locks.delete(key + ":lock")
                else:
                    state = pending
            else:
                state = store.get(key) or locks.get(key + ":lock")
    return state or {"status": "idle"}


def public_status(state):
    return {key: value for key, value in state.items() if key != "result"}