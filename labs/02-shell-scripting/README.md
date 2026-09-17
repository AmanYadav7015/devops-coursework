# Homework 2: Shell Scripting - System Information Script

Build one shell script that reports the current date, hostname, username, disk usage and running
processes, stores data in variables, asks the user for input with `read -p`, creates a directory with
`mkdir`, creates files with `touch`, and writes the running-process list into a file using `>`
output redirection.

Everything below was executed on a real machine and the output blocks are copied from the terminal
as-is.

- Host: macOS (Darwin 25.5.0, arm64), GNU bash 3.2.57
- Cross-check: `ubuntu:24.04` and `alpine:latest` containers on Docker Desktop

---

## Requirement checklist

| Requirement | Where it lives in `system-info.sh` |
| --- | --- |
| Current date | line 7 `CURRENT_DATE="$(date '+%A %d %B %Y, %H:%M:%S %Z')"` |
| Hostname | line 8 `HOST_NAME="$(hostname)"` |
| Username | line 9 `USER_NAME="$(whoami)"` |
| Disk usage | line 31 `df -h` |
| Running processes | lines 34-35 `ps aux \| ...` |
| Variables | lines 5-15 and every `${VAR}` expansion after |
| User input | line 39 `read -r -p "Enter a name for this report [...]: " REPORT_NAME` |
| Directory creation | line 50 `mkdir -p "${REPORT_DIR}"` |
| File creation | line 53 `touch "${PROCESS_FILE}" "${DISK_FILE}" "${SUMMARY_FILE}"` |
| `>` redirection of process info | line 56 `ps aux > "${PROCESS_FILE}"` |

Verify it yourself:

```bash
grep -n -E 'date |hostname|whoami|df -h|ps aux|read -r -p|mkdir -p|touch |> "\$\{' system-info.sh
```

Output:

```text
6:TIMESTAMP="$(date '+%Y%m%d-%H%M%S')"
7:CURRENT_DATE="$(date '+%A %d %B %Y, %H:%M:%S %Z')"
8:HOST_NAME="$(hostname)"
9:USER_NAME="$(whoami)"
25:echo "Current date : ${CURRENT_DATE}"
30:banner "DISK USAGE (df -h)"
31:df -h
34:ps aux | awk 'NR == 1' | cut -c "1-${LINE_WIDTH}"
35:ps aux | awk 'NR > 1' | sort -b -k3,3 -nr | awk -v rows="${TOP_PROCESS_COUNT}" 'NR <= rows' | cut -c "1-${LINE_WIDTH}"
39:read -r -p "Enter a name for this report [${DEFAULT_REPORT_NAME}]: " REPORT_NAME || REPORT_NAME=""
50:mkdir -p "${REPORT_DIR}"
53:touch "${PROCESS_FILE}" "${DISK_FILE}" "${SUMMARY_FILE}"
56:ps aux > "${PROCESS_FILE}"
57:df -h > "${DISK_FILE}"
71:} > "${SUMMARY_FILE}"
```

---

## The script

```bash
cat system-info.sh
```

```bash
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
```

### Walkthrough

**`set -euo pipefail`** - the safety belt. `-e` aborts on the first failing command, `-u` aborts on an
undefined variable (a typo in `${REPORT_DIR}` would otherwise silently expand to an empty string and
`mkdir` would create junk in the wrong place), and `pipefail` makes a pipeline fail if *any* stage
fails, not just the last one.

**Variables block (lines 5-15)** - every value the script needs is captured once, at the top, into a
named variable. `TIMESTAMP` is used to make each report folder unique, `CURRENT_DATE` is the
human-readable date printed and saved, and `OUTPUT_ROOT` uses `${SYSINFO_OUTPUT_DIR:-${PWD}/system-reports}`
so the report location can be overridden from the environment without editing the script.

**`banner()`** - a small function so the section headings are written once instead of copy-pasted
six times.

