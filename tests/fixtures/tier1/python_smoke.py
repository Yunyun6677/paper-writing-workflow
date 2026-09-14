import json
import pathlib
import sys

target = pathlib.Path(sys.argv[1])
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps({"engine": "python", "coefficient": 2.0}), encoding="utf-8")
