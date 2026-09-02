# Task 4 — Linux Command Cheat Sheet

**Assignment requirements** (verbatim from `DevOps Homework.docx`):

> - Review the Linux command cheat sheet.
> - Practice the important commands covered in the cheat sheet.
> - Understand the purpose and basic usage of each command.

*Practised for real on Ubuntu 24.04 in container `hw-t4`. Every command below was executed; all output is verbatim.*

[← Back to Linux Fundamentals](../README.md)

---

> The source assignment document references "the Linux command cheat sheet" as something to review, but no cheat sheet was actually attached to the .docx — only the task description was present. This section therefore **is** the cheat sheet: a DevOps-oriented reference table for each command group, built and verified by actually running every command below on a real Ubuntu 24.04 container (`hw-t4`) and capturing the real output. Full transcripts: `transcripts/task4a.txt` (navigation/files/text), `transcripts/task4b.txt` (permissions/users/processes), `transcripts/task4c.txt` (disk/network/archives/packages/services).

All practice below runs against a scratch workspace built at `/root/cheatsheet` (log files, a CSV, config files, scripts, an archive source tree, a 5 MB binary) so every command has real, non-trivial data to operate on.

### 1. Navigation, Files & Directories

| Command | Purpose | Common flags | Example |
|---|---|---|---|
| `pwd` | Print current directory | — | `pwd` |
| `cd` | Change directory | `-` (previous dir), `..` (parent) | `cd /root/cheatsheet` |
| `ls` | List directory contents | `-l` long, `-a` all, `-h` human sizes, `-t` by time | `ls -lah` |
| `tree` | Visual directory tree | `-L n` depth limit | `tree /root/cheatsheet` |
| `mkdir -p` | Create directories, including missing parents | `-p` | `mkdir -p a/b/c` |
| `touch` | Create empty file / update mtime | `-d` set a specific time | `touch file.txt` |
| `cp` | Copy files | `-r` recursive, `-p` preserve attrs | `cp a.txt b.txt` |
| `mv` | Move / rename | — | `mv a.txt archive/a.txt` |
| `rm` | Delete files | `-r` recursive, `-f` force | `rm file.txt` |
| `find` | Search the filesystem by criteria | `-name`, `-type`, `-size`, `-mtime`, `-exec` | `find . -name "*.log"` |
| `file` | Identify file type by content | — | `file data.bin` |
| `stat` | Detailed metadata (inode, timestamps, perms) | `-c` custom format | `stat file.txt` |
| `du -sh` | Disk usage of files/dirs, human readable | `-s` summary, `-h` human | `du -sh /var/*` |
| `basename` / `dirname` | Strip path down to filename / directory | — | `basename /a/b/c.txt` → `c.txt` |
| `which` / `whereis` | Locate a command's binary (+ man/source) | — | `which awk` |

**Practised:** `transcripts/task4a.txt` sections 1–4. Built a nested workspace with `mkdir -p`, copied it wholesale with `cp -r`, renamed a backup with `mv`, and deleted a scratch tree with `rm -r`. `find` was run by name (`find /root/cheatsheet -name "*.log"`), type (`-type d`), size (`-size +1M` → correctly matched only `bigfile.bin`, a real 5 MB file made with `dd`), mtime (`-mtime +7`, which correctly caught two files we deliberately back-dated 35 and 20 days with `touch -d`), and with `-exec ls -l {} \;` to inspect every `*.sh` match in one pass. `stat` on `bigfile.bin` showed `Size: 5242880`, matching the `dd bs=1M count=5` that created it.

### 2. Viewing & Searching Text

