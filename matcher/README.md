This package contains the core functionality required for comparing submissions to each other and producing similarity scores for the compared pairs.
Submissions are matched in parallel with Celery by using the tasks defined in `tasks.py`.

Submissions are matched if one of these 4 different events occur:

* The data provider sends a hook request for a single, new submission. (automatic, e.g. A+)
* The user selects "Clear and re-compare" from exercise settings. (manual, recompares existing submissions)
* The user selects "Clear and reload" from exercise settings. (manual, deletes all submissions and reloads them from the data provider)
* The user selects "Retrieve exercise data -> Create and compare all" from the course configure view. (manual, same as "Clear and reload" but only for exercises that do not already exist)

Here is an approximate sketch of what happens during the first event in the above list, when matching a single new submission, that is queued using the hook request:

![alt text](./matcher.png)
