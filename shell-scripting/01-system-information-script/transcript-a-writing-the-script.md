# Shell Scripting — writing & checking the script

> Real session captured in container `sh-t1`.
> Every command was executed; the output is verbatim.

[← Back](README.md)

---

```console
root@ubuntu-hw:~# cd /root && cat -n sysinfo.sh
     1	#!/bin/bash
     2	#
     3	# sysinfo.sh - System Information Script
     4	#
     5	# DevOps Homework - Shell Scripting - Task 1
     6	#
     7	# What it does:
     8	#   - Prints the current date, hostname and username.
     9	#   - Prints disk usage (df -h) and the list of running processes (ps aux).
    10	#   - Asks the user (via `read -p`) for a "report label" that is used to
    11	#     name an output directory.
    12	#   - Creates that directory with `mkdir -p`, creates an empty report file
    13	#     in it with `touch`, then overwrites that file with the running
    14	#     process list using `>` output redirection.
    15	#   - Prints a final summary of everything that was created.
    16	#
    17	# Usage:
    18	#   ./sysinfo.sh                      (interactive - will prompt you)
    19	#   echo "myreport" | ./sysinfo.sh    (non-interactive - piped input)
    20	#   ./sysinfo.sh <<< "myreport"       (non-interactive - here-string)
    21	#
    22	set -euo pipefail
    23	
    24	# ---------------------------------------------------------------------------
    25	# 1. Variables - gather system information via command substitution
    26	# ---------------------------------------------------------------------------
    27	current_date="$(date)"
    28	current_hostname="$(hostname)"
    29	current_user="$(whoami)"
    30	kernel_info="$(uname -srm)"
    31	uptime_info="$(uptime -p 2>/dev/null || uptime)"
    32	
    33	# ---------------------------------------------------------------------------
    34	# 2. Section header helper - keeps the `echo` output tidy and consistent
    35	# ---------------------------------------------------------------------------
    36	print_section() {
    37	    local title="$1"
    38	    echo ""
    39	    echo "==============================================================="
    40	    echo " ${title}"
    41	    echo "==============================================================="
    42	}
    43	
    44	# ---------------------------------------------------------------------------
    45	# 3. Basic system information
    46	# ---------------------------------------------------------------------------
    47	print_section "SYSTEM INFORMATION"
    48	echo "Date       : ${current_date}"
    49	echo "Hostname   : ${current_hostname}"
    50	echo "User       : ${current_user}"
    51	echo "Kernel     : ${kernel_info}"
    52	echo "Uptime     : ${uptime_info}"
    53	
    54	# ---------------------------------------------------------------------------
    55	# 4. Disk usage
    56	# ---------------------------------------------------------------------------
    57	print_section "DISK USAGE (df -h)"
    58	df -h
    59	
    60	# ---------------------------------------------------------------------------
    61	# 5. Running processes (shown on screen first)
    62	# ---------------------------------------------------------------------------
    63	print_section "RUNNING PROCESSES (ps aux) - first 10 lines shown here"
    64	ps aux | head -n 10
    65	
    66	# ---------------------------------------------------------------------------
    67	# 6. Take user input for the report label / output directory name
    68	# ---------------------------------------------------------------------------
    69	print_section "REPORT SETUP"
    70	read -p "Enter a label for this report (used as the output directory name): " report_label
    71	
    72	# Guard against an empty answer so mkdir/touch always get a sane name.
    73	if [ -z "${report_label}" ]; then
    74	    report_label="sysinfo_report"
    75	    echo "No label entered - defaulting to \"${report_label}\""
    76	fi
    77	
    78	echo "Using report label: \"${report_label}\""
    79	
    80	# ---------------------------------------------------------------------------
    81	# 7. Create the output directory and the report file
    82	# ---------------------------------------------------------------------------
    83	output_dir="./${report_label}"
    84	output_file="${output_dir}/processes.txt"
    85	
    86	mkdir -p "${output_dir}"
    87	echo "Created directory : ${output_dir}"
    88	
    89	touch "${output_file}"
    90	echo "Created file      : ${output_file}"
    91	
    92	# ---------------------------------------------------------------------------
    93	# 8. Store the FULL running-process list in the file using > redirection
    94	# ---------------------------------------------------------------------------
    95	ps aux > "${output_file}"
    96	process_count="$(wc -l < "${output_file}")"
    97	echo "Wrote $(( process_count - 1 )) running processes (plus a header line) to ${output_file}"
    98	
    99	# Also drop a small metadata file in the same directory, purely for extra
   100	# context in the submission - demonstrates another > redirection + variables.
   101	info_file="${output_dir}/system_info.txt"
   102	{
   103	    echo "Report label : ${report_label}"
   104	    echo "Generated by : ${current_user}"
   105	    echo "Generated on : ${current_date}"
   106	    echo "Host         : ${current_hostname}"
   107	} > "${info_file}"
   108	echo "Created file      : ${info_file}"
   109	
   110	# ---------------------------------------------------------------------------
   111	# 9. Final summary
   112	# ---------------------------------------------------------------------------
   113	print_section "SUMMARY"
   114	echo "Report label      : ${report_label}"
   115	echo "Output directory  : ${output_dir}"
   116	echo "Files created     :"
   117	echo "  - ${output_file}  ($(wc -l < "${output_file}") lines)"
   118	echo "  - ${info_file}"
   119	echo ""
   120	echo "Done. Run 'ls -lR ${output_dir}' to inspect the created files."

# --- syntax check (no execution) ---
root@ubuntu-hw:~# cd /root && bash -n sysinfo.sh && echo "Syntax OK"
Syntax OK

# --- current permissions (not yet executable) ---
root@ubuntu-hw:~# cd /root && ls -l sysinfo.sh
-rw-r--r-- 1 501 dialout 4911 Sep  2 17:25 sysinfo.sh

# --- make it executable ---
root@ubuntu-hw:~# cd /root && chmod +x sysinfo.sh

# --- confirm permissions changed ---
root@ubuntu-hw:~# cd /root && ls -l sysinfo.sh
-rwxr-xr-x 1 501 dialout 4911 Sep  2 17:25 sysinfo.sh
```
