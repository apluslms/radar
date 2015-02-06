"""
Token operations.

"""

def overlap(beg_a, end_a, beg_b, end_b):
    if beg_a >= beg_b and beg_a <= end_b:
        if end_a > end_b:
            return (beg_b, end_a)
        return (beg_b, end_b)
    if end_a >= beg_b and end_a <= end_b:
        if beg_a < beg_b:
            return (beg_a, end_b)
        return (beg_b, end_b)
    if beg_a < beg_b and end_a > end_b:
        return (beg_a, end_a)
    return None
