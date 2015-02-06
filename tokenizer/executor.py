
import subprocess

class RunError(Exception):
    pass

def run(cmd, stdin):
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate(input=stdin)
    if p.returncode != 0:
        raise RunError(err)
    return out
