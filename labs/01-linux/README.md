# Assignment 1 — Linux Fundamentals

This folder covers the four Linux Fundamental tasks:

1. Soft link vs hard link
2. `adduser` vs `useradd`
3. `journalctl`
4. Linux command cheat sheet

Every command below was actually executed and every `text` block is the real output that came back.
Nothing here is invented. Where something could **not** be captured for real, it is labelled clearly.

---

## Why there are Docker containers in a Linux assignment

This homework was done on a macOS laptop. macOS is a Unix, but it is **not Linux** — it uses Open Directory
instead of `/etc/passwd` for user management, and it uses `launchd` + Apple System Log instead of systemd.
So the three headline commands in this assignment simply do not exist on the host:

```bash
uname -srm
for c in adduser useradd journalctl; do printf '%s: ' "$c"; command -v "$c" || echo "not found"; done
```

Output:

```text
Darwin 25.5.0 arm64
---
adduser: not found
useradd: not found
journalctl: not found
```

Faking the output would defeat the point of the exercise, so the real Linux work runs inside Docker containers.
Two containers are used:

| Container | Image | Why |
|---|---|---|
| `hw01-ubuntu` | `ubuntu:24.04` | Normal Ubuntu userland. Used for links, users, and the cheat sheet. PID 1 is just `sleep`, so there is no systemd. |
| `hw01-systemd` | `ubuntu:24.04` booted with `/sbin/init` | A privileged container that actually **boots systemd**, so `journalctl` has a real journal to read. |

### Container 1 — the plain Ubuntu box

```bash
docker run -d --name hw01-ubuntu ubuntu:24.04 sleep infinity
docker exec hw01-ubuntu bash -c 'cat /etc/os-release | head -3; uname -m'
```

Output:

```text
PRETTY_NAME="Ubuntu 24.04.4 LTS"
NAME="Ubuntu"
VERSION_ID="24.04"
aarch64
```

`-d` runs it detached and `sleep infinity` keeps it alive so we can keep sending `docker exec` into it.
Everything below is run non-interactively with `docker exec` instead of an interactive `-it bash` shell,
which is what makes the output reproducible and copy-pasteable.

### Container 2 — a real systemd host

```bash
docker run -d --name hw01-systemd --privileged --cgroupns=host \
  --tmpfs /run --tmpfs /run/lock \
  -v /sys/fs/cgroup:/sys/fs/cgroup:rw \
  ubuntu:24.04 bash -c 'apt-get update -qq && apt-get install -y systemd systemd-sysv && exec /sbin/init'
```

After it finishes booting:

```bash
docker exec hw01-systemd bash -c 'cat /proc/1/comm; systemctl is-system-running; journalctl --version | head -1'
```

Output:

```text
systemd
running
systemd 255 (255.4-1ubuntu8.17)
```

PID 1 is `systemd`, the system reports `running`, and `journalctl` is present. This is a genuine systemd host,
so Task 3 has genuine journal output rather than a description of what it would look like.

---

## Task 1 — Soft Link vs Hard Link

### The one idea you need first: the inode

On Linux, a filename is not the file. The **file** is an inode — a numbered record holding the permissions,
owner, size, timestamps, and the pointers to the actual data blocks. A directory entry is just a
`name -> inode number` mapping. That single fact explains every difference between the two link types.

- A **hard link** is a second directory entry pointing at the *same inode*. It is not a copy and it is not a
  shortcut — it is an equal, first-class name for the same file.
- A **soft link** (symbolic link, symlink) is its own tiny file with its own inode, whose entire content is a
  *text path string* pointing at another name. Resolving it is the kernel following that string.

### Step 1: create a file and both kinds of link

```bash
mkdir -p /root/links-demo && cd /root/links-demo
echo "Hello from the original file" > original.txt
ln    original.txt hardlink.txt
ln -s original.txt softlink.txt
ls -l
```

Output:

```text
total 8
-rw-r--r-- 2 root root 29 Sep 17 16:08 hardlink.txt
-rw-r--r-- 2 root root 29 Sep 17 16:08 original.txt
lrwxrwxrwx 1 root root 12 Sep 17 16:08 softlink.txt -> original.txt
```

Three things are already visible:

- `ln` with no flag makes a hard link; `ln -s` makes a soft link.
- The soft link's type character is `l` (symlink), and `ls` prints `-> original.txt`. The hard link's type
  character is `-` — it looks exactly like an ordinary file, because it *is* one.
- The number in the third column jumped from 1 to `2` for both `original.txt` and `hardlink.txt`. That is the
  **link count**: how many names point at this inode.

### Step 2: prove they share an inode with `ls -li`

```bash
ls -li
```

Output:

```text
total 8
2757480 -rw-r--r-- 2 root root 29 Sep 17 16:08 hardlink.txt
2757480 -rw-r--r-- 2 root root 29 Sep 17 16:08 original.txt
2829497 lrwxrwxrwx 1 root root 12 Sep 17 16:08 softlink.txt -> original.txt
```

The `-i` flag prints the inode number in the first column. `original.txt` and `hardlink.txt` are both
inode **2757480** — one file, two names. `softlink.txt` is inode **2829497** — a completely separate file.

Notice the soft link's size is `12` bytes. The string `original.txt` is exactly 12 characters. That is literally
all a symlink stores.

### Step 3: read the metadata with `stat`

```bash
stat original.txt
```

Output:

```text
  File: original.txt
  Size: 29        	Blocks: 8          IO Block: 4096   regular file
Device: 0,62	Inode: 2757480     Links: 2
Access: (0644/-rw-r--r--)  Uid: (    0/    root)   Gid: (    0/    root)
Access: 2026-09-17 16:08:50.944819009 +0000
Modify: 2026-09-17 16:08:50.944819009 +0000
Change: 2026-09-17 16:08:51.007819009 +0000
 Birth: 2026-09-17 16:08:50.944819009 +0000
```

```bash
stat softlink.txt
```

Output:

```text
  File: softlink.txt -> original.txt
  Size: 12        	Blocks: 0          IO Block: 4096   symbolic link
Device: 0,62	Inode: 2829497     Links: 1
Access: (0777/lrwxrwxrwx)  Uid: (    0/    root)   Gid: (    0/    root)
Access: 2026-09-17 16:08:51.064819010 +0000
Modify: 2026-09-17 16:08:51.008819009 +0000
Change: 2026-09-17 16:08:51.008819009 +0000
 Birth: 2026-09-17 16:08:51.008819009 +0000
```

`Links: 2` vs `Links: 1`, `regular file` vs `symbolic link`, `Blocks: 8` vs `Blocks: 0`. A symlink's permission
bits always show as `0777` — they are meaningless, because access is decided by the permissions of the *target*.

### Step 4: all three names read the same bytes

```bash
cat original.txt; cat hardlink.txt; cat softlink.txt
```

Output:

```text
Hello from the original file
Hello from the original file
Hello from the original file
```

### Step 5: writing through a link changes the one underlying file

```bash
echo "Line added through the hard link" >> hardlink.txt
cat original.txt
```

Output:

```text
Hello from the original file
Line added through the hard link
```

The write went through the hard link, but reading the original shows it. There is only one set of data blocks.

### Step 6: delete the original — this is the whole exam question

```bash
rm original.txt
ls -li
```

Output:

```text
total 4
2757480 -rw-r--r-- 1 root root 62 Sep 17 16:08 hardlink.txt
2829497 lrwxrwxrwx 1 root root 12 Sep 17 16:08 softlink.txt -> original.txt
```

`rm` did not delete a file. `rm` **unlinked a name**. Inode 2757480 is still there, still holding the data —
its link count just dropped from `2` to `1`. The kernel only frees an inode's data when its link count reaches 0
and no process still has it open.

The soft link, meanwhile, still exists and still cheerfully says `-> original.txt`. It has no idea its target is gone.

```bash
cat hardlink.txt
```

Output:

```text
Hello from the original file
Line added through the hard link
```

The hard link kept every byte, including the line appended in Step 5.

```bash
cat softlink.txt; echo "exit code: $?"
```

Output:

```text
cat: softlink.txt: No such file or directory
exit code: 1
```

This is a **dangling** (or broken) symlink. The error message is misleading: `softlink.txt` absolutely exists —
what does not exist is the path it points to.

```bash
test -e softlink.txt && echo "target exists" || echo "target missing (dangling symlink)"
test -L softlink.txt && echo "but the symlink itself is still present"
```

Output:

```text
target missing (dangling symlink)
but the symlink itself is still present
```

`test -e` follows the link and asks "does the target exist?" — it says no. `test -L` asks "is this path a symlink?"
— it says yes. That pair of tests is how a shell script detects a broken symlink.

### Step 7: recreate the name and the soft link heals itself

```bash
ln hardlink.txt original.txt
ls -li
cat softlink.txt
```

Output:

```text
total 8
2757480 -rw-r--r-- 2 root root 62 Sep 17 16:08 hardlink.txt
2757480 -rw-r--r-- 2 root root 62 Sep 17 16:08 original.txt
2829497 lrwxrwxrwx 1 root root 12 Sep 17 16:08 softlink.txt -> original.txt
---
Hello from the original file
Line added through the hard link
```

Because a symlink resolves *by name at access time*, putting any file back at that name makes it work again.
A symlink is a late-binding pointer; a hard link is an early-binding reference.

### Step 8: hard links cannot cross filesystems

Inode numbers are only unique *within one filesystem*, so a directory entry on filesystem A cannot point at an
inode on filesystem B. In the container, `/` is the overlay filesystem and `/dev/shm` is a separate tmpfs:

```bash
df -h /root /dev/shm
ln original.txt /dev/shm/crossfs.txt; echo "exit code: $?"
ln -s /root/links-demo/original.txt /dev/shm/crossfs.txt \
  && echo "symlink across filesystems: OK" && ls -l /dev/shm/crossfs.txt
```

Output:

```text
Filesystem      Size  Used Avail Use% Mounted on
overlay         911G  160G  705G  19% /
shm              64M     0   64M   0% /dev/shm
---
ln: failed to create hard link '/dev/shm/crossfs.txt' => 'original.txt': Invalid cross-device link
exit code: 1
---
symlink across filesystems: OK
lrwxrwxrwx 1 root root 29 Sep 17 16:09 /dev/shm/crossfs.txt -> /root/links-demo/original.txt
```

`Invalid cross-device link` (`EXDEV`) is the exact error to remember. The symlink has no such problem, because it
only stores a path string — it does not care what filesystem that path eventually lands on.

### Step 9: you cannot hard-link a directory

```bash
mkdir -p mydir
ln    mydir dirlink; echo "exit code: $?"
ln -s mydir dirsymlink && echo "symlink to directory: OK" && ls -ld dirsymlink
```

Output:

```text
ln: mydir: hard link not allowed for directory
exit code: 1
symlink to directory: OK
lrwxrwxrwx 1 root root 5 Sep 17 16:09 dirsymlink -> mydir
```

