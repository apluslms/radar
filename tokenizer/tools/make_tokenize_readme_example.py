import python
import tokenize


source = '''import math
# import cmath

def f(x):
    """calculate stuff"""
    if x > 1:
        return math.log(x)
    return x'''

print(source)

print("{:12s} {:21s} {:8} {:8}".format("Token type", "string", "start", "end"))
print("-"*51)
for t in python.token_generator_from_source(source):
    print("{:12s} {!r:21s} {!s:8} {!s:8}"
          .format(
              tokenize.tok_name[t.exact_type],
              t.string if len(t.string) < 19 else t.string[:15] + "...",
              t.start,
              t.end)
    )

print(python.tokenize(source))
