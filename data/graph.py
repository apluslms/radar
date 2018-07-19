import collections

from django.db import models


class Graph:
    def __init__(self):
        self.nodes = set()
        self.edges = collections.defaultdict(list)

    def add_edge(self, a, b, edge_data):
        if a not in self.nodes:
            self.nodes.add(a)
        if b not in self.nodes:
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
    for student_a, student_b, similarity, exercise_id in course.all_student_pair_matches(min_similarity):
        edge_data = {
            "exercise_id": exercise_id,
            "max_similarity": similarity,
        }
        graph.add_edge(student_a, student_b, edge_data)
    return graph.as_dict()
