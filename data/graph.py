import collections
# import functools

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
        edge_key = (b, a) if (b, a) in self.edges else (a, b)
        self.edges[edge_key].append(edge_data)
        return self.edges[edge_key]

    def serializable_edge_data(self, data):
        return [{"eid": d["exercise_id"],
                 "similarity": {
                     k: format(val, ".2f")
                     for k, val in d["similarity"].items()}}
                for d in data]

    def as_dict(self):
        return {
            "nodes": list(self.nodes),
            "edges": [{"source": from_to[0],
                       "target": from_to[1],
                       "data": self.serializable_edge_data(data)}
                      for from_to, data in self.edges.items()],
        }


# TODO invalidate cache every time course gets new submission
# @functools.lru_cache(maxsize=10)
def generate_match_graph(course, min_similarity):
    annotation = (
        "submission_a__student__key",
        "submission_b__student__key",
        "submission_a__exercise_id",
        "submission_b__exercise_id",
    )
    annotated_match_iter = (
        course
            .all_comparisons(min_similarity)
            .exclude(submission_b__max_similarity__isnull=True)
            .filter(submission_a__exercise=models.F("submission_b__exercise"))
            .values(*annotation)
            .annotate(max_sim=models.Max("similarity"),
                    sim_sum=models.Sum("similarity"),
                    avg_sim=models.Avg("similarity"))
            .values_list(*annotation[:3], "max_sim", "sim_sum", "avg_sim")
    )

    graph = Graph()
    for (student_a_key, student_b_key, exercise_id,
         max_similarity, similarity_sum, avg_similarity) in annotated_match_iter:
        edge_data = {
            "exercise_id": exercise_id,
            "similarity": {
                "max": max_similarity,
                "sum": similarity_sum,
                "avg": avg_similarity
            }
        }
        graph.add_edge(student_a_key, student_b_key, edge_data)
    return graph.as_dict()


# def invalidate_lru_cache():
#     generate_match_graph.cache_clear()

