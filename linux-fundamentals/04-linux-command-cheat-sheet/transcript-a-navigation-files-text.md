# Task 4a — navigation, files & text search · terminal transcript

> Real session captured on Ubuntu 24.04 in container `hw-t4`.
> Every command was executed; the output is verbatim.

[← Back to Task 4 — Linux Command Cheat Sheet](README.md) · [Topic index](../README.md)

---

### 0. Setup: build a realistic scratch workspace under /root/cheatsheet (seed content was staged in /root/seed by the assignment author)

```console
root@ubuntu-hw:~# rm -rf /root/cheatsheet
root@ubuntu-hw:~# mkdir -p /root/cheatsheet/logs /root/cheatsheet/data /root/cheatsheet/configs /root/cheatsheet/scripts /root/cheatsheet/reports /root/cheatsheet/archive_src/public /root/cheatsheet/archive_src/private
root@ubuntu-hw:~# cp /root/seed/app.log /root/cheatsheet/logs/app.log
root@ubuntu-hw:~# cp /root/seed/app.log /root/cheatsheet/logs/app.log.1
root@ubuntu-hw:~# cp /root/seed/employees.csv /root/cheatsheet/data/employees.csv
root@ubuntu-hw:~# cp /root/seed/numbers.txt /root/cheatsheet/data/numbers.txt
root@ubuntu-hw:~# cp /root/seed/app.conf /root/cheatsheet/configs/app.conf
root@ubuntu-hw:~# cp /root/seed/hello.sh /root/cheatsheet/scripts/hello.sh
root@ubuntu-hw:~# cp /root/seed/deploy.sh /root/cheatsheet/scripts/deploy.sh
root@ubuntu-hw:~# cp /root/seed/index.html /root/cheatsheet/archive_src/public/index.html
root@ubuntu-hw:~# cp /root/seed/style.css /root/cheatsheet/archive_src/public/style.css
root@ubuntu-hw:~# cp /root/seed/secret.txt /root/cheatsheet/archive_src/private/secret_notes.txt
root@ubuntu-hw:~# cp /root/seed/old_report.txt /root/cheatsheet/reports/old_report.txt
root@ubuntu-hw:~# cp /root/seed/recent_report.txt /root/cheatsheet/reports/recent_report.txt
root@ubuntu-hw:~# chmod +x /root/cheatsheet/scripts/hello.sh
root@ubuntu-hw:~# touch -d "35 days ago" /root/cheatsheet/reports/old_report.txt
root@ubuntu-hw:~# touch -d "20 days ago" /root/cheatsheet/logs/app.log.1
root@ubuntu-hw:~# touch -d "1 hour ago" /root/cheatsheet/reports/recent_report.txt
root@ubuntu-hw:~# dd if=/dev/zero of=/root/cheatsheet/bigfile.bin bs=1M count=5
5+0 records in
5+0 records out
5242880 bytes (5.2 MB, 5.0 MiB) copied, 0.00293662 s, 1.8 GB/s
```

### 1. Navigation: pwd, cd, ls -lah, tree

```console
# --- where am I right now ---
root@ubuntu-hw:~# pwd
/root

# --- move into the workspace and confirm ---
root@ubuntu-hw:~# cd /root/cheatsheet && pwd
/root/cheatsheet

# --- long, all-files, human-readable listing ---
root@ubuntu-hw:~# cd /root/cheatsheet && ls -lah
total 5.1M
drwxr-xr-x 8 root root 4.0K Sep  2 16:57 .
drwx------ 1 root root 4.0K Sep  2 16:57 ..
drwxr-xr-x 4 root root 4.0K Sep  2 16:57 archive_src
-rw-r--r-- 1 root root 5.0M Sep  2 16:57 bigfile.bin
drwxr-xr-x 2 root root 4.0K Sep  2 16:57 configs
drwxr-xr-x 2 root root 4.0K Sep  2 16:57 data
drwxr-xr-x 2 root root 4.0K Sep  2 16:57 logs
drwxr-xr-x 2 root root 4.0K Sep  2 16:57 reports
drwxr-xr-x 2 root root 4.0K Sep  2 16:57 scripts

# --- relative cd, then back up with cd .. ---
root@ubuntu-hw:~# cd /root/cheatsheet/logs && pwd; cd ..; pwd
/root/cheatsheet/logs
/root/cheatsheet

# --- full tree of the workspace ---
root@ubuntu-hw:~# tree /root/cheatsheet
/root/cheatsheet
|-- archive_src
|   |-- private
|   |   `-- secret_notes.txt
|   `-- public
|       |-- index.html
|       `-- style.css
|-- bigfile.bin
|-- configs
|   `-- app.conf
|-- data
|   |-- employees.csv
|   `-- numbers.txt
|-- logs
|   |-- app.log
|   `-- app.log.1
|-- reports
|   |-- old_report.txt
|   `-- recent_report.txt
`-- scripts
    |-- deploy.sh
    `-- hello.sh

