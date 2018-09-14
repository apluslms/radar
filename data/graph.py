import collections
import functools

from django.urls import reverse
from data.models import Course


class LRU(collections.OrderedDict):
    """Custom LRU cache inspired by https://bugs.python.org/msg292251"""

    def __init__(self, func, maxsize=256):
        self.maxsize = maxsize
        self.func = func
        functools.update_wrapper(self, func)

    def __call__(self, *args):
        if args in self:
            graph = self[args]
            self.move_to_end(args)
            return graph
        graph = self.func(*args)
        if len(self) >= self.maxsize:
            self.popitem(last=False)
        self[args] = graph
        return graph

    def invalidate_all(self):
        self.clear()

    # FIXME this method should have a mutex if several celery workers invalidate concurrently
    def invalidate_for_course(self, course_key):
        # As long as the cache max size is relatively small, walking through all keys is hardly a performance disaster
        course_entries = [key for key in self.keys() if key[0] == course_key]
        for key in course_entries:
            del self[key]

    def is_cached(self, *args):
        return args in self


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

    def as_dict(self):
        return {
            "nodes": list(self.nodes),
            "edges": [{"source": from_to[0],
                       "target": from_to[1],
                       "matches_in_exercises": match_data}
                      for from_to, match_data in self.edges.items()],
        }


@LRU
def generate_match_graph(course_key, min_similarity, unique_exercises=True):
    """Constructs a graph as a dictionary from all comparisons with a minimum similarity on a given course."""
    course = Course.objects.filter(key=course_key).first()
    graph = Graph()
    # Get all comparisons for every student pair grouped by exercise
    for exercise_comparisons in course.all_student_pair_matches(min_similarity):
        if unique_exercises:
            # Choose only one exercise, based on the maximum similarity
            exercise_comparisons = exercise_comparisons.order_by("-similarity")[:1]
        for comparison in exercise_comparisons:
            student_a, student_b = comparison.submission_a.student.key, comparison.submission_b.student.key
            if student_a == student_b:
                continue
            exercise = comparison.submission_a.exercise
            exercise_url = reverse("exercise", args=[course.key, exercise.key])
            comparison_url = reverse("comparison", args=[course.key, exercise.key, student_a, student_b, comparison.id])
            edge_data = {
                "exercise_name": exercise.name,
                "exercise_url": exercise_url,
                "comparison_url": comparison_url,
                "max_similarity": comparison.similarity,
            }
            graph.add_edge(student_a, student_b, edge_data)
    return graph.as_dict()


# Cache interface

def is_cached(course_key, *args):
    return generate_match_graph.is_cached((course_key, ) + args)

def invalidate_course_graphs(course):
    generate_match_graph.invalidate_for_course(course.key)

def invalidate_all_graphs():
    generate_match_graph.invalidate_all()
