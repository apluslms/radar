import collections
from django.urls import reverse


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


def generate_match_graph(course, min_similarity=0.95):
    graph = Graph()
    for comparison in course.all_student_pair_matches(min_similarity):
        student_a, student_b = comparison.submission_a.student.key, comparison.submission_b.student.key
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