9 directories, 13 files
```

### 2. mkdir -p, touch, cp, cp -r, mv, rm, rm -r

```console
# --- mkdir -p creates the whole nested path in one shot ---
root@ubuntu-hw:~# mkdir -p /root/cheatsheet/reports/2026/09
root@ubuntu-hw:~# touch /root/cheatsheet/reports/2026/09/placeholder.txt
root@ubuntu-hw:~# find /root/cheatsheet/reports -type d
/root/cheatsheet/reports
/root/cheatsheet/reports/2026
/root/cheatsheet/reports/2026/09

# --- cp: simple file copy ---
root@ubuntu-hw:~# cp /root/cheatsheet/data/employees.csv /root/cheatsheet/data/employees_backup.csv
root@ubuntu-hw:~# ls -l /root/cheatsheet/data/
total 12
-rw-r--r-- 1 root root 202 Sep  2 16:57 employees.csv
-rw-r--r-- 1 root root 202 Sep  2 16:57 employees_backup.csv
-rw-r--r-- 1 root root  22 Sep  2 16:57 numbers.txt

# --- cp -r: recursive directory copy ---
root@ubuntu-hw:~# cp -r /root/cheatsheet/archive_src /root/cheatsheet/archive_src_copy
root@ubuntu-hw:~# tree /root/cheatsheet/archive_src_copy
/root/cheatsheet/archive_src_copy
|-- private
|   `-- secret_notes.txt
`-- public
    |-- index.html
    `-- style.css

3 directories, 3 files

# --- mv: rename/move ---
root@ubuntu-hw:~# mv /root/cheatsheet/data/employees_backup.csv /root/cheatsheet/data/employees_backup_2026-09-02.csv
root@ubuntu-hw:~# ls -l /root/cheatsheet/data/
total 12
-rw-r--r-- 1 root root 202 Sep  2 16:57 employees.csv
-rw-r--r-- 1 root root 202 Sep  2 16:57 employees_backup_2026-09-02.csv
-rw-r--r-- 1 root root  22 Sep  2 16:57 numbers.txt

# --- rm: delete a single file ---
root@ubuntu-hw:~# echo "scratch, safe to delete" > /root/cheatsheet/scratch.txt
root@ubuntu-hw:~# ls /root/cheatsheet/scratch.txt
/root/cheatsheet/scratch.txt
root@ubuntu-hw:~# rm /root/cheatsheet/scratch.txt
root@ubuntu-hw:~# ls /root/cheatsheet/scratch.txt
ls: cannot access '/root/cheatsheet/scratch.txt': No such file or directory

# --- rm -r: delete a directory tree ---
root@ubuntu-hw:~# mkdir -p /root/cheatsheet/tmp_to_remove/nested
root@ubuntu-hw:~# touch /root/cheatsheet/tmp_to_remove/a.txt /root/cheatsheet/tmp_to_remove/nested/b.txt
root@ubuntu-hw:~# tree /root/cheatsheet/tmp_to_remove
/root/cheatsheet/tmp_to_remove
|-- a.txt
`-- nested
    `-- b.txt

2 directories, 2 files
root@ubuntu-hw:~# rm -r /root/cheatsheet/tmp_to_remove
root@ubuntu-hw:~# ls /root/cheatsheet/tmp_to_remove
ls: cannot access '/root/cheatsheet/tmp_to_remove': No such file or directory
```

### 3. find -- by name, type, size, mtime, and with -exec