**Process listing (lines 34-35)** - the header row is printed first, then the remaining rows are
sorted numerically in reverse on field 3 (`%CPU`) and the top 10 are kept. `awk 'NR <= rows'` is used
instead of `head -n` on purpose: `head` closes the pipe as soon as it has enough lines, `ps` gets
SIGPIPE, exits 141, and with `pipefail` + `set -e` the whole script dies at that point (the first
draft of this script did exactly that and exited with code 141). `awk` drains its input, so there is
no SIGPIPE.

**`read -r -p` (line 39)** - `-p` shows the prompt, `-r` stops backslashes from being treated as
escapes. `|| REPORT_NAME=""` handles the piped / non-interactive case: at EOF `read` returns non-zero
and `set -e` would otherwise kill the script. The next two lines strip anything that is not a letter,
digit, dot, underscore or dash (so a name like `my report /../etc` cannot escape the output folder)
and then fall back to `DEFAULT_REPORT_NAME` if what is left is empty. That is why the script runs
both interactively and under a pipe.

**`mkdir` / `touch` / `>` (lines 50-71)** - `mkdir -p` creates the timestamped report directory,
`touch` creates the three empty files, then `ps aux > processes.txt` and `df -h > disk-usage.txt`
overwrite them with real content. The summary is written with a grouped redirect `{ ...; } > file`,
which is the same `>` operator applied to a block instead of a single command.

**Quoting** - every variable expansion is `"${QUOTED}"`, so a path containing a space (very common on
macOS) does not split into two arguments.

---

## Step 1: Make the script executable

```bash
cd homework/02-shell-scripting
chmod +x system-info.sh
ls -l
```

Output:

```text
total 8
-rwxr-xr-x  1 aman  staff  2474 Sep 17 21:40 system-info.sh
```

Check the syntax without executing anything:

```bash
bash -n system-info.sh && echo "SYNTAX OK"
```

Output:

```text
SYNTAX OK
```

---

## Step 2: Run it non-interactively (piped input)

```bash
echo "myreport" | bash system-info.sh
```

Output:

