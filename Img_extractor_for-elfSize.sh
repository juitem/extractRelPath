#!/bin/bash

# Determine script directory to ensure relative paths to helper scripts work
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default Configuration variables (relative to script location)
LOG_DIR="$SCRIPT_DIR/download/logs"
IMG_DIR="$SCRIPT_DIR/download/img"
VERBOSE=""

# Parse arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --logdir) LOG_DIR="$2"; shift ;;
        --imgdir) IMG_DIR="$2"; shift ;;
        -v|--verbose) VERBOSE="-v" ;;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

# Resolve absolute paths for directories using python3
LOG_DIR=$(python3 -c "import os; print(os.path.abspath('$LOG_DIR'))")
IMG_DIR=$(python3 -c "import os; print(os.path.abspath('$IMG_DIR'))")

if [ -n "$VERBOSE" ]; then
    echo "Running in verbose mode"
    echo "Script Directory: $SCRIPT_DIR"
    echo "Log Directory:    $LOG_DIR"
    echo "Image Directory:  $IMG_DIR"
fi

# Change working directory to script location
cd "$SCRIPT_DIR" || { echo "Failed to change directory to $SCRIPT_DIR"; exit 1; }

# Global variables to store results
ROOTFS_SYMLINKS=0
OPT_SYMLINKS=0
HAL_SYMLINKS=0
MODULES_SYMLINKS=0

# Function to extract an image
extract_image() {
    local image_path=$1
    local output_dir=$2
    local log_filename=$3
    local display_name=$4
    
    echo "Extracting $display_name..."
    python3 ./extract_ext4_debugfs/extract_ext4_debugfs.py $VERBOSE "$image_path" -o "$output_dir" --log-file "$LOG_DIR/$log_filename"
    if [ $? -ne 0 ]; then
        echo "Failed to extract $display_name"
        exit 1
    fi
    
    # Set permissions
    echo "Setting permissions for $display_name..."
    chmod -R 755 "$output_dir"
}

convert_symlink() {
    local output_dir=$1
    local log_file="$LOG_DIR/fix_symlink_$(basename "$output_dir").log"
    
    # Clear previous log file
    > "$log_file"
    
    chmod -R 755 "$output_dir"
    python3 ./fix_symlink/cvt_symlink.py "$output_dir" -v >> "$log_file" 2>&1
    
    # Count fixed symlinks and store in global variables
    if [ -f "$log_file" ]; then
        FIXED_COUNT=$(grep "\[INFO\]" "$log_file" 2>/dev/null | grep "\->" | wc -l 2>/dev/null)
        if [ -z "$FIXED_COUNT" ]; then FIXED_COUNT=0; fi
        if ! [[ "$FIXED_COUNT" =~ ^[0-9]+$ ]]; then
            FIXED_COUNT=0
        fi
        
        # Store in appropriate global variable
        if [ "$(basename "$output_dir")" = "rootfs" ]; then
            ROOTFS_SYMLINKS=$FIXED_COUNT
        elif [ "$(basename "$output_dir")" = "opt" ]; then
            OPT_SYMLINKS=$FIXED_COUNT
        elif [ "$(basename "$output_dir")" = "hal" ]; then
            HAL_SYMLINKS=$FIXED_COUNT
        elif [ "$(basename "$output_dir")" = "modules" ]; then
            MODULES_SYMLINKS=$FIXED_COUNT
        fi
    fi
}

# Function to count errors in log file
count_errors_in_log() {
    local log_filename=$1
    local display_name=$2
    
    local log_file="$LOG_DIR/$log_filename"
    local error_count=0
    if [ -f "$log_file" ]; then
        error_count=$(grep -c "Operation not permitted while changing ownership" "$log_file" 2>/dev/null)
        if [ -z "$error_count" ]; then error_count=0; fi
    fi
    
    echo "$error_count"
}

