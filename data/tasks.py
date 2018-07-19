import json
import celery
from celery.utils.log import get_task_logger

from data.models import Course
from data.graph import generate_match_graph


logger = get_task_logger(__name__)


@celery.shared_task(ignore_result=True)
def update_all_similarity_graphs():
    """
    Update expired similarity graphs for all active courses.
    """
    for course in Course.objects.filter(archived=False, similarity_graph_expired=True):
        course.similarity_graph_json = json.dumps(generate_match_graph(course))
        course.similarity_graph_expired = False
        course.save()
