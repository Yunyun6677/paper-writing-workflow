"""Audited R batch bridge for smoke tests and coefficient plotting."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import time
from pathlib import Path


def file_hash(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path: Path, value: object) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def rscript_path(value: str | None = None) -> Path:
    configured = value or os.environ.get("R_SCRIPT") or shutil.which("Rscript")
    if not configured:
        raise ValueError("Set R_SCRIPT or pass --rscript with a verified Rscript executable")
    path = Path(configured).resolve()
    if not path.is_file() or path.name.lower() not in {"rscript", "rscript.exe"}:
        raise ValueError("Rscript executable is missing or has an unexpected name")
    return path


def fresh_output(value: str) -> Path:
    output = Path(value).resolve()
    if output.exists():
        raise FileExistsError("R output already exists; use a new directory")
    output.mkdir(parents=True)
    return output


def run_r(executable: Path, script: Path, arguments: list[str], cwd: Path, timeout: int, log: Path) -> dict:
    started = time.time()
    environment = os.environ.copy()
    for key in ("LC_ALL", "LC_COLLATE", "LC_CTYPE", "LC_MONETARY", "LC_TIME"):
        if environment.get(key, "").upper() == "C.UTF-8":
            environment.pop(key)
    process = subprocess.run(
        [str(executable), "--vanilla", str(script), *arguments],
        cwd=str(cwd), timeout=timeout, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace",
        env=environment,
    )
    log.write_text(
        "COMMAND: Rscript --vanilla " + script.name + "\n\nSTDOUT\n" + process.stdout
        + "\nSTDERR\n" + process.stderr,
        encoding="utf-8",
    )
    return {"returncode": process.returncode, "elapsed_seconds": round(time.time() - started, 3)}


def artifact(path: Path, root: Path) -> dict:
    resolved = path.resolve()
    if root != resolved and root not in resolved.parents:
        raise ValueError("R artifact escaped the output directory")
    return {"path": resolved.relative_to(root).as_posix(), "bytes": resolved.stat().st_size, "sha256": file_hash(resolved)}


def verify_marker(marker: Path, execution: dict, log: Path) -> None:
    if execution["returncode"] != 0 or not marker.is_file() or marker.read_text(encoding="utf-8").strip() != "complete":
        raise RuntimeError(f"R batch did not complete; inspect {log}")


def smoke(executable: Path, output_value: str, timeout: int) -> dict:
    output = fresh_output(output_value)
    script = output / "smoke.R"
    results = output / "results.csv"
    figure = output / "coefficient.svg"
    session = output / "session-info.txt"
    marker = output / "R_COMPLETE.txt"
    log = output / "execution.log"
    script.write_text(
        """args <- commandArgs(trailingOnly = TRUE)
