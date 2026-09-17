#!/bin/bash

set -euo pipefail

DEFAULT_REPORT_NAME="system-report"
TIMESTAMP="$(date '+%Y%m%d-%H%M%S')"
CURRENT_DATE="$(date '+%A %d %B %Y, %H:%M:%S %Z')"
HOST_NAME="$(hostname)"
USER_NAME="$(whoami)"
OS_NAME="$(uname -s)"
OS_RELEASE="$(uname -r)"
OS_ARCH="$(uname -m)"
OUTPUT_ROOT="${SYSINFO_OUTPUT_DIR:-${PWD}/system-reports}"
TOP_PROCESS_COUNT=10
LINE_WIDTH=105

banner() {
    echo ""
    echo "=================================================================="
    echo "  $1"
    echo "=================================================================="
}

banner "SYSTEM INFORMATION REPORT"
echo "Current date : ${CURRENT_DATE}"
echo "Hostname     : ${HOST_NAME}"
echo "Username     : ${USER_NAME}"
echo "Kernel       : ${OS_NAME} ${OS_RELEASE} (${OS_ARCH})"

banner "DISK USAGE (df -h)"
df -h

banner "RUNNING PROCESSES (top ${TOP_PROCESS_COUNT} by CPU)"
ps aux | awk 'NR == 1' | cut -c "1-${LINE_WIDTH}"
ps aux | awk 'NR > 1' | sort -b -k3,3 -nr | awk -v rows="${TOP_PROCESS_COUNT}" 'NR <= rows' | cut -c "1-${LINE_WIDTH}"

banner "REPORT INPUT"
REPORT_NAME=""
read -r -p "Enter a name for this report [${DEFAULT_REPORT_NAME}]: " REPORT_NAME || REPORT_NAME=""
REPORT_NAME="$(printf '%s' "${REPORT_NAME}" | tr -cd '[:alnum:]._-')"
REPORT_NAME="${REPORT_NAME:-${DEFAULT_REPORT_NAME}}"
echo "Using report name: ${REPORT_NAME}"

REPORT_DIR="${OUTPUT_ROOT}/${REPORT_NAME}-${TIMESTAMP}"
PROCESS_FILE="${REPORT_DIR}/processes.txt"
DISK_FILE="${REPORT_DIR}/disk-usage.txt"
SUMMARY_FILE="${REPORT_DIR}/summary.txt"

banner "CREATING REPORT DIRECTORY AND FILES"
mkdir -p "${REPORT_DIR}"
echo "Directory created : ${REPORT_DIR}"

touch "${PROCESS_FILE}" "${DISK_FILE}" "${SUMMARY_FILE}"
echo "Files created     : processes.txt, disk-usage.txt, summary.txt"

ps aux > "${PROCESS_FILE}"
df -h > "${DISK_FILE}"
echo "Processes saved   : ${PROCESS_FILE}"
echo "Disk usage saved  : ${DISK_FILE}"

PROCESS_COUNT="$(( $(wc -l < "${PROCESS_FILE}") - 1 ))"

{
    echo "Report name   : ${REPORT_NAME}"
    echo "Generated on  : ${CURRENT_DATE}"
    echo "Hostname      : ${HOST_NAME}"
    echo "Username      : ${USER_NAME}"
    echo "Kernel        : ${OS_NAME} ${OS_RELEASE} (${OS_ARCH})"
    echo "Processes     : ${PROCESS_COUNT}"
    echo "Report folder : ${REPORT_DIR}"
} > "${SUMMARY_FILE}"

banner "SUMMARY"
cat "${SUMMARY_FILE}"

echo ""
echo "Files in ${REPORT_DIR}:"
ls -l "${REPORT_DIR}"
echo ""
echo "Done. ${PROCESS_COUNT} running processes recorded in ${PROCESS_FILE}"
