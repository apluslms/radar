import json


def updated_edge_weights(weights, similarity):
    return [(threshold, count + int(threshold <= similarity))
            for threshold, count in weights]


def empty_weights():
    return [(s/10, 0) for s in range(0, 11)]


class Graph:
    def __init__(self):
        self.nodes = set()
        self.edges = dict()

    def add_edge(self, a, b, similarity):
        if a not in self.nodes:
            self.nodes.add(a)
        if b not in self.nodes:
            self.nodes.add(b)
        edge_key = (b, a) if (b, a) in self.edges else (a, b)
        if edge_key not in self.edges:
            self.edges[edge_key] = empty_weights()
        self.edges[edge_key] = updated_edge_weights(self.edges[edge_key], similarity)
        return self.edges[edge_key]

    def to_json(self):
        return json.dumps({
            "nodes": list(self.nodes),
            "edges": [{"source": key[0],
                       "target": key[1],
                       "data": weights}
                      for key, weights in self.edges.items()]
        })


def get_graph_json(course):
    graph = Graph()
    for comparison in course.all_comparisons():
        if comparison.submission_a is None or comparison.submission_b is None:
            # Skip template comparisons
            continue
        # probably redundant, but just in case
        assert comparison.submission_a.exercise.key == comparison.submission_b.exercise.key, "Comparison object with submissions to different exercises {} {}".format(comparison.submission_a.exercise.key, comparison.submission_b.exercise.key)
        graph.add_edge(
            comparison.submission_a.student.key,
            comparison.submission_b.student.key,
            comparison.similarity
        )
    return graph.to_json()