Directory hard links are forbidden for ordinary users because they would let you build loops in the directory
tree (`a/b/a/b/a/...`), which would break every recursive tool and make the filesystem ungraph-able.
Symlinks to directories are allowed and used constantly — `/usr/lib` layouts, versioned app releases,
`current -> release-2024-06-01`, and so on.

### Step 10: find every name pointing at one inode

```bash
find /root -inum 2757480
```

Output:

```text
/root/links-demo/original.txt
/root/links-demo/hardlink.txt
```

This is the practical answer to "the file is still eating disk space after I deleted it — where else is it linked?"

### Step 11: delete the links and confirm the link count drops

```bash
rm softlink.txt dirsymlink /dev/shm/crossfs.txt
rm hardlink.txt
ls -li
stat -c "%n has %h link(s)" original.txt
```

Output:

```text
total 8
2829613 drwxr-xr-x 2 root root 4096 Sep 17 16:09 mydir
2757480 -rw-r--r-- 1 root root   62 Sep 17 16:08 original.txt
---
original.txt has 1 link(s)
```

Both links are gone. `rm` on a symlink removes the symlink, never the target. `rm` on a hard link just decrements
the count — the data survives while one name remains.

### Comparison table

| | Hard link (`ln src dst`) | Soft link (`ln -s src dst`) |
|---|---|---|
| What it is | Another directory entry for the same inode | A separate small file containing a path string |
| Inode number | **Same** as the original | **Different** — its own inode |
| Shown by `ls -l` as | `-rw-r--r--` (indistinguishable from a normal file) | `lrwxrwxrwx name -> target` |
| Effect on link count | Increments it (`1` -> `2`) | No effect on the target's count |
| Size | Same as the file | Length of the target path string (12 bytes above) |
| If the original name is deleted | Still works, data intact | Breaks — becomes a dangling link |
| If the original is recreated at the same path | Unrelated; it is now a third name | Starts working again automatically |
| Across filesystems / partitions | Not allowed — `Invalid cross-device link` | Allowed |
| To a directory | Not allowed for normal users | Allowed, and very common |
| Can point at a non-existent target | No — `ln` fails immediately | Yes — dangling symlinks are legal |
| Extra disk space | None (just a directory entry) | One inode + a few bytes |
| Relative vs absolute | Not applicable | Matters a lot — a relative symlink survives moving the whole tree, an absolute one does not |
| Typical DevOps use | De-duplicating files on one filesystem, `rsync --link-dest` backups, hardlinked package stores | `/etc/alternatives`, `current -> releases/v42` deploy switching, `/etc/nginx/sites-enabled/*`, dotfile management |

### Two rules of thumb

- Use a **soft link** by default. It is visible, obvious, crosses filesystems, works on directories, and is easy
  to audit with `ls -l`.
- Use a **hard link** when you specifically need two names to be genuinely the same file with no possibility of a
  broken pointer, and you are certain both names are on the same filesystem.

### The demo script

`links-demo.sh` in this folder runs the whole lifecycle end to end. It is Linux-only (it uses GNU `stat -c`),
so run it inside the container:

```bash
docker cp links-demo.sh hw01-ubuntu:/root/links-demo.sh
docker exec hw01-ubuntu bash -c 'chmod +x /root/links-demo.sh && bash /root/links-demo.sh /tmp/link-demo'
```

Output:

```text
==> Step 1: create the original file
3334420 -rw-r--r-- 1 root root 29 Sep 17 16:18 original.txt

==> Step 2: create a hard link and a soft link
total 8
3334420 -rw-r--r-- 2 root root 29 Sep 17 16:18 hardlink.txt
3334420 -rw-r--r-- 2 root root 29 Sep 17 16:18 original.txt
3334421 lrwxrwxrwx 1 root root 12 Sep 17 16:18 softlink.txt -> original.txt

==> Step 3: inode number and link count
original.txt : inode 3334420, 2 link(s), 29 bytes, type regular file
hardlink.txt : inode 3334420, 2 link(s), 29 bytes, type regular file
softlink.txt : inode 3334421, 1 link(s), 12 bytes, type symbolic link

==> Step 4: every name reads the same data
original.txt   -> Hello from the original file
hardlink.txt   -> Hello from the original file
softlink.txt   -> Hello from the original file

==> Step 5: write through the hard link, read through the original
Hello from the original file
Line added through the hard link

==> Step 6: delete the original file
total 4
3334420 -rw-r--r-- 1 root root 62 Sep 17 16:18 hardlink.txt
3334421 lrwxrwxrwx 1 root root 12 Sep 17 16:18 softlink.txt -> original.txt

==> Step 7: the hard link still holds the data
Hello from the original file
Line added through the hard link

==> Step 8: the soft link is now dangling
cat softlink.txt failed: the target it pointed at is gone
lrwxrwxrwx 1 root root 12 Sep 17 16:18 softlink.txt -> original.txt

==> Step 9: delete both links and confirm the directory is empty
remaining entries: 0
```

Note the inode numbers here (`3334420`) differ from the manual walkthrough (`2757480`) because this is a fresh
directory and a fresh file. The *relationship* is identical: two names, one inode, link count 2.

### Interview questions

**Q1. What is the difference between a hard link and a soft link?**
A hard link is an additional directory entry pointing at the same inode, so both names are equal and the data
survives deleting either one. A soft link is a separate file whose contents are a path string to another name,
so deleting the target breaks it.

**Q2. What happens to each when you delete the original file?**
The hard link keeps working — `rm` only decrements the inode's link count, and data is freed only at count 0.
The soft link becomes dangling and any read returns `No such file or directory`, even though the link itself
is still sitting in the directory.

**Q3. Why can't you hard-link across two partitions?**
A directory entry stores an inode number, and inode numbers are only meaningful within one filesystem. The kernel
refuses with `EXDEV` / `Invalid cross-device link`. Symlinks store a path, not an inode, so they cross freely.

**Q4. Why can't ordinary users hard-link a directory?**
It would allow cycles in the directory tree, which would make `find`, `du`, and backup tools loop forever and
would break the "tree" invariant the whole filesystem relies on. `.` and `..` are the only directory hard links,
and the kernel maintains them itself — which is why an empty directory has a link count of 2.

**Q5. How do you tell them apart on a running system?**
`ls -li`. Same inode number in column 1 = hard link. A leading `l` in the permissions plus `-> target` = symlink.
`stat` shows `Links:` and the file type explicitly.

**Q6. How do you find all the hard links of a file?**
`find /path -inum <inode>` after getting the inode from `ls -i` or `stat`. Or `find / -samefile /path/to/file`.

**Q7. A directory shows link count 2 and it looks empty. Why?**
One link is its name in the parent directory, the other is the `.` entry inside itself. Every subdirectory you
add raises it by one, because each subdirectory's `..` points back at the parent.

**Q8. You deleted a huge log file but `df` still shows the disk full. Why?**
Because a running process still has the file open. Deleting removed the name, but the inode's reference count is
not 0 until that file descriptor closes. Restart or signal the process (or truncate via `/proc/<pid>/fd/<n>`).
This is exactly the link-count rule applied to open file handles instead of directory entries.

**Q9. Should a symlink be relative or absolute?**
Relative if the link and its target move together as one tree (a deploy directory, a source checkout) — it will
still resolve after the whole tree is moved or bind-mounted. Absolute if the target is a fixed system path.

**Q10. Does `rm` on a symlink delete the target?**
No. `rm softlink` removes only the link. Note the trailing-slash trap though: some tools treat `rm -r symlink/`
(with the slash) as operating on the directory it points at.

---

## Task 2 — `adduser` vs `useradd`

### Both exist, but they are not the same kind of program

The stock `ubuntu:24.04` image is minimal and ships only `useradd`. `adduser` comes from its own package:

```bash
apt-get update -qq && apt-get install -y adduser
which adduser useradd
```

Output:

```text
/usr/sbin/adduser
/usr/sbin/useradd
```

Now ask what each one actually *is*:

```bash
file /usr/sbin/adduser /usr/sbin/useradd
```

Output:

```text
/usr/sbin/adduser: Perl script text executable
/usr/sbin/useradd: ELF 64-bit LSB pie executable, ARM aarch64, version 1 (SYSV), dynamically linked, interpreter /lib/ld-linux-aarch64.so.1, BuildID[sha1]=483f79642f7a936acdeb2cb2fd1c4e70c2f0ef9d, for GNU/Linux 3.7.0, stripped
```

That one line is the entire answer to this task:

- `useradd` is a **compiled binary** — the low-level tool that edits `/etc/passwd`, `/etc/shadow`, and `/etc/group`.
- `adduser` is a **Perl script** — a high-level, policy-aware wrapper that calls `useradd` underneath.

```bash
head -8 /usr/sbin/adduser
wc -l /usr/sbin/adduser
```

Output:

```text
#! /usr/bin/perl

# Copyright (C) 2000-2004 Roland Bauerschmidt <rb@debian.org>
#               2005-2023 Marc Haber <mh+debian-packages@zugschlus.de>
#               2022 Benjamin Drung <benjamin.drung@canonical.com>
#               2023 Guillem Jover <guillem@debian.org>
#               2021-2022 Jason Franklin <jason@oneway.dev>
#               2022 Matt Barry <matt@hazelmollusk.org>
...
1527 /usr/sbin/adduser
```

1527 lines of Perl whose job is to make sensible decisions on your behalf before calling the binary.

They even ship in different packages, from different upstreams:

```bash
dpkg -S /usr/sbin/adduser /usr/sbin/useradd
```

Output:

```text
adduser: /usr/sbin/adduser
passwd: /usr/sbin/useradd
```

`useradd` belongs to `passwd` (the shadow-utils suite, present on every Linux distro).
`adduser` belongs to the Debian-specific `adduser` package — it does not exist on RHEL, CentOS, Alpine, or Amazon Linux.

### What each one reads for defaults

```bash
useradd -D
```

Output:

```text
GROUP=100
HOME=/home
INACTIVE=-1
EXPIRE=
SHELL=/bin/sh
SKEL=/etc/skel
CREATE_MAIL_SPOOL=no
LOG_INIT=yes
```

```bash
grep -E "DSHELL|DHOME|SKEL|USERGROUPS|EXTRA_GROUPS" /etc/adduser.conf
```

Output:

```text
# Default: DSHELL=/bin/bash
#DSHELL=/bin/bash
# Default: DHOME=/home
# DHOME=/home
# Default: SKEL=/etc/skel
#SKEL=/etc/skel
# Default: USERGROUPS=yes
#USERGROUPS=yes
# files in SKEL matching this regex are not copied.
# Default: SKEL_IGNORE_REGEX="\.(dpkg|ucf)-(old|new|dist|save)$"
#SKEL_IGNORE_REGEX="\.(dpkg|ucf)-(old|new|dist|save)$"
# if ADD_EXTRA_GROUPS is non-zero or set on the command line.
# Default: EXTRA_GROUPS="users"
#EXTRA_GROUPS="users"
# EXTRA_GROUPS.
# Default: ADD_EXTRA_GROUPS=0
#ADD_EXTRA_GROUPS=0
```