```console
# --- by name (quoted glob so the SHELL doesn't expand it, find does) ---
root@ubuntu-hw:~# find /root/cheatsheet -name "*.log"
/root/cheatsheet/logs/app.log

# --- by type: directories only ---
root@ubuntu-hw:~# find /root/cheatsheet -type d
/root/cheatsheet
/root/cheatsheet/reports
/root/cheatsheet/reports/2026
/root/cheatsheet/reports/2026/09
/root/cheatsheet/configs
/root/cheatsheet/logs
/root/cheatsheet/scripts
/root/cheatsheet/archive_src_copy
/root/cheatsheet/archive_src_copy/public
/root/cheatsheet/archive_src_copy/private
/root/cheatsheet/archive_src
/root/cheatsheet/archive_src/public
/root/cheatsheet/archive_src/private
/root/cheatsheet/data

# --- by type: regular files matching a pattern ---
root@ubuntu-hw:~# find /root/cheatsheet -type f -name "*.txt"
/root/cheatsheet/reports/old_report.txt
/root/cheatsheet/reports/2026/09/placeholder.txt
/root/cheatsheet/reports/recent_report.txt
/root/cheatsheet/archive_src_copy/private/secret_notes.txt
/root/cheatsheet/archive_src/private/secret_notes.txt
/root/cheatsheet/data/numbers.txt

# --- by size: bigger than 1 megabyte ---
root@ubuntu-hw:~# find /root/cheatsheet -size +1M
/root/cheatsheet/bigfile.bin

# --- by size: smaller than 1 kilobyte ---
root@ubuntu-hw:~# find /root/cheatsheet -size -1k -type f
/root/cheatsheet/reports/2026/09/placeholder.txt

# --- by mtime: modified more than 7 days ago ---
root@ubuntu-hw:~# find /root/cheatsheet -mtime +7
/root/cheatsheet/reports/old_report.txt
/root/cheatsheet/logs/app.log.1

# --- by mtime: modified within the last 1 day ---
root@ubuntu-hw:~# find /root/cheatsheet -mtime -1 -type f
/root/cheatsheet/reports/2026/09/placeholder.txt
/root/cheatsheet/reports/recent_report.txt
/root/cheatsheet/configs/app.conf
/root/cheatsheet/logs/app.log
/root/cheatsheet/scripts/deploy.sh
/root/cheatsheet/scripts/hello.sh
/root/cheatsheet/archive_src_copy/public/style.css
/root/cheatsheet/archive_src_copy/public/index.html
/root/cheatsheet/archive_src_copy/private/secret_notes.txt
/root/cheatsheet/bigfile.bin
/root/cheatsheet/archive_src/public/style.css
/root/cheatsheet/archive_src/public/index.html
/root/cheatsheet/archive_src/private/secret_notes.txt
/root/cheatsheet/data/employees.csv
/root/cheatsheet/data/numbers.txt
/root/cheatsheet/data/employees_backup_2026-09-02.csv

# --- -exec: run a command on every match ---
root@ubuntu-hw:~# find /root/cheatsheet -name "*.sh" -exec ls -l {} \;
-rw-r--r-- 1 root root 79 Sep  2 16:57 /root/cheatsheet/scripts/deploy.sh
-rwxr-xr-x 1 root root 62 Sep  2 16:57 /root/cheatsheet/scripts/hello.sh
```

### 4. file, stat, du -sh, basename/dirname, which/whereis

```console
# --- file: identify file types ---
root@ubuntu-hw:~# file /root/cheatsheet/bigfile.bin /root/cheatsheet/scripts/hello.sh /root/cheatsheet/data/employees.csv /root/cheatsheet/archive_src
/root/cheatsheet/bigfile.bin:        data
/root/cheatsheet/scripts/hello.sh:   Bourne-Again shell script, ASCII text executable
/root/cheatsheet/data/employees.csv: CSV ASCII text
/root/cheatsheet/archive_src:        directory

# --- stat: detailed metadata ---
root@ubuntu-hw:~# stat /root/cheatsheet/bigfile.bin
  File: /root/cheatsheet/bigfile.bin
  Size: 5242880   	Blocks: 10240      IO Block: 4096   regular file
Device: 0,72	Inode: 798237      Links: 1
Access: (0644/-rw-r--r--)  Uid: (    0/    root)   Gid: (    0/    root)
Access: 2026-09-02 16:57:41.398061007 +0000
Modify: 2026-09-02 16:57:39.432061006 +0000
Change: 2026-09-02 16:57:39.432061006 +0000
 Birth: 2026-09-02 16:57:39.429061006 +0000

# --- du -sh: size of each top-level item ---
root@ubuntu-hw:~# du -sh /root/cheatsheet/*
24K	/root/cheatsheet/archive_src
24K	/root/cheatsheet/archive_src_copy
5.0M	/root/cheatsheet/bigfile.bin
8.0K	/root/cheatsheet/configs
16K	/root/cheatsheet/data
12K	/root/cheatsheet/logs
20K	/root/cheatsheet/reports
12K	/root/cheatsheet/scripts

# --- basename / dirname ---
root@ubuntu-hw:~# basename /root/cheatsheet/data/employees.csv
employees.csv
root@ubuntu-hw:~# dirname /root/cheatsheet/data/employees.csv
/root/cheatsheet/data

# --- which / whereis: locate a command ---
root@ubuntu-hw:~# which awk
/usr/bin/awk
root@ubuntu-hw:~# whereis awk
awk: /usr/bin/awk
```

### 5. Viewing text: cat, tac, head, tail, wc -l

```console
# --- cat: dump a whole small file ---
root@ubuntu-hw:~# cat /root/cheatsheet/data/numbers.txt
5
3
9
3
1
5
5
2
9
1
7

# --- cat -n: with line numbers ---
root@ubuntu-hw:~# cat -n /root/cheatsheet/data/employees.csv
     1	id,name,dept,salary
     2	1,Alice,Engineering,95000
     3	2,Bob,Sales,62000
     4	3,Carol,Engineering,105000
     5	4,Dave,Marketing,58000
     6	5,Eve,Sales,71000
     7	6,Frank,Engineering,88000
     8	7,Grace,Marketing,64000
     9	8,Heidi,Sales,59000

# --- tac: cat backwards (last line first) ---
root@ubuntu-hw:~# tac /root/cheatsheet/data/numbers.txt
7
1
9
2
5
5
1
3
9
3
5

# --- head: first lines (default 10), and explicit -n ---
root@ubuntu-hw:~# head /root/cheatsheet/logs/app.log
2026-09-01 09:00:01 INFO 10.0.0.11 GET /index.html 200 12ms
2026-09-01 09:00:03 INFO 10.0.0.12 GET /api/users 200 45ms
2026-09-01 09:00:05 WARN 10.0.0.11 GET /api/orders 404 8ms
2026-09-01 09:00:07 ERROR 10.0.0.13 POST /api/login 500 120ms
2026-09-01 09:00:09 INFO 10.0.0.14 GET /index.html 200 10ms
2026-09-01 09:00:12 INFO 10.0.0.11 GET /api/users 200 38ms
2026-09-01 09:00:15 ERROR 10.0.0.15 POST /api/login 500 98ms
2026-09-01 09:00:18 INFO 10.0.0.12 GET /api/products 200 22ms
2026-09-01 09:00:21 WARN 10.0.0.16 GET /api/cart 404 6ms
2026-09-01 09:00:24 INFO 10.0.0.11 GET /index.html 200 11ms
root@ubuntu-hw:~# head -n 5 /root/cheatsheet/logs/app.log
2026-09-01 09:00:01 INFO 10.0.0.11 GET /index.html 200 12ms
2026-09-01 09:00:03 INFO 10.0.0.12 GET /api/users 200 45ms
2026-09-01 09:00:05 WARN 10.0.0.11 GET /api/orders 404 8ms
2026-09-01 09:00:07 ERROR 10.0.0.13 POST /api/login 500 120ms
2026-09-01 09:00:09 INFO 10.0.0.14 GET /index.html 200 10ms

# --- tail: last lines, and tail -n +N to start partway through ---
root@ubuntu-hw:~# tail -n 5 /root/cheatsheet/logs/app.log
2026-09-01 09:00:57 INFO 10.0.0.21 GET /api/products 200 24ms
2026-09-01 09:01:00 ERROR 10.0.0.13 POST /api/login 500 105ms
2026-09-01 09:01:03 INFO 10.0.0.11 GET /api/cart 200 29ms
2026-09-01 09:01:06 WARN 10.0.0.22 GET /api/orders 404 6ms
2026-09-01 09:01:09 INFO 10.0.0.12 GET /index.html 200 10ms
root@ubuntu-hw:~# tail -n +20 /root/cheatsheet/logs/app.log
2026-09-01 09:00:54 INFO 10.0.0.12 GET /index.html 200 13ms
2026-09-01 09:00:57 INFO 10.0.0.21 GET /api/products 200 24ms
2026-09-01 09:01:00 ERROR 10.0.0.13 POST /api/login 500 105ms
2026-09-01 09:01:03 INFO 10.0.0.11 GET /api/cart 200 29ms
2026-09-01 09:01:06 WARN 10.0.0.22 GET /api/orders 404 6ms
2026-09-01 09:01:09 INFO 10.0.0.12 GET /index.html 200 10ms

# --- wc -l: count lines ---
root@ubuntu-hw:~# wc -l /root/cheatsheet/logs/app.log
25 /root/cheatsheet/logs/app.log
```

### 6. Searching text: grep -i -r -n -v -c -E

```console
# --- case-insensitive match ---
root@ubuntu-hw:~# grep -i "error" /root/cheatsheet/logs/app.log
2026-09-01 09:00:07 ERROR 10.0.0.13 POST /api/login 500 120ms
2026-09-01 09:00:15 ERROR 10.0.0.15 POST /api/login 500 98ms
2026-09-01 09:00:30 ERROR 10.0.0.13 GET /api/orders 500 150ms
2026-09-01 09:00:45 ERROR 10.0.0.14 POST /api/checkout 500 210ms
2026-09-01 09:01:00 ERROR 10.0.0.13 POST /api/login 500 105ms

# --- recursive search across a whole directory ---
root@ubuntu-hw:~# grep -r "ERROR" /root/cheatsheet/logs/
/root/cheatsheet/logs/app.log:2026-09-01 09:00:07 ERROR 10.0.0.13 POST /api/login 500 120ms
/root/cheatsheet/logs/app.log:2026-09-01 09:00:15 ERROR 10.0.0.15 POST /api/login 500 98ms
/root/cheatsheet/logs/app.log:2026-09-01 09:00:30 ERROR 10.0.0.13 GET /api/orders 500 150ms
/root/cheatsheet/logs/app.log:2026-09-01 09:00:45 ERROR 10.0.0.14 POST /api/checkout 500 210ms
/root/cheatsheet/logs/app.log:2026-09-01 09:01:00 ERROR 10.0.0.13 POST /api/login 500 105ms
/root/cheatsheet/logs/app.log.1:2026-09-01 09:00:07 ERROR 10.0.0.13 POST /api/login 500 120ms
/root/cheatsheet/logs/app.log.1:2026-09-01 09:00:15 ERROR 10.0.0.15 POST /api/login 500 98ms
/root/cheatsheet/logs/app.log.1:2026-09-01 09:00:30 ERROR 10.0.0.13 GET /api/orders 500 150ms
/root/cheatsheet/logs/app.log.1:2026-09-01 09:00:45 ERROR 10.0.0.14 POST /api/checkout 500 210ms
/root/cheatsheet/logs/app.log.1:2026-09-01 09:01:00 ERROR 10.0.0.13 POST /api/login 500 105ms

# --- show line numbers ---
root@ubuntu-hw:~# grep -n "500" /root/cheatsheet/logs/app.log
4:2026-09-01 09:00:07 ERROR 10.0.0.13 POST /api/login 500 120ms
7:2026-09-01 09:00:15 ERROR 10.0.0.15 POST /api/login 500 98ms
12:2026-09-01 09:00:30 ERROR 10.0.0.13 GET /api/orders 500 150ms
17:2026-09-01 09:00:45 ERROR 10.0.0.14 POST /api/checkout 500 210ms
22:2026-09-01 09:01:00 ERROR 10.0.0.13 POST /api/login 500 105ms

# --- invert match: lines that are NOT INFO ---
root@ubuntu-hw:~# grep -v "INFO" /root/cheatsheet/logs/app.log
2026-09-01 09:00:05 WARN 10.0.0.11 GET /api/orders 404 8ms
2026-09-01 09:00:07 ERROR 10.0.0.13 POST /api/login 500 120ms
2026-09-01 09:00:15 ERROR 10.0.0.15 POST /api/login 500 98ms
2026-09-01 09:00:21 WARN 10.0.0.16 GET /api/cart 404 6ms
2026-09-01 09:00:30 ERROR 10.0.0.13 GET /api/orders 500 150ms
2026-09-01 09:00:36 WARN 10.0.0.11 POST /api/login 401 15ms
2026-09-01 09:00:45 ERROR 10.0.0.14 POST /api/checkout 500 210ms
2026-09-01 09:00:51 WARN 10.0.0.20 GET /api/orders 404 7ms
2026-09-01 09:01:00 ERROR 10.0.0.13 POST /api/login 500 105ms
2026-09-01 09:01:06 WARN 10.0.0.22 GET /api/orders 404 6ms

# --- count matching lines only ---
root@ubuntu-hw:~# grep -c "ERROR" /root/cheatsheet/logs/app.log
5

# --- extended regex: match ERROR or WARN ---
root@ubuntu-hw:~# grep -E "ERROR|WARN" /root/cheatsheet/logs/app.log
2026-09-01 09:00:05 WARN 10.0.0.11 GET /api/orders 404 8ms
2026-09-01 09:00:07 ERROR 10.0.0.13 POST /api/login 500 120ms
2026-09-01 09:00:15 ERROR 10.0.0.15 POST /api/login 500 98ms
2026-09-01 09:00:21 WARN 10.0.0.16 GET /api/cart 404 6ms
2026-09-01 09:00:30 ERROR 10.0.0.13 GET /api/orders 500 150ms
2026-09-01 09:00:36 WARN 10.0.0.11 POST /api/login 401 15ms
2026-09-01 09:00:45 ERROR 10.0.0.14 POST /api/checkout 500 210ms
2026-09-01 09:00:51 WARN 10.0.0.20 GET /api/orders 404 7ms
2026-09-01 09:01:00 ERROR 10.0.0.13 POST /api/login 500 105ms
2026-09-01 09:01:06 WARN 10.0.0.22 GET /api/orders 404 6ms
```

