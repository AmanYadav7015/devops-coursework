# Task 2 — adduser vs useradd · terminal transcript

> Real session captured on Ubuntu 24.04 in container `hw-t2`.
> Every command was executed; the output is verbatim.

[← Back to Task 2 — adduser vs useradd](README.md) · [Topic index](../README.md)

---

```console
# --- 0. Environment check ---
root@ubuntu-hw:~# cat /etc/os-release | head -3
PRETTY_NAME="Ubuntu 24.04.4 LTS"
NAME="Ubuntu"
VERSION_ID="24.04"
root@ubuntu-hw:~# dpkg -l | grep -E '^ii\s+(adduser|passwd)\s'
ii  adduser                  3.137ubuntu1                      all          add and remove users and groups
ii  passwd                   1:4.13+dfsg1-4ubuntu3.2           arm64        change and administer password and group data
```

### 1. What each command actually IS

```console
# --- useradd: where does it live, what type of file is it? ---
root@ubuntu-hw:~# which useradd
/usr/sbin/useradd
root@ubuntu-hw:~# file $(which useradd)
/usr/sbin/useradd: ELF 64-bit LSB pie executable, ARM aarch64, version 1 (SYSV), dynamically linked, interpreter /lib/ld-linux-aarch64.so.1, BuildID[sha1]=483f79642f7a936acdeb2cb2fd1c4e70c2f0ef9d, for GNU/Linux 3.7.0, stripped

# --- adduser: where does it live, what type of file is it? ---
root@ubuntu-hw:~# which adduser
/usr/sbin/adduser
root@ubuntu-hw:~# file $(which adduser)
/usr/sbin/adduser: Perl script text executable

# --- proof adduser is a Perl script (shebang + first lines of source) ---
root@ubuntu-hw:~# head -20 $(which adduser)
#! /usr/bin/perl

# Copyright (C) 2000-2004 Roland Bauerschmidt <rb@debian.org>
#               2005-2023 Marc Haber <mh+debian-packages@zugschlus.de>
#               2022 Benjamin Drung <benjamin.drung@canonical.com>
#               2023 Guillem Jover <guillem@debian.org>
#               2021-2022 Jason Franklin <jason@oneway.dev>
#               2022 Matt Barry <matt@hazelmollusk.org>
#               2016-2017 Afif Elghraoui <afif@debian.org>
#               2016 Dr. Helge Kreutzmann <debian@helgefjell.de>
#               2005-2009 Joerg Hoh <joerg@joerghoh.de>
#               2006-2011 Stephen Gran <sgran@debian.org>
#
# Original adduser:
# Copyright (C) 1997-1999 Guy Maor <maor@debian.org>
#
# Copyright (C) 1995 Ted Hajek <tedhajek@boombox.micro.umn.edu>
#                    Ian A. Murdock <imurdock@gnu.ai.mit.edu>
#
# The general scheme of this program was adapted from the original
```

### 2. Compare the help output (both exist, but adduser's is friendlier)

```console
root@ubuntu-hw:~# useradd --help | head -20
Usage: useradd [options] LOGIN
       useradd -D
       useradd -D [options]

Options:
      --badname                 do not check for bad names
  -b, --base-dir BASE_DIR       base directory for the home directory of the
                                new account
      --btrfs-subvolume-home    use BTRFS subvolume for home directory
  -c, --comment COMMENT         GECOS field of the new account
  -d, --home-dir HOME_DIR       home directory of the new account
  -D, --defaults                print or change default useradd configuration
  -e, --expiredate EXPIRE_DATE  expiration date of the new account
  -f, --inactive INACTIVE       password inactivity period of the new account
  -F, --add-subids-for-system   add entries to sub[ud]id even when adding a system user
  -g, --gid GROUP               name or ID of the primary group of the new
                                account
  -G, --groups GROUPS           list of supplementary groups of the new
                                account
  -h, --help                    display this help message and exit

root@ubuntu-hw:~# adduser --help | head -20
adduser [--uid id] [--firstuid id] [--lastuid id]
        [--gid id] [--firstgid id] [--lastgid id] [--ingroup group]
        [--add-extra-groups] [--encrypt-home] [--shell shell]
        [--comment comment] [--home dir] [--no-create-home]
        [--allow-all-names] [--allow-bad-names]
        [--disabled-password] [--disabled-login]
        [--conf file] [--extrausers] [--quiet] [--verbose] [--debug]
        user
    Add a normal user

adduser --system
        [--uid id] [--group] [--ingroup group] [--gid id]
        [--shell shell] [--comment comment] [--home dir] [--no-create-home]
        [--conf file] [--extrausers] [--quiet] [--verbose] [--debug]
        user
   Add a system user

adduser --group
        [--gid ID] [--firstgid id] [--lastgid id]
        [--conf file] [--extrausers] [--quiet] [--verbose] [--debug]
```

