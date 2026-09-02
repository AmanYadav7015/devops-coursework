# Networking — interfaces & addressing

> Real session captured in container `net-t1`.
> Every command was executed; the output is verbatim.

[← Back](README.md)

---

```console
# --- ip a: full detail on every interface (link, IPv4, IPv6, flags, MTU, counters) ---
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
    link/tunnel6 :: brd :: permaddr d246:e021:2295::
8: sit0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN group default qlen 1000
    link/sit 0.0.0.0 brd 0.0.0.0
9: ip6tnl0@NONE: <NOARP> mtu 1452 qdisc noop state DOWN group default qlen 1000
    link/tunnel6 :: brd :: permaddr ca3e:71f5:6f4e::
10: ip6gre0@NONE: <NOARP> mtu 1448 qdisc noop state DOWN group default qlen 1000
    link/gre6 :: brd :: permaddr 325c:2a2e:4a57::
11: eth0@if306: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 65535 qdisc noqueue state UP group default 
    link/ether 7e:bd:7f:bb:7e:79 brd ff:ff:ff:ff:ff:ff link-netnsid 0
    inet 172.17.0.7/16 brd 172.17.255.255 scope global eth0
       valid_lft forever preferred_lft forever

# --- ip -br a: brief, script/eyeball-friendly one-line-per-interface view ---
root@ubuntu-hw:~# ip -br a
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
eth0@if306       UP             172.17.0.7/16 

# --- ip link: layer-2 (link) info only — MAC address, MTU, state — no IP addresses ---
root@ubuntu-hw:~# ip link
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN mode DEFAULT group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
2: tunl0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN mode DEFAULT group default qlen 1000
    link/ipip 0.0.0.0 brd 0.0.0.0
3: gre0@NONE: <NOARP> mtu 1476 qdisc noop state DOWN mode DEFAULT group default qlen 1000
    link/gre 0.0.0.0 brd 0.0.0.0
4: gretap0@NONE: <BROADCAST,MULTICAST> mtu 1462 qdisc noop state DOWN mode DEFAULT group default qlen 1000
    link/ether 00:00:00:00:00:00 brd ff:ff:ff:ff:ff:ff
5: erspan0@NONE: <BROADCAST,MULTICAST> mtu 1450 qdisc noop state DOWN mode DEFAULT group default qlen 1000
    link/ether 00:00:00:00:00:00 brd ff:ff:ff:ff:ff:ff
6: ip_vti0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN mode DEFAULT group default qlen 1000
    link/ipip 0.0.0.0 brd 0.0.0.0
7: ip6_vti0@NONE: <NOARP> mtu 1428 qdisc noop state DOWN mode DEFAULT group default qlen 1000
    link/tunnel6 :: brd :: permaddr d246:e021:2295::
8: sit0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN mode DEFAULT group default qlen 1000
    link/sit 0.0.0.0 brd 0.0.0.0
9: ip6tnl0@NONE: <NOARP> mtu 1452 qdisc noop state DOWN mode DEFAULT group default qlen 1000
    link/tunnel6 :: brd :: permaddr ca3e:71f5:6f4e::
10: ip6gre0@NONE: <NOARP> mtu 1448 qdisc noop state DOWN mode DEFAULT group default qlen 1000
    link/gre6 :: brd :: permaddr 325c:2a2e:4a57::
11: eth0@if306: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 65535 qdisc noqueue state UP mode DEFAULT group default 
    link/ether 7e:bd:7f:bb:7e:79 brd ff:ff:ff:ff:ff:ff link-netnsid 0

# --- ip r: the kernel routing table ---
root@ubuntu-hw:~# ip r
default via 172.17.0.1 dev eth0 
172.17.0.0/16 dev eth0 proto kernel scope link src 172.17.0.7 

# --- ip -br link: brief link-layer view ---
root@ubuntu-hw:~# ip -br link
lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP> 
tunl0@NONE       DOWN           0.0.0.0 <NOARP> 
gre0@NONE        DOWN           0.0.0.0 <NOARP> 
gretap0@NONE     DOWN           00:00:00:00:00:00 <BROADCAST,MULTICAST> 
erspan0@NONE     DOWN           00:00:00:00:00:00 <BROADCAST,MULTICAST> 
ip_vti0@NONE     DOWN           0.0.0.0 <NOARP> 
ip6_vti0@NONE    DOWN           :: <NOARP> 
sit0@NONE        DOWN           0.0.0.0 <NOARP> 
ip6tnl0@NONE     DOWN           :: <NOARP> 
ip6gre0@NONE     DOWN           :: <NOARP> 
eth0@if306       UP             7e:bd:7f:bb:7e:79 <BROADCAST,MULTICAST,UP,LOWER_UP> 

# --- ifconfig: legacy net-tools equivalent of ip a ---
root@ubuntu-hw:~# ifconfig
eth0: flags=4163<UP,BROADCAST,RUNNING,MULTICAST>  mtu 65535
        inet 172.17.0.7  netmask 255.255.0.0  broadcast 172.17.255.255
        ether 7e:bd:7f:bb:7e:79  txqueuelen 0  (Ethernet)
        RX packets 2680  bytes 58476894 (58.4 MB)
        RX errors 0  dropped 0  overruns 0  frame 0
        TX packets 1479  bytes 110377 (110.3 KB)
        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0

lo: flags=73<UP,LOOPBACK,RUNNING>  mtu 65536
        inet 127.0.0.1  netmask 255.0.0.0
        inet6 ::1  prefixlen 128  scopeid 0x10<host>
        loop  txqueuelen 1000  (Local Loopback)
        RX packets 0  bytes 0 (0.0 B)
        RX errors 0  dropped 0  overruns 0  frame 0
        TX packets 0  bytes 0 (0.0 B)
        TX errors 0  dropped 0 overruns 0  carrier 0  collisions 0


# --- hostname -I: every IP address assigned to this host, space separated ---
root@ubuntu-hw:~# hostname -I
172.17.0.7 

# --- hostname -f: the fully-qualified domain name ---
root@ubuntu-hw:~# hostname -f
ubuntu-hw

# --- /etc/hosts: static hostname -> IP mappings, checked before DNS ---
root@ubuntu-hw:~# cat /etc/hosts
127.0.0.1	localhost
::1	localhost ip6-localhost ip6-loopback
fe00::	ip6-localnet
ff00::	ip6-mcastprefix
ff02::1	ip6-allnodes
ff02::2	ip6-allrouters
172.17.0.7	ubuntu-hw

# --- /etc/resolv.conf: which DNS resolver(s) this host is configured to use ---
root@ubuntu-hw:~# cat /etc/resolv.conf
# Generated by Docker Engine.
# This file can be edited; Docker Engine will not make further changes once it
# has been modified.

nameserver 192.168.65.7

# Based on host file: '/etc/resolv.conf' (legacy)
# Overrides: []
```

### CIDR notation, explained by demo

```console
# --- -o = one line per address (no wrapping), -f inet = IPv4 only. ---
# --- The "a.b.c.d/NN" field IS the CIDR notation: NN is the prefix  ---
# --- length (bits reserved for network), 32-NN bits are host bits. ---
root@ubuntu-hw:~# ip -o -f inet a
1: lo    inet 127.0.0.1/8 scope host lo\       valid_lft forever preferred_lft forever
11: eth0    inet 172.17.0.7/16 brd 172.17.255.255 scope global eth0\       valid_lft forever preferred_lft forever
```
