
import subprocess

class RunError(Exception):
    pass

def run(cmd, stdin):
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate(bytes(stdin, 'UTF-8'))
    if p.returncode != 0:
        print(err)
        raise RunError(err)
    return out