### 7. sed and awk

```console
# --- sed -n 'Np' : print just a line range ---
root@ubuntu-hw:~# sed -n '1,5p' /root/cheatsheet/logs/app.log
2026-09-01 09:00:01 INFO 10.0.0.11 GET /index.html 200 12ms
2026-09-01 09:00:03 INFO 10.0.0.12 GET /api/users 200 45ms
2026-09-01 09:00:05 WARN 10.0.0.11 GET /api/orders 404 8ms
2026-09-01 09:00:07 ERROR 10.0.0.13 POST /api/login 500 120ms
2026-09-01 09:00:09 INFO 10.0.0.14 GET /index.html 200 10ms

# --- sed substitution (stream edit, original file untouched) ---
root@ubuntu-hw:~# sed 's/INFO/NOTICE/' /root/cheatsheet/logs/app.log | head -5
2026-09-01 09:00:01 NOTICE 10.0.0.11 GET /index.html 200 12ms
2026-09-01 09:00:03 NOTICE 10.0.0.12 GET /api/users 200 45ms
2026-09-01 09:00:05 WARN 10.0.0.11 GET /api/orders 404 8ms
2026-09-01 09:00:07 ERROR 10.0.0.13 POST /api/login 500 120ms
2026-09-01 09:00:09 NOTICE 10.0.0.14 GET /index.html 200 10ms

# --- awk: print specific columns (log level + status code) ---
root@ubuntu-hw:~# awk '{print $3, $7}' /root/cheatsheet/logs/app.log | head -8
INFO 200
INFO 200
WARN 404
ERROR 500
INFO 200
INFO 200
ERROR 500
INFO 200

# --- awk -F: change field separator for a CSV, print two columns ---
root@ubuntu-hw:~# awk -F',' '{print $2, $4}' /root/cheatsheet/data/employees.csv
name salary
Alice 95000
Bob 62000
Carol 105000
Dave 58000
Eve 71000
Frank 88000
Grace 64000
Heidi 59000

# --- awk: filter rows by a column value ---
root@ubuntu-hw:~# awk -F',' '$3=="Engineering" {print $2, $4}' /root/cheatsheet/data/employees.csv
Alice 95000
Carol 105000
Frank 88000
```

### 8. cut, sort, uniq -c, tr

