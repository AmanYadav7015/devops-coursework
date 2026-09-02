# Task 4c — disk, network, archives & packages · terminal transcript

> Real session captured on Ubuntu 24.04 in container `hw-t4`.
> Every command was executed; the output is verbatim.

[← Back to Task 4 — Linux Command Cheat Sheet](README.md) · [Topic index](../README.md)

---

```console
# (continues in the /root/cheatsheet workspace built during task4a/4b)
```

### 1. Disk & system info

```console
# --- df -h: filesystem usage ---
root@ubuntu-hw:~# df -h
Filesystem      Size  Used Avail Use% Mounted on
overlay         911G  121G  744G  14% /
tmpfs            64M     0   64M   0% /dev
shm              64M     0   64M   0% /dev/shm
/dev/vda1       911G  121G  744G  14% /etc/hosts
tmpfs           3.9G     0  3.9G   0% /proc/scsi
tmpfs           3.9G     0  3.9G   0% /sys/firmware

# --- du -sh: biggest consumers under /var ---
root@ubuntu-hw:~# du -sh /var/* 2>&1 | sort -rh
60M	/var/lib
1.2M	/var/cache
408K	/var/log
16K	/var/spool
12K	/var/www
4.0K	/var/tmp
4.0K	/var/opt
4.0K	/var/mail
4.0K	/var/local
4.0K	/var/backups
0	/var/run
0	/var/lock

# --- lsblk: block devices (container view -- see note in write-up) ---
root@ubuntu-hw:~# lsblk
NAME   MAJ:MIN RM   SIZE RO TYPE MOUNTPOINTS
nbd0    43:0    0     0B  0 disk 
nbd1    43:32   0     0B  0 disk 
nbd2    43:64   0     0B  0 disk 
nbd3    43:96   0     0B  0 disk 
nbd4    43:128  0     0B  0 disk 
nbd5    43:160  0     0B  0 disk 
nbd6    43:192  0     0B  0 disk 
nbd7    43:224  0     0B  0 disk 
vda    254:0    0 926.3G  0 disk 
`-vda1 254:1    0 926.3G  0 part /etc/hosts
                                 /etc/hostname
                                 /etc/resolv.conf
vdb    254:16   0 623.1M  1 disk 
nbd8    43:256  0     0B  0 disk 
nbd9    43:288  0     0B  0 disk 
nbd10   43:320  0     0B  0 disk 
nbd11   43:352  0     0B  0 disk 
nbd12   43:384  0     0B  0 disk 
nbd13   43:416  0     0B  0 disk 
nbd14   43:448  0     0B  0 disk 
nbd15   43:480  0     0B  0 disk 

# --- uname -a: kernel + arch ---
root@ubuntu-hw:~# uname -a
Linux ubuntu-hw 6.12.76-linuxkit #1 SMP Fri Apr 17 14:56:37 UTC 2026 aarch64 aarch64 aarch64 GNU/Linux

# --- hostnamectl / os-release: OS identity ---
root@ubuntu-hw:~# hostnamectl
System has not been booted with systemd as init system (PID 1). Can't operate.
Failed to connect to bus: Host is down
root@ubuntu-hw:~# cat /etc/os-release
PRETTY_NAME="Ubuntu 24.04.4 LTS"
NAME="Ubuntu"
VERSION_ID="24.04"
VERSION="24.04.4 LTS (Noble Numbat)"
VERSION_CODENAME=noble
ID=ubuntu
ID_LIKE=debian
HOME_URL="https://www.ubuntu.com/"
SUPPORT_URL="https://help.ubuntu.com/"
BUG_REPORT_URL="https://bugs.launchpad.net/ubuntu/"
PRIVACY_POLICY_URL="https://www.ubuntu.com/legal/terms-and-policies/privacy-policy"
UBUNTU_CODENAME=noble
LOGO=ubuntu-logo

# --- date ---
root@ubuntu-hw:~# date
Wed Sep  2 17:00:01 UTC 2026
root@ubuntu-hw:~# date +"%Y-%m-%d %H:%M:%S %Z"
2026-09-02 17:00:01 UTC

# --- env: process environment ---
root@ubuntu-hw:~# env | sort | head -10
DEBIAN_FRONTEND=noninteractive
HOME=/root
HOSTNAME=ubuntu-hw
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
PWD=/root
SHLVL=1
_=/usr/bin/env

# --- history: note on non-interactive shells ---
root@ubuntu-hw:~# history
```

### 2. Networking

```console
# --- ip a: interfaces and addresses ---
root@ubuntu-hw:~# ip a
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host 
       valid_lft forever preferred_lft forever
2: tunl0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN group default qlen 1000
    link/ipip 0.0.0.0 brd 0.0.0.0