| Command | Purpose | Common flags | Example |
|---|---|---|---|
| `cat` | Print whole file | `-n` number lines | `cat -n employees.csv` |
| `tac` | Print file in reverse line order | — | `tac numbers.txt` |
| `head` / `tail` | First / last N lines | `-n N`, `tail -n +N` | `tail -n 5 app.log` |
| `wc -l` | Count lines (also `-w` words, `-c` bytes) | `-l` | `wc -l app.log` |
| `grep` | Search text by pattern | `-i` ignore case, `-r` recursive, `-n` line numbers, `-v` invert, `-c` count, `-E` extended regex | `grep -iE "error\|warn" app.log` |
| `sed` | Stream editor: substitute/print by line | `s/old/new/`, `-n 'N,Mp'` | `sed 's/INFO/NOTICE/' app.log` |
| `awk` | Column-oriented text processing | `-F` field sep, `{print $N}`, pattern filters | `awk -F',' '$3=="Sales"{print $2}' f.csv` |
| `cut` | Extract columns by delimiter/position | `-d` delimiter, `-f` fields | `cut -d',' -f2,4 f.csv` |
| `sort` | Sort lines | `-n` numeric, `-r` reverse, `-u` unique | `sort -rn numbers.txt` |
| `uniq -c` | Collapse and count adjacent duplicates | (needs sorted input) | `sort f.txt \| uniq -c` |
| `tr` | Translate/delete characters | `'a-z' 'A-Z'` | `echo hi \| tr a-z A-Z` |
| `>` / `>>` | Redirect stdout (overwrite / append) | — | `grep ERR log > errs.txt` |
| `2>` | Redirect stderr only | — | `cmd 2> err.txt` |
| `\|` / `tee` | Pipe a stream / split it to a file and stdout | `tee -a` append | `cmd \| tee out.txt` |
| `xargs` | Turn stdin lines into command arguments | `-I{}` placeholder | `find . -name "*.txt" \| xargs wc -l` |

**Practised:** `transcripts/task4a.txt` sections 5–9, all against a 25-line synthetic app log and an 8-row employee CSV. `grep -c "ERROR" app.log` returned `5` (real count), `grep -v "INFO"` correctly left only the WARN/ERROR lines, and `grep -E "ERROR|WARN"` merged both. `awk -F',' '$3=="Engineering" {print $2, $4}'` on the CSV correctly filtered to exactly Alice, Carol, and Frank. `sort numbers.txt | uniq -c` produced real counts (`3 5`, `2 9`, etc.) from a hand-built list with duplicates. The redirection block captured a genuine stderr message via `2>`: `ls: cannot access '/root/cheatsheet/does_not_exist': No such file or directory`. `find ... | xargs wc -l` fed six real file paths straight into `wc -l` in one shot.

### 3. Permissions & Ownership

| Command | Purpose | Common flags | Example |
|---|---|---|---|
| `ls -l` | Show permission string, owner, group, size, mtime | — | `ls -l file.sh` |
| `chmod` | Change permissions | Symbolic (`u+x`, `g-w`) or numeric (`750`) | `chmod 750 deploy.sh` |
| `chown` | Change owner (and optionally group) | `user`, `user:group` | `chown deploy:devops f` |
| `chgrp` | Change group only | — | `chgrp devops f` |
| `umask` | Default permission mask for newly created files | set with `umask NNN` | `umask 027` |

`ls -l` breakdown for `-rwxr-x---`: position 1 = file type (`-`=file, `d`=dir, `l`=symlink); positions 2–4 = owner `rwx`; 5–7 = group `r-x`; 8–10 = other `---`.

**Practised:** `transcripts/task4b.txt` sections 1–4, all on the *same file* (`scripts/deploy.sh`) so the before/after is directly comparable:
- Before: `-rw-r--r-- 1 root root 79 ... deploy.sh`
- After `chmod u+x`: `-rwxr--r--`
- After `chmod 750`: `-rwxr-x---`

`chown`/`chgrp` were exercised against a real new user/group (`useradd deploy`, `groupadd devops`), moving the file through `deploy:root` → `deploy:devops` and back to `root:root`. `umask` produced a genuine, quantified difference: with the default `umask 0022`, `touch` created a file `-rw-r--r--` (644); with `umask 027` **in the same shell invocation**, an identical `touch` created `-rw-r-----` (640) — 666 minus 027. (See the Gotchas section below for why the umask change had to be chained into one command.)

The permission-denied demo was captured verbatim: a root-owned, `chmod 600` file at `/srv/permdemo/secret.txt`, read as the unprivileged `deploy` user via `su - deploy -c "cat ..."`, produced the real error:
```
cat: /srv/permdemo/secret.txt: Permission denied
```
Re-running `chmod 644` on the same file and repeating the `su` command then succeeded and printed the file's real contents.

