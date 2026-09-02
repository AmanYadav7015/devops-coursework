# Task 1 — Soft Link & Hard Link · terminal transcript

> Real session captured on Ubuntu 24.04 in container `hw-t1`.
> Every command was executed; the output is verbatim.

[← Back to Task 1 — Soft Link & Hard Link](README.md) · [Topic index](../README.md)

---

```console
# --- 0. Setup: clean scratch dir under /root/task1 ---
root@ubuntu-hw:~# rm -rf /root/task1
root@ubuntu-hw:~# mkdir -p /root/task1
root@ubuntu-hw:~# cd /root/task1 && pwd
/root/task1
```

### 1. Create an original file with known content

```console
root@ubuntu-hw:~# cd /root/task1 && echo "Hello from the original file - Task 1 DevOps HW" > original.txt
root@ubuntu-hw:~# cd /root/task1 && cat original.txt
Hello from the original file - Task 1 DevOps HW
root@ubuntu-hw:~# cd /root/task1 && ls -li original.txt
742466 -rw-r--r-- 1 root root 48 Sep  2 16:51 original.txt
```

### 2. Create a HARD LINK

```console
root@ubuntu-hw:~# cd /root/task1 && ln original.txt hardlink.txt
root@ubuntu-hw:~# cd /root/task1 && ls -li original.txt hardlink.txt
742466 -rw-r--r-- 2 root root 48 Sep  2 16:51 hardlink.txt
742466 -rw-r--r-- 2 root root 48 Sep  2 16:51 original.txt

# --- confirm identical inode number and link count = 2 ---
root@ubuntu-hw:~# cd /root/task1 && stat -c '%n  inode=%i  links=%h  size=%s' original.txt hardlink.txt
original.txt  inode=742466  links=2  size=48
hardlink.txt  inode=742466  links=2  size=48
```

### 3. Create a SOFT (SYMBOLIC) LINK

```console
root@ubuntu-hw:~# cd /root/task1 && ln -s original.txt softlink.txt
root@ubuntu-hw:~# cd /root/task1 && ls -li original.txt hardlink.txt softlink.txt
742466 -rw-r--r-- 2 root root 48 Sep  2 16:51 hardlink.txt
742466 -rw-r--r-- 2 root root 48 Sep  2 16:51 original.txt
742520 lrwxrwxrwx 1 root root 12 Sep  2 16:51 softlink.txt -> original.txt

# --- note: different inode, 'l' file type, "-> original.txt", tiny size ---
root@ubuntu-hw:~# cd /root/task1 && stat -c '%n  inode=%i  links=%h  size=%s  type=%F' original.txt hardlink.txt softlink.txt
original.txt  inode=742466  links=2  size=48  type=regular file
hardlink.txt  inode=742466  links=2  size=48  type=regular file
softlink.txt  inode=742520  links=1  size=12  type=symbolic link
```

### 4. Full stat output on all three

```console
root@ubuntu-hw:~# cd /root/task1 && stat original.txt
  File: original.txt
  Size: 48        	Blocks: 8          IO Block: 4096   regular file
Device: 0,63	Inode: 742466      Links: 2
Access: (0644/-rw-r--r--)  Uid: (    0/    root)   Gid: (    0/    root)
Access: 2026-09-02 16:51:59.459583001 +0000
Modify: 2026-09-02 16:51:59.408583001 +0000
Change: 2026-09-02 16:51:59.572583002 +0000
 Birth: 2026-09-02 16:51:59.408583001 +0000
root@ubuntu-hw:~# cd /root/task1 && stat hardlink.txt
  File: hardlink.txt
  Size: 48        	Blocks: 8          IO Block: 4096   regular file
Device: 0,63	Inode: 742466      Links: 2
Access: (0644/-rw-r--r--)  Uid: (    0/    root)   Gid: (    0/    root)
Access: 2026-09-02 16:51:59.459583001 +0000
Modify: 2026-09-02 16:51:59.408583001 +0000
Change: 2026-09-02 16:51:59.572583002 +0000
 Birth: 2026-09-02 16:51:59.408583001 +0000
root@ubuntu-hw:~# cd /root/task1 && stat softlink.txt
  File: softlink.txt -> original.txt
  Size: 12        	Blocks: 0          IO Block: 4096   symbolic link
Device: 0,63	Inode: 742520      Links: 1
Access: (0777/lrwxrwxrwx)  Uid: (    0/    root)   Gid: (    0/    root)
Access: 2026-09-02 16:51:59.806583002 +0000
Modify: 2026-09-02 16:51:59.754583002 +0000
Change: 2026-09-02 16:51:59.754583002 +0000
 Birth: 2026-09-02 16:51:59.754583002 +0000
```

### 5. readlink on the symlink

```console
root@ubuntu-hw:~# cd /root/task1 && readlink softlink.txt
original.txt
root@ubuntu-hw:~# cd /root/task1 && readlink -f softlink.txt
/root/task1/original.txt
```

