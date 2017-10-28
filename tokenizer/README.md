# Tokenizers

A Radar tokenizer of some programming language produces a compact string representation of all syntax tokens of some source code (e.g. exercise submission).

A tokenizer contains a function:
  * That accepts one string as a parameter, which is the source code of some programming language, that should be tokenized.
  * Returns a 2-tuple, that contains the tokenized string and source code mappings of the tokenized string back to the source code. The source code mappings are returned as a JSON-serialized string of arrays containing the starting and ending indexes of tokens. See the example below.

### Tokenized source string

A tokenized source string is a sequence of characters, without whitespace, where each (single) character uniquely identifies a syntax token in some language.
The amount of available UTF-8 characters should be sufficient to cover the syntax tokens of most languages.
The tokenized string is consumed by the matching algorithm and is not intended to be human readable.
The characters chosen to represent some syntax token should be unique and consistent for each tokenization of some tokenizer.

For example, if a tokenizer tokenizes the left parenthesis `(` as `1`, then `1` should always correspond to the left parenthesis `(` in every tokenization done by that tokenizer.
See the Python tokenizer example below for a more detailed example.

### Source mappings

The source code mappings are used to highlight matches in compared source code when viewed using the Radar UI.
The source code mappings are one-dimensional, starting at 0 and indexed by characters in the source code.
The source code mappings are an array of pairs, in the same order as the tokens appear in the original source code, where each pair contains the start and end index of a token.

## Example: Python

The Python tokenizer utilizes the tokenize-module from the Python standard library to parse source code.
Some additional effort was required to convert the two-dimensional (row, column) token indexing returned by the standard library tokenizer to support the one-dimensional representation understood by Radar.

Consider an arbitrary snippet of Python syntax:
```
import math

def f(x):
    if x > 1:
        return math.log(x)
    return x
```

The standard library tokenizer produces:
```
Token type   string       start    end
------------------------------------------
BACKQUOTE    'utf-8'      (0, 0)   (0, 0)
NAME         'import'     (1, 0)   (1, 6)
NAME         'math'       (1, 7)   (1, 11)
NEWLINE      '\n'         (1, 11)  (1, 12)
NL           '\n'         (2, 0)   (2, 1)
NAME         'def'        (3, 0)   (3, 3)
NAME         'f'          (3, 4)   (3, 5)
LPAR         '('          (3, 5)   (3, 6)
NAME         'x'          (3, 6)   (3, 7)
RPAR         ')'          (3, 7)   (3, 8)
COLON        ':'          (3, 8)   (3, 9)
NEWLINE      '\n'         (3, 9)   (3, 10)
INDENT       '    '       (4, 0)   (4, 4)
NAME         'if'         (4, 4)   (4, 6)
NAME         'x'          (4, 7)   (4, 8)
GREATER      '>'          (4, 9)   (4, 10)
NUMBER       '1'          (4, 11)  (4, 12)
COLON        ':'          (4, 12)  (4, 13)
NEWLINE      '\n'         (4, 13)  (4, 14)
INDENT       '        '   (5, 0)   (5, 8)
NAME         'return'     (5, 8)   (5, 14)
NAME         'math'       (5, 15)  (5, 19)
DOT          '.'          (5, 19)  (5, 20)
NAME         'log'        (5, 20)  (5, 23)
LPAR         '('          (5, 23)  (5, 24)
NAME         'x'          (5, 24)  (5, 25)
RPAR         ')'          (5, 25)  (5, 26)
NEWLINE      '\n'         (5, 26)  (5, 27)
DEDENT       ''           (6, 4)   (6, 4)
NAME         'return'     (6, 4)   (6, 10)
NAME         'x'          (6, 11)  (6, 12)
NEWLINE      '\n'         (6, 12)  (6, 13)
DEDENT       ''           (7, 0)   (7, 0)
ENDMARKER    ''           (7, 0)   (7, 0)
```

The Radar tokenizer `tokenizer.python.tokenize` produces:
```
('11411718;4511E2;4511G17184114',
 '[[0, 6], [7, 11], [11, 12], [13, 16], [17, 18], [18, 19], [19, 20], [20, 21], [21, 22], [22, 23], [23, 27], [27, 29], [30, 31], [32, 33], [34, 35], [35, 36], [36, 37], [37, 45], [45, 51], [52, 56], [56, 57], [57, 60], [60, 61], [61, 62], [62, 63], [63, 64], [68, 74], [75, 76], [76, 77]]')
```
Notice that `tokenizer.python.tokenize` drops tokens that are irrelevant when comparing two exercise submissions.
Either these tokens are expected to always be present in code that is valid Python or they do not contribute to the semantics of the code.
For example `BACKQUOTE` and `NL`.
See `tokenizer.python.SKIP_TOKENS` for details.

## Checklist for adding a new tokenizer

Adding a tokenizer for some language `lang` requires at least these steps:
* Implement `lang.py` containing the function `tokenize` conforming to the above specifications.
* Append a pair `("lang", "Language name")` to `radar.settings.TOKENIZER_CHOICES`.
* Add the key `"lang"` to `radar.settings.TOKENIZERS` and define the tokenizer function and a separator string. The `%s` in the separator will be replaced with the filename where the tokenized source code originated from (e.g. an exercise submission).

