#!/usr/bin/env python3

import argparse
import os
import sys


def is_absolute_link_target(target: str) -> bool:
    """Check if symlink target is an absolute path."""
    return target.startswith("/")


def make_relative_target(root_dir: str, link_path: str, abs_target: str) -> str | None:
    """
    Convert an absolute target like '/usr/lib/libc.so'
    into a relative path from directory of link_path, if possible.

    Returns None if the resolved target does not exist under root_dir.
    """
    root_dir = os.path.abspath(root_dir)

    # Resolved absolute path within extracted root
    candidate = os.path.normpath(os.path.join(root_dir, abs_target.lstrip("/")))

    # Ensure candidate is inside root_dir
    if not candidate.startswith(root_dir + os.sep) and candidate != root_dir:
        return None

    if not os.path.exists(candidate):
        return None

    link_dir = os.path.dirname(os.path.abspath(link_path))
    rel = os.path.relpath(candidate, link_dir)
    return rel


def fix_symlink(root_dir: str, link_path: str, dry_run: bool, verbose: bool) -> None:
    try:
        target = os.readlink(link_path)
    except OSError as e:
        if verbose:
            print(f"[WARN] Failed to readlink {link_path}: {e}")
        return

    if not is_absolute_link_target(target):
        # Not an absolute target; ignore
        return

    new_target = make_relative_target(root_dir, link_path, target)
    if new_target is None:
        if verbose:
            print(f"[INFO] Skipping {link_path} -> {target} (no valid target under root)")
        return

    if verbose:
        print(f"[INFO] {link_path}: {target} -> {new_target}")

    if dry_run:
        return

    # Replace symlink
    try:
        os.unlink(link_path)
        os.symlink(new_target, link_path)
    except OSError as e:
        print(f"[ERROR] Failed to update symlink {link_path}: {e}", file=sys.stderr)


def walk_and_fix(root_dir: str, dry_run: bool, verbose: bool) -> None:
    root_dir = os.path.abspath(root_dir)
    if not os.path.isdir(root_dir):
        raise NotADirectoryError(f"Not a directory: {root_dir}")

    for cur_dir, dirs, files in os.walk(root_dir, followlinks=False):
        # Check entries in this directory
        for name in dirs + files:
            path = os.path.join(cur_dir, name)
            if os.path.islink(path):
                fix_symlink(root_dir, path, dry_run=dry_run, verbose=verbose)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Fix symlinks in an extracted root by converting absolute targets "
            "to relative paths (if the target exists under the root)."
        )
    )
    parser.add_argument(
        "root_dir",
        help="Extracted root directory (top of filesystem tree)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not modify anything, just print what would change",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        walk_and_fix(args.root_dir, dry_run=args.dry_run, verbose=args.verbose)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()