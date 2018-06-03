import string
import random
import time
import logging
logging.disable(logging.CRITICAL)

from django.test import TestCase

import matcher.jplag_ext as jplag_ext
import matcher.jplag as jplag

def random_char():
    return random.choice(string.printable)

def random_string(size):
    return ''.join(random_char() for _ in range(size))

def random_string_copy(string, copy_pr):
    # note that copy_pr == 0 does not guarantee that the randomly drawn char does not happen to be equal to c
    return ''.join((random_char() if copy_pr < random.random() else c) for c in string)

def generate_data(a_size, b_size, similarity_p):
    tokens_a = random_string(a_size)
    tokens_b = random_string_copy(tokens_a, similarity_p)[:b_size]
    return (tokens_a, len(tokens_a)*[False], tokens_b, len(tokens_b)*[False], 15)


class TestBenchmark(TestCase):

    def setUp(self):
        self.results = []
        self.iterations = 100

    def benchmark(self, args):
        result = {"name": "jplag", "times": []}
        for _ in range(self.iterations):
            start_time = time.perf_counter()
            jplag.match(*args)
            end_time = time.perf_counter()
            result["times"].append(end_time - start_time)
        self.results.append(result)
        result = {"name": "jplag_ext", "times": []}
        for _ in range(self.iterations):
            start_time = time.perf_counter()
            jplag_ext.match(*args)
            end_time = time.perf_counter()
            result["times"].append(end_time - start_time)
        self.results.append(result)

    def tearDown(self):
        print("\n{}\n{} iterations".format(self, self.iterations))
        print("{:10s};{:4s} {:4s} {:4s} {:4s} {:s}"
              .format("algorithm", "min", "max", "avg", "sum", "(seconds)"))
        for res in self.results:
            algname, times = res["name"], res["times"]
            print("{:10s}: {:.2f} {:.2f} {:.2f} {:.2f}"
                  .format(algname, min(times), max(times), sum(times)/len(times), sum(times)))

    def test_a1_very_unlikely_equal_tiny(self):
        self.benchmark(generate_data(100, 100, 0))
    def test_a2_unlikely_equal_tiny(self):
        self.benchmark(generate_data(100, 100, 0.25))
    def test_a3_likely_equal_tiny(self):
        self.benchmark(generate_data(100, 100, 0.75))
    def test_a4_very_likely_equal_tiny(self):
        self.benchmark(generate_data(100, 100, 1))

    def test_b1_very_unlikely_equal_average(self):
        self.benchmark(generate_data(500, 500, 0))
    def test_b2_unlikely_equal_average(self):
        self.benchmark(generate_data(500, 500, 0.25))
    def test_b3_likely_equal_average(self):
        self.benchmark(generate_data(500, 500, 0.75))
    def test_b4_very_likely_equal_average(self):
        self.benchmark(generate_data(500, 500, 1))

    def test_c1_very_unlikely_equal_large(self):
        self.benchmark(generate_data(1000, 1000, 0))
    def test_c2_unlikely_equal_large(self):
        self.benchmark(generate_data(1000, 1000, 0.25))
    def test_c3_likely_equal_large(self):
        self.benchmark(generate_data(1000, 1000, 0.75))
    def test_c4_very_likely_equal_large(self):
        self.benchmark(generate_data(1000, 1000, 1))