### 4. Users & Groups

| Command | Purpose | Common flags | Example |
|---|---|---|---|
| `whoami` | Current effective username | — | `whoami` |
| `id` | UID, GID, and all group memberships | `-u`, `-g`, `-Gn` | `id deploy` |
| `groups` | Groups the current/named user belongs to | — | `groups` |
| `getent passwd` | Look up an account (works with any nsswitch source) | — | `getent passwd root` |
| `useradd` / `groupadd` | Create a user / group | `-m` create home dir, `-s` shell | `useradd -m -s /bin/bash deploy` |
| `su - user -c "cmd"` | Run one command as another user, with their login environment | `-` full login shell | `su - deploy -c whoami` |

`/etc/passwd` fields: `username:x:UID:GID:comment:home:shell`. `/etc/group` fields: `groupname:x:GID:comma-separated-members`.

**Practised:** `transcripts/task4b.txt` section 5. Created and inspected a real account: `id deploy` → `uid=1001(deploy) gid=1002(deploy) groups=1002(deploy)`, confirmed against `getent passwd deploy` (`deploy:x:1001:1002::/home/deploy:/bin/bash`) and a `grep` of `/etc/group` showing the freshly created `devops:x:1001:` and `deploy:x:1002:` lines. `su - deploy -c "whoami && id && pwd"` proved the full identity switch, including `pwd` correctly resolving to `/home/deploy`.

### 5. Processes

| Command | Purpose | Common flags | Example |
|---|---|---|---|
| `ps aux` | All processes, BSD style (rich %CPU/%MEM) | — | `ps aux \| grep nginx` |
| `ps -ef` | All processes, UNIX style (parent PID, full cmd) | — | `ps -ef \| head` |
| `top -b -n1` | One-shot, non-interactive snapshot of top | `-b` batch, `-n1` one iteration | `top -b -n1 \| head -12` |
| `pgrep` / `pidof` | Find PID(s) by process name | `-a` show full cmdline | `pgrep -a nginx` |
| `kill` | Send a signal (default TERM) to a PID | `-9` KILL, `-l` list signals | `kill 1234` |
| `jobs` | List background jobs of the current shell | `-l` include PIDs | `jobs -l` |
| `nice` | Launch a process with adjusted CPU priority | `-n N` (-20 highest … 19 lowest) | `nice -n 10 sleep 5` |
| `free -h` | RAM/swap usage, human readable | `-h` | `free -h` |
| `uptime` | How long the system's been up + load average | — | `uptime` |

**Practised:** `transcripts/task4b.txt` section 6. `ps aux`/`ps -ef` on the container show PID 1 really is `sleep infinity` (see Services below). `top -b -n1 | head -12` returned a genuine one-shot snapshot: `MiB Mem: 7935.5 total, ... buff/cache`. A real background job was launched and killed in a single shell (`sleep 300 & BGPID=$!; jobs -l; kill $BGPID`): `jobs -l` first reported `[1]+ 2964 Running sleep 300 &`, and after `kill` + a 1-second pause the job was gone from both `jobs -l` and `ps -p $BGPID`. `nice -n 10 sleep 5` was confirmed with `ps -o pid,ni,cmd`, which showed the real niceness value: `NI=10`.

### 6. Disk & System Info

| Command | Purpose | Common flags | Example |
|---|---|---|---|
| `df -h` | Filesystem space usage, human readable | `-h`, `-T` show fs type | `df -h` |
| `du -sh` | Directory/file size summary | `-s` summarize, `-h` human | `du -sh /var/*` |
| `lsblk` | List block devices and their mount points | `-f` show filesystem | `lsblk` |
| `uname -a` | Kernel name, version, architecture | `-r` release only | `uname -a` |
| `hostnamectl` / `/etc/os-release` | OS/distro identity | — | `cat /etc/os-release` |
| `date` | Show/format the current date-time | `+"FORMAT"` | `date +"%F %T"` |
| `env` | Show the process environment | — | `env \| sort` |