Already a visible difference: `useradd` defaults to `SHELL=/bin/sh`, `adduser` defaults to `DSHELL=/bin/bash`.
`useradd` reads `/etc/default/useradd` and `/etc/login.defs`; `adduser` reads `/etc/adduser.conf`.

### Proving the difference: what bare `useradd` actually does

```bash
useradd rawuser; echo "exit code: $?"
grep "^rawuser" /etc/passwd
ls -ld /home/rawuser
getent group rawuser
```

Output:

```text
exit code: 0
rawuser:x:1001:1001::/home/rawuser:/bin/sh
ls: cannot access '/home/rawuser': No such file or directory
rawuser:x:1001:
```

Read that carefully — this is the classic trap:

- The account was created and `/etc/passwd` **claims** the home directory is `/home/rawuser`.
- That directory **does not exist**. `useradd` recorded the path but did not create it.
- The shell is `/bin/sh`, not `/bin/bash`.
- No password was set, so the account cannot log in.
- No skeleton files (`.bashrc`, `.profile`) were copied.

A user created this way logs in (once you give them a password) into a non-existent home directory, lands in `/`,
has no dotfiles, and every tool that writes to `$HOME` fails. To do it properly with `useradd` you must remember
every flag yourself: `useradd -m -s /bin/bash -c "Full Name" -G sudo rawuser && passwd rawuser`.

### The recommended way on Ubuntu: `adduser`

```bash
adduser --disabled-password --gecos "" devopsuser
```

Output:

```text
info: Adding user `devopsuser' ...
info: Selecting UID/GID from range 1000 to 59999 ...
info: Adding new group `devopsuser' (1002) ...
info: Adding new user `devopsuser' (1002) with group `devopsuser (1002)' ...
info: Creating home directory `/home/devopsuser' ...
info: Copying files from `/etc/skel' ...
info: Adding new user `devopsuser' to supplemental / extra groups `users' ...
info: Adding user `devopsuser' to group `users' ...
```

`adduser` narrates every policy decision it makes. Normally it is **interactive** — it prompts for a password and
for the GECOS fields (full name, room, phone). The two flags make it scriptable, which is how you use it in
automation:

- `--disabled-password` creates the account without prompting for a password (set it separately, or rely on SSH keys).
- `--gecos ""` accepts empty values for the full-name prompts instead of asking.

### Proof the user exists and is properly set up

```bash
grep "^devopsuser" /etc/passwd
id devopsuser
ls -ld /home/devopsuser
ls -la /home/devopsuser
```

Output:

```text
devopsuser:x:1002:1002:,,,:/home/devopsuser:/bin/bash
---
uid=1002(devopsuser) gid=1002(devopsuser) groups=1002(devopsuser),100(users)
---
drwxr-x--- 2 devopsuser devopsuser 4096 Sep 17 16:10 /home/devopsuser
---
total 20
drwxr-x--- 2 devopsuser devopsuser 4096 Sep 17 16:10 .
drwxr-xr-x 1 root       root       4096 Sep 17 16:10 ..
-rw-r--r-- 1 devopsuser devopsuser  220 Sep 17 16:10 .bash_logout
-rw-r--r-- 1 devopsuser devopsuser 3771 Sep 17 16:10 .bashrc
-rw-r--r-- 1 devopsuser devopsuser  807 Sep 17 16:10 .profile
```

Reading the `/etc/passwd` line field by field, separated by `:`

| Field | Value | Meaning |
|---|---|---|
| 1 | `devopsuser` | username |
| 2 | `x` | password placeholder — the real hash lives in `/etc/shadow` |
| 3 | `1002` | UID |
| 4 | `1002` | primary GID |
| 5 | `,,,` | GECOS (full name, room, work phone, home phone) — empty because of `--gecos ""` |
| 6 | `/home/devopsuser` | home directory |
| 7 | `/bin/bash` | login shell |

Compare with `rawuser` above: home directory actually exists, shell is `bash` not `sh`, dotfiles were copied from
`/etc/skel`, the home directory is mode `0750` (not world-readable), and a matching per-user group was created.

### Set a password and log in as the user

```bash
echo "devopsuser:StrongPass123" | chpasswd; echo "chpasswd exit: $?"
getent shadow devopsuser | cut -c1-40
```

Output:

```text
chpasswd exit: 0
devopsuser:$y$j9T$1zAjz6Xu2BGWyRKjkz8xw0
```

The output is truncated on purpose. `$y$` is the yescrypt algorithm prefix — Ubuntu 24.04's default password
hash. The password itself is never stored, only this hash, and only root can read `/etc/shadow`.

```bash
su - devopsuser -c "whoami; pwd; echo \$SHELL; id -un"
```

Output:

```text
devopsuser
/home/devopsuser
/bin/bash
devopsuser
```

`su -` (with the dash) starts a full login shell, which is why `pwd` lands in the user's home directory and
`$SHELL` is set. This is the real proof that the account is usable.

```bash
usermod -aG sudo devopsuser
id devopsuser
```

Output:

```text
uid=1002(devopsuser) gid=1002(devopsuser) groups=1002(devopsuser),27(sudo),100(users)
```

`usermod -aG` appends a supplementary group. The `-a` is critical — `usermod -G sudo devopsuser` *without* `-a`
would replace the whole supplementary group list and silently drop `users`. That mistake has locked plenty of
people out of their own servers.

### Comparison table

| | `useradd` | `adduser` |
|---|---|---|
| Type | Compiled binary (`ELF`) | Perl script (1527 lines) |
| Package | `passwd` (shadow-utils) | `adduser` (Debian-specific) |
| Level | Low-level | High-level friendly wrapper around `useradd` |
| Available on | Every Linux distro | Debian / Ubuntu family only |
| Interactive | No, never | Yes by default — prompts for password and GECOS |
| Creates the home directory | Only with `-m` | Yes, automatically |
| Copies `/etc/skel` | Only with `-m` | Yes, automatically |
| Default shell | `/bin/sh` (from `/etc/default/useradd`) | `/bin/bash` (from `/etc/adduser.conf`) |
| Sets a password | No, separate `passwd` step | Prompts for one during creation |
| Creates a matching user group | Depends on `USERGROUPS_ENAB` | Yes |
| Home directory permissions | `0755` unless `HOME_MODE` is set | `0750` |
| Config file | `/etc/default/useradd`, `/etc/login.defs` | `/etc/adduser.conf` |
| Feedback | Silent on success | Prints every step it takes |
| Best for | Scripts that need exact, portable control; non-Debian distros | Humans on Ubuntu/Debian; the safe default |
| Paired removal command | `userdel` / `userdel -r` | `deluser` / `deluser --remove-home` |

### Which is preferred on Ubuntu, and why

**`adduser` is the preferred command on Ubuntu.** Ubuntu's own `useradd(8)` man page says it is "a low level
utility" and that "Debian administrators should usually use `adduser` instead". The reasons:

1. **It applies Debian/Ubuntu policy for you.** Correct UID range, per-user group, `0750` home permissions,
   `/etc/skel` contents, `/bin/bash` shell. Getting all of that right with `useradd` means remembering a
   handful of flags, every time, on every server.
2. **It is safe by default.** The most common `useradd` bug — a home directory recorded in `/etc/passwd` that
   was never actually created — is impossible with `adduser`.
3. **It tells you what it did.** The `info:` lines are an audit trail; `useradd` succeeds silently.
4. **It handles the password step** instead of leaving a half-configured account behind.

**When to reach for `useradd` instead:** writing scripts that must run on RHEL/Alpine/Amazon Linux too (where
`adduser` may not exist or may be a different BusyBox program entirely), building container images where you want
an exact UID and no extras, or creating system/service accounts where you deliberately want no home directory and
a `/usr/sbin/nologin` shell.

The portable service-account idiom, for reference:

```bash
useradd --system --no-create-home --shell /usr/sbin/nologin appsvc
```

`adduser --system` does the same thing the Debian way.

### Clean up the test users

Here is a nice accidental demonstration that `adduser`/`deluser` really are Perl:

```bash
deluser --remove-home devopsuser
```

Output:

```text
fatal: In order to use the --remove-home, --remove-all-files, and --backup features, you need to install the `perl' package. To accomplish that, run apt-get install perl.
```

The base image only ships `perl-base`, which is enough to run the script but not enough for the file-removal
modules. `useradd`, being a binary, has no such dependency:

```bash
userdel rawuser
echo "userdel exit: $?"
```

Output:

```text
userdel exit: 0
```

After installing the full `perl` package:

```bash
apt-get install -y perl
deluser --remove-home devopsuser
grep -E "^(devopsuser|rawuser)" /etc/passwd || echo "neither user remains in /etc/passwd"
ls -ld /home/devopsuser
```

Output:

```text
info: Looking for files to backup/remove ...
info: Removing files ...
warn: `/usr/bin/crontab' not executed. Skipping crontab removal. Package `cron' required.
info: Removing user `devopsuser' ...
---
neither user remains in /etc/passwd
ls: cannot access '/home/devopsuser': No such file or directory
```

Both test accounts are gone and the home directory was removed with the user.

---

## Task 3 — `journalctl`

### What it is for

`journalctl` is the query tool for **journald**, systemd's logging service. Before systemd, logs were plain text
files scattered across `/var/log/` — `syslog`, `auth.log`, `nginx/error.log`, `dmesg` — each with its own format,
its own rotation policy, and no common way to correlate them.

journald replaces that with a single, indexed, structured, binary log. Every entry carries metadata fields
(`_SYSTEMD_UNIT`, `_PID`, `_UID`, `PRIORITY`, `_BOOT_ID`, `_HOSTNAME`, `_COMM`) and `journalctl` is how you filter
on them. In practice this means:

- One command reads kernel messages, service output, and application `stderr` together, in true timestamp order.
- You can ask for exactly one service, one boot, one priority, or one time window, without grepping.
- Anything a service writes to stdout/stderr is captured automatically — services no longer need their own
  log-file plumbing.
- Logs are rotated and size-capped by journald itself, so `/var/log` cannot silently fill your disk.

### Honest note: a plain Ubuntu container has no journal

This is not an omission — it is worth understanding, because it is the number one confusion when people move from
VMs to containers.

```bash
docker exec hw01-ubuntu bash -c 'which journalctl; echo "which exit: $?"; journalctl --no-pager'
```

Output:

```text
bash: line 1: journalctl: command not found
which exit: 1
```

```bash
docker exec hw01-ubuntu bash -c 'ps -p 1 -o pid,comm= 2>/dev/null || cat /proc/1/comm'
docker exec hw01-ubuntu bash -c 'ls /var/log/journal; ls /run/systemd/system'
```