# Function to display errors from log file
display_errors_from_log() {
    local log_filename=$1
    local display_name=$2
    
    local log_file="$LOG_DIR/$log_filename"
    local error_count=0
    if [ -f "$log_file" ]; then
        error_count=$(grep -c "Operation not permitted while changing ownership" "$log_file" 2>/dev/null)
        if [ -z "$error_count" ]; then error_count=0; fi
        if [ "$error_count" -gt 0 ]; then
            echo "  $display_name: $error_count ownership permission warnings"
        fi
    fi
}

# Ensure log directory exists
mkdir -p "$LOG_DIR"
mkdir -p "$IMG_DIR"

# Extract images
extract_image "$IMG_DIR/rootfs.img" "$IMG_DIR/extracted/rootfs" "extract_errors_ROOTFS.log" "rootfs.img"
convert_symlink "$IMG_DIR/extracted/rootfs"
extract_image "$IMG_DIR/hal.img" "$IMG_DIR/extracted/hal" "extract_errors_hal.log" "hal.img"
convert_symlink "$IMG_DIR/extracted/hal"
extract_image "$IMG_DIR/modules.img" "$IMG_DIR/extracted/modules" "extract_errors_modules.log" "modules.img"
convert_symlink "$IMG_DIR/extracted/modules"
extract_image "$IMG_DIR/system-data.img" "$IMG_DIR/extracted/opt" "extract_errors_opt.log" "system-data.img"
convert_symlink "$IMG_DIR/extracted/opt"
# mkdir -p "$IMG_DIR/ROOTFS/opt/usr/home"
# mkdir -p "$IMG_DIR/ROOTFS/opt/var"

echo "Extraction completed!"

# Display all results together
echo ""
echo "=== SUMMARY ==="

# Display symlink fixing results
if [ "$ROOTFS_SYMLINKS" -gt 0 ] || [ "$OPT_SYMLINKS" -gt 0 ] || [ "$HAL_SYMLINKS" -gt 0 ] || [ "$MODULES_SYMLINKS" -gt 0 ]; then
    echo "Symlink fixing results:"
    if [ "$ROOTFS_SYMLINKS" -gt 0 ]; then
        echo "  ROOTFS symlinks fixed: $ROOTFS_SYMLINKS"
    fi
    if [ "$OPT_SYMLINKS" -gt 0 ]; then
        echo "  OPT symlinks fixed: $OPT_SYMLINKS"
    fi
    if [ "$HAL_SYMLINKS" -gt 0 ]; then
        echo "  HAL symlinks fixed: $HAL_SYMLINKS"
    fi
    if [ "$MODULES_SYMLINKS" -gt 0 ]; then
        echo "  MODULES symlinks fixed: $MODULES_SYMLINKS"
    fi
    echo ""
fi

# Count and display errors
echo "Ownership permission warnings:"
ROOTFS_ERRORS=$(count_errors_in_log "extract_errors_rootfs.log" "ROOTFS")
OPT_ERRORS=$(count_errors_in_log "extract_errors_opt.log" "OPT")
HAL_ERRORS=$(count_errors_in_log "extract_errors_hal.log" "HAL")
MODULES_ERRORS=$(count_errors_in_log "extract_errors_modules.log" "MODULES")
# Display errors
display_errors_from_log "extract_errors_rootfs.log" "ROOTFS"
display_errors_from_log "extract_errors_opt.log" "OPT"
display_errors_from_log "extract_errors_hal.log" "HAL"
display_errors_from_log "extract_errors_modules.log" "MODULES"

# Show total errors
TOTAL_ERRORS=$((ROOTFS_ERRORS + OPT_ERRORS + HAL_ERRORS + MODULES_ERRORS))
if [ "$TOTAL_ERRORS" -gt 0 ]; then
    echo ""
    echo "Total ownership permission warnings: $TOTAL_ERRORS"
else
    echo ""
    echo "No ownership permission warnings encountered."
fi

echo "Log files:"
echo "  $LOG_DIR/extract_errors_rootfs.log"
echo "  $LOG_DIR/extract_errors_opt.log"
echo "  $LOG_DIR/extract_errors_hal.log"
echo "  $LOG_DIR/extract_errors_modules.log"