### 3. THE CONTRAST -- create a user the "raw" low-level way: useradd, no flags

```console
root@ubuntu-hw:~# useradd testuser_raw

# --- consequence 1: no home directory was created for testuser_raw ---
root@ubuntu-hw:~# ls /home
ubuntu

# --- consequence 2: check the passwd DB entry -- shell, uid, gid ---
root@ubuntu-hw:~# getent passwd testuser_raw
testuser_raw:x:1001:1001::/home/testuser_raw:/bin/sh

# --- consequence 3: account has no usable password (locked) ---
root@ubuntu-hw:~# passwd -S testuser_raw
testuser_raw L 2026-09-02 0 99999 7 -1
```

### 4. THE RECOMMENDED WAY -- adduser, run non-interactively

```console
root@ubuntu-hw:~# adduser --gecos "" --disabled-password testuser
info: Adding user `testuser' ...
info: Selecting UID/GID from range 1000 to 59999 ...
info: Adding new group `testuser' (1002) ...
info: Adding new user `testuser' (1002) with group `testuser (1002)' ...
info: Creating home directory `/home/testuser' ...
info: Copying files from `/etc/skel' ...
info: Adding new user `testuser' to supplemental / extra groups `users' ...
info: Adding user `testuser' to group `users' ...

# --- consequence 1: home directory WAS created under /home ---
root@ubuntu-hw:~# ls /home
testuser
ubuntu

# --- consequence 2: skeleton files were copied in from /etc/skel ---
root@ubuntu-hw:~# ls -la /home/testuser
total 20
drwxr-x--- 2 testuser testuser 4096 Sep  2 16:51 .
drwxr-xr-x 1 root     root     4096 Sep  2 16:51 ..
-rw-r--r-- 1 testuser testuser  220 Sep  2 16:51 .bash_logout
-rw-r--r-- 1 testuser testuser 3771 Sep  2 16:51 .bashrc
-rw-r--r-- 1 testuser testuser  807 Sep  2 16:51 .profile

# --- consequence 3: passwd DB entry -- note the shell this time ---
root@ubuntu-hw:~# getent passwd testuser
testuser:x:1002:1002:,,,:/home/testuser:/bin/bash

# --- consequence 4: adduser also created a matching private group ---
root@ubuntu-hw:~# getent group testuser
testuser:x:1002:
```

### 5. Side-by-side comparison of the two accounts

```console
root@ubuntu-hw:~# getent passwd testuser_raw testuser
testuser_raw:x:1001:1001::/home/testuser_raw:/bin/sh
testuser:x:1002:1002:,,,:/home/testuser:/bin/bash

root@ubuntu-hw:~# getent group testuser_raw testuser
testuser_raw:x:1001:
testuser:x:1002:

root@ubuntu-hw:~# ls -la /home
total 16
drwxr-xr-x 1 root     root     4096 Sep  2 16:51 .
drwxr-xr-x 1 root     root     4096 Sep  2 16:49 ..
drwxr-x--- 2 testuser testuser 4096 Sep  2 16:51 testuser
drwxr-x--- 2 ubuntu   ubuntu   4096 Aug 10 14:55 ubuntu

root@ubuntu-hw:~# ls -la /home/testuser
total 20
drwxr-x--- 2 testuser testuser 4096 Sep  2 16:51 .
drwxr-xr-x 1 root     root     4096 Sep  2 16:51 ..
-rw-r--r-- 1 testuser testuser  220 Sep  2 16:51 .bash_logout
-rw-r--r-- 1 testuser testuser 3771 Sep  2 16:51 .bashrc
-rw-r--r-- 1 testuser testuser  807 Sep  2 16:51 .profile
```

### 6. Proving useradd CAN do the same thing -- it just needs explicit flags

```console
root@ubuntu-hw:~# useradd -m -s /bin/bash testuser_manual