### 6. Prove the HARD LINK survives deletion of the original NAME

```console
root@ubuntu-hw:~# cd /root/task1 && rm original.txt
root@ubuntu-hw:~# cd /root/task1 && ls -li
total 4
742466 -rw-r--r-- 1 root root 48 Sep  2 16:51 hardlink.txt
742520 lrwxrwxrwx 1 root root 12 Sep  2 16:51 softlink.txt -> original.txt

# --- hard link still has the data; link count drops from 2 to 1 (one name left) ---
root@ubuntu-hw:~# cd /root/task1 && cat hardlink.txt
Hello from the original file - Task 1 DevOps HW
root@ubuntu-hw:~# cd /root/task1 && stat -c '%n  inode=%i  links=%h' hardlink.txt
hardlink.txt  inode=742466  links=1

# --- soft link is now DANGLING because the name it points to is gone ---
root@ubuntu-hw:~# cd /root/task1 && cat softlink.txt
cat: softlink.txt: No such file or directory
root@ubuntu-hw:~# cd /root/task1 && ls -l softlink.txt
lrwxrwxrwx 1 root root 12 Sep  2 16:51 softlink.txt -> original.txt
```

### 7. Recreate original.txt -- soft link "heals", hard link does NOT

```console
root@ubuntu-hw:~# cd /root/task1 && echo "Hello from the original file - Task 1 DevOps HW" > original.txt
root@ubuntu-hw:~# cd /root/task1 && cat softlink.txt
Hello from the original file - Task 1 DevOps HW

# --- IMPORTANT: this is a brand-new inode, unrelated to hardlink.txt's old inode ---
root@ubuntu-hw:~# cd /root/task1 && stat -c '%n  inode=%i  links=%h' original.txt hardlink.txt softlink.txt
original.txt  inode=742700  links=1
hardlink.txt  inode=742466  links=1
softlink.txt  inode=742520  links=1
```

### 8. Hard links cannot span directories; soft links can

```console
root@ubuntu-hw:~# cd /root/task1 && mkdir mydir
root@ubuntu-hw:~# cd /root/task1 && ln mydir hardlink_to_dir
ln: mydir: hard link not allowed for directory

# --- soft link to a directory works fine ---
root@ubuntu-hw:~# cd /root/task1 && ln -s mydir softlink_to_dir
root@ubuntu-hw:~# cd /root/task1 && ls -li mydir softlink_to_dir
742702 lrwxrwxrwx 1 root root    5 Sep  2 16:52 softlink_to_dir -> mydir

mydir:
total 0
root@ubuntu-hw:~# cd /root/task1 && ls -F
hardlink.txt
mydir/
original.txt
softlink.txt@
softlink_to_dir@
```

### 9. Hard links cannot cross filesystems; soft links can

```console
root@ubuntu-hw:~# cd /root/task1 && df -T / /tmp
Filesystem     Type    1K-blocks      Used Available Use% Mounted on
overlay        overlay 954932096 126243260 780107576  14% /
overlay        overlay 954932096 126243260 780107576  14% /
root@ubuntu-hw:~# cd /root/task1 && stat -c '%n  device=%d' /root/task1 /tmp
/root/task1  device=63
/tmp  device=63

# --- in THIS container /tmp and /root are the SAME overlay filesystem (same device id), ---
# --- so this ln will actually SUCCEED here -- that itself proves the rule: ---
# --- ln only fails with "Invalid cross-device link" when source and target are on ---
# --- DIFFERENT mounted filesystems (e.g. / vs a separate /mnt/usb or /data volume). ---
root@ubuntu-hw:~# cd /root/task1 && echo "cross-fs test file" > fstest.txt
root@ubuntu-hw:~# cd /root/task1 && ln fstest.txt /tmp/fstest_hardlink
root@ubuntu-hw:~# cd /root/task1 && stat -c '%n  inode=%i  links=%h  device=%d' fstest.txt /tmp/fstest_hardlink
fstest.txt  inode=742703  links=2  device=63
/tmp/fstest_hardlink  inode=742703  links=2  device=63

# --- soft link has no such restriction: it can always point across filesystems ---
root@ubuntu-hw:~# cd /root/task1 && ln -s /root/task1/fstest.txt /tmp/fstest_softlink
root@ubuntu-hw:~# cd /root/task1 && ls -li /tmp/fstest_softlink
742704 lrwxrwxrwx 1 root root 22 Sep  2 16:52 /tmp/fstest_softlink -> /root/task1/fstest.txt
root@ubuntu-hw:~# cd /root/task1 && cat /tmp/fstest_softlink
cross-fs test file

# --- clean up the cross-fs experiment so it doesn't affect later link counts ---
root@ubuntu-hw:~# cd /root/task1 && rm /tmp/fstest_hardlink /tmp/fstest_softlink fstest.txt
root@ubuntu-hw:~# cd /root/task1 && ls -li
total 12
742466 -rw-r--r-- 1 root root   48 Sep  2 16:51 hardlink.txt
742701 drwxr-xr-x 2 root root 4096 Sep  2 16:52 mydir
742700 -rw-r--r-- 1 root root   48 Sep  2 16:52 original.txt
742520 lrwxrwxrwx 1 root root   12 Sep  2 16:51 softlink.txt -> original.txt
742702 lrwxrwxrwx 1 root root    5 Sep  2 16:52 softlink_to_dir -> mydir
```