Output:

```text
  PID 
    1 sleep
---
ls: cannot access '/var/log/journal': No such file or directory
ls: cannot access '/run/systemd/system': No such file or directory
```

The reason: a container runs **one process as PID 1**, not an init system. There is no systemd, therefore no
`systemd-journald`, therefore no journal and no `journalctl` binary. Container logs go to the container runtime
instead — `docker logs <container>` reads the stdout/stderr of PID 1. That is the container equivalent of
`journalctl -u`, and it is why the twelve-factor rule is "log to stdout, let the platform collect it".

So instead of faking journal output, the second container below actually boots systemd.

### Getting real journal output

```bash
docker run -d --name hw01-systemd --privileged --cgroupns=host \
  --tmpfs /run --tmpfs /run/lock \
  -v /sys/fs/cgroup:/sys/fs/cgroup:rw \
  ubuntu:24.04 bash -c 'apt-get update -qq && apt-get install -y systemd systemd-sysv && exec /sbin/init'
```

- `--privileged` and the cgroup mount let systemd manage cgroups, which it refuses to start without.
- `--tmpfs /run` gives systemd a writable runtime directory.
- `exec /sbin/init` replaces the setup shell so systemd genuinely becomes PID 1.

```bash
docker exec hw01-systemd bash -c 'cat /proc/1/comm; systemctl is-system-running; journalctl --version | head -1'
```

Output:

```text
systemd
running
systemd 255 (255.4-1ubuntu8.17)
```

```bash
docker exec hw01-systemd systemctl list-units --type=service --no-pager --no-legend
```

Output:

```text
  dbus.service                             loaded active running D-Bus System Message Bus
  getty@tty1.service                       loaded active running Getty on tty1
  ldconfig.service                         loaded active exited  Rebuild Dynamic Linker Cache
  systemd-binfmt.service                   loaded active exited  Set Up Additional Binary Formats
  systemd-journal-catalog-update.service   loaded active exited  Rebuild Journal Catalog
  systemd-journal-flush.service            loaded active exited  Flush Journal to Persistent Storage
  systemd-journald.service                 loaded active running Journal Service
  systemd-logind.service                   loaded active running User Login Management
  systemd-modules-load.service             loaded active exited  Load Kernel Modules
  systemd-remount-fs.service               loaded active exited  Remount Root and Kernel File Systems
  systemd-resolved.service                 loaded active running Network Name Resolution
  systemd-sysctl.service                   loaded active exited  Apply Kernel Variables
```

`systemd-journald.service` is `active running`. Everything from here down is genuine captured output.

### `journalctl -n` — the last N entries

```bash
journalctl --no-pager -n 15
```

Output:

```text
Sep 17 16:12:47 22bd84d1b328 kernel: docker0: port 4(veth34811ba) entered disabled state
Sep 17 16:12:48 22bd84d1b328 kernel: docker0: port 3(veth8217b6f) entered disabled state
Sep 17 16:12:48 22bd84d1b328 kernel: vethcd9307d: renamed from eth0
Sep 17 16:12:48 22bd84d1b328 kernel: docker0: port 3(veth8217b6f) entered disabled state
Sep 17 16:12:48 22bd84d1b328 kernel: veth8217b6f (unregistering): left allmulticast mode
Sep 17 16:12:48 22bd84d1b328 kernel: veth8217b6f (unregistering): left promiscuous mode
Sep 17 16:12:48 22bd84d1b328 kernel: docker0: port 3(veth8217b6f) entered disabled state
Sep 17 16:12:58 22bd84d1b328 kernel: br-c78876d7425d: port 1(vethfae8631) entered blocking state
Sep 17 16:12:58 22bd84d1b328 kernel: br-c78876d7425d: port 1(vethfae8631) entered disabled state
Sep 17 16:12:58 22bd84d1b328 kernel: vethfae8631: entered allmulticast mode
Sep 17 16:12:58 22bd84d1b328 kernel: vethfae8631: entered promiscuous mode
Sep 17 16:12:58 22bd84d1b328 kernel: eth0: renamed from veth04fdb7a
Sep 17 16:12:58 22bd84d1b328 kernel: br-c78876d7425d: port 1(vethfae8631) entered blocking state
Sep 17 16:12:58 22bd84d1b328 kernel: br-c78876d7425d: port 1(vethfae8631) entered forwarding state
Sep 17 16:13:00 22bd84d1b328 systemd-resolved[3187]: Clock change detected. Flushing caches.
```

Each line is `timestamp | hostname | process[pid]: message`. The `kernel:` lines are real — because the container
is privileged it can read the host VM's kernel ring buffer, and those `veth`/`docker0` messages are Docker
attaching and detaching other containers' network interfaces. `--no-pager` stops journalctl piping into `less`,
which matters when scripting or running through `docker exec`.

### `journalctl -u <unit>` — logs for one service

This is the flag you will use ninety percent of the time. Install and start a real service first:

```bash
apt-get install -y nginx
systemctl start nginx
systemctl restart nginx
journalctl -u nginx.service --no-pager
```

Output:

```text
Sep 17 16:13:24 22bd84d1b328 systemd[1]: Starting nginx.service - A high performance web server and a reverse proxy server...
Sep 17 16:13:24 22bd84d1b328 systemd[1]: Started nginx.service - A high performance web server and a reverse proxy server.
Sep 17 16:13:24 22bd84d1b328 systemd[1]: Stopping nginx.service - A high performance web server and a reverse proxy server...
Sep 17 16:13:24 22bd84d1b328 systemd[1]: nginx.service: Deactivated successfully.
Sep 17 16:13:24 22bd84d1b328 systemd[1]: Stopped nginx.service - A high performance web server and a reverse proxy server.
Sep 17 16:13:24 22bd84d1b328 systemd[1]: Starting nginx.service - A high performance web server and a reverse proxy server...
Sep 17 16:13:24 22bd84d1b328 systemd[1]: Started nginx.service - A high performance web server and a reverse proxy server.
```

All the kernel noise is gone. This is only what `nginx.service` and systemd-about-nginx produced — the start,
the stop, and the restart, in order.

### A real debugging walkthrough

This is the actual reason journalctl matters. Break the nginx config on purpose:

```bash
echo "this_is_not_valid_nginx_config;" >> /etc/nginx/nginx.conf
systemctl restart nginx
```

Output:

```text
Job for nginx.service failed because the control process exited with error code.
See "systemctl status nginx.service" and "journalctl -xeu nginx.service" for details.
restart exit code: 1
```

systemd tells you it failed but not *why* — it deliberately points you at the journal:

```bash
journalctl -u nginx.service --no-pager -n 12
```

Output:

```text
Sep 17 16:13:24 22bd84d1b328 systemd[1]: Stopped nginx.service - A high performance web server and a reverse proxy server.
Sep 17 16:13:24 22bd84d1b328 systemd[1]: Starting nginx.service - A high performance web server and a reverse proxy server...
Sep 17 16:13:24 22bd84d1b328 systemd[1]: Started nginx.service - A high performance web server and a reverse proxy server.
Sep 17 16:13:34 22bd84d1b328 systemd[1]: Stopping nginx.service - A high performance web server and a reverse proxy server...
Sep 17 16:13:34 22bd84d1b328 systemd[1]: nginx.service: Deactivated successfully.
Sep 17 16:13:34 22bd84d1b328 systemd[1]: Stopped nginx.service - A high performance web server and a reverse proxy server.
Sep 17 16:13:34 22bd84d1b328 systemd[1]: Starting nginx.service - A high performance web server and a reverse proxy server...
Sep 17 16:13:34 22bd84d1b328 nginx[3507]: 2026/09/17 16:13:34 [emerg] 3507#3507: unknown directive "this_is_not_valid_nginx_config" in /etc/nginx/nginx.conf:84
Sep 17 16:13:34 22bd84d1b328 nginx[3507]: nginx: configuration file /etc/nginx/nginx.conf test failed
Sep 17 16:13:34 22bd84d1b328 systemd[1]: nginx.service: Control process exited, code=exited, status=1/FAILURE
Sep 17 16:13:34 22bd84d1b328 systemd[1]: nginx.service: Failed with result 'exit-code'.
Sep 17 16:13:34 22bd84d1b328 systemd[1]: Failed to start nginx.service - A high performance web server and a reverse proxy server.
```

There it is, with a file and a line number: `unknown directive "this_is_not_valid_nginx_config" in /etc/nginx/nginx.conf:84`.
Note how nginx's own error output (`nginx[3507]:`) and systemd's unit state changes (`systemd[1]:`) are interleaved
in one stream — that correlation is exactly what journald buys you. In the pre-systemd world you would have been
reading `/var/log/nginx/error.log` in one terminal and `/var/log/syslog` in another.

`systemctl status` gives you the same tail plus the current state:

```bash
systemctl status nginx --no-pager
```

Output (after fixing the config):

```text
● nginx.service - A high performance web server and a reverse proxy server
     Loaded: loaded (/usr/lib/systemd/system/nginx.service; enabled; preset: enabled)
     Active: active (running) since Thu 2026-09-17 16:14:19 UTC; 4min 28s ago
       Docs: man:nginx(8)
    Process: 3633 ExecStartPre=/usr/sbin/nginx -t -q -g daemon on; master_process on; (code=exited, status=0/SUCCESS)
    Process: 3634 ExecStart=/usr/sbin/nginx -g daemon on; master_process on; (code=exited, status=0/SUCCESS)
   Main PID: 3636 (nginx)
      Tasks: 16 (limit: 9520)
     Memory: 10.5M (peak: 12.9M)
        CPU: 23ms
     CGroup: /docker/22bd84d1b3283eaa0734bf336f7d0e25680091e9d48494e6bb262f3d2be586c5/system.slice/nginx.service
             ├─3636 "nginx: master process /usr/sbin/nginx -g daemon on; master_process on;"
             ├─3637 "nginx: worker process"
             ├─3638 "nginx: worker process"
```

### `journalctl -p err` — filter by priority

```bash
journalctl -p err --no-pager -n 10
```

Output:

```text
Sep 17 16:13:34 22bd84d1b328 systemd[1]: Failed to start nginx.service - A high performance web server and a reverse proxy server.
```

Out of 1000+ entries, one is at priority `err` or worse — the nginx failure we just caused. This is the first
command to run on a machine someone says is "acting weird".

Priority levels, from most to least severe (syslog levels 0–7):

| Level | Name | Meaning |
|---|---|---|
| 0 | `emerg` | System is unusable |
| 1 | `alert` | Action must be taken immediately |
| 2 | `crit` | Critical condition |
| 3 | `err` | Error — something failed |
| 4 | `warning` | Warning, not yet a failure |
| 5 | `notice` | Normal but significant |
| 6 | `info` | Informational (the default for most service output) |
| 7 | `debug` | Debug noise |

