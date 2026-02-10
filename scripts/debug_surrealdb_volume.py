#!/usr/bin/env python3
"""One-off debug script: log volume /data permissions and write attempt as NDJSON.
Run inside a container with surrealdb-data mounted at /data. Log is written inside
the volume at /data/debug.log; if COPY_LOG_TO is set, the file is copied there
(e.g. host-mounted path) for reading."""
import json
import os
import shutil
import time

# #region agent log
# Prefer writing inside the Docker volume so we get data regardless of host mounts.
LOG_PATH = os.getenv("DEBUG_LOG_PATH", "/data/debug.log")
COPY_LOG_TO = os.getenv("COPY_LOG_TO")  # e.g. /out/debug.log for host copy
SESSION = "debug-session"
TS = int(time.time() * 1000)
# #endregion

def write_log(obj: dict) -> None:
    # #region agent log
    obj.setdefault("sessionId", SESSION)
    obj.setdefault("timestamp", TS)
    dirpath = os.path.dirname(LOG_PATH)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(obj) + "\n")
    # #endregion

def main() -> None:
    # Hypothesis A: container user (SurrealDB runs as 65532)
    # #region agent log
    write_log({
        "hypothesisId": "A",
        "location": "debug_surrealdb_volume.py:main",
        "message": "container_user",
        "data": {"uid": os.getuid(), "gid": os.getgid(), "cwd": os.getcwd()},
    })
    # #endregion

    data_path = "/data"
    # Hypothesis B: /data exists and its ownership
    # #region agent log
    if os.path.exists(data_path):
        st = os.stat(data_path)
        write_log({
            "hypothesisId": "B",
            "location": "debug_surrealdb_volume.py:stat_data",
            "message": "data_volume_stat",
            "data": {
                "path": data_path,
                "mode_oct": oct(st.st_mode),
                "uid": st.st_uid,
                "gid": st.st_gid,
                "listdir": os.listdir(data_path) if os.path.isdir(data_path) else "not_dir",
            },
        })
    else:
        write_log({
            "hypothesisId": "B",
            "location": "debug_surrealdb_volume.py:stat_data",
            "message": "data_volume_missing",
            "data": {"path": data_path},
        })
    # #endregion

    # Hypothesis C: can we create a file under /data? (same as RocksDB dir create)
    # #region agent log
    test_file = os.path.join(data_path, "debug_write_test")
    err = None
    try:
        with open(test_file, "w") as f:
            f.write("ok")
        write_ok = True
        try:
            os.remove(test_file)
        except Exception:
            pass
    except Exception as e:
        write_ok = False
        err = str(e)
    write_log({
        "hypothesisId": "C",
        "location": "debug_surrealdb_volume.py:write_attempt",
        "message": "write_attempt_under_data",
        "data": {"path": test_file, "write_ok": write_ok, "error": err if not write_ok else None},
    })
    # #endregion

    # Hypothesis D: can we create a directory under /data? (RocksDB creates dirs)
    # #region agent log
    test_dir = os.path.join(data_path, "debug_mkdir_test")
    err_d = None
    try:
        os.mkdir(test_dir)
        mkdir_ok = True
        try:
            os.rmdir(test_dir)
        except Exception:
            pass
    except Exception as e:
        mkdir_ok = False
        err_d = str(e)
    write_log({
        "hypothesisId": "D",
        "location": "debug_surrealdb_volume.py:mkdir_attempt",
        "message": "mkdir_attempt_under_data",
        "data": {"path": test_dir, "mkdir_ok": mkdir_ok, "error": err_d if not mkdir_ok else None},
    })
    # #endregion

    # Copy log from volume to host-mounted path if requested
    # #region agent log
    if COPY_LOG_TO and os.path.isfile(LOG_PATH):
        out_dir = os.path.dirname(COPY_LOG_TO)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        shutil.copy2(LOG_PATH, COPY_LOG_TO)
    # #endregion

if __name__ == "__main__":
    main()
