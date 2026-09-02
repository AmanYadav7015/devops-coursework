# Networking — connectivity & routing

> Real session captured in container `net-t1`.
> Every command was executed; the output is verbatim.

[← Back](README.md)

---

```console
# --- ping a raw IP: pure ICMP echo, no DNS lookup involved ---
root@ubuntu-hw:~# ping -c 3 8.8.8.8
PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
64 bytes from 8.8.8.8: icmp_seq=1 ttl=63 time=87.5 ms
64 bytes from 8.8.8.8: icmp_seq=2 ttl=63 time=77.4 ms

--- 8.8.8.8 ping statistics ---
3 packets transmitted, 2 received, 33.3333% packet loss, time 2005ms
rtt min/avg/max/mdev = 77.434/82.445/87.457/5.011 ms

# --- ping a hostname: exercises DNS resolution first, then ICMP echo ---
root@ubuntu-hw:~# ping -c 3 google.com
PING google.com (142.251.221.238) 56(84) bytes of data.
64 bytes from pnbomb-bk-in-f14.1e100.net (142.251.221.238): icmp_seq=1 ttl=63 time=35.4 ms
64 bytes from pnbomb-bk-in-f14.1e100.net (142.251.221.238): icmp_seq=2 ttl=63 time=61.9 ms
64 bytes from pnbomb-bk-in-f14.1e100.net (142.251.221.238): icmp_seq=3 ttl=63 time=99.3 ms

--- google.com ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2015ms
rtt min/avg/max/mdev = 35.417/65.527/99.281/26.199 ms

# --- traceroute: map the path hop by hop. -m 8 caps at 8 hops, ---
# --- -w 1 -q 1 (1s wait, 1 probe/hop) so a filtered hop doesn't stall us ---
root@ubuntu-hw:~# traceroute -m 8 -w 1 -q 1 google.com
traceroute to google.com (142.251.221.238), 8 hops max, 60 byte packets
 1  172.17.0.1 (172.17.0.1)  0.357 ms
 2  *
 3  *
 4  *
 5  *
 6  *
 7  *
 8  *

# --- mtr: ping+traceroute combined, one summary report, 3 cycles ---
root@ubuntu-hw:~# mtr --report -c 3 google.com
Start: 2026-09-02T17:28:24+0000
HOST: ubuntu-hw                   Loss%   Snt   Last   Avg  Best  Wrst StDev
  1.|-- 172.17.0.1                 0.0%     3    0.2   0.2   0.1   0.2   0.1
  2.|-- pnbomb-bk-in-f14.1e100.ne  0.0%     3   34.6  40.0  31.4  53.9  12.2

# --- ask the kernel which route/interface/source-IP it would actually use for 8.8.8.8 ---
root@ubuntu-hw:~# ip route get 8.8.8.8
8.8.8.8 via 172.17.0.1 dev eth0 src 172.17.0.7 uid 0 
    cache 
```
