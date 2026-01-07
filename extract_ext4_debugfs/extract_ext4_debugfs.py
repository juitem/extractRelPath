import argparse
import os
import subprocess
import sys
from datetime import datetime


def run(cmd, verbose=False, log_file=None):
    if verbose:
        print(f"[INFO] Running: {' '.join(cmd)}")
    
    # Run command and capture output
    result = subprocess.run(
        cmd, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE,
        text=True
    )
    
    # Log stderr output if log file is provided
    if log_file and result.stderr:
        with open(log_file, 'a') as f:  # Append mode for subsequent entries in same execution
            f.write(f"[STDERR] Command: {' '.join(cmd)}\n")
            f.write(result.stderr)
            f.write("\n" + "="*50 + "\n")
    
    if result.returncode != 0:
        # Count ownership-related errors
        error_output = result.stderr if result.stderr else ""
        ownership_errors = error_output.count("Operation not permitted while changing ownership")
        
        # Return error information instead of raising exception immediately
        return {
            'success': False,
            'returncode': result.returncode,
            'stderr': error_output,
            'ownership_errors': ownership_errors,
            'cmd': ' '.join(cmd)
        }
    
    return {
        'success': True,
        'returncode': 0,
        'stderr': result.stderr if result.stderr else "",
        'ownership_errors': 0,
        'cmd': ' '.join(cmd)
    }

def ensure_output_dir(path):
    path = os.path.abspath(path)
    if os.path.exists(path):
        if not os.path.isdir(path):
            raise RuntimeError(f"Output path exists and is not a directory: {path}")
    else:
        os.makedirs(path, exist_ok=True)
    return path


def extract_ext4_with_debugfs(image_path, output_dir, debugfs_bin="debugfs", verbose=False, log_file=None):
    image_path = os.path.abspath(image_path)
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    output_dir = ensure_output_dir(output_dir)

    # debugfs command: rdump / <output_dir>
    # We quote the output dir inside the -R command.
    safe_output_dir = output_dir.replace('"', '\\"')
    rdump_cmd = f'rdump / "{safe_output_dir}"'

    cmd = [
        debugfs_bin,
        "-R",
        rdump_cmd,
        image_path,
    ]

    result = run(cmd, verbose=verbose, log_file=log_file)
    
    if not result['success']:
        # Count total ownership errors
        ownership_errors = result['ownership_errors']
        # For non-verbose mode, we don't raise exception for ownership errors
        # but we do for other errors
        if not verbose:
            # If all errors are ownership errors, we can continue
            # Otherwise, we need to raise an exception
            error_lines = result['stderr'].strip().split('\n') if result['stderr'].strip() else []
            non_ownership_errors = len(error_lines) - ownership_errors
            
            if non_ownership_errors > 0:
                raise RuntimeError(f"Command failed with {non_ownership_errors} non-ownership errors (see log for details): {result['cmd']}")
        else:
            # In verbose mode, show all errors
            raise RuntimeError(f"Command failed with code {result['returncode']}: {result['cmd']}\n{result['stderr']}")
    
    if verbose:
        print(f"[INFO] Extracted ext4 image to: {output_dir}")
    
    return result


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract an ext4 filesystem image using debugfs (no sudo required)."
    )
    parser.add_argument(
        "image",
        help="Path to ext4 image file (e.g. rootfs.ext4, rootfs.img)",
    )
    parser.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output directory to extract filesystem into",
    )
    parser.add_argument(
        "--debugfs",
        default="debugfs",
        help="debugfs executable (default: debugfs)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--log-file",
        help="Log file to store detailed error messages (default: extract_errors.log in output directory)",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        # Create default log file path if not specified
        if args.log_file:
            log_file = args.log_file
        else:
            # Create log file in output directory
            output_dir = os.path.abspath(args.output)
            ensure_output_dir(output_dir)
            log_file = os.path.join(output_dir, "extract_errors.log")
        
        # Create new log file for each execution (don't accumulate logs)
        with open(log_file, 'w') as f:
            f.write(f"=== Extraction started at {datetime.now()} ===\n")
        
        result = extract_ext4_with_debugfs(
            image_path=args.image,
            output_dir=args.output,
            debugfs_bin=args.debugfs,
            verbose=args.verbose,
            log_file=log_file,
        )
        
        # Show summary
        ownership_errors = result['ownership_errors'] if not result['success'] else 0
        if ownership_errors > 0:
            print(f"[INFO] Extraction completed with {ownership_errors} ownership permission warnings (see {log_file} for details)")
        elif result['success']:
            print(f"[INFO] Extraction completed successfully")
        else:
            print(f"[INFO] Extraction completed")
            
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
