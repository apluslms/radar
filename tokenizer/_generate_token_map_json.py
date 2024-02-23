"""
Generate unique token mappings from token names to single characters for HTML, CSS, and JavaScript tokens.
First 94 tokens are assigned to matching index from string.printable.
After that, tokens are assigned to characters represented by Unicode code points from 161 up.
The resulting map is serialized to JSON and printed to stdout.
"""

import argparse
import collections
import json
import string

from util import run
from html_parser import HTML_TOKEN_TYPES


MAX_ASCII_INDEX = string.printable.index("~")


def token_num_to_char(i):
    assert i >= 0
    if i <= MAX_ASCII_INDEX:
        return string.printable[i]
    return chr(i - MAX_ASCII_INDEX + 160)


def get_node_tokenizer_tokens(tokenizer_path):
    """
    Return a list of token types of the Node.js tokenizer at given path.
    """
    node_print_tokentypes = (
        "console.log(JSON.stringify(Array.from(require('{:s}').tokenTypes)))".format(
            tokenizer_path
        )
    )
    stdout = run(["node", "--eval", node_print_tokentypes], '')
    return json.loads(stdout.decode("utf-8"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "js_tokenizer", type=str, help="Path to a Node.js JavaScript tokenizer"
    )
    parser.add_argument(
        "css_tokenizer", type=str, help="Path to a Node.js CSS tokenizer"
    )
    args = parser.parse_args()
    all_tokens = (
        HTML_TOKEN_TYPES
        + get_node_tokenizer_tokens(args.js_tokenizer)
        + get_node_tokenizer_tokens(args.css_tokenizer)
    )
    assert len(all_tokens) == len(
        set(all_tokens)
    ), "The set of all tokens had less elements than the list of all tokens, are all tokens unique?"
    token_map = collections.OrderedDict(
        [
            (token_type, token_num_to_char(token_num))
            for token_num, token_type in enumerate(all_tokens)
        ]
    )
    print(json.dumps(token_map, indent="  "))