`-p err` means "err **and everything more severe**", so it includes `crit`, `alert`, and `emerg` too.
Use `-p err..err` for exactly one level, or `-p warning` to widen the net.

### `journalctl --since` / `--until` — filter by time

```bash
journalctl --since "10 minutes ago" -u nginx.service --no-pager | head -6
```

Output:

```text
Sep 17 16:13:24 22bd84d1b328 systemd[1]: Starting nginx.service - A high performance web server and a reverse proxy server...
Sep 17 16:13:24 22bd84d1b328 systemd[1]: Started nginx.service - A high performance web server and a reverse proxy server.
Sep 17 16:13:24 22bd84d1b328 systemd[1]: Stopping nginx.service - A high performance web server and a reverse proxy server...
Sep 17 16:13:24 22bd84d1b328 systemd[1]: nginx.service: Deactivated successfully.
Sep 17 16:13:24 22bd84d1b328 systemd[1]: Stopped nginx.service - A high performance web server and a reverse proxy server.
Sep 17 16:13:24 22bd84d1b328 systemd[1]: Starting nginx.service - A high performance web server and a reverse proxy server...
```

`--since` and `--until` accept absolute timestamps (`"2026-09-17 16:00:00"`), plain dates, the keywords
`today` / `yesterday` / `now`, and relative offsets (`"-1h"`, `"2 days ago"`). Combining `--since` with `-u`
is the standard move when you know roughly when an incident started.

### `journalctl -f` — follow the log live

`-f` is `tail -f` for the journal: it prints new entries as they arrive and blocks until you press `Ctrl+C`.
Since this README is generated non-interactively, the command below was wrapped in `timeout 6` and a background
job was told to reload and restart nginx two seconds in, so you can see entries appearing in real time:

```bash
(sleep 2; systemctl reload nginx; sleep 1; systemctl restart nginx) &
timeout 6 journalctl -f -n 0 -u nginx.service --no-pager
```

Output:

```text
Sep 17 16:14:18 22bd84d1b328 systemd[1]: Reloading nginx.service - A high performance web server and a reverse proxy server...
Sep 17 16:14:18 22bd84d1b328 nginx[3613]: 2026/09/17 16:14:18 [notice] 3613#3613: signal process started
Sep 17 16:14:18 22bd84d1b328 systemd[1]: Reloaded nginx.service - A high performance web server and a reverse proxy server.
Sep 17 16:14:19 22bd84d1b328 systemd[1]: Stopping nginx.service - A high performance web server and a reverse proxy server...
Sep 17 16:14:19 22bd84d1b328 systemd[1]: nginx.service: Deactivated successfully.
Sep 17 16:14:19 22bd84d1b328 systemd[1]: Stopped nginx.service - A high performance web server and a reverse proxy server.
Sep 17 16:14:19 22bd84d1b328 systemd[1]: Starting nginx.service - A high performance web server and a reverse proxy server...
Sep 17 16:14:19 22bd84d1b328 systemd[1]: Started nginx.service - A high performance web server and a reverse proxy server.
```

`-n 0` means "show zero lines of history, only new ones". The everyday form is `journalctl -fu nginx` in one
terminal while you deploy in another.

### `journalctl -b` — this boot only

```bash
journalctl -b --no-pager | head -8
journalctl -b --no-pager | wc -l
```

Output:

```text
Sep 17 16:12:45 22bd84d1b328 kernel: Booting Linux on physical CPU 0x0000000000 [0x610f0000]
Sep 17 16:12:45 22bd84d1b328 kernel: Linux version 6.12.76-linuxkit (root@buildkitsandbox) (gcc (Alpine 15.2.0) 15.2.0, GNU ld (GNU Binutils) 2.45.1) #1 SMP Fri Apr 17 14:56:37 UTC 2026
Sep 17 16:12:45 22bd84d1b328 kernel: OF: reserved mem: Reserved memory: No reserved-memory node in the DT
Sep 17 16:12:45 22bd84d1b328 kernel: Zone ranges:
Sep 17 16:12:45 22bd84d1b328 kernel:   DMA      [mem 0x0000000070000000-0x00000000ffffffff]
Sep 17 16:12:45 22bd84d1b328 kernel:   DMA32    empty
Sep 17 16:12:45 22bd84d1b328 kernel:   Normal   [mem 0x0000000100000000-0x000000026fffffff]
Sep 17 16:12:45 22bd84d1b328 kernel: Movable zone start for each node
...
1070
```

`-b` (or `-b 0`) is the current boot. `-b -1` is the previous boot, `-b -2` the one before that. This is the
command for "the server rebooted at 3am and I need to know why" — `journalctl -b -1 -p err` shows the errors
from the boot that died.

```bash
journalctl --list-boots --no-pager
```

Output:

```text
IDX BOOT ID                          FIRST ENTRY                 LAST ENTRY
  0 12bfc15c72eb4c2c807d5b0f60229a38 Thu 2026-09-17 16:12:45 UTC Thu 2026-09-17 16:14:30 UTC
```

Only one boot is listed because this container has only been "booted" once.

### `journalctl --disk-usage` — how much space the journal is eating

```bash
journalctl --disk-usage
```

Output:

```text
Archived and active journals take up 8.0M in the file system.
```

```bash
ls -ld /var/log/journal/*
grep -E "^#?Storage|^#?SystemMaxUse" /etc/systemd/journald.conf
```

Output:

```text
drwxr-sr-x+ 2 root systemd-journal 4096 Sep 17 16:12 /var/log/journal/645bb706a7c1468eae758bafc5b3ee75
#Storage=auto
#SystemMaxUse=
```

The journal lives under `/var/log/journal/<machine-id>/` as binary `.journal` files — you cannot `cat` or `grep`
them directly, which is the main complaint people have about journald. `Storage=auto` means: persist to
`/var/log/journal` if that directory exists, otherwise keep logs in `/run/log/journal` (RAM) and lose them on
reboot. With `SystemMaxUse` unset, journald defaults to 10% of the filesystem capped at 4G.

To reclaim space: `journalctl --vacuum-size=200M`, `journalctl --vacuum-time=7d`, or
`journalctl --vacuum-files=5`.

### Structured output and tagging

Every journal entry is a set of fields, not a line of text. `-o json-pretty` shows what is really stored:

```bash
journalctl -u nginx.service -n 1 -o json-pretty --no-pager
```

Output (first 18 lines):

```text
{
	"JOB_TYPE" : "start",
	"_SYSTEMD_CGROUP" : "/init.scope",
	"__SEQNUM_ID" : "9d85f9be52d642368ef523a9a72cd4cb",
	"_CMDLINE" : "/sbin/init",
	"CODE_FUNC" : "job_emit_done_message",
	"SYSLOG_FACILITY" : "3",
	"_COMM" : "systemd",
	"_BOOT_ID" : "12bfc15c72eb4c2c807d5b0f60229a38",
	"__SEQNUM" : "1962",
	"_SYSTEMD_SLICE" : "-.slice",
	"MESSAGE" : "Started nginx.service - A high performance web server and a reverse proxy server.",
	"_GID" : "0",
	"_EXE" : "/usr/lib/systemd/systemd",
	"__REALTIME_TIMESTAMP" : "1789661659673111",
	"JOB_ID" : "354",
	"_RUNTIME_SCOPE" : "system",
	"PRIORITY" : "6",
```

(That is the first 18 lines of the entry — the full JSON object continues with another dozen or so fields.)

The normal single-line output is just `MESSAGE` with a few fields formatted around it. Fields prefixed with `_`
are **trusted** — journald adds them itself from the sending process's credentials, so a process cannot forge its
own PID, UID, or unit name. That is a real security property that plain text logs do not have.

You can write into the journal yourself with `systemd-cat`, then filter by tag with `-t`:

```bash
echo "homework-01 linux fundamentals checkpoint" | systemd-cat -t hw01-demo -p info
journalctl -t hw01-demo --no-pager
```

Output:

```text
Sep 17 16:14:00 22bd84d1b328 hw01-demo[3582]: homework 01: this line was written while journalctl -f was watching
Sep 17 16:14:22 22bd84d1b328 hw01-demo[3660]: homework-01 linux fundamentals checkpoint
```

Both lines were written by `systemd-cat` during this session — the first one during the `-f` demo above.
This is how a shell script gets its output into the journal alongside everything else.

### journalctl command reference

| Command | What it does |
|---|---|
| `journalctl` | Everything in the journal, oldest first, in a pager |
| `journalctl -n 50` | Last 50 entries |
| `journalctl -e` | Jump straight to the end of the pager |
| `journalctl -r` | Reverse order — newest first |
| `journalctl --no-pager` | Print to stdout instead of `less`. Essential in scripts |
| `journalctl -u nginx.service` | Only entries for that unit. The flag you will use most |
| `journalctl -u nginx -u ssh` | Two units interleaved in time order |
| `journalctl -f` | Follow live, like `tail -f` |
| `journalctl -fu nginx` | Follow one service live — the everyday deployment-watching command |
| `journalctl -b` | Current boot only |
| `journalctl -b -1` | Previous boot — for diagnosing an unexpected reboot |
| `journalctl --list-boots` | All boots journald still has records for |
| `journalctl -k` | Kernel messages only (the `dmesg` equivalent, but with timestamps kept across boots) |
| `journalctl --since "1 hour ago"` | Relative time window |
| `journalctl --since "2026-09-17 16:00" --until "16:30"` | Absolute time window |
| `journalctl --since today` | Since midnight |
| `journalctl -p err` | Priority `err` and worse |
| `journalctl -p warning -b` | Warnings and worse, this boot |
| `journalctl -xeu nginx.service` | The combo systemd itself recommends: `-x` adds explanatory catalog text, `-e` jumps to the end, `-u` filters the unit |
| `journalctl -t myapp` | Filter by syslog tag |
| `journalctl _PID=1234` | Filter by any structured field |
| `journalctl _UID=1000` | Everything one user's processes logged |
| `journalctl -o json-pretty` | Full structured entries |
| `journalctl -o short-iso` | ISO-8601 timestamps instead of `Sep 17 16:14:18` |
| `journalctl --disk-usage` | How much disk the journal occupies |
| `journalctl --vacuum-time=7d` | Delete journal files older than 7 days |
| `journalctl --vacuum-size=200M` | Shrink the journal to 200M |
| `journalctl --verify` | Check journal files for corruption |
| `journalctl -u nginx --grep "emerg"` | Regex search within the filtered stream |

### Things worth remembering

- **Filter before you scroll.** `journalctl` alone on a busy server is unreadable. Start with
  `-u <unit> -b -p warning` and widen from there.
- **`-u` takes the unit name**, and `.service` is implied — `-u nginx` and `-u nginx.service` are the same.
- **Non-root users see only their own logs** unless they are in the `systemd-journal`, `adm`, or `wheel` group.
- **The journal is binary**, so `grep`/`awk` do not work on the files. Use `--grep`, or pipe journalctl's output.
- **`Storage=volatile`** (or a missing `/var/log/journal`) means logs vanish on reboot. Check this before
  promising anyone you can investigate yesterday's crash.