**Practised:** `transcripts/task4c.txt` section 1. `df -h` returned real numbers for this container: `overlay 911G 121G 744G 14% /`. `du -sh /var/* | sort -rh` ranked real directories (`60M /var/lib`, `1.2M /var/cache`, `408K /var/log`, ...). `uname -a` showed `Linux ubuntu-hw 6.12.76-linuxkit ... aarch64` — confirming this Docker Desktop VM runs an Apple-Silicon (arm64) Linux kernel. `history` returned nothing, and `hostnamectl` failed the same way `systemctl` does (see Gotchas / Services) — both are honest container limitations, not omissions.

### 7. Networking

| Command | Purpose | Common flags | Example |
|---|---|---|---|
| `ip a` | Show interfaces and their addresses | `a` = `addr show` | `ip a` |
| `ip r` | Show the routing table | `r` = `route show` | `ip r` |
| `ss -tuln` | Listening sockets, TCP+UDP, numeric ports | `-t` TCP, `-u` UDP, `-l` listening, `-n` numeric | `ss -tuln` |
| `ping -c N` | ICMP echo test, N packets then stop | `-c` count | `ping -c 2 8.8.8.8` |
| `curl -I` | Fetch HTTP headers only | `-I` head, `-s` silent, `-i` headers+body | `curl -I http://localhost/` |
| `hostname -I` | This host's IP address(es) | — | `hostname -I` |
| `dig` / `nslookup` | DNS lookup | `+short` (dig) | `dig +short example.com` |
| `/etc/hosts` | Static hostname → IP overrides | — | `cat /etc/hosts` |

**Practised:** `transcripts/task4c.txt` section 2. `ip a` showed the container's real interface: `11: eth0@if293 ... inet 172.17.0.4/16` (plus a handful of unused tunnel interfaces the Ubuntu kernel always registers — `tunl0`, `gre0`, `sit0`, etc. — which is normal and not Docker-specific). `ip r` confirmed the default route via `172.17.0.1`. `ping -c 2 8.8.8.8` genuinely succeeded (`0% packet loss`) — this container was granted `NET_RAW`, which is not guaranteed in every container runtime (see Gotchas). `dig +short google.com` resolved a real address (`142.250.205.206`). After `service nginx start`, `curl -I http://localhost/` returned a real `HTTP/1.1 200 OK` with `Server: nginx/1.24.0 (Ubuntu)`.

### 8. Archives & Compression

| Command | Purpose | Common flags | Example |
|---|---|---|---|
| `tar -czf` | Create a gzip-compressed tarball | `c` create, `z` gzip, `f` filename | `tar -czf out.tar.gz dir/` |
| `tar -tzf` | List a tarball's contents without extracting | `t` list | `tar -tzf out.tar.gz` |
| `tar -xzf` | Extract a tarball | `x` extract, `-C dir` target dir | `tar -xzf out.tar.gz -C dest/` |
| `gzip` / `gunzip` | Compress/decompress a single file | `-k` keep original | `gzip -k file.txt` |
| `zip -r` / `unzip` | Create/extract a zip archive | `-r` recursive, `-l` list, `-d` dest | `zip -r site.zip dir/` |

**Practised:** `transcripts/task4c.txt` section 3. Built `archive_src.tar.gz` from a real directory tree, listed it with `tar -tzf` (6 real entries), then extracted it into a fresh `extracted/` directory and confirmed the 3 files landed at the right paths. `gzip -k` / `gunzip -k` were run back-to-back on the same file to prove `-k` really does preserve the original: after `gzip -k old_report.txt` both `old_report.txt` and `old_report.txt.gz` existed; the plain file was then deleted, and `gunzip -k old_report.txt.gz` restored it (and still kept the `.gz`). `zip -r site.zip archive_src/` and `unzip -l`/`unzip -d` were run the same way, with `unzip -l` reporting the real compressed sizes (`321` bytes total across 6 entries).

### 9. Packages

| Command | Purpose | Common flags | Example |
|---|---|---|---|
| `apt list --installed` | List installed packages (APT view) | — | `apt list --installed \| head` |
| `dpkg -l` | List installed packages (dpkg view, incl. status codes) | — | `dpkg -l \| grep nginx` |
| `apt-cache policy <pkg>` | Installed vs. candidate version + which repo it comes from | — | `apt-cache policy nginx` |
| `dpkg -L <pkg>` | List every file a package actually installed | — | `dpkg -L nginx` |
| `which` / `command -v` | Resolve a command to its binary path | — | `command -v nginx` |