```text
==================================================================
  SYSTEM INFORMATION REPORT
==================================================================
Current date : Thursday 17 September 2026, 21:40:49 IST
Hostname     : MacBook-Pro-7.local
Username     : aman
Kernel       : Darwin 25.5.0 (arm64)

==================================================================
  DISK USAGE (df -h)
==================================================================
Filesystem        Size    Used   Avail Capacity iused ifree %iused  Mounted on
/dev/disk3s1s1   926Gi    16Gi   516Gi     3%    459k  4.3G    0%   /
devfs            205Ki   205Ki     0Bi   100%     708     0  100%   /dev
/dev/disk3s6     926Gi    14Gi   516Gi     3%      14  5.4G    0%   /System/Volumes/VM
/dev/disk3s2     926Gi    17Gi   516Gi     4%    2.2k  5.4G    0%   /System/Volumes/Preboot
/dev/disk3s4     926Gi   870Mi   516Gi     1%     538  5.4G    0%   /System/Volumes/Update
/dev/disk1s2     550Mi   6.0Mi   531Mi     2%       1  5.4M    0%   /System/Volumes/xarts
/dev/disk1s1     550Mi   5.9Mi   531Mi     2%      43  5.4M    0%   /System/Volumes/iSCPreboot
/dev/disk1s3     550Mi   2.3Mi   531Mi     1%     108  5.4M    0%   /System/Volumes/Hardware
/dev/disk3s5     926Gi   360Gi   516Gi    42%    3.1M  5.4G    0%   /System/Volumes/Data
map auto_home      0Bi     0Bi     0Bi   100%       0     0     -   /System/Volumes/Data/home
/dev/disk2s1     5.0Gi   1.3Gi   3.7Gi    26%      50   39M    0%   /System/Volumes/Update/SFR/mnt1
/dev/disk3s1     926Gi    16Gi   516Gi     3%    459k  4.3G    0%   /System/Volumes/Update/mnt1

==================================================================
  RUNNING PROCESSES (top 10 by CPU)
==================================================================
USER               PID  %CPU %MEM      VSZ    RSS   TT  STAT STARTED      TIME COMMAND
aman             23446  87.8 12.0 443790672 3019584   ??  Ss    9:38PM   0:51.62 /System/Library/Framewor
aman             98796  13.0  0.8 437991280 207296   ??  R     5:54PM   0:58.29 /Applications/Docker.app/
_windowserver      168  11.4  0.5 436377520 115072   ??  Ss    7Sep26 550:24.15 /System/Library/PrivateFr
aman             44678   8.9  1.0 436320352 241104   ??  S    12:42AM   1:35.82 /System/Library/PrivateFr
_driverkit       60975   6.6  0.2 435328560  47664   ??  Rs   Sun04PM  61:01.56 /System/Library/DriverExt
aman             24364   4.8  0.1 435427312  25936   ??  S     9:40PM   0:00.08 /System/Library/CoreServi
aman             24363   4.7  0.1 435362944  20176   ??  S     9:40PM   0:00.06 /usr/sbin/screencapture -
root               137   4.1  0.1 435405584  12928   ??  Ss    7Sep26   9:38.02 /usr/libexec/opendirector
aman             22150   4.0  2.3 441029696 590192 s006  S+    8:06PM   0:42.37 <redacted>
aman             52760   2.4  1.7 442086000 439904 s003  S+   Sat06PM 175:28.93 <redacted>

==================================================================
  REPORT INPUT
==================================================================
Using report name: myreport

==================================================================
  CREATING REPORT DIRECTORY AND FILES
==================================================================
Directory created : /Users/aman/Desktop/devops-heros/homework/02-shell-scripting/system-reports/myreport-20260917-214049
Files created     : processes.txt, disk-usage.txt, summary.txt
Processes saved   : /Users/aman/Desktop/devops-heros/homework/02-shell-scripting/system-reports/myreport-20260917-214049/processes.txt
Disk usage saved  : /Users/aman/Desktop/devops-heros/homework/02-shell-scripting/system-reports/myreport-20260917-214049/disk-usage.txt

==================================================================
  SUMMARY
==================================================================
Report name   : myreport
Generated on  : Thursday 17 September 2026, 21:40:49 IST
Hostname      : MacBook-Pro-7.local
Username      : aman
Kernel        : Darwin 25.5.0 (arm64)
Processes     : 583
Report folder : /Users/aman/Desktop/devops-heros/homework/02-shell-scripting/system-reports/myreport-20260917-214049

Files in /Users/aman/Desktop/devops-heros/homework/02-shell-scripting/system-reports/myreport-20260917-214049:
total 328
-rw-r--r--  1 aman  staff    1149 Sep 17 21:40 disk-usage.txt
-rw-r--r--  1 aman  staff  158151 Sep 17 21:40 processes.txt
-rw-r--r--  1 aman  staff     314 Sep 17 21:40 summary.txt

Done. 583 running processes recorded in /Users/aman/Desktop/devops-heros/homework/02-shell-scripting/system-reports/myreport-20260917-214049/processes.txt
```

Two `COMMAND` values in the listing above are shown as `<redacted>`; they were local developer
tooling processes and are masked here. Every other column and row is verbatim captured output.


The `read -p` prompt does not appear here. That is bash behaviour, not a bug: bash only prints the
`-p` prompt when standard input is a terminal. The value `myreport` still arrives from the pipe,
which is why the folder is named `myreport-20260917-214049`. The script printed `Using report name:`
so the chosen value is visible either way.

---

## Step 3: Run it interactively (prompt visible)

To prove the prompt renders, the script is run under a pseudo-terminal and only Enter is pressed, so
the default is used:

```bash
printf '\n' | script -q /dev/null bash system-info.sh
```

Output (report-input section onwards):

```text
  REPORT INPUT
==================================================================
Enter a name for this report [system-report]: Using report name: system-report

==================================================================
  CREATING REPORT DIRECTORY AND FILES
==================================================================
Directory created : /Users/aman/Desktop/devops-heros/homework/02-shell-scripting/system-reports/system-report-20260917-214124
Files created     : processes.txt, disk-usage.txt, summary.txt
```

