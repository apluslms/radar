import json
import collections
# import functools


class Graph:
    def __init__(self):
        self.nodes = set()
        self.edges = collections.Counter()

    def add_edge(self, a, b):
        if a not in self.nodes:
            self.nodes.add(a)
        if b not in self.nodes:
            self.nodes.add(b)
        edge_key = (b, a) if (b, a) in self.edges else (a, b)
        self.edges[edge_key] += 1
        return self.edges[edge_key]

    def as_dict(self):
        heaviest_edges = self.edges.most_common(1)
        return {
            "nodes": list(self.nodes),
            "edges": [{"source": from_to[0],
                       "target": from_to[1],
                       "count": count}
                      for from_to, count in self.edges.items()],
            # here, we could also export all N pairs of students with the most matches,
            # by e.g. list(map(list(self.edges.most_common(N))))
            "max_edge_weight": heaviest_edges[0][1] if heaviest_edges else 0
        }


# @functools.lru_cache(maxsize=1)
def generate_match_graph(course, min_similarity):
    graph = Graph()
    for comparison in course.all_comparisons(min_similarity):
        if comparison.submission_a is None or comparison.submission_b is None:
            # Skip template comparisons
            continue
        # probably redundant, but just in case
        assert comparison.submission_a.exercise.key == comparison.submission_b.exercise.key, "Comparison object with submissions to different exercises {} {}".format(comparison.submission_a.exercise.key, comparison.submission_b.exercise.key)
        graph.add_edge(
            comparison.submission_a.student.key,
            comparison.submission_b.student.key
        )
    return graph.as_dict()


# def invalidate_lru_cache():
#     get_graph_json.cache_clear()

