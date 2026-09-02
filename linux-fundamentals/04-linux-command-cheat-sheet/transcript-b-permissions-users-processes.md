# Task 4b — permissions, users & processes · terminal transcript

> Real session captured on Ubuntu 24.04 in container `hw-t4`.
> Every command was executed; the output is verbatim.

[← Back to Task 4 — Linux Command Cheat Sheet](README.md) · [Topic index](../README.md)

---

```console
# (continues in the /root/cheatsheet workspace built during task4a)
```

### 1. ls -l breakdown + chmod (symbolic AND numeric) on the SAME file

```console
# --- before: deploy.sh is a plain, non-executable file ---
root@ubuntu-hw:~# ls -l /root/cheatsheet/scripts/deploy.sh
-rw-r--r-- 1 root root 79 Sep  2 16:57 /root/cheatsheet/scripts/deploy.sh

# --- symbolic chmod: add execute for the owner (u+x) ---
root@ubuntu-hw:~# chmod u+x /root/cheatsheet/scripts/deploy.sh
root@ubuntu-hw:~# ls -l /root/cheatsheet/scripts/deploy.sh
-rwxr--r-- 1 root root 79 Sep  2 16:57 /root/cheatsheet/scripts/deploy.sh

# --- numeric chmod: rwxr-x--- = 750 ---
root@ubuntu-hw:~# chmod 750 /root/cheatsheet/scripts/deploy.sh
root@ubuntu-hw:~# ls -l /root/cheatsheet/scripts/deploy.sh
-rwxr-x--- 1 root root 79 Sep  2 16:57 /root/cheatsheet/scripts/deploy.sh

# --- numeric chmod: back to a plain, safe 644 ---
root@ubuntu-hw:~# chmod 644 /root/cheatsheet/scripts/deploy.sh
root@ubuntu-hw:~# ls -l /root/cheatsheet/scripts/deploy.sh
-rw-r--r-- 1 root root 79 Sep  2 16:57 /root/cheatsheet/scripts/deploy.sh
```

### 2. chown / chgrp

```console
# --- create a group and a user to own things (real system accounts) ---
root@ubuntu-hw:~# groupadd devops
root@ubuntu-hw:~# useradd -m -s /bin/bash deploy
root@ubuntu-hw:~# id deploy
uid=1001(deploy) gid=1002(deploy) groups=1002(deploy)

# --- chown: change owner only ---
root@ubuntu-hw:~# chown deploy /root/cheatsheet/scripts/deploy.sh
root@ubuntu-hw:~# ls -l /root/cheatsheet/scripts/deploy.sh
-rw-r--r-- 1 deploy root 79 Sep  2 16:57 /root/cheatsheet/scripts/deploy.sh

# --- chgrp: change group only ---
root@ubuntu-hw:~# chgrp devops /root/cheatsheet/scripts/deploy.sh
root@ubuntu-hw:~# ls -l /root/cheatsheet/scripts/deploy.sh
-rw-r--r-- 1 deploy devops 79 Sep  2 16:57 /root/cheatsheet/scripts/deploy.sh

# --- chown user:group in one shot, then put ownership back to root:root ---
root@ubuntu-hw:~# chown deploy:devops /root/cheatsheet/scripts/deploy.sh
root@ubuntu-hw:~# ls -l /root/cheatsheet/scripts/deploy.sh
-rw-r--r-- 1 deploy devops 79 Sep  2 16:57 /root/cheatsheet/scripts/deploy.sh
root@ubuntu-hw:~# chown root:root /root/cheatsheet/scripts/deploy.sh
root@ubuntu-hw:~# ls -l /root/cheatsheet/scripts/deploy.sh
-rw-r--r-- 1 root root 79 Sep  2 16:57 /root/cheatsheet/scripts/deploy.sh
```

### 3. umask

