# Tokenizers

### Currently implemented
* Python 3, using tokens from the stdlib [tokenize](https://github.com/python/cpython/blob/3.5/Lib/tokenize.py) module
* Scala, using scalariform
* JavaScript, using tokens from [Esprima 4](https://github.com/jquery/esprima/tree/4.0/)
* HTML, using custom tokens parsed with the Python stdlib [html.parser](https://github.com/python/cpython/blob/3.5/Lib/html/parser.py) module


## Radar tokenizer

A Radar tokenizer produces a compact string representation of all syntax tokens of some source code (e.g. exercise submission) and source mappings of the tokens back to the source code.
The matcher algorithm does not need the source mappings when doing comparisons, because the source mappings are needed only when highlighting matches.
It is still recommended that a tokenizer implements the source mappings in order to make inspecting matches easier.

A tokenizer should implement a function that
  * accepts one UTF-8 encoded string as a parameter, which is the source code that should be tokenized.
  * returns a 2-tuple, that contains one UTF-8 encoded, tokenized string, and single-dimensional source code mappings of the tokenized string back to the source code.
  The source code mappings are returned as a JSON-serialized string of arrays containing the starting and ending indexes of tokens.

Check out the Python tokenizer example below for more details.

### Tokenized source string

The tokenizer should implement an injective function that maps from the space of syntax tokens to the space of Unicode characters.
Applying this injective function over all syntax tokens, produces the tokenized source string.
In other words, a tokenized source string is a sequence of characters, without whitespace, where each character uniquely identifies a syntax token in some language.

The tokenized string is consumed by the matching algorithm and is not intended to be human readable, but it is important that the characters are unique and consistent for each tokenization of some tokenizer in order to make comparisons possible.
The matcher algorithm encodes tokenized strings using UTF-8, so any Unicode character should work.
However, for optimal space usage and easier debugging, it is probably a good idea to first use all printable ASCII characters (except space), before using code points beyond ASCII.

### Source mappings

Source code mappings from tokens to the original source code are used to highlight matches when comparing two different instances of source code in the Radar UI.
The source code mappings are one-dimensional, starting at 0 and indexed by characters in the source code.
The source code mappings are an array of pairs, in the same order as the tokens appear in the original source code, where each pair contains the start and end index of a token.

## Example: Python

The Python tokenizer utilizes the [tokenize](https://github.com/python/cpython/blob/3.5/Lib/tokenize.py) module from the Python standard library to parse source code.
Some additional effort was required to convert the two-dimensional (row, column) token indexing returned by the standard library tokenizer to support the one-dimensional representation understood by Radar.

Consider an arbitrary snippet of Python syntax:

```python
import math
# import cmath

def f(x):
    """calculate stuff"""
    if x > 1:
        return math.log(x)
    return x
```

The standard library tokenizer produces the following syntax tokens:
```
Token type   string                start    end
---------------------------------------------------
ENCODING     'utf-8'               (0, 0)   (0, 0)
NAME         'import'              (1, 0)   (1, 6)
NAME         'math'                (1, 7)   (1, 11)
NEWLINE      '\n'                  (1, 11)  (1, 12)
COMMENT      '# import cmath'      (2, 0)   (2, 14)
NL           '\n'                  (2, 14)  (2, 15)
NL           '\n'                  (3, 0)   (3, 1)
NAME         'def'                 (4, 0)   (4, 3)
NAME         'f'                   (4, 4)   (4, 5)
LPAR         '('                   (4, 5)   (4, 6)
NAME         'x'                   (4, 6)   (4, 7)
RPAR         ')'                   (4, 7)   (4, 8)
COLON        ':'                   (4, 8)   (4, 9)
NEWLINE      '\n'                  (4, 9)   (4, 10)
INDENT       '    '                (5, 0)   (5, 4)
STRING       '"""calculate st...'  (5, 4)   (5, 25)
NEWLINE      '\n'                  (5, 25)  (5, 26)
NAME         'if'                  (6, 4)   (6, 6)
NAME         'x'                   (6, 7)   (6, 8)
GREATER      '>'                   (6, 9)   (6, 10)
NUMBER       '1'                   (6, 11)  (6, 12)
COLON        ':'                   (6, 12)  (6, 13)
NEWLINE      '\n'                  (6, 13)  (6, 14)
INDENT       '        '            (7, 0)   (7, 8)
NAME         'return'              (7, 8)   (7, 14)
NAME         'math'                (7, 15)  (7, 19)
DOT          '.'                   (7, 19)  (7, 20)
NAME         'log'                 (7, 20)  (7, 23)
LPAR         '('                   (7, 23)  (7, 24)
NAME         'x'                   (7, 24)  (7, 25)
RPAR         ')'                   (7, 25)  (7, 26)
NEWLINE      '\n'                  (7, 26)  (7, 27)
DEDENT       ''                    (8, 4)   (8, 4)
NAME         'return'              (8, 4)   (8, 10)
NAME         'x'                   (8, 11)  (8, 12)
DEDENT       ''                    (9, 0)   (9, 0)
ENDMARKER    ''                    (9, 0)   (9, 0)
```

The Radar tokenizer `tokenizer.python.tokenize` maps these into:
```
('11411718;453411E2;4511G1718411',
'[[0, 6], [7, 11], [11, 12], [28, 31], [32, 33], [33, 34], [34, 35], [35, 36], [36, 37], [37, 38], [38, 42], [42, 63], [63, 64], [68, 70], [71, 72], [73, 74], [75, 76], [76, 77], [77, 78], [78, 86], [86, 92], [93, 97], [97, 98], [98, 101], [101, 102], [102, 103], [103, 104], [104, 105], [109, 115], [116, 117]]')
```
Notice that `tokenizer.python.tokenize` drops tokens that are irrelevant when comparing two exercise submissions.
For example `DEDENT` and `ENDMARKER`, which are non-printable and added implicitly, or `NL` and `COMMENT`, which do not change the semantics of the code.
Skipped tokens can be seen in `tokenizer.python.SKIP_TOKENS`.

## Checklist for adding a new tokenizer

Adding a tokenizer for some language `lang` requires at least these steps:
* Implement a module `lang.py`, containing a function `tokenize` conforming to the above specifications.
* Append a pair `("lang", "Display name for language")` to `radar.settings.TOKENIZER_CHOICES`.
* Add the key `"lang"` to `radar.settings.TOKENIZERS`, define the tokenizer function, e.g. `tokenizer.lang.tokenize`, and a separator string.
The separator string is prepended to each source code and `%s` is replaced with the filename, from where the tokenized source code originated from (e.g. an exercise submission).

