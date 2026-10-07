#!/bin/bash
#
# system_info.sh - System Information Script
#
# Prints date, hostname, username, disk usage and running processes,
# then saves the process list into a file created inside a new directory.
#
# Demonstrates: variables, read -p, mkdir, touch, echo, date, df, ps,
#               and > output redirection.

echo "==============================================="
echo "           SYSTEM INFORMATION SCRIPT           "
echo "==============================================="
echo

# ---------- Variables holding system data ----------
CURRENT_DATE=$(date)
HOST_NAME=$(hostname)
USER_NAME=$(whoami)

echo "1. Current Date : $CURRENT_DATE"
echo "2. Hostname     : $HOST_NAME"
echo "3. Username     : $USER_NAME"
echo

# ---------- Disk usage ----------
echo "4. Disk Usage (df -h)"
echo "-----------------------------------------------"
df -h
echo

# ---------- Running processes ----------
echo "5. Running Processes (top 10 by CPU)"
echo "-----------------------------------------------"
ps aux --sort=-%cpu 2>/dev/null | head -n 11 || ps aux | head -n 11
echo

# ---------- Take input from the user ----------
read -p "Enter a name for the report directory: " DIR_NAME
read -p "Enter a name for the report file (without .txt): " FILE_NAME

# Fall back to defaults if the user just pressed Enter
DIR_NAME=${DIR_NAME:-system_report}
FILE_NAME=${FILE_NAME:-processes}

REPORT_FILE="$DIR_NAME/$FILE_NAME.txt"

# ---------- Create directory and file ----------
mkdir -p "$DIR_NAME"
echo "Created directory : $DIR_NAME"

touch "$REPORT_FILE"
echo "Created file      : $REPORT_FILE"
echo

# ---------- Write the report using > output redirection ----------
echo "===== SYSTEM REPORT =====" > "$REPORT_FILE"
echo "Date     : $CURRENT_DATE" >> "$REPORT_FILE"
echo "Hostname : $HOST_NAME" >> "$REPORT_FILE"
echo "User     : $USER_NAME" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "===== DISK USAGE =====" >> "$REPORT_FILE"
df -h >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "===== RUNNING PROCESSES =====" >> "$REPORT_FILE"
ps aux >> "$REPORT_FILE"

echo "Running processes saved to: $REPORT_FILE"
echo "File size: $(du -h "$REPORT_FILE" | cut -f1)"
echo
echo "----- First 15 lines of $REPORT_FILE -----"
head -n 15 "$REPORT_FILE"
echo "..."
echo
echo "Script finished successfully."