```console
# --- current umask (root's default) ---
root@ubuntu-hw:~# umask
0022

# --- create a file under that umask and see the resulting permissions ---
root@ubuntu-hw:~# touch /root/cheatsheet/umask_test_default.txt && ls -l /root/cheatsheet/umask_test_default.txt
-rw-r--r-- 1 root root 0 Sep  2 16:59 /root/cheatsheet/umask_test_default.txt

# --- tighten the umask, create another file, compare (same shell, so the umask actually applies) ---
root@ubuntu-hw:~# umask 027 && touch /root/cheatsheet/umask_test_027.txt && ls -l /root/cheatsheet/umask_test_027.txt
-rw-r----- 1 root root 0 Sep  2 16:59 /root/cheatsheet/umask_test_027.txt

# --- confirm the umask reverts in a fresh shell (each line here is its own login shell) ---
root@ubuntu-hw:~# umask
0022
```

### 4. A REAL permission-denied error, then fix it with chmod

```console
# --- a world-traversable directory holding a root-only secret ---
root@ubuntu-hw:~# mkdir -p /srv/permdemo
root@ubuntu-hw:~# cp /root/seed/secret.txt /srv/permdemo/secret.txt
root@ubuntu-hw:~# chmod 600 /srv/permdemo/secret.txt
root@ubuntu-hw:~# chown root:root /srv/permdemo/secret.txt
root@ubuntu-hw:~# ls -l /srv/permdemo/secret.txt
-rw------- 1 root root 59 Sep  2 16:59 /srv/permdemo/secret.txt

# --- the 'deploy' user tries to read it: REAL permission-denied error ---
root@ubuntu-hw:~# su - deploy -c "cat /srv/permdemo/secret.txt"
cat: /srv/permdemo/secret.txt: Permission denied

# --- fix it: open up read access for everyone ---
root@ubuntu-hw:~# chmod 644 /srv/permdemo/secret.txt
root@ubuntu-hw:~# ls -l /srv/permdemo/secret.txt
-rw-r--r-- 1 root root 59 Sep  2 16:59 /srv/permdemo/secret.txt

# --- now it works ---
root@ubuntu-hw:~# su - deploy -c "cat /srv/permdemo/secret.txt"
DB_PASSWORD=super-secret-value
API_KEY=abcd-1234-efgh-5678
```

### 5. Users & groups: whoami, id, groups, getent, /etc/passwd, /etc/group

```console
root@ubuntu-hw:~# whoami
root
root@ubuntu-hw:~# id
uid=0(root) gid=0(root) groups=0(root)
root@ubuntu-hw:~# groups
root

# --- inspect the accounts created above ---
root@ubuntu-hw:~# id deploy
uid=1001(deploy) gid=1002(deploy) groups=1002(deploy)
root@ubuntu-hw:~# getent passwd deploy
deploy:x:1001:1002::/home/deploy:/bin/bash
root@ubuntu-hw:~# getent passwd root
root:x:0:0:root:/root:/bin/bash

# --- structure of /etc/passwd: name:x:uid:gid:comment:home:shell ---
root@ubuntu-hw:~# head -3 /etc/passwd
root:x:0:0:root:/root:/bin/bash
daemon:x:1:1:daemon:/usr/sbin:/usr/sbin/nologin
bin:x:2:2:bin:/bin:/usr/sbin/nologin
root@ubuntu-hw:~# tail -3 /etc/passwd
messagebus:x:100:101::/nonexistent:/usr/sbin/nologin
syslog:x:101:102::/nonexistent:/usr/sbin/nologin
deploy:x:1001:1002::/home/deploy:/bin/bash

# --- structure of /etc/group: name:x:gid:members ---
root@ubuntu-hw:~# grep -E "^(devops|deploy|ubuntu):" /etc/group
ubuntu:x:1000:
devops:x:1001:
deploy:x:1002:
root@ubuntu-hw:~# tail -3 /etc/group
syslog:x:102:
devops:x:1001:
deploy:x:1002:

# --- su -c: run a single command as another user ---
root@ubuntu-hw:~# su - deploy -c "whoami && id && pwd"
deploy
uid=1001(deploy) gid=1002(deploy) groups=1002(deploy)
/home/deploy
```

### 6. Processes: ps, top, pgrep/pidof, background + kill, jobs, nice