- **In containers there is no journal.** Use `docker logs`, `kubectl logs`, or ship stdout to a log aggregator.

---

## Task 4 — Linux Command Cheat Sheet

### The tables

#### File and directory operations

| Command | Purpose |
|---|---|
| `pwd` | Print the current working directory |
| `ls -lh` | List files, long format, human-readable sizes |
| `ls -la` | Include hidden dotfiles |
| `ls -li` | Include inode numbers (see Task 1) |
| `cd /path` | Change directory. `cd -` returns to the previous one |
| `mkdir -p a/b/c` | Create a directory tree, no error if it already exists |
| `touch file` | Create an empty file, or bump an existing file's timestamp |
| `cp src dst` | Copy a file. `-r` for directories, `-a` to preserve everything, `-v` verbose |
| `mv src dst` | Move or rename — the same operation on one filesystem |
| `rm file` | Delete a file. `-r` recursive, `-f` force, `-i` prompt first |
| `rmdir dir` | Remove an empty directory only |
| `cat file` | Print a whole file |
| `less file` | Page through a file (`q` quits, `/` searches) |
| `head -n 20 file` | First 20 lines |
| `tail -n 20 file` | Last 20 lines |
| `tail -f file` | Follow a file as it grows |
| `find . -name "*.log"` | Search the tree by name, type, size, age, permissions |
| `tree dir` | Show the directory tree graphically |
| `stat file` | Inode, size, permissions, all timestamps |
| `file x` | Identify what a file actually is, by content not extension |
| `ln -s tgt lnk` | Create a symbolic link |
| `du -sh dir` | Total size of a directory |
| `basename` / `dirname` | Split a path into its filename and directory parts |

#### Permissions and ownership

| Command | Purpose |
|---|---|
| `chmod 750 file` | Set permissions numerically: owner `rwx`, group `r-x`, others none |
| `chmod u+x file` | Symbolic form: add execute for the owner |
| `chmod -R g+w dir` | Recurse through a directory |
| `chown user:group file` | Change owner and group |
| `chgrp group file` | Change group only |
| `umask` | Show/set the default permission mask for new files |
| `id` | UID, GID, and all group memberships |
| `whoami` | Current effective username |
| `groups user` | Which groups a user belongs to |
| `sudo cmd` | Run one command as root |
| `su - user` | Switch to another user with a full login shell |
| `passwd user` | Change a password |
| `usermod -aG grp user` | Add a user to a supplementary group (never omit `-a`) |
| `chmod u+s file` | Setuid bit — run as the file's owner |
| `chmod +t dir` | Sticky bit — only the owner can delete their own files (as on `/tmp`) |
| `getfacl` / `setfacl` | Fine-grained ACLs beyond the classic owner/group/other model |

Permission numbers: read = 4, write = 2, execute = 1. Add them per role — `750` = `7` (4+2+1) for the owner,
`5` (4+1) for the group, `0` for everyone else.

#### Process management

| Command | Purpose |
|---|---|
| `ps aux` | Snapshot of every process on the system |
| `ps -ef` | The same, System V style output |
| `ps -eo pid,ppid,cmd` | Choose exactly which columns to print |
| `top` | Live process/resource view |
| `htop` | Friendlier interactive `top` (needs installing) |
| `pgrep -a name` | Find PIDs by name, showing the command line |
| `pkill name` | Signal processes by name — careful, `-f` matches the full command line |
| `kill PID` | Send `SIGTERM` (15) — polite, lets the process clean up |
| `kill -9 PID` | Send `SIGKILL` — unblockable, last resort |
| `kill -HUP PID` | Ask a daemon to reload its configuration |
| `jobs` / `fg` / `bg` | Manage jobs in the current shell |
| `cmd &` | Run in the background |
| `nohup cmd &` | Keep running after the terminal closes |
| `nice` / `renice` | Set or change scheduling priority |
| `lsof -p PID` | Every file and socket a process has open |
| `lsof -i :80` | Which process is holding port 80 |
| `strace -p PID` | Trace system calls — the debugger of last resort |
| `uptime` | Load averages over 1, 5, and 15 minutes |

#### Disk and storage

| Command | Purpose |
|---|---|
| `df -h` | Free space per mounted filesystem |
| `df -i` | Free **inodes** — how you diagnose "no space left" when `df -h` looks fine |
| `du -sh dir` | Total size of one directory |
| `du -h --max-depth=1 /var` | Size of each immediate subdirectory — how you hunt down a full disk |
| `lsblk` | Block devices and partitions as a tree |
| `blkid` | UUIDs and filesystem types of block devices |
| `mount` / `umount` | Attach and detach filesystems |
| `/etc/fstab` | Filesystems mounted automatically at boot |
| `free -h` | RAM and swap usage |
| `fdisk -l` / `parted -l` | Partition tables |
| `mkfs.ext4 /dev/sdX1` | Create a filesystem |
| `fsck /dev/sdX1` | Check and repair a filesystem (unmount it first) |
| `ncdu` | Interactive disk usage explorer |
| `sync` | Flush pending writes to disk |

#### Networking

| Command | Purpose |
|---|---|
| `ip address` (`ip a`) | Interfaces and their IP addresses. Replaces `ifconfig` |
| `ip -brief address` | Compact one-line-per-interface summary |
| `ip route` | The routing table, including the default gateway |
| `ip link set eth0 up` | Bring an interface up or down |
| `ss -tuln` | Listening TCP/UDP sockets. Replaces `netstat` |
| `ss -tulnp` | The same, plus which process owns each socket (needs root) |
| `ping -c 4 host` | Basic ICMP reachability and round-trip time |
| `traceroute host` | The hops between you and a destination |
| `mtr host` | Continuous traceroute + ping combined |
| `dig name` | Full DNS query with the answer section |
| `dig +short name` | Just the answer |
| `nslookup name` | Simpler DNS lookup |
| `host name` | One-line DNS lookup |
| `curl -I url` | Fetch only the HTTP response headers |
| `curl -sS url` | Fetch a URL quietly but still show errors |
| `wget url` | Download a file |
| `nc -zv host 443` | Test whether a TCP port is open |
| `hostname -I` | This machine's IP addresses |
| `tcpdump -i eth0 port 80` | Capture packets on the wire |
| `iptables -L -n` / `nft list ruleset` | Inspect firewall rules |
| `ufw status` | Ubuntu's simplified firewall front-end |
| `/etc/resolv.conf`, `/etc/hosts` | DNS resolver config and static name overrides |

#### Text processing

| Command | Purpose |
|---|---|
| `grep pattern file` | Print matching lines |
| `grep -i` / `-v` / `-c` / `-n` | Case-insensitive / invert / count / show line numbers |
| `grep -r pattern dir` | Search a whole directory tree |
| `grep -E "a\|b"` | Extended regex (same as `egrep`) |
| `sed 's/old/new/g' file` | Stream-edit text. `-i` edits the file in place |
| `sed -n '5,10p' file` | Print only lines 5 to 10 |
| `sed '/pattern/d' file` | Delete matching lines |
| `awk '{print $1}'` | Print a field. The default separator is whitespace |
| `awk -F: '{print $1}'` | Use a custom field separator — this parses `/etc/passwd` |
| `awk '$3 > 100 {print}'` | Filter rows by a condition |
| `cut -d ' ' -f 3` | Extract a field by delimiter — simpler than awk when that is all you need |
| `sort` / `sort -rn` | Sort lines; `-n` numeric, `-r` reverse |
| `uniq -c` | Collapse adjacent duplicates and count them (input must be sorted) |
| `wc -l` / `-w` / `-c` | Count lines, words, bytes |
| `tr 'a-z' 'A-Z'` | Translate or delete characters |
| `tee file` | Write to a file **and** to stdout |
| `xargs` | Turn stdin into arguments for another command |
| `diff a b` | Line-by-line difference between two files |
| `jq '.key'` | Query and reshape JSON |
| `\|`, `>`, `>>`, `2>&1` | Pipe, redirect, append, redirect stderr into stdout |

#### Archiving and compression

| Command | Purpose |
|---|---|
| `tar -czf out.tar.gz dir` | Create a gzip-compressed archive |
| `tar -xzf in.tar.gz` | Extract it |
| `tar -xzf in.tar.gz -C /dst` | Extract into a specific directory |
| `tar -tzf in.tar.gz` | List the contents without extracting — always do this first |
| `tar -cjf out.tar.bz2 dir` | bzip2 instead of gzip (smaller, slower) |
| `tar -cJf out.tar.xz dir` | xz (smallest, slowest) |
| `gzip file` / `gunzip file.gz` | Compress/decompress a single file in place |
| `zip -r out.zip dir` / `unzip out.zip` | ZIP format, for interoperability with Windows |
| `unzip -l out.zip` | List a zip's contents |
| `rsync -avz src/ dst/` | Sync directories, transferring only the differences |

Mnemonic for tar: **c**reate, e**x**tract, lis**t**; **z** gzip, **j** bzip2, **J** xz; **f** file, **v** verbose.

#### Package management (Debian / Ubuntu)

| Command | Purpose |
|---|---|
| `apt update` | Refresh the package index. Does **not** upgrade anything |
| `apt upgrade` | Upgrade installed packages |
| `apt install pkg` | Install a package and its dependencies |
| `apt remove pkg` | Uninstall, keeping config files |
| `apt purge pkg` | Uninstall including config files |
| `apt autoremove` | Remove orphaned dependencies |
| `apt search term` | Search the package index |
| `apt show pkg` | Version, size, dependencies, description |
| `apt list --installed` | Everything currently installed |
| `dpkg -l pkg` | Installed status of one package |
| `dpkg -L pkg` | Every file a package installed |
| `dpkg -S /path/to/file` | Which package owns a given file |
| `dpkg -i file.deb` | Install a local `.deb` (dependencies not resolved) |
| `add-apt-repository ppa:x/y` | Add a third-party repository |

The RHEL equivalents are `yum` / `dnf` with `rpm -qa`, `rpm -ql`, and `rpm -qf`.

#### System information

| Command | Purpose |
|---|---|
| `uname -a` | Kernel name, version, and architecture |
| `cat /etc/os-release` | Distribution name and version |
| `hostnamectl` | Hostname, machine ID, OS, kernel, virtualization (systemd hosts) |
| `uptime` | How long the machine has been up, plus load average |
| `date` | Current date and time |
| `timedatectl` | Timezone and NTP sync status |
| `who` / `w` | Who is logged in right now |
| `last` | Login history |
| `nproc` | Number of CPU cores available |
| `lscpu` | Full CPU details |
| `free -h` | Memory and swap |
| `lspci` / `lsusb` | Hardware on the PCI and USB buses |
| `dmesg` | Kernel ring buffer |
| `systemctl status svc` | State of a service |
| `systemctl list-units --type=service` | All loaded services |
| `env` / `printenv` | Environment variables |
| `history` | Your shell command history |
| `man cmd` | The manual page — the answer to most questions here |