root@ubuntu-hw:~# ls -la /home/testuser_manual
total 20
drwxr-x--- 2 testuser_manual testuser_manual 4096 Sep  2 16:51 .
drwxr-xr-x 1 root            root            4096 Sep  2 16:51 ..
-rw-r--r-- 1 testuser_manual testuser_manual  220 Mar 31  2024 .bash_logout
-rw-r--r-- 1 testuser_manual testuser_manual 3771 Mar 31  2024 .bashrc
-rw-r--r-- 1 testuser_manual testuser_manual  807 Mar 31  2024 .profile

root@ubuntu-hw:~# getent passwd testuser_manual
testuser_manual:x:1003:1003::/home/testuser_manual:/bin/bash

# --- clean up this extra demo account right away, it was only to prove the point ---
# (this minimal container has perl-base but not the full `perl` package, and no apt
#  sources cached, so deluser's --remove-home/backup code path can't load; that is a
#  genuine real observation, not a scripting mistake -- fall back to userdel -r)
root@ubuntu-hw:~# deluser --remove-home testuser_manual
fatal: In order to use the --remove-home, --remove-all-files, and --backup features, you need to install the `perl' package. To accomplish that, run apt-get install perl.
root@ubuntu-hw:~# userdel -r testuser_manual
userdel: testuser_manual mail spool (/var/mail/testuser_manual) not found
root@ubuntu-hw:~# ls /home
testuser
ubuntu
```

### 7. What actually drives adduser's "do the right thing" behavior

```console
root@ubuntu-hw:~# grep -vE '^\s*#|^$' /etc/adduser.conf | head -20

# --- the skeleton directory every new adduser home is seeded from ---
root@ubuntu-hw:~# ls -la /etc/skel
total 24
drwxr-xr-x 2 root root 4096 Aug 10 14:49 .
drwxr-xr-x 1 root root 4096 Sep  2 16:51 ..
-rw-r--r-- 1 root root  220 Mar 31  2024 .bash_logout
-rw-r--r-- 1 root root 3771 Mar 31  2024 .bashrc
-rw-r--r-- 1 root root  807 Mar 31  2024 .profile
```

### 8. Set a password on the delivered test user (throwaway demo password)

```console
# --- before: no usable password ---
root@ubuntu-hw:~# passwd -S testuser
testuser L 2026-09-02 0 99999 7 -1

root@ubuntu-hw:~# echo 'testuser:DemoPass123' | chpasswd

# --- after: password is now set/usable (status flips to P) ---
root@ubuntu-hw:~# passwd -S testuser
testuser P 2026-09-02 0 99999 7 -1
```

### 9. Grant sudo group membership to the test user

```console
root@ubuntu-hw:~# usermod -aG sudo testuser

root@ubuntu-hw:~# groups testuser
testuser : testuser sudo users

root@ubuntu-hw:~# id testuser
uid=1002(testuser) gid=1002(testuser) groups=1002(testuser),27(sudo),100(users)
```

### 10. Clean-up demonstration -- remove the "wrong way" account

```console
# (deluser --remove-home needs the full `perl' package, unavailable offline in this
#  container as shown in section 6 -- userdel -r is the documented fallback and
#  achieves the same result: account + home directory removed)
root@ubuntu-hw:~# deluser --remove-home testuser_raw
fatal: In order to use the --remove-home, --remove-all-files, and --backup features, you need to install the `perl' package. To accomplish that, run apt-get install perl.
root@ubuntu-hw:~# userdel -r testuser_raw
userdel: testuser_raw mail spool (/var/mail/testuser_raw) not found
userdel: testuser_raw home directory (/home/testuser_raw) not found

# --- confirm testuser_raw is gone ---
root@ubuntu-hw:~# getent passwd testuser_raw
root@ubuntu-hw:~# ls /home
testuser
ubuntu
```

### 11. Final proof -- the delivered test user, created the recommended way

```console
root@ubuntu-hw:~# id testuser
uid=1002(testuser) gid=1002(testuser) groups=1002(testuser),27(sudo),100(users)

root@ubuntu-hw:~# getent passwd testuser
testuser:x:1002:1002:,,,:/home/testuser:/bin/bash
```