results <- args[[1]]
figure <- args[[2]]
session_file <- args[[3]]
marker <- args[[4]]
x <- seq_len(100)
y <- 1 + 2 * x
fit <- lm(y ~ x)
coefs <- summary(fit)$coefficients
out <- data.frame(term = rownames(coefs), estimate = coefs[, 1], std_error = coefs[, 2])
write.csv(out, results, row.names = FALSE)
svg(figure, width = 7, height = 4)
plot(x, y, pch = 16, cex = 0.45, xlab = "x", ylab = "y", main = "R bridge smoke test")
abline(fit, col = "#2166ac", lwd = 2)
dev.off()
writeLines(capture.output(sessionInfo()), session_file)
writeLines("complete", marker)
""",
        encoding="utf-8",
    )
    execution = run_r(executable, script, [str(results), str(figure), str(session), str(marker)], output, timeout, log)
    verify_marker(marker, execution, log)
    with results.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    slope = next(float(row["estimate"]) for row in rows if row["term"] == "x")
    if not math.isfinite(slope) or abs(slope - 2) > 1e-10 or figure.stat().st_size < 100:
        raise RuntimeError("R smoke numerical or figure assertion failed")
    files = [script, results, figure, session, marker, log]
    receipt = {
        "schema_version": "engine-execution/1.0", "status": "complete", "engine": "r", "mode": "smoke",
        "executable_name": executable.name, "slope": slope, "artifacts": [artifact(path, output) for path in files], **execution,
    }
    write_json(output / "receipt.json", receipt)
    return receipt


def validate_coefficients(path: Path) -> None:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"term", "estimate", "std_error"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("Coefficient CSV requires term, estimate, and std_error columns")
        rows = list(reader)
    if not rows:
        raise ValueError("Coefficient CSV is empty")
    for row in rows:
        if not row["term"].strip():
            raise ValueError("Coefficient term cannot be empty")
        estimate, standard_error = float(row["estimate"]), float(row["std_error"])
        if not math.isfinite(estimate) or not math.isfinite(standard_error) or standard_error < 0:
            raise ValueError("Coefficient estimates and nonnegative standard errors must be finite")


def plot(executable: Path, input_value: str, output_value: str, script_value: str, timeout: int) -> dict:
    source = Path(input_value).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    validate_coefficients(source)
    output = fresh_output(output_value)
    normalized = output / "coefficients.csv"
    shutil.copyfile(source, normalized)
    script = Path(script_value).resolve()
    if not script.is_file():
        raise FileNotFoundError(script)
    figure, preview = output / "coefficient-plot.svg", output / "coefficient-plot.png"
    session, marker, log = output / "session-info.txt", output / "R_COMPLETE.txt", output / "execution.log"
    execution = run_r(executable, script, [str(normalized), str(figure), str(preview), str(session), str(marker)], output, timeout, log)
    verify_marker(marker, execution, log)
    if not figure.is_file() or figure.stat().st_size < 100:
        raise RuntimeError("R did not create a valid SVG figure")
    if not preview.is_file() or preview.stat().st_size < 100:
        raise RuntimeError("R did not create a valid PNG preview")
    files = [normalized, figure, preview, session, marker, log]
    receipt = {
        "schema_version": "engine-execution/1.0", "status": "complete", "engine": "r", "mode": "coefficient-plot",
        "executable_name": executable.name, "source_sha256": file_hash(source),
        "script_sha256": file_hash(script), "artifacts": [artifact(path, output) for path in files], **execution,
    }
    write_json(output / "receipt.json", receipt)
    return receipt


def analysis(executable: Path, input_value: str, output_value: str, script_value: str, timeout: int) -> dict:
    source, script = Path(input_value).resolve(), Path(script_value).resolve()
    if not source.is_file() or not script.is_file():
        raise FileNotFoundError("R analysis input or script is missing")
    output = fresh_output(output_value)
    log, marker = output / "execution.log", output / "R_COMPLETE.txt"
    execution = run_r(executable, script, [str(source), str(output)], output, timeout, log)
    verify_marker(marker, execution, log)
    produced = sorted(path for path in output.rglob("*") if path.is_file())
    if not any(path.suffix.lower() in {".csv", ".json"} for path in produced):
        raise RuntimeError("R analysis produced no machine-readable CSV or JSON result")
    if any(path.is_symlink() for path in produced):
        raise RuntimeError("R analysis output cannot contain symbolic links")
    receipt = {
        "schema_version": "engine-execution/1.0", "status": "complete", "engine": "r", "mode": "analysis",
        "executable_name": executable.name, "source_sha256": file_hash(source), "script_sha256": file_hash(script),
        "artifacts": [artifact(path, output) for path in produced], **execution,
    }
    write_json(output / "receipt.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--smoke", action="store_true")
    mode.add_argument("--plot", action="store_true")
    mode.add_argument("--analysis", action="store_true")
    parser.add_argument("--rscript")
    parser.add_argument("--input")
    parser.add_argument("--output", required=True)
    parser.add_argument("--plot-script", default=str(Path(__file__).with_name("plot_coefficients.R")))
    parser.add_argument("--analysis-script")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    try:
        executable = rscript_path(args.rscript)
        if args.smoke:
            receipt = smoke(executable, args.output, args.timeout)
        elif args.plot:
            if not args.input:
                raise ValueError("--input is required with --plot")
            receipt = plot(executable, args.input, args.output, args.plot_script, args.timeout)
        else:
            if not args.input or not args.analysis_script:
                raise ValueError("--input and --analysis-script are required with --analysis")
            receipt = analysis(executable, args.input, args.output, args.analysis_script, args.timeout)
        print(json.dumps({"status": receipt["status"], "engine": "r", "mode": receipt["mode"]}))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