3: gre0@NONE: <NOARP> mtu 1476 qdisc noop state DOWN group default qlen 1000
    link/gre 0.0.0.0 brd 0.0.0.0
4: gretap0@NONE: <BROADCAST,MULTICAST> mtu 1462 qdisc noop state DOWN group default qlen 1000
    link/ether 00:00:00:00:00:00 brd ff:ff:ff:ff:ff:ff
5: erspan0@NONE: <BROADCAST,MULTICAST> mtu 1450 qdisc noop state DOWN group default qlen 1000
    link/ether 00:00:00:00:00:00 brd ff:ff:ff:ff:ff:ff
6: ip_vti0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN group default qlen 1000
    link/ipip 0.0.0.0 brd 0.0.0.0
7: ip6_vti0@NONE: <NOARP> mtu 1428 qdisc noop state DOWN group default qlen 1000
    link/tunnel6 :: brd :: permaddr beee:99a3:e87c::
8: sit0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN group default qlen 1000
    link/sit 0.0.0.0 brd 0.0.0.0
9: ip6tnl0@NONE: <NOARP> mtu 1452 qdisc noop state DOWN group default qlen 1000
    link/tunnel6 :: brd :: permaddr 64c:b1ee:792e::
10: ip6gre0@NONE: <NOARP> mtu 1448 qdisc noop state DOWN group default qlen 1000
    link/gre6 :: brd :: permaddr 4ad2:4269:93af::
11: eth0@if293: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 65535 qdisc noqueue state UP group default 
    link/ether aa:bf:0d:7a:98:7b brd ff:ff:ff:ff:ff:ff link-netnsid 0
    inet 172.17.0.4/16 brd 172.17.255.255 scope global eth0
       valid_lft forever preferred_lft forever

# --- ip r: routing table ---
root@ubuntu-hw:~# ip r
default via 172.17.0.1 dev eth0 
172.17.0.0/16 dev eth0 proto kernel scope link src 172.17.0.4 

# --- ss -tuln: listening TCP/UDP sockets, numeric ---
root@ubuntu-hw:~# ss -tuln
Netid State Recv-Q Send-Q Local Address:Port Peer Address:PortProcess

# --- hostname -I: this host's IP address(es) ---
root@ubuntu-hw:~# hostname -I
172.17.0.4 

# --- ping: loopback and an external host ---
root@ubuntu-hw:~# ping -c 2 127.0.0.1
PING 127.0.0.1 (127.0.0.1) 56(84) bytes of data.
64 bytes from 127.0.0.1: icmp_seq=1 ttl=64 time=0.032 ms
64 bytes from 127.0.0.1: icmp_seq=2 ttl=64 time=0.069 ms

--- 127.0.0.1 ping statistics ---
2 packets transmitted, 2 received, 0% packet loss, time 1017ms
rtt min/avg/max/mdev = 0.032/0.050/0.069/0.018 ms
root@ubuntu-hw:~# ping -c 2 8.8.8.8
PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
64 bytes from 8.8.8.8: icmp_seq=1 ttl=63 time=20.6 ms
64 bytes from 8.8.8.8: icmp_seq=2 ttl=63 time=47.4 ms

--- 8.8.8.8 ping statistics ---
2 packets transmitted, 2 received, 0% packet loss, time 1003ms
rtt min/avg/max/mdev = 20.629/34.004/47.380/13.375 ms

# --- /etc/hosts ---
root@ubuntu-hw:~# cat /etc/hosts
127.0.0.1	localhost
::1	localhost ip6-localhost ip6-loopback
fe00::	ip6-localnet
ff00::	ip6-mcastprefix
ff02::1	ip6-allnodes
ff02::2	ip6-allrouters
172.17.0.4	ubuntu-hw

# --- DNS lookups ---
root@ubuntu-hw:~# dig +short google.com
142.250.205.206
root@ubuntu-hw:~# nslookup google.com
Server:		192.168.65.7
Address:	192.168.65.7#53

Non-authoritative answer:
Name:	google.com
Address: 142.250.205.206


# --- start nginx, then curl it ---
root@ubuntu-hw:~# service nginx start
 * Starting nginx nginx
   ...done.
root@ubuntu-hw:~# sleep 1
root@ubuntu-hw:~# service nginx status
 * nginx is running
root@ubuntu-hw:~# curl -I http://localhost/
  % Total    % Received % Xferd  Average Speed   Time    Time     Time  Current
                                 Dload  Upload   Total   Spent    Left  Speed

  0     0    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0HTTP/1.1 200 OK