**Practised:** `transcripts/task4c.txt` section 4. `apt-cache policy nginx` showed a real installed/candidate match (`1.24.0-2ubuntu7.17`) sourced from `noble-updates`/`noble-security`. `dpkg -L nginx` listed real installed paths (`/usr/sbin/nginx`, `/usr/share/doc/nginx/...`). Both `which nginx` and `command -v nginx` agreed on `/usr/sbin/nginx`.

### 10. Services

| Command | Purpose | Common flags | Example |
|---|---|---|---|
| `systemctl status <svc>` | Show a systemd unit's state | `start`/`stop`/`restart`/`enable` | `systemctl status nginx` |
| `journalctl -u <svc>` | View a systemd unit's logs | `-f` follow, `-n N` last N | `journalctl -u nginx -n 50` |
| `service <svc> <action>` | Legacy SysV-init wrapper (works with or without systemd) | `start`/`stop`/`status` | `service nginx status` |

**Practised (reference table above is syntax-only for `systemctl`/`journalctl`; the actual demonstrated commands are below):** `transcripts/task4c.txt` section 5. `hw-t4` has **no systemd** — its PID 1 is literally `sleep infinity` (confirmed with `ps -p 1 -o pid,comm,args`), not `/sbin/init`. Running `systemctl status nginx` produced the real, expected failure:
```
System has not been booted with systemd as init system (PID 1). Can't operate.
Failed to connect to bus: Host is down
```
Ubuntu's `service` command falls back to the classic SysV `/etc/init.d` scripts when systemd/D-Bus isn't present, so `service nginx start` / `service nginx status` **did** work for real in this container and were used throughout task4c to actually run nginx for the `curl` demo.

### Top 25 commands a DevOps engineer types every day

| # | Command | What it's for |
|---|---|---|
| 1 | `ls -lah` | See what's in a directory, including hidden/size info |
| 2 | `cd` | Move around the filesystem |
| 3 | `pwd` | Confirm where you are |
| 4 | `cat` / `less` | Read a file |
| 5 | `tail -f` | Watch a log file grow live |
| 6 | `grep -rn` | Find a string across a codebase/logs |
| 7 | `find` | Locate files by name/size/age |
| 8 | `chmod` / `chown` | Fix permission/ownership issues |
| 9 | `ps aux` / `top` | See what's running and eating resources |
| 10 | `kill` / `kill -9` | Stop a runaway process |
| 11 | `df -h` / `du -sh` | Check disk space before it's a 2 a.m. page |
| 12 | `free -h` | Check memory pressure |
| 13 | `ssh` | Get onto a remote box |
| 14 | `scp` / `rsync -av` | Copy files to/from a remote box |
| 15 | `curl -I` / `curl -s` | Poke an HTTP endpoint |
| 16 | `ip a` / `ss -tuln` | Check interfaces and listening ports |
| 17 | `systemctl status/restart` | Manage a service |
| 18 | `journalctl -u <svc> -n 100` | Read a service's recent logs |
| 19 | `tar -czf` / `tar -xzf` | Package or unpack a directory |
| 20 | `git status` / `git log` | Check repo state before doing anything else |
| 21 | `docker ps` / `docker logs` | Check running containers and their output |
| 22 | `vim` / `nano` | Quick edit on a remote box |
| 23 | `sudo` | Run something that needs elevated rights |
| 24 | `history \| grep` | Find that command you ran last week |
| 25 | `man <cmd>` / `<cmd> --help` | Remember the flag you always forget |

### Gotchas

