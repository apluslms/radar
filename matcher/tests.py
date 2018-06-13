import logging
import random
import string
import time
logging.disable(logging.CRITICAL)

from django.test import TestCase
from django.conf import settings
from django.utils.module_loading import import_string

match_algorithm = import_string(settings.MATCH_ALGORITHM)

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
    """For the match algorithm specified in the settings module, run benchmark tests with random data and assert that the amount of successful iterations is large enough"""

    def benchmark(self, match_args, min_iterations=10):
        timeout_seconds = 0.5
        iterations = 0
        total_time = 0
        while total_time < timeout_seconds:
            start_time = time.perf_counter()
            match_algorithm(*match_args)
            end_time = time.perf_counter()
            total_time += end_time - start_time
            iterations += 1
        self.assertGreater(iterations, min_iterations,
                "Expected match algorithm {0!r} to compute its result at least {1} times in {2} seconds but it managed only {3} iterations before {2} second timeout."
                .format(match_algorithm, min_iterations, timeout_seconds, iterations))

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


class TestMatcherState(TestCase):
    """Attempt to cover as many failure states as possible when calling matcher.match with some submission object."""
    pass