The prompt shows `[system-report]`, Enter is pressed, the empty answer falls back to the default and
the folder is named `system-report-...`. Running `./system-info.sh` normally in a terminal behaves
exactly the same.

---

## Step 4: Inspect what the script created

```bash
ls -lR system-reports
```

Output:

```text
total 0
drwxr-xr-x  5 aman  staff  160 Sep 17 21:40 myreport-20260917-214049

system-reports/myreport-20260917-214049:
total 328
-rw-r--r--  1 aman  staff    1149 Sep 17 21:40 disk-usage.txt
-rw-r--r--  1 aman  staff  158151 Sep 17 21:40 processes.txt
-rw-r--r--  1 aman  staff     314 Sep 17 21:40 summary.txt
```

### The process file written with `>`

```bash
wc -l system-reports/*/processes.txt
head -n 6 system-reports/*/processes.txt | cut -c1-105
```

Output:

```text
     584 system-reports/myreport-20260917-214049/processes.txt
USER               PID  %CPU %MEM      VSZ    RSS   TT  STAT STARTED      TIME COMMAND
aman             23446  85.2 12.0 443790672 3019584   ??  Rs    9:38PM   0:51.68 /System/Library/Framewor
aman             98796  17.2  0.8 437991280 207296   ??  S     5:54PM   0:58.30 /Applications/Docker.app/
_windowserver      168  11.4  0.5 436377520 115120   ??  Ss    7Sep26 550:24.16 /System/Library/PrivateFr
_driverkit       60975   6.5  0.2 435328560  47664   ??  Ss   Sun04PM  61:01.56 /System/Library/DriverExt
aman             24363   5.5  0.1 435362944  20176   ??  S     9:40PM   0:00.07 /usr/sbin/screencapture -
```

584 lines = 1 header + 583 processes, which matches the `Processes : 583` line in the summary. The
`cut -c1-105` above is only for readability in this README; the file itself holds the full untruncated
`ps aux` output, including long Chrome and Docker command lines.

### The summary file

```bash
cat system-reports/*/summary.txt
```

Output:

```text
Report name   : myreport
Generated on  : Thursday 17 September 2026, 21:40:49 IST
Hostname      : MacBook-Pro-7.local
Username      : aman
Kernel        : Darwin 25.5.0 (arm64)
Processes     : 583
Report folder : /Users/aman/Desktop/devops-heros/homework/02-shell-scripting/system-reports/myreport-20260917-214049
```

### The disk usage file

```bash
cat system-reports/*/disk-usage.txt
```

Output:

```text
Filesystem        Size    Used   Avail Capacity iused ifree %iused  Mounted on
/dev/disk3s1s1   926Gi    16Gi   516Gi     3%    459k  4.3G    0%   /
devfs            205Ki   205Ki     0Bi   100%     708     0  100%   /dev
/dev/disk3s6     926Gi    14Gi   516Gi     3%      14  5.4G    0%   /System/Volumes/VM
/dev/disk3s2     926Gi    17Gi   516Gi     4%    2.2k  5.4G    0%   /System/Volumes/Preboot
/dev/disk3s4     926Gi   870Mi   516Gi     1%     538  5.4G    0%   /System/Volumes/Update
/dev/disk1s2     550Mi   6.0Mi   531Mi     2%       1  5.4M    0%   /System/Volumes/xarts
/dev/disk1s1     550Mi   5.9Mi   531Mi     2%      43  5.4M    0%   /System/Volumes/iSCPreboot
/dev/disk1s3     550Mi   2.3Mi   531Mi     1%     108  5.4M    0%   /System/Volumes/Hardware
/dev/disk3s5     926Gi   360Gi   516Gi    42%    3.1M  5.4G    0%   /System/Volumes/Data
map auto_home      0Bi     0Bi     0Bi   100%       0     0     -   /System/Volumes/Data/home
/dev/disk2s1     5.0Gi   1.3Gi   3.7Gi    26%      50   39M    0%   /System/Volumes/Update/SFR/mnt1
/dev/disk3s1     926Gi    16Gi   516Gi     3%    459k  4.3G    0%   /System/Volumes/Update/mnt1
```

