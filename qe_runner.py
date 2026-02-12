#!/usr/bin/env python3
"""
Quantum Espresso runner
Executes pw.x with basic error detection, logging, and timeout handling.
"""
import argparse
import logging
import os
import re
import shutil
import subprocess
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
LOG = logging.getLogger("qe_runner")

ERROR_PATTERNS = [
    r"Error in routine",
    r"MPI_ABORT",
    r"forrtl: severe",
    r"Maximum CPU time exceeded",
    r"cannot open file",
    r"ERROR",
]

SUCCESS_PATTERNS = [
    r"convergence has been achieved",
    r"JOB DONE\.",
]


def _find_pw_executable(pw_cmd):
    if os.path.isabs(pw_cmd) or "/" in pw_cmd:
        return pw_cmd if os.path.exists(pw_cmd) else None
    return shutil.which(pw_cmd)


def _parse_namelist_value(text, key):
    pattern = re.compile(rf"{key}\s*=\s*['\"]?([^,'\"\s]+)", re.IGNORECASE)
    match = pattern.search(text)
    return match.group(1) if match else None


def _ensure_output_dirs(input_path):
    try:
        content = input_path.read_text()
    except OSError:
        return

    outdir = _parse_namelist_value(content, "outdir")
    if outdir:
        out_path = Path(outdir)
        if not out_path.is_absolute():
            out_path = input_path.parent / out_path
        out_path.mkdir(parents=True, exist_ok=True)

    pseudo_dir = _parse_namelist_value(content, "pseudo_dir")
    if pseudo_dir:
        pseudo_path = Path(pseudo_dir)
        if not pseudo_path.is_absolute():
            pseudo_path = input_path.parent / pseudo_path
        if not pseudo_path.exists():
            LOG.warning("Pseudo directory not found: %s", pseudo_path)


def _detect_qe_errors(output_path):
    try:
        content = output_path.read_text(errors="ignore")
    except OSError:
        return False, False

    has_error = any(re.search(pat, content) for pat in ERROR_PATTERNS)
    has_success = any(re.search(pat, content) for pat in SUCCESS_PATTERNS)
    return has_error, has_success


def run_pw(input_file, pw_exec, output_path, error_path, cwd, timeout, mpi_cmd):
    cmd = []
    if mpi_cmd:
        cmd.extend(mpi_cmd)
    cmd.extend([pw_exec, "-in", str(input_file)])

    LOG.info("Running: %s", " ".join(cmd))
    start_time = time.time()

    with open(output_path, "w") as out_f, open(error_path, "w") as err_f:
        process = subprocess.Popen(cmd, cwd=cwd, stdout=out_f, stderr=err_f)
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
            LOG.error("QE run timed out after %s seconds", timeout)
            return 124

    elapsed = time.time() - start_time
    LOG.info("QE finished in %.1f s with exit code %s", elapsed, process.returncode)
    return process.returncode


def main():
    parser = argparse.ArgumentParser(description="Run Quantum Espresso pw.x with logging and timeout handling.")
    parser.add_argument("input", type=str, help="Input .in file")
    parser.add_argument("--pw", type=str, default="pw.x", help="pw.x executable or path (default: pw.x)")
    parser.add_argument("--mpi", nargs="+", default=None, help="MPI command prefix (e.g., mpirun -np 4)")
    parser.add_argument("--timeout", type=int, default=None, help="Timeout in seconds")
    parser.add_argument("--run_dir", type=str, default="qe_runs", help="Directory for logs and .out files")
    parser.add_argument("--out", type=str, default=None, help="Output .out file name (default: <input>.out)")
    parser.add_argument("--no_timestamp", action="store_true", help="Write outputs directly into run_dir")

    args = parser.parse_args()
    input_path = Path(args.input).resolve()

    if not input_path.exists():
        LOG.error("Input file not found: %s", input_path)
        return 1

    pw_exec = _find_pw_executable(args.pw)
    if not pw_exec:
        LOG.error("pw.x not found. Provide --pw or load Quantum Espresso in PATH.")
        return 1

    _ensure_output_dirs(input_path)

    if args.no_timestamp:
        run_dir = Path(args.run_dir)
    else:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        run_dir = Path(args.run_dir) / f"{input_path.stem}_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    output_name = args.out or f"{input_path.stem}.out"
    output_path = run_dir / output_name
    error_path = run_dir / f"{input_path.stem}.err"

    exit_code = run_pw(
        input_file=input_path,
        pw_exec=pw_exec,
        output_path=output_path,
        error_path=error_path,
        cwd=input_path.parent,
        timeout=args.timeout,
        mpi_cmd=args.mpi,
    )

    has_error, has_success = _detect_qe_errors(output_path)
    if has_error:
        LOG.error("QE output indicates an error. See %s", output_path)
        return 2
    if not has_success:
        LOG.warning("QE finished without a clear success marker. Check %s", output_path)

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