Server: nginx/1.24.0 (Ubuntu)
Date: Wed, 02 Sep 2026 17:00:06 GMT
Content-Type: text/html
Content-Length: 615
Last-Modified: Wed, 02 Sep 2026 16:46:29 GMT
Connection: keep-alive
ETag: "6a9852e5-267"
Accept-Ranges: bytes


  0   615    0     0    0     0      0      0 --:--:-- --:--:-- --:--:--     0
root@ubuntu-hw:~# curl -s http://localhost/ | head -6
<!DOCTYPE html>
<html>
<head>
<title>Welcome to nginx!</title>
<style>
html { color-scheme: light dark; }
```

### 3. Archives & compression

```console
# --- tar -czf: create a gzip-compressed tarball ---
root@ubuntu-hw:~# cd /root/cheatsheet && tar -czf archive_src.tar.gz archive_src/

# --- tar -tzf: list contents WITHOUT extracting ---
root@ubuntu-hw:~# cd /root/cheatsheet && tar -tzf archive_src.tar.gz
archive_src/
archive_src/public/
archive_src/public/style.css
archive_src/public/index.html
archive_src/private/
archive_src/private/secret_notes.txt

# --- tar -xzf: extract into a fresh directory ---
root@ubuntu-hw:~# mkdir -p /root/cheatsheet/extracted
root@ubuntu-hw:~# cd /root/cheatsheet && tar -xzf archive_src.tar.gz -C extracted
root@ubuntu-hw:~# find /root/cheatsheet/extracted -type f
/root/cheatsheet/extracted/archive_src/public/style.css
/root/cheatsheet/extracted/archive_src/public/index.html
/root/cheatsheet/extracted/archive_src/private/secret_notes.txt

# --- gzip / gunzip ---
root@ubuntu-hw:~# gzip -k /root/cheatsheet/reports/old_report.txt
root@ubuntu-hw:~# ls -l /root/cheatsheet/reports/
total 16
drwxr-xr-x 3 root root 4096 Sep  2 16:57 2026
-rw-r--r-- 1 root root   57 Jul 29 16:57 old_report.txt
-rw-r--r-- 1 root root   88 Jul 29 16:57 old_report.txt.gz
-rw-r--r-- 1 root root   72 Sep  2 15:57 recent_report.txt
root@ubuntu-hw:~# rm /root/cheatsheet/reports/old_report.txt
root@ubuntu-hw:~# ls -l /root/cheatsheet/reports/
total 12
drwxr-xr-x 3 root root 4096 Sep  2 16:57 2026
-rw-r--r-- 1 root root   88 Jul 29 16:57 old_report.txt.gz
-rw-r--r-- 1 root root   72 Sep  2 15:57 recent_report.txt
root@ubuntu-hw:~# gunzip -k /root/cheatsheet/reports/old_report.txt.gz
root@ubuntu-hw:~# ls -l /root/cheatsheet/reports/
total 16
drwxr-xr-x 3 root root 4096 Sep  2 16:57 2026
-rw-r--r-- 1 root root   57 Jul 29 16:57 old_report.txt
-rw-r--r-- 1 root root   88 Jul 29 16:57 old_report.txt.gz
-rw-r--r-- 1 root root   72 Sep  2 15:57 recent_report.txt
root@ubuntu-hw:~# cat /root/cheatsheet/reports/old_report.txt
Monthly report - August
Total requests: 15234
Errors: 12

# --- zip / unzip ---
root@ubuntu-hw:~# cd /root/cheatsheet && zip -r site.zip archive_src/
  adding: archive_src/ (stored 0%)
  adding: archive_src/public/ (stored 0%)
  adding: archive_src/public/style.css (deflated 6%)
  adding: archive_src/public/index.html (deflated 25%)
  adding: archive_src/private/ (stored 0%)
  adding: archive_src/private/secret_notes.txt (stored 0%)
root@ubuntu-hw:~# unzip -l /root/cheatsheet/site.zip
Archive:  /root/cheatsheet/site.zip
  Length      Date    Time    Name
---------  ---------- -----   ----
        0  2026-09-02 16:57   archive_src/
        0  2026-09-02 16:57   archive_src/public/
       78  2026-09-02 16:57   archive_src/public/style.css
      184  2026-09-02 16:57   archive_src/public/index.html
        0  2026-09-02 16:57   archive_src/private/
       59  2026-09-02 16:57   archive_src/private/secret_notes.txt
---------                     -------
      321                     6 files
