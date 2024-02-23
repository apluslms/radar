import json
import subprocess


class RunError(Exception):
    pass


def run(cmd, stdin):
    """
    Runs a command in subprocess.

    @param stdin the standard input str
    @return the standard output str
    """
    p = subprocess.Popen(
        cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    out, err = p.communicate(bytes(stdin, 'UTF-8'))
    if p.returncode != 0:
        raise RunError(err)
    return out


def parse_from_json(fname):
    with open(fname) as f:
        return json.load(f)


def key_to_list_mappings_inverted(d):
    new_d = {}
    for key, values in d.items():
        new_d.update(dict.fromkeys(values, key))
    return new_d