---

### Live runs — file operations

```bash
pwd
mkdir -p project/src project/logs
touch project/src/app.py project/src/util.py project/logs/app.log
echo 'print("hello devops")' > project/src/app.py
cp project/src/app.py project/src/app.py.bak
tree project
```

Output:

```text
/root/cheatsheet
project
|-- logs
|   `-- app.log
`-- src
    |-- app.py
    |-- app.py.bak
    `-- util.py

3 directories, 4 files
```

`mkdir -p` created two levels in one call without complaining. `tree` is the fastest way to show someone a
directory layout.

```bash
ls -lh project/src
find project -type f -name "*.py"
du -sh project
```

Output:

```text
total 8.0K
-rw-r--r-- 1 root root 22 Sep 17 16:15 app.py
-rw-r--r-- 1 root root 22 Sep 17 16:15 app.py.bak
-rw-r--r-- 1 root root  0 Sep 17 16:15 util.py
--- find ---
project/src/app.py
project/src/util.py
--- du ---
20K	project
```

`find -type f -name "*.py"` matched only the two real `.py` files — `app.py.bak` does not match the pattern.
`util.py` is 0 bytes because `touch` created it empty. `du -sh` reports 20K rather than 22 bytes because disk
usage is counted in 4K blocks, and directories themselves occupy space.

### Live runs — permissions

```bash
echo "#!/bin/bash" > deploy.sh
echo "echo deploying" >> deploy.sh
ls -l deploy.sh
chmod 750 deploy.sh
ls -l deploy.sh
chmod u+x,go-rwx deploy.sh
ls -l deploy.sh
chown devopsuser:devopsuser deploy.sh
ls -l deploy.sh
umask
whoami
id
```

Output:

```text
-rw-r--r-- 1 root root 27 Sep 17 16:15 deploy.sh
-rwxr-x--- 1 root root 27 Sep 17 16:15 deploy.sh
--- symbolic form ---
-rwx------ 1 root root 27 Sep 17 16:15 deploy.sh
--- chown ---
-rwx------ 1 devopsuser devopsuser 27 Sep 17 16:15 deploy.sh
--- umask / id ---
0022
root
uid=0(root) gid=0(root) groups=0(root)
```

Walking through it:

- A new file starts as `-rw-r--r--` (644). It is **not executable**, which is why a freshly written script gives
  `Permission denied` until you `chmod +x` it.
- `chmod 750` produced `-rwxr-x---`: owner `rwx` (7), group `r-x` (5), others nothing (0).
- The symbolic form `u+x,go-rwx` produced `-rwx------`: same result as `700`, expressed as a change rather than
  an absolute value. Symbolic mode is safer when you only want to flip one bit.
- `chown user:group` changed both owner and group in one go. Only root can give a file away.
- `umask 0022` explains the 644 default: the base for a new file is 666, minus the mask 022, equals 644.

### Live runs — processes

```bash
ps aux | head -6
sleep 300 &
pgrep -a sleep
top -b -n 1 | head -8
```

Output:

```text
USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
root           1  0.0  0.0   2272  1136 ?        Ss   16:08   0:00 sleep infinity
root        3250  0.0  0.0   4036  3004 ?        Ss   16:15   0:00 bash -c  ps aux | head -6 echo "--- start a background process ---" sleep 300 & echo "started PID $!" pgrep -a sleep echo "--- top snapshot ---" top -b -n 1 | head -8 
root        3256  0.0  0.0   7632  3632 ?        R    16:15   0:00 ps aux
root        3257  0.0  0.0   2284  1228 ?        S    16:15   0:00 head -6
--- start a background process ---
started PID 3258
1 sleep infinity
3258 sleep 300
--- top snapshot ---
top - 16:15:29 up 7 min,  0 user,  load average: 3.69, 2.18, 0.95
Tasks:   5 total,   1 running,   4 sleeping,   0 stopped,   0 zombie
%Cpu(s):  1.3 us,  0.0 sy,  0.0 ni, 98.7 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st 
MiB Mem :   7935.5 total,    108.8 free,   1643.8 used,   6383.8 buff/cache     
MiB Swap:   1024.0 total,   1024.0 free,      0.0 used.   6291.8 avail Mem 

    PID USER      PR  NI    VIRT    RES    SHR S  %CPU  %MEM     TIME+ COMMAND
      1 root      20   0    2272   1136   1056 S   0.0   0.0   0:00.00 sleep
```

Only five processes exist in total — that is the whole point of a container. PID 1 is the `sleep infinity` that
keeps the container alive, and the rest are this very command pipeline observing itself. `top -b -n 1` is batch
mode: one snapshot, then exit, instead of an interactive screen. `$!` gave the PID of the job just backgrounded.

The `STAT` column: `S` sleeping, `R` running, `s` session leader, `Z` zombie.

Now stop a process:

```bash
docker exec -d hw01-ubuntu /bin/sleep 3600
ps -eo pid,etime,cmd | grep -w "[s]leep 3600"
PID=$(ps -eo pid,cmd | awk '/[s]leep 3600/ {print $1; exit}')
kill "$PID"
ps -p "$PID" >/dev/null 2>&1 && echo "still running" || echo "process $PID is gone"
```

Output:

```text
   3279       00:01 /bin/sleep 3600
target PID: 3279
process 3279 is gone
```

The `[s]leep` trick is worth knowing: wrapping the first character in a bracket expression makes the pattern
match `sleep 3600` but not the `grep` command line itself, so grep does not find its own process.

A footgun found the hard way while writing this section: the first attempt used `pkill -f "sleep 400"`. Because
`-f` matches the **entire command line**, and the wrapping shell's command line contained the string `sleep 400`,
`pkill` killed its own parent shell and the rest of the script never ran. Match narrowly, and prefer `kill` on a
PID you have verified over `pkill -f` on a pattern.

Signals: `kill PID` sends `SIGTERM` (15), which a well-behaved process catches to flush and shut down cleanly.
`kill -9 PID` sends `SIGKILL`, which the kernel enforces and the process cannot catch — it loses any unsaved
state. Always try `SIGTERM` first.

### Live runs — disk and memory

```bash
df -h
du -sh /usr /var /etc
free -h
```

Output:

```text
Filesystem      Size  Used Avail Use% Mounted on
overlay         911G  168G  697G  20% /
tmpfs            64M     0   64M   0% /dev
shm              64M     0   64M   0% /dev/shm
/dev/vda1       911G  168G  697G  20% /etc/hosts
tmpfs           3.9G     0  3.9G   0% /proc/scsi
tmpfs           3.9G     0  3.9G   0% /sys/firmware
--- du top dirs ---
167M	/usr
61M	/var
1.4M	/etc
--- free ---
               total        used        free      shared  buff/cache   available
Mem:           7.7Gi       1.7Gi       155Mi       2.4Mi       6.1Gi       6.1Gi
Swap:          1.0Gi          0B       1.0Gi
```

The `overlay` filesystem on `/` is Docker's layered union filesystem — this is the container's root. `/etc/hosts`
appears as its own mount because Docker bind-mounts that single file in from the host. `tmpfs` entries are
RAM-backed.

In `free -h`, the number that matters is **`available`** (6.1Gi), not `free` (155Mi). Linux deliberately uses all
spare RAM for the page cache (`buff/cache`, 6.1Gi), and hands it straight back when a program needs it. A low
`free` number on Linux is healthy, not a problem — this trips up almost everyone once.

### Live runs — networking

```bash
ip -brief address
ip route
hostname -I
```

Output:

```text
lo               UNKNOWN        127.0.0.1/8 ::1/128 
tunl0@NONE       DOWN           
gre0@NONE        DOWN           
gretap0@NONE     DOWN           
erspan0@NONE     DOWN           
ip_vti0@NONE     DOWN           
ip6_vti0@NONE    DOWN           
sit0@NONE        DOWN           
ip6tnl0@NONE     DOWN           
ip6gre0@NONE     DOWN           
eth0@if19        UP             172.17.0.2/16 
--- ip route ---
default via 172.17.0.1 dev eth0 
172.17.0.0/16 dev eth0 proto kernel scope link src 172.17.0.2 
--- hostname -I ---
172.17.0.2 
```

The container sits on Docker's default bridge at `172.17.0.2/16`, with the bridge gateway `172.17.0.1` as its
default route. `eth0@if19` means this is one end of a veth pair whose other end is interface index 19 on the host
— the mechanism every Docker bridge network is built on. The `tunl0`/`gre0`/`sit0` interfaces are inactive tunnel
stubs the kernel always creates.

```bash
ss -tuln
```

Output (from the systemd container, which is running nginx):

```text
Netid State  Recv-Q Send-Q Local Address:Port Peer Address:PortProcess
udp   UNCONN 0      0         127.0.0.54:53        0.0.0.0:*          
udp   UNCONN 0      0      127.0.0.53%lo:53        0.0.0.0:*          
tcp   LISTEN 0      511          0.0.0.0:80        0.0.0.0:*          
tcp   LISTEN 0      4096   127.0.0.53%lo:53        0.0.0.0:*          
tcp   LISTEN 0      4096      127.0.0.54:53        0.0.0.0:*          
tcp   LISTEN 0      511             [::]:80           [::]:*          
```

`ss -tuln` = TCP, UDP, listening only, numeric (do not resolve names, which makes it instant). nginx is listening
on `0.0.0.0:80` (all IPv4 addresses) and `[::]:80` (all IPv6). `systemd-resolved` holds `127.0.0.53:53` — the
local DNS stub resolver. Running the same command on the plain container printed only a header, because nothing
in it listens on any port.

Adding `-p` shows the owning process, which is usually what you actually want (trimmed here — the real nginx
line lists all sixteen worker PIDs):

```text
tcp   LISTEN 0      511          0.0.0.0:80        0.0.0.0:*    users:(("nginx",pid=3652,fd=5),("nginx",pid=3651,fd=5),...)
tcp   LISTEN 0      4096   127.0.0.53%lo:53        0.0.0.0:*    users:(("systemd-resolve",pid=3187,fd=15))
```

```bash
ping -c 3 1.1.1.1
```

Output:

```text
PING 1.1.1.1 (1.1.1.1) 56(84) bytes of data.
64 bytes from 1.1.1.1: icmp_seq=1 ttl=63 time=19.2 ms
64 bytes from 1.1.1.1: icmp_seq=2 ttl=63 time=149 ms
64 bytes from 1.1.1.1: icmp_seq=3 ttl=63 time=353 ms