- **`rm -rf` has no undo.** There's no trash can on a typical Linux server — double-check the path (especially after a `cd` that didn't go where you expected) before hitting enter, and never run it with an unquoted variable that might be empty (`rm -rf $VAR/` when `$VAR` is unset becomes `rm -rf /`).
- **`chmod 777` is not a fix, it's a bigger problem.** It silences a permission error by making a file world-writable/executable, which is almost never what you actually want. Diagnose *why* the permission is denied (wrong owner? wrong group? missing directory execute bit?) and grant the minimum needed — this write-up's own permission-denied demo was fixed with `chmod 644`, not `777`.
- **Trailing slashes change behavior in `cp`/`rsync`.** `rsync -av src/ dest/` copies the *contents* of `src` into `dest`; `rsync -av src dest/` copies `src` itself *as a subdirectory* of `dest`. `cp -r` is more forgiving but the same mental trap applies — always double-check what a trailing slash will do before running it against production data.
- **Quote your `find -name` patterns.** `find . -name *.log` (unquoted) lets the *shell* glob-expand `*.log` in the current directory first, which either breaks the command or silently searches for the wrong thing. Always write `find . -name "*.log"`.
- **`umask`/`cd`/backgrounded jobs are per-shell state, not global.** We hit this for real while building this cheat sheet: our test harness runs each command in its own fresh non-interactive shell, so a bare `umask 027` on one line had zero effect on a `touch` on the next line — the umask reset to the shell's default before the next command ran. The fix was chaining them (`umask 027 && touch file && ls -l file`) into one shell invocation. The same rule bit the background-job demo: `sleep 300 &` and a later `kill` only work together if they share the same shell process (or you pass a real PID/PID-file across processes). This is exactly why `nohup`, `disown`, systemd units, or a process supervisor exist for anything that needs to outlive one shell.
- **`ping` failing inside a container is normal, not a bug.** Many container runtimes drop `CAP_NET_RAW` or block raw ICMP sockets by default, so `ping` inside a container often fails with `Operation not permitted` even though the container has working network access otherwise (DNS, TCP, `curl` all still work). In `hw-t4` specifically, `ping` *did* work (Docker Desktop's default seccomp/capabilities allowed it here), but don't assume that's true everywhere — if `ping` fails in a container, reach for `curl`/`nc`/`ss` to actually diagnose connectivity instead.
- **`systemctl`/`hostnamectl` need a real systemd PID 1 and a working D-Bus.** Inside a minimal container (like `hw-t4`, where PID 1 is `sleep infinity`) they fail immediately with `Failed to connect to bus: Host is down`. That's expected — containers built for a single process almost never run systemd. Use `service <name> <action>` (SysV-style) or run the daemon's binary directly instead.
- **`lsblk`/`df` inside a container can show the *host's* block devices and disk size**, not a size specific to the container — because containers usually share the host kernel's device/mount view rather than getting fully isolated block-device namespacing. Don't be surprised by huge or unfamiliar numbers; cross-check with `df -h` on the actual mount point you care about.

---

## Screenshots — practice session

**Navigation, files, and text search**

![task4a-1.png](screenshots/task4a-1.png)
![task4a-2.png](screenshots/task4a-2.png)
![task4a-3.png](screenshots/task4a-3.png)
![task4a-4.png](screenshots/task4a-4.png)
![task4a-5.png](screenshots/task4a-5.png)
![task4a-6.png](screenshots/task4a-6.png)
![task4a-7.png](screenshots/task4a-7.png)
![task4a-8.png](screenshots/task4a-8.png)
![task4a-9.png](screenshots/task4a-9.png)

**Permissions, users, and processes**

![task4b-1.png](screenshots/task4b-1.png)
![task4b-2.png](screenshots/task4b-2.png)
![task4b-3.png](screenshots/task4b-3.png)

**Disk, network, archives, packages**

![task4c-1.png](screenshots/task4c-1.png)
![task4c-2.png](screenshots/task4c-2.png)
![task4c-3.png](screenshots/task4c-3.png)
![task4c-4.png](screenshots/task4c-4.png)
![task4c-5.png](screenshots/task4c-5.png)
![task4c-6.png](screenshots/task4c-6.png)

## Full terminal transcripts

- [Task 4a — navigation, files & text search · terminal transcript](transcript-a-navigation-files-text.md)
- [Task 4b — permissions, users & processes · terminal transcript](transcript-b-permissions-users-processes.md)
- [Task 4c — disk, network, archives & packages · terminal transcript](transcript-c-disk-network-archives-packages.md)