---

## Step 5: Input is sanitised

A messy answer cannot break out of the output folder:

```bash
echo 'my report /../etc 2026!' | bash system-info.sh
```

Relevant output lines:

```text
Using report name: myreport..etc2026
Directory created : /Users/aman/Desktop/devops-heros/homework/02-shell-scripting/system-reports/myreport..etc2026-20260917-214124
```

Spaces, slashes and `!` are dropped by `tr -cd '[:alnum:]._-'`, so the `/../` traversal attempt
collapses into a harmless folder name.

---

## Step 6: Cross-check on Linux (Docker)

The same file was mounted read-only into an Ubuntu container and executed there:

```bash
docker run --rm --name hw02-linux-check \
  -v "$PWD/system-info.sh:/opt/system-info.sh:ro" \
  -w /root ubuntu:24.04 \
  bash -c 'echo "linux-check" | bash /opt/system-info.sh; echo "EXIT=$?"'
```

Output:

```text
==================================================================
  SYSTEM INFORMATION REPORT
==================================================================
Current date : Thursday 17 September 2026, 16:11:45 UTC
Hostname     : d26b8588a315
Username     : root
Kernel       : Linux 6.12.76-linuxkit (aarch64)

==================================================================
  DISK USAGE (df -h)
==================================================================
Filesystem            Size  Used Avail Use% Mounted on
overlay               911G  162G  704G  19% /
tmpfs                  64M     0   64M   0% /dev
shm                    64M     0   64M   0% /dev/shm
/run/host_mark/Users  927G  412G  515G  45% /opt/system-info.sh
/dev/vda1             911G  162G  704G  19% /etc/hosts
tmpfs                 3.9G     0  3.9G   0% /proc/scsi
tmpfs                 3.9G     0  3.9G   0% /sys/firmware

==================================================================
  RUNNING PROCESSES (top 10 by CPU)
==================================================================
USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
root        24  0.0  0.0   2284  1412 ?        S    16:11   0:00 cut -c 1-105
root        23  0.0  0.0   3392  1460 ?        S    16:11   0:00 awk -v rows=10 NR <= rows
root        22  0.0  0.0    228     4 ?        D    16:11   0:00 [sort]
root        21  0.0  0.0   3392  1460 ?        S    16:11   0:00 awk NR > 1
root        20  0.0  0.0   7632  3624 ?        R    16:11   0:00 ps aux
root         8  0.0  0.0   4036  3044 ?        S    16:11   0:00 bash /opt/system-info.sh
root         1  0.0  0.0   4036  3012 ?        Ss   16:11   0:00 bash -c echo "linux-check" | bash /opt/s

==================================================================
  REPORT INPUT
==================================================================
Using report name: linux-check

==================================================================
  CREATING REPORT DIRECTORY AND FILES
==================================================================
Directory created : /root/system-reports/linux-check-20260917-161145
Files created     : processes.txt, disk-usage.txt, summary.txt
Processes saved   : /root/system-reports/linux-check-20260917-161145/processes.txt
Disk usage saved  : /root/system-reports/linux-check-20260917-161145/disk-usage.txt

==================================================================
  SUMMARY
==================================================================
Report name   : linux-check
Generated on  : Thursday 17 September 2026, 16:11:45 UTC
Hostname      : d26b8588a315
Username      : root
Kernel        : Linux 6.12.76-linuxkit (aarch64)
Processes     : 3
Report folder : /root/system-reports/linux-check-20260917-161145

Files in /root/system-reports/linux-check-20260917-161145:
total 12
-rw-r--r-- 1 root root 435 Sep 17 16:11 disk-usage.txt
-rw-r--r-- 1 root root 524 Sep 17 16:11 processes.txt
-rw-r--r-- 1 root root 267 Sep 17 16:11 summary.txt

Done. 3 running processes recorded in /root/system-reports/linux-check-20260917-161145/processes.txt
EXIT=0
```

