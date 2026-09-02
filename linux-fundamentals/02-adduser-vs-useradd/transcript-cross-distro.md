# Task 2 — cross-distro check: Ubuntu 24.04 vs Rocky Linux 9

> Real session captured on Ubuntu 24.04 in container `hw-t2`.
> Every command was executed; the output is verbatim.

[← Back to Task 2 — adduser vs useradd](README.md) · [Topic index](../README.md)

---

```console
# --- On Ubuntu 24.04: adduser is a separate Perl wrapper ---
root@ubuntu-hw:~# ls -l /usr/sbin/adduser /usr/sbin/useradd
-rwxr-xr-x 1 root root  55191 Jul  5  2023 /usr/sbin/adduser
-rwxr-xr-x 1 root root 142784 May 30  2024 /usr/sbin/useradd
root@ubuntu-hw:~# file /usr/sbin/adduser
/usr/sbin/adduser: Perl script text executable
root@ubuntu-hw:~# dpkg -S /usr/sbin/adduser /usr/sbin/useradd
adduser: /usr/sbin/adduser
passwd: /usr/sbin/useradd

# --- On Rocky Linux 9: adduser is merely a symlink to useradd ---
[root@rocky9 ~]# ls -l /usr/sbin/adduser
lrwxrwxrwx 1 root root 7 Dec 29  2025 /usr/sbin/adduser -> useradd
[root@rocky9 ~]# readlink -f /usr/sbin/adduser
/usr/sbin/useradd
[root@rocky9 ~]# rpm -qf /usr/sbin/adduser /usr/sbin/useradd
shadow-utils-4.9-16.el9.aarch64
shadow-utils-4.9-16.el9.aarch64
[root@rocky9 ~]# ls /etc/adduser.conf 2>&1 || echo 'no /etc/adduser.conf -> no Debian adduser policy on RHEL'
ls: cannot access '/etc/adduser.conf': No such file or directory
no /etc/adduser.conf -> no Debian adduser policy on RHEL
```
