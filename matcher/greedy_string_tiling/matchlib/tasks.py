import celery
from ..matchlib import matcher

logger = celery.utils.log.get_task_logger(__name__)

# pylint: disable=inconsistent-return-statements

@celery.shared_task
def match_all_combinations(config, string_data_iter, delay=False):
    logger.info("Got match all combinations task")

    matches = []

    if delay:
        matcher.match_all_combinations(config, string_data_iter, delay=delay)
    else:
        matches = list(matcher.match_all_combinations(config, string_data_iter, delay=delay))

    logger.info("All matched")

    if not delay:
        return {"meta": matcher.RESULT_KEYS, "results": matches, "config": config}


@celery.shared_task
def match_to_others(config, *args):
    logger.info("Got match to others task")
    matches = list(matcher.match_to_others(config, *args))
    logger.info("All matched")
    return {"meta": matcher.RESULT_KEYS, "results": matches, "config": config}
