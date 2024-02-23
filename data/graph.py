import collections
import json

import celery
from celery.utils.log import get_task_logger
from django.urls import reverse

from data.models import Course

logger = get_task_logger(__name__)


class Graph:
    def __init__(self):
        self.nodes = set()
        self.edges = collections.defaultdict(list)

    def add_edge(self, a, b, edge_data):
        self.nodes.add(a)
        self.nodes.add(b)
        edge_key = (b, a) if b < a else (a, b)
        self.edges[edge_key].append(edge_data)
        return self.edges[edge_key]

    def as_dict(self, min_matches):
        return {
            "nodes": list(self.nodes),
            "edges": [
                {
                    "source": from_to[0],
                    "target": from_to[1],
                    "matches_in_exercises": match_data,
                }
                for from_to, match_data in self.edges.items()
                if len(match_data) >= min_matches
            ],
        }


@celery.shared_task
def generate_match_graph(
    course_key, min_similarity, min_matches, unique_exercises=True
):
    """
    Constructs a graph as a dictionary from all comparisons with a minimum similarity on a given course.
    If unique_exercises is True, and two students have several matches in one exercise, return the match with the
    highest similarity. min_matches is the smallest amount of matches two students must have in order to add the match
    as an edge in the graph.
    """
    course = Course.objects.filter(key=course_key).first()
    logger.info("Generating match graph for %s", course)
    graph = Graph()
    # Get all comparisons for every student pair grouped by exercise
    for exercise_comparisons in course.all_student_pair_matches(min_similarity):
        if unique_exercises:
            # Choose only one exercise, based on the maximum similarity
            exercise_comparisons = exercise_comparisons.order_by("-similarity")[:1]
        for comparison in exercise_comparisons:
            student_a, student_b = (
                comparison.submission_a.student.key,
                comparison.submission_b.student.key,
            )
            if student_a == student_b:
                continue
            exercise = comparison.submission_a.exercise
            exercise_url = reverse("exercise", args=[course.key, exercise.key])
            comparison_url = reverse(
                "comparison",
                args=[course.key, exercise.key, student_a, student_b, comparison.id],
            )
            edge_data = {
                "exercise_name": exercise.name,
                "exercise_url": exercise_url,
                "comparison_url": comparison_url,
                "max_similarity": comparison.similarity,
            }
            graph.add_edge(student_a, student_b, edge_data)
    # Return a JSON serializable graph with the used params
    result = graph.as_dict(min_matches)
    result["min_similarity"] = format(min_similarity, ".2f")
    result["min_matches"] = format(min_matches, "d")
    # Cache graph definition
    course.similarity_graph_json = json.dumps(result)
    course.save()
    return result