```console
# --- cut: select CSV columns by delimiter and field number ---
root@ubuntu-hw:~# cut -d',' -f2,4 /root/cheatsheet/data/employees.csv
name,salary
Alice,95000
Bob,62000
Carol,105000
Dave,58000
Eve,71000
Frank,88000
Grace,64000
Heidi,59000

# --- cut: select space-delimited columns from the log ---
root@ubuntu-hw:~# cut -d' ' -f1,3 /root/cheatsheet/logs/app.log | head -5
2026-09-01 INFO
2026-09-01 INFO
2026-09-01 WARN
2026-09-01 ERROR
2026-09-01 INFO

# --- sort: default (lexicographic) ---
root@ubuntu-hw:~# sort /root/cheatsheet/data/numbers.txt
1
1
2
3
3
5
5
5
7
9
9

# --- sort -n: numeric ---
root@ubuntu-hw:~# sort -n /root/cheatsheet/data/numbers.txt
1
1
2
3
3
5
5
5
7
9
9

# --- sort -rn: numeric, reversed ---
root@ubuntu-hw:~# sort -rn /root/cheatsheet/data/numbers.txt
9
9
7
5
5
5
3
3
2
1
1

# --- sort -u: sort and dedupe ---
root@ubuntu-hw:~# sort -u /root/cheatsheet/data/numbers.txt
1
2
3
5
7
9

# --- uniq -c: count occurrences (input must be sorted first) ---
root@ubuntu-hw:~# sort /root/cheatsheet/data/numbers.txt | uniq -c
      2 1
      1 2
      2 3
      3 5
      1 7
      2 9

# --- tr: translate characters ---
root@ubuntu-hw:~# echo "hello world" | tr 'a-z' 'A-Z'
HELLO WORLD
```

### 9. Pipes and redirection: >, >>, 2>, |, tee ; plus xargs

```console
# --- > : redirect stdout, overwriting ---
root@ubuntu-hw:~# grep "ERROR" /root/cheatsheet/logs/app.log > /root/cheatsheet/logs/errors_only.log
root@ubuntu-hw:~# cat /root/cheatsheet/logs/errors_only.log
2026-09-01 09:00:07 ERROR 10.0.0.13 POST /api/login 500 120ms
2026-09-01 09:00:15 ERROR 10.0.0.15 POST /api/login 500 98ms
2026-09-01 09:00:30 ERROR 10.0.0.13 GET /api/orders 500 150ms
2026-09-01 09:00:45 ERROR 10.0.0.14 POST /api/checkout 500 210ms
2026-09-01 09:01:00 ERROR 10.0.0.13 POST /api/login 500 105ms
root@ubuntu-hw:~# wc -l /root/cheatsheet/logs/errors_only.log
5 /root/cheatsheet/logs/errors_only.log

# --- >> : redirect stdout, appending ---
root@ubuntu-hw:~# grep "WARN" /root/cheatsheet/logs/app.log >> /root/cheatsheet/logs/errors_only.log
root@ubuntu-hw:~# wc -l /root/cheatsheet/logs/errors_only.log
10 /root/cheatsheet/logs/errors_only.log

# --- 2> : redirect stderr only, capturing a REAL error ---
root@ubuntu-hw:~# ls /root/cheatsheet/does_not_exist 2> /root/cheatsheet/logs/stderr_demo.txt
root@ubuntu-hw:~# cat /root/cheatsheet/logs/stderr_demo.txt
ls: cannot access '/root/cheatsheet/does_not_exist': No such file or directory

# --- | and tee: split a stream to a file AND stdout at the same time ---
root@ubuntu-hw:~# grep "ERROR" /root/cheatsheet/logs/app.log | tee /root/cheatsheet/logs/errors_tee.log | wc -l
5
root@ubuntu-hw:~# cat /root/cheatsheet/logs/errors_tee.log | head -3
2026-09-01 09:00:07 ERROR 10.0.0.13 POST /api/login 500 120ms
2026-09-01 09:00:15 ERROR 10.0.0.15 POST /api/login 500 98ms
2026-09-01 09:00:30 ERROR 10.0.0.13 GET /api/orders 500 150ms

# --- xargs: feed find's output as arguments to another command ---
root@ubuntu-hw:~# find /root/cheatsheet -name "*.txt" | xargs wc -l
  3 /root/cheatsheet/reports/old_report.txt
  0 /root/cheatsheet/reports/2026/09/placeholder.txt
  3 /root/cheatsheet/reports/recent_report.txt
  1 /root/cheatsheet/logs/stderr_demo.txt
  2 /root/cheatsheet/archive_src_copy/private/secret_notes.txt
  2 /root/cheatsheet/archive_src/private/secret_notes.txt
 11 /root/cheatsheet/data/numbers.txt
 22 total
```