### 10. Use find to locate all hard links to a file (same inode)

```console
root@ubuntu-hw:~# cd /root/task1 && ln original.txt original_link2.txt
root@ubuntu-hw:~# cd /root/task1 && stat -c '%n  inode=%i  links=%h' original.txt original_link2.txt
original.txt  inode=742700  links=2
original_link2.txt  inode=742700  links=2
root@ubuntu-hw:~# cd /root/task1 && find /root/task1 -inum $(stat -c '%i' original.txt) -print
/root/task1/original.txt
/root/task1/original_link2.txt
root@ubuntu-hw:~# cd /root/task1 && find /root/task1 -samefile original.txt -print
/root/task1/original.txt
/root/task1/original_link2.txt
```

### 11. Deleting links properly

```console
root@ubuntu-hw:~# cd /root/task1 && rm softlink.txt
root@ubuntu-hw:~# cd /root/task1 && ls -li
total 16
742466 -rw-r--r-- 1 root root   48 Sep  2 16:51 hardlink.txt
742701 drwxr-xr-x 2 root root 4096 Sep  2 16:52 mydir
742700 -rw-r--r-- 2 root root   48 Sep  2 16:52 original.txt
742700 -rw-r--r-- 2 root root   48 Sep  2 16:52 original_link2.txt
742702 lrwxrwxrwx 1 root root    5 Sep  2 16:52 softlink_to_dir -> mydir

# --- removing one hard-link NAME just decrements the link count; data survives ---
root@ubuntu-hw:~# cd /root/task1 && rm original_link2.txt
root@ubuntu-hw:~# cd /root/task1 && stat -c '%n  inode=%i  links=%h' original.txt
original.txt  inode=742700  links=1

# --- hardlink.txt is an independent file now (see step 7) -- remove it too ---
root@ubuntu-hw:~# cd /root/task1 && rm hardlink.txt
root@ubuntu-hw:~# cd /root/task1 && ls -li
total 8
742701 drwxr-xr-x 2 root root 4096 Sep  2 16:52 mydir
742700 -rw-r--r-- 1 root root   48 Sep  2 16:52 original.txt
742702 lrwxrwxrwx 1 root root    5 Sep  2 16:52 softlink_to_dir -> mydir

# --- classic gotcha: removing a symlink-to-directory ---
root@ubuntu-hw:~# cd /root/task1 && ls -F
mydir/
original.txt
softlink_to_dir@
root@ubuntu-hw:~# cd /root/task1 && rm softlink_to_dir
root@ubuntu-hw:~# cd /root/task1 && ls -F
mydir/
original.txt
root@ubuntu-hw:~# cd /root/task1 && ls mydir

# --- recreate it to show the trailing-slash mistake ---
root@ubuntu-hw:~# cd /root/task1 && ln -s mydir softlink_to_dir
root@ubuntu-hw:~# cd /root/task1 && ls -F
mydir/
original.txt
softlink_to_dir@
root@ubuntu-hw:~# echo "Attempting: rm softlink_to_dir/  (trailing slash forces rm to treat it as the directory itself)"
Attempting: rm softlink_to_dir/  (trailing slash forces rm to treat it as the directory itself)
root@ubuntu-hw:~# cd /root/task1 && rm softlink_to_dir/ 2>&1 || echo "^ rm refuses -- classic gotcha: trailing slash makes rm resolve into the target directory instead of removing the link"
rm: cannot remove 'softlink_to_dir/': Is a directory
^ rm refuses -- classic gotcha: trailing slash makes rm resolve into the target directory instead of removing the link
root@ubuntu-hw:~# cd /root/task1 && ls -F
mydir/
original.txt
softlink_to_dir@

# --- correct way: no trailing slash removes only the link, directory is untouched ---
root@ubuntu-hw:~# cd /root/task1 && rm softlink_to_dir
root@ubuntu-hw:~# cd /root/task1 && ls -F
mydir/
original.txt
root@ubuntu-hw:~# cd /root/task1 && ls mydir
```

### 12. Final cleanup / final state

```console
root@ubuntu-hw:~# cd /root/task1 && rmdir mydir
root@ubuntu-hw:~# cd /root/task1 && ls -la /root/task1
total 12
drwxr-xr-x 2 root root 4096 Sep  2 16:52 .
drwx------ 1 root root 4096 Sep  2 16:51 ..
-rw-r--r-- 1 root root   48 Sep  2 16:52 original.txt
```