root@ubuntu-hw:~# unzip /root/cheatsheet/site.zip -d /root/cheatsheet/unzipped_site
Archive:  /root/cheatsheet/site.zip
   creating: /root/cheatsheet/unzipped_site/archive_src/
   creating: /root/cheatsheet/unzipped_site/archive_src/public/
  inflating: /root/cheatsheet/unzipped_site/archive_src/public/style.css  
  inflating: /root/cheatsheet/unzipped_site/archive_src/public/index.html  
   creating: /root/cheatsheet/unzipped_site/archive_src/private/
 extracting: /root/cheatsheet/unzipped_site/archive_src/private/secret_notes.txt  
root@ubuntu-hw:~# find /root/cheatsheet/unzipped_site -type f
/root/cheatsheet/unzipped_site/archive_src/public/style.css
/root/cheatsheet/unzipped_site/archive_src/public/index.html
/root/cheatsheet/unzipped_site/archive_src/private/secret_notes.txt
```

### 4. Packages

```console
# --- apt list --installed ---
root@ubuntu-hw:~# apt list --installed 2>/dev/null | head -10
Listing...
adduser/noble,now 3.137ubuntu1 all [installed]
apt/noble-updates,now 2.8.3 arm64 [installed]
base-files/noble-updates,now 13ubuntu10.4 arm64 [installed]
base-passwd/noble,now 3.6.3build1 arm64 [installed]
bash/noble,now 5.2.21-2ubuntu4 arm64 [installed]
bind9-dnsutils/noble-updates,noble-security,now 1:9.18.39-0ubuntu0.24.04.7 arm64 [installed,automatic]
bind9-host/noble-updates,noble-security,now 1:9.18.39-0ubuntu0.24.04.7 arm64 [installed,automatic]
bind9-libs/noble-updates,noble-security,now 1:9.18.39-0ubuntu0.24.04.7 arm64 [installed,automatic]
bsdutils/noble-updates,noble-security,now 1:2.39.3-9ubuntu6.6 arm64 [installed]

# --- dpkg -l ---
root@ubuntu-hw:~# dpkg -l | head -10
Desired=Unknown/Install/Remove/Purge/Hold
| Status=Not/Inst/Conf-files/Unpacked/halF-conf/Half-inst/trig-aWait/Trig-pend
|/ Err?=(none)/Reinst-required (Status,Err: uppercase=bad)
||/ Name                      Version                           Architecture Description
+++-=========================-=================================-============-===========================================================================
ii  adduser                   3.137ubuntu1                      all          add and remove users and groups
ii  apt                       2.8.3                             arm64        commandline package manager
ii  base-files                13ubuntu10.4                      arm64        Debian base system miscellaneous files
ii  base-passwd               3.6.3build1                       arm64        Debian base system master password and group files
ii  bash                      5.2.21-2ubuntu4                   arm64        GNU Bourne Again SHell

# --- apt-cache policy: installed vs candidate version, and where it comes from ---
root@ubuntu-hw:~# apt-cache policy nginx
nginx:
  Installed: 1.24.0-2ubuntu7.17
  Candidate: 1.24.0-2ubuntu7.17
  Version table:
 *** 1.24.0-2ubuntu7.17 500
        500 http://ports.ubuntu.com/ubuntu-ports noble-updates/main arm64 Packages
        500 http://ports.ubuntu.com/ubuntu-ports noble-security/main arm64 Packages
        100 /var/lib/dpkg/status
     1.24.0-2ubuntu7 500
        500 http://ports.ubuntu.com/ubuntu-ports noble/main arm64 Packages

# --- dpkg -L: which files a package actually installed ---
root@ubuntu-hw:~# dpkg -L nginx | head -10
/.
/usr
/usr/sbin
/usr/sbin/nginx
/usr/share
/usr/share/doc
/usr/share/doc/nginx
/usr/share/doc/nginx/changelog.Debian.gz
/usr/share/doc/nginx/copyright
/usr/share/man

# --- which / command -v ---
root@ubuntu-hw:~# which nginx
/usr/sbin/nginx
root@ubuntu-hw:~# command -v nginx
/usr/sbin/nginx
```

### 5. Services (systemd reference only -- hw-t4 has NO systemd, PID 1 is literally "sleep infinity"; see the real failure below)

```console
# --- systemctl: fails for real in this container (no systemd, no D-Bus) ---
root@ubuntu-hw:~# systemctl status nginx
System has not been booted with systemd as init system (PID 1). Can't operate.
Failed to connect to bus: Host is down

# --- ps -p 1: proof there is no systemd/init here ---
root@ubuntu-hw:~# ps -p 1 -o pid,comm,args
    PID COMMAND         COMMAND
      1 sleep           sleep infinity

# --- on hw-t4, nginx is managed the old sysvinit way instead ---
root@ubuntu-hw:~# service nginx stop
 * Stopping nginx nginx
   ...fail!
root@ubuntu-hw:~# service nginx status
 * nginx is not running
```
