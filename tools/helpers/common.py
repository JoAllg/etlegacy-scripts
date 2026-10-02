"""Helpers shared by the tools: the game's console log, color codes, cfg-safe text, file writes."""
import os
import re
import time

from helpers.settings import HOMEPATH

STAMP = re.compile(r"^ *\d+ ")  # game time column of every log line


# A color code as the engine reads it (src/qcommon/q_shared.h Q_IsColorString): ^ and a visible character other
# than ^ ("^^1" shows "^" in color 1, "^ " stays as it is). COLOR is its regex text for building other patterns.
COLOR_CHAR = r"[^\x00-\x20\x7f^]"
COLOR = rf"\^{COLOR_CHAR}"


def strip_colors(text):
    return re.sub(COLOR, "", text)


def clean(text):
    """Text that is safe inside a quoted cfg command: no quote, no command separator, printable latin1 only."""
    text = text.replace('"', "'").replace(";", ",")
    return "".join(c for c in text if 32 <= ord(c) < 256 and ord(c) != 127)


def write_atomic(path, text):
    """Writes a file the game may exec at any time: swapped in whole. latin1 keeps every byte as it is."""
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")  # own name per process: two tools may write the same file
    tmp.write_text(text, "latin1")
    os.replace(tmp, path)


def find_log():
    """Most recently written <HOMEPATH>/<mod>/etconsole.log (the engine writes it into fs_game), or None."""
    logs = []
    for path in HOMEPATH.glob("*/etconsole.log"):
        try:
            logs.append((path.stat().st_mtime, path))
        except OSError:
            continue
    return max(logs)[1] if logs else None


def first_line(path):
    """First line of a log as bytes: "logfile opened on <date>" (src/qcommon/common.c Com_Printf), new with every game start."""
    with open(path, "rb") as log:
        return log.readline(200)


def follow(find=find_log, pause=.2):
    """Lines of the game's console log as they are written (needs `logfile 2`, 1 buffers 4 KB), without end.
    Yields None when a log is opened, which is read from its start (the game truncates it at launch, so a replay
    restores the state), and "" each time the end of the log is reached."""
    while True:
        path = find()
        if not path:
            time.sleep(2)
            continue
        print(f"following {path}")
        yield None
        with open(path, errors="replace") as log:
            line, head = "", b""
            while True:
                line += log.readline()
                if line.endswith("\n"):
                    yield line
                    line = ""
                    continue
                yield ""
                time.sleep(pause)
                try:
                    # game restarted (a new log can outgrow a short old one between two looks, so its first line
                    # is compared too) or another mod's log is newer
                    now = first_line(path)
                    if path.stat().st_size < log.tell() or (head.endswith(b"\n") and now != head) or find() != path:
                        break
                    head = now
                except OSError:
                    break