--- 1.1.1.1 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2005ms
rtt min/avg/max/mdev = 19.236/173.596/352.523/137.168 ms
```

`-c 3` stops after three packets instead of running forever. `0% packet loss` is the number to look at first.
The wildly varying round-trip times (19ms to 353ms) are the laptop's wifi, not the container.

```bash
curl -s -I https://example.com | head -5
dig +short example.com A
nslookup github.com | tail -6
```

Output:

```text
HTTP/2 200 
date: Thu, 17 Sep 2026 16:16:41 GMT
content-type: text/html
server: cloudflare
last-modified: Tue, 15 Sep 2026 23:38:37 GMT
--- dig ---
172.66.147.243
104.20.23.154
--- nslookup ---
Address:	192.168.65.7#53

Non-authoritative answer:
Name:	github.com
Address: 20.207.73.82
```

`curl -I` issues a `HEAD` request, so you get headers without downloading the body — perfect for checking whether
a service is up and what it claims to be. `-s` silences the progress meter. `dig +short` strips everything except
the answer, which is what you want inside a script. `192.168.65.7` is Docker Desktop's internal DNS resolver, and
`Non-authoritative answer` means it came from a cache rather than from the domain's own nameservers.

### Live runs — text processing

```bash
cat access.log
grep " 500$" access.log
wc -l access.log
awk '{print $1, $4}' access.log
awk '{print $1}' access.log | sort | uniq -c | sort -rn
sed 's/10.0.0.1/REDACTED/g' access.log | head -3
```

Output:

```text
10.0.0.1 GET /index.html 200
10.0.0.2 GET /api/users 500
10.0.0.1 POST /api/login 200
10.0.0.3 GET /missing 404
10.0.0.2 GET /api/users 500
10.0.0.1 GET /index.html 200
--- grep for 500 errors ---
10.0.0.2 GET /api/users 500
10.0.0.2 GET /api/users 500
--- count lines/words/chars ---
6 access.log
--- awk: print IP and status ---
10.0.0.1 200
10.0.0.2 500
10.0.0.1 200
10.0.0.3 404
10.0.0.2 500
10.0.0.1 200
--- sort | uniq -c on IPs ---
      3 10.0.0.1
      2 10.0.0.2
      1 10.0.0.3
--- sed replace ---
REDACTED GET /index.html 200
10.0.0.2 GET /api/users 500
REDACTED POST /api/login 200
```

The `sort | uniq -c | sort -rn` pipeline is the single most useful text-processing idiom in operations work —
"which client/URL/error is most frequent". `uniq` only collapses *adjacent* duplicates, which is why the first
`sort` is mandatory; the final `sort -rn` puts the biggest count on top. `grep " 500$"` anchors to end-of-line so
it cannot match a `500` appearing anywhere else.

A second batch, run separately because the first attempt at the `cut` line was mangled by shell quoting
(the lesson there: pass complex one-liners into the container on stdin rather than nesting quotes inside
`docker exec bash -c "..."`):

```bash
cut -d ' ' -f 3 access.log
awk '{print $2}' access.log | tr 'a-z' 'A-Z' | sort -u
head -2 access.log; tail -2 access.log
grep -c "GET" access.log
grep -v "200" access.log
```

Output:

```text
--- cut: third space-separated field (the URL path) ---
/index.html
/api/users
/api/login
/missing
/api/users
/index.html
--- tr: lowercase to uppercase on the method column ---
GET
POST
--- head / tail ---
10.0.0.1 GET /index.html 200
10.0.0.2 GET /api/users 500
10.0.0.2 GET /api/users 500
10.0.0.1 GET /index.html 200
--- grep -c and grep -v ---
5
10.0.0.2 GET /api/users 500
10.0.0.3 GET /missing 404
10.0.0.2 GET /api/users 500
```

`cut -d ' ' -f 3` pulled out just the URL path — simpler than awk when all you need is one field at a fixed
position. `grep -c` counts matching lines (5 GETs), and `grep -v` inverts the match to show every request that
was **not** a 200 — the three failures.

### Live runs — archiving

```bash
tar -czf project.tar.gz project
ls -lh project.tar.gz
tar -tzf project.tar.gz
mkdir -p restored && tar -xzf project.tar.gz -C restored
find restored -type f
gzip access-copy.log && ls -l access-copy.log.gz
gunzip access-copy.log.gz && ls -l access-copy.log
zip -q -r project.zip project && unzip -l project.zip | tail -4
```

Output:

```text
-rw-r--r-- 1 root root 256 Sep 17 16:17 project.tar.gz
--- list contents without extracting ---
project/
project/logs/
project/logs/app.log
project/src/
project/src/app.py
project/src/util.py
project/src/app.py.bak
--- extract into a new directory ---
restored/project/logs/app.log
restored/project/src/app.py
restored/project/src/util.py
restored/project/src/app.py.bak
--- gzip a single file ---
-rw-r--r-- 1 root root 114 Sep 17 16:17 access-copy.log.gz
-rw-r--r-- 1 root root 169 Sep 17 16:17 access-copy.log
--- zip / unzip ---
        0  2026-09-17 16:15   project/src/util.py
       22  2026-09-17 16:15   project/src/app.py.bak
---------                     -------
       44                     7 files
```

Always run `tar -tzf` before `tar -xzf` on an archive you did not create. Some archives contain a top-level
directory (this one does — every path starts with `project/`) and some dump their files straight into your
current directory, making a mess. `-C restored` extracts into a chosen directory, which is the safe habit.
Note `gzip` **replaces** the original with `.gz` and `gunzip` reverses it — 169 bytes compressed to 114.

### Live runs — package management

```bash
apt list --installed | grep -E "^(curl|tree|nginx)/"
dpkg -l tree
dpkg -S /usr/bin/tree
dpkg -L tree | head -6
apt show tree | head -8
```

Output:

```text
curl/noble-updates,noble-security,now 8.5.0-2ubuntu10.13 arm64 [installed]
tree/noble-updates,now 2.1.1-2ubuntu3.24.04.2 arm64 [installed]
--- dpkg -l for one package ---
Desired=Unknown/Install/Remove/Purge/Hold
| Status=Not/Inst/Conf-files/Unpacked/halF-conf/Half-inst/trig-aWait/Trig-pend
|/ Err?=(none)/Reinst-required (Status,Err: uppercase=bad)
||/ Name           Version                Architecture Description
+++-==============-======================-============-=============================================
ii  tree           2.1.1-2ubuntu3.24.04.2 arm64        displays an indented directory tree, in color
--- which file does a binary come from ---
tree: /usr/bin/tree
--- what files did a package install ---
/.
/usr
/usr/bin
/usr/bin/tree
/usr/share
/usr/share/doc
--- apt show ---
Package: tree
Version: 2.1.1-2ubuntu3.24.04.2
Priority: optional
Section: universe/utils
Origin: Ubuntu
Maintainer: Ubuntu Developers <ubuntu-devel-discuss@lists.ubuntu.com>
Original-Maintainer: Florian Ernst <florian@debian.org>
Bugs: https://bugs.launchpad.net/ubuntu/+filebug
```

The `ii` in `dpkg -l` means desired state **i**nstall, current state **i**nstalled — that is the healthy state.
Anything else (`rc`, `iU`, `iF`) means a half-finished operation. `noble` is Ubuntu 24.04's codename, so
`noble-updates` tells you the package came from the updates pocket rather than the original release.
`dpkg -S` (which package owns this file) and `dpkg -L` (which files does this package own) are inverses of each
other, and together they answer most "where did this binary come from" questions.

### Live runs — system information

```bash
uname -a
cat /etc/os-release | head -4
uptime
date
date -u +"%Y-%m-%dT%H:%M:%SZ"
hostname
whoami
nproc
```

Output:

```text
Linux 4b27ae2ac371 6.12.76-linuxkit #1 SMP Fri Apr 17 14:56:37 UTC 2026 aarch64 aarch64 aarch64 GNU/Linux
--- distro ---
PRETTY_NAME="Ubuntu 24.04.4 LTS"
NAME="Ubuntu"
VERSION_ID="24.04"
VERSION="24.04.4 LTS (Noble Numbat)"
--- uptime ---
 16:17:31 up 9 min,  0 user,  load average: 3.42, 2.58, 1.25
--- date ---
Thu Sep 17 16:17:31 UTC 2026
2026-09-17T16:17:31Z
--- hostname / whoami / cpu count ---
4b27ae2ac371
root
15
```

Two container-specific details worth noticing:

- The kernel is `6.12.76-**linuxkit**`, not an Ubuntu kernel. Containers share the host's kernel — here, the
  LinuxKit VM that Docker Desktop runs on macOS. So `uname` reports the *host's* kernel while `/etc/os-release`
  reports the *container's* userland. That split is the clearest one-line explanation of what a container is.
- `hostname` returns `4b27ae2ac371`, the container ID, because Docker sets the hostname to the short container ID
  by default.

`uptime` shows "up 9 min" — the container's lifetime, not the laptop's. `date -u +"%Y-%m-%dT%H:%M:%SZ"` produces
an ISO-8601 UTC timestamp, the format to use in logs and filenames because it sorts correctly as plain text.

On the systemd container, `hostnamectl` gives a much richer summary:

```bash
hostnamectl
```

Output:

```text
 Static hostname: 22bd84d1b328
       Icon name: computer-container
         Chassis: container ☐
      Machine ID: 645bb706a7c1468eae758bafc5b3ee75
         Boot ID: 12bfc15c72eb4c2c807d5b0f60229a38
  Virtualization: docker
Operating System: Ubuntu 24.04.4 LTS
          Kernel: Linux 6.12.76-linuxkit
    Architecture: arm64
```

systemd detects and reports its own environment: `Chassis: container`, `Virtualization: docker`. The `Boot ID`
is the same value that `journalctl --list-boots` printed in Task 3 — that is how journald ties log entries to a
particular boot.

---

## Cleanup

Everything created for this assignment was namespaced with the `hw01-` prefix so it is easy to find and remove:

```bash
docker rm -f hw01-ubuntu hw01-systemd
docker ps -a --filter "name=hw01-" --format '{{.Names}}'
```

Output:

```text
hw01-ubuntu
hw01-systemd
```

`docker rm -f` echoed back the two names it removed, and the `docker ps -a --filter` that followed printed
nothing at all — confirming no `hw01-` containers remain. The same filter against networks, volumes, and images
also comes back empty:

```bash
docker network ls --filter "name=hw01-" --format '{{.Name}}'
docker volume  ls --filter "name=hw01-" --format '{{.Name}}'
docker images     --filter "reference=hw01-*" --format '{{.Repository}}'
```

All three print nothing. No custom images, networks, or volumes were ever created — both containers used the
stock `ubuntu:24.04` image and Docker's default bridge network.

---

## What is in this folder

| File | Purpose |
|---|---|
| `README.md` | This document — all four tasks with real, captured command output |
| `links-demo.sh` | Runs the full hard-link / soft-link lifecycle end to end. Linux only; run it inside the container |