```console
# --- ps aux: BSD-style, all processes ---
root@ubuntu-hw:~# ps aux | head -10
USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
root           1  0.0  0.0   2272  1220 ?        Ss   16:49   0:00 sleep infinity
root         605  0.0  0.0      0     0 ?        Zs   16:53   0:00 [nginx] <defunct>
root         773  0.0  0.0      0     0 ?        Z    16:56   0:00 [pkill] <defunct>
root        2910  0.0  0.0   4036  3032 ?        Ss   16:59   0:00 bash -lc ps aux | head -10
root        2918  0.0  0.0   7632  3640 ?        R    16:59   0:00 ps aux
root        2919  0.0  0.0   2284  1236 ?        S    16:59   0:00 head -10

# --- ps -ef: UNIX-style, all processes, full command ---
root@ubuntu-hw:~# ps -ef | head -10
UID          PID    PPID  C STIME TTY          TIME CMD
root           1       0  0 16:49 ?        00:00:00 sleep infinity
root         605       1  0 16:53 ?        00:00:00 [nginx] <defunct>
root         773       1  0 16:56 ?        00:00:00 [pkill] <defunct>
root        2920       0  0 16:59 ?        00:00:00 bash -lc ps -ef | head -10
root        2928    2920  0 16:59 ?        00:00:00 ps -ef
root        2929    2920  0 16:59 ?        00:00:00 head -10

# --- top -b -n1: one non-interactive snapshot ---
root@ubuntu-hw:~# top -b -n1 | head -12
top - 16:59:35 up 2 days, 22:58,  0 user,  load average: 0.51, 0.76, 0.67
Tasks:   6 total,   1 running,   3 sleeping,   0 stopped,   2 zombie
%Cpu(s):  0.0 us,  0.0 sy,  0.0 ni,100.0 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st 
MiB Mem :   7935.5 total,    130.2 free,   1379.4 used,   6652.7 buff/cache     
MiB Swap:   1024.0 total,   1019.7 free,      4.3 used.   6556.2 avail Mem 

    PID USER      PR  NI    VIRT    RES    SHR S  %CPU  %MEM     TIME+ COMMAND
      1 root      20   0    2272   1220   1140 S   0.0   0.0   0:00.00 sleep
    605 root      20   0       0      0      0 Z   0.0   0.0   0:00.00 nginx
    773 root      20   0       0      0      0 Z   0.0   0.0   0:00.00 pkill
   2930 root      20   0    4036   3048   2784 S   0.0   0.0   0:00.00 bash
   2938 root      20   0    8492   4664   2688 R   0.0   0.1   0:00.00 top

# --- pgrep / pidof: find PIDs by name ---
root@ubuntu-hw:~# pgrep -a sleep
1 sleep infinity
root@ubuntu-hw:~# pidof sleep
1

# --- background a job, list it, kill it (all in one shell so state persists) ---
root@ubuntu-hw:~# sleep 300 & BGPID=$!; echo "started sleep with PID $BGPID"; jobs -l; ps -p $BGPID; kill $BGPID; sleep 1; jobs -l; ps -p $BGPID
started sleep with PID 2964
[1]+  2964 Running                 sleep 300 &
    PID TTY          TIME CMD
   2964 ?        00:00:00 sleep
    PID TTY          TIME CMD

# --- nice: launch a low-priority background job and inspect its niceness ---
root@ubuntu-hw:~# nice -n 10 sleep 5 & NPID=$!; sleep 0.5; ps -o pid,ni,cmd -p $NPID; wait $NPID 2>/dev/null; echo "job $NPID finished"
    PID  NI CMD
   2975  10 sleep 5
job 2975 finished

# --- free -h / uptime: memory and load ---
root@ubuntu-hw:~# free -h
               total        used        free      shared  buff/cache   available
Mem:           7.7Gi       1.3Gi       134Mi        28Mi       6.5Gi       6.4Gi
Swap:          1.0Gi       4.3Mi       1.0Gi
root@ubuntu-hw:~# uptime
 16:59:41 up 2 days, 22:58,  0 user,  load average: 0.47, 0.75, 0.67
```