### macOS vs Linux differences worth knowing

| | macOS (BSD userland) | Ubuntu (GNU coreutils / procps) |
| --- | --- | --- |
| `df -h` columns | `Size Used Avail Capacity iused ifree %iused Mounted on` | `Size Used Avail Use% Mounted on` |
| `df -h` units | `926Gi`, `550Mi`, `205Ki` (binary suffix spelled out) | `911G`, `64M` |
| `ps aux` tty column | `TT` | `TTY` |
| `ps aux` start column | `STARTED` (`7Sep26`, `9:38PM`) | `START` (`16:11`) |
| `ps aux` default order | already CPU-descending | PID-ascending, so the explicit `sort -k3,3 -nr` matters |
| Process count | 583 on the host | 3 inside the container - the PID namespace only sees its own processes |
| `hostname` | `MacBook-Pro-7.local` | the container ID, `d26b8588a315` |
| `date` timezone | `IST` (host timezone) | `UTC` (container default) |

Because the script only uses `df -h` and `ps aux` as opaque text and never parses named columns, the
different layouts do not break it. The one place column position matters is `sort -b -k3,3 -nr`, and
field 3 is `%CPU` in both BSD and procps `ps aux`.

### Alpine note

Alpine also runs the script to completion (`EXIT=0`) after `apk add --no-cache bash`, but busybox
`ps` ignores the BSD `aux` options:

```bash
docker run --rm --name hw02-alpine-check \
  -v "$PWD/system-info.sh:/opt/system-info.sh:ro" \
  -w /root alpine:latest \
  sh -c 'apk add --no-cache bash >/dev/null 2>&1 && echo "alpine-check" | bash /opt/system-info.sh'
```

Process section of the output:

```text
==================================================================
  RUNNING PROCESSES (top 10 by CPU)
==================================================================
PID   USER     TIME  COMMAND
   29 root      0:00 bash /opt/system-info.sh
   28 root      0:00 bash /opt/system-info.sh
   27 root      0:00 sort -b -k3,3 -nr
   26 root      0:00 awk NR > 1
   25 root      0:00 ps aux
   13 root      0:00 bash /opt/system-info.sh
    1 root      0:00 sh -c apk add --no-cache bash >/dev/null 2>&1 && echo "alpine-check" | bash /opt/sys
```

Only four columns (`PID USER TIME COMMAND`) and no `%CPU` at all, so the "top by CPU" sort is
meaningless on busybox even though nothing errors. Lesson: `ps aux` is not as portable as it looks -
on a busybox-based image install `procps` or switch to a POSIX form such as
`ps -eo pid,user,pcpu,comm`.

---

## Cleanup

The report folders are throwaway build output and are deliberately not committed:

```bash
rm -rf system-reports
ls -l
```

Output:

```text
total 8
-rwxr-xr-x  1 aman  staff  2474 Sep 17 21:40 system-info.sh
```

The Docker containers were all started with `--rm`, so nothing is left behind:

```bash
docker ps -a --filter "name=hw02" --format '{{.Names}} {{.Status}}'
```

Output:

```text
```

Empty, as expected.

---

## Commands used in this assignment

| Command | Purpose |
| --- | --- |
| `date` | current date and timestamp for the report folder name |
| `hostname` | machine name |
| `whoami` | current user |
| `uname -s -r -m` | OS, kernel release, architecture |
| `df -h` | disk usage in human-readable units |
| `ps aux` | full list of running processes |
| `read -r -p` | prompt the user for the report name |
| `mkdir -p` | create the report directory |
| `touch` | create the three empty report files |
| `>` | write `ps aux` and `df -h` output into files |
| `awk`, `sort`, `cut`, `tr`, `wc` | format the on-screen top-10 list and sanitise the input |
| `chmod +x` | make the script executable |
| `bash -n` | syntax-check without running |
