# Assignment 3 — Networking Fundamentals

**Task 1:** Practice the commands and resources from the `devops-hero` repository (`session4-networking/ip.md`, `session4-networking/resources.md`).
**Task 2:** Run the networking commands, capture the real output, and explain what each one means.

Every block below is a command that was actually executed on this machine, followed by the output it actually printed.

---

## Lab Environment

| Item | Value |
| --- | --- |
| Host OS | macOS 26.5.2, Darwin kernel 25.5.0, `arm64` (Apple Silicon) |
| Linux used for `ip` / `ss` | `nicolaka/netshoot` container on Docker Desktop 29.4.1 |
| Host interface under test | `en0` (Wi-Fi) |
| Docker resources created | network `hw03-lab`, container `hw03-web` (nginx), throwaway `hw03-net*` containers |

### Why two machines?

macOS **does not ship the `ip` command**. `ip` comes from the Linux `iproute2` package. On macOS the equivalent tools are the older BSD ones: `ifconfig`, `netstat -rn`, `arp`, `route`.

So this lab runs each command on the platform where it is real:

* The **macOS** commands run natively in the terminal.
* The **Linux** commands (`ip a`, `ip route`, `ip neigh`, `ss`) run inside a Linux container, so the output is genuine Linux output and not a made-up example.

```bash
uname -a
```

```text
Darwin MacBook-Pro-7.local 25.5.0 Darwin Kernel Version 25.5.0: Tue Jun  9 22:28:34 PDT 2026; root:xnu-12377.121.10~1/RELEASE_ARM64_T6050 arm64
```

`Darwin` is the kernel name, so this is a BSD-family system, not Linux. That single word is what tells you `ip`, `ss`, and `/proc` will not be there.

> **Note on IP addresses in this document:** LAN and container addresses are shown exactly as captured. Upstream ISP router hops in the `traceroute` output are masked as `x.x.x.x`, and their reverse-DNS names as `<masked>`, because they identify the internet connection this was run from. Everything else is verbatim.

---

## Lab Setup — One Container to Inspect

A container that actually listens on a port gives the socket commands something real to find.

```bash
docker network create hw03-lab
docker run -d --name hw03-web --network hw03-lab -p 8080:80 nginx:alpine
docker ps --filter name=hw03- --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
```

```text
NAMES      IMAGE          STATUS         PORTS
hw03-web   nginx:alpine   Up 2 seconds   0.0.0.0:8080->80/tcp, [::]:8080->80/tcp
```

`0.0.0.0:8080->80/tcp` is the port mapping: anything that arrives at **port 8080 on the Mac** is forwarded to **port 80 inside the container**. Port 80 is the container's own port and is not reachable from the host by that number.

```bash
docker network inspect hw03-lab --format '{{json .IPAM.Config}}'
```

```text
[{"Subnet":"172.23.0.0/16","Gateway":"172.23.0.1"}]
```

Docker carved out the private subnet `172.23.0.0/16` for this network and made itself the gateway at `172.23.0.1`. Every container joined to `hw03-lab` gets an address inside that range. This is the same network model as any physical LAN, just implemented in software.

---

## Part 1 — IP and Interface Inspection

### 1.1 `ip a` (Linux)

**What it does:** lists every network interface and the IP addresses assigned to them. `a` is short for `address`.
**When you reach for it:** first command on any Linux box or in any container when something cannot be reached. It answers "does this machine even have an IP, and on which interface?"

```bash
docker run --rm --name hw03-net --network hw03-lab nicolaka/netshoot ip a
```

```text
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host proto kernel_lo
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
    link/tunnel6 :: brd :: permaddr de21:1d25:b3e0::
8: sit0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN group default qlen 1000
    link/sit 0.0.0.0 brd 0.0.0.0
9: ip6tnl0@NONE: <NOARP> mtu 1452 qdisc noop state DOWN group default qlen 1000
    link/tunnel6 :: brd :: permaddr 6e19:6c34:8d9d::
10: ip6gre0@NONE: <NOARP> mtu 1448 qdisc noop state DOWN group default qlen 1000
    link/gre6 :: brd :: permaddr 42d5:ca1c:3f8e::
11: eth0@if53: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP group default
    link/ether 4a:df:24:db:d8:d4 brd ff:ff:ff:ff:ff:ff link-netnsid 0
    inet 172.23.0.3/16 brd 172.23.255.255 scope global eth0
       valid_lft forever preferred_lft forever
```

**Reading this output:**

* `1: lo` — the **loopback** interface, always `127.0.0.1/8`. Traffic to it never leaves the machine. This is why a service bound to `127.0.0.1` is unreachable from outside, which is one of the most common "my app works locally but not from the LB" bugs.
* Interfaces 2 through 10 (`tunl0`, `gre0`, `sit0`, ...) are tunnel drivers the kernel registers by default. All say `state DOWN` and have no `inet` line, so they are noise. Ignore them.
* `11: eth0@if53` — the interface that matters. `UP,LOWER_UP` means the kernel enabled it **and** the link is actually carrying signal. `@if53` says this is one end of a **veth pair**, and its partner is interface index 53 in another namespace (on the Docker host). That pairing is exactly how a container is plugged into a bridge.
* `link/ether 4a:df:24:db:d8:d4` — the MAC address, the Layer 2 identity.
* `inet 172.23.0.3/16` — the IPv4 address and prefix. This container is `.3` inside the `172.23.0.0/16` network Docker created.
* `mtu 1500` — the largest frame this interface will send. Mismatched MTU across a VPN or overlay causes large packets to silently vanish while `ping` (small packets) still works.

### 1.2 `ip -br a` — the readable version

```bash
docker run --rm --name hw03-net --network hw03-lab nicolaka/netshoot ip -br a
```

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
eth0@if55        UP             172.23.0.3/16
```

`-br` means *brief*: one line per interface, name / state / addresses. This is the form worth memorising — it answers "which interfaces are up and what are their IPs" in a single screen. Note this was a fresh container, so the veth peer index is `if55` this time instead of `if53`; the index changes every time a container is created, the IP `172.23.0.3` did not because Docker reissued the same free address.

### 1.3 `ifconfig` — the macOS equivalent

**What it does:** the BSD tool that `ip a` replaced on Linux. Still the standard on macOS.
**When you reach for it:** same job — find the Mac's IP, MAC address, and interface state.

```bash
ifconfig -l
```

```text
lo0 gif0 stf0 anpi1 anpi2 anpi0 en3 en4 en5 en1 en6 en2 bridge0 utun0 utun1 utun2 utun3 utun4 ap1 en0 awdl0 llw0
```

A quick list of every interface name. On a Mac, `en0` is normally Wi-Fi, `lo0` is loopback, `utunN` are VPN tunnels, `bridge0` is used by virtualisation, and `awdl0`/`llw0` are Apple Wireless Direct Link (AirDrop / Continuity).

```bash
ifconfig en0
```

```text
en0: flags=8863<UP,BROADCAST,SMART,RUNNING,SIMPLEX,MULTICAST> mtu 1500
	options=6460<TSO4,TSO6,CHANNEL_IO,PARTIAL_CSUM,ZEROINVERT_CSUM>
	ether b6:02:d9:97:6d:91
	inet6 fe80::448:c7c1:353b:a04d%en0 prefixlen 64 secured scopeid 0xf
	inet 100.129.164.121 netmask 0xfffff000 broadcast 100.129.175.255
	nd6 options=201<PERFORMNUD,DAD>
	media: autoselect
	status: active
```

**Reading this output:**

* `UP` = administratively enabled, `RUNNING` = the link is live. Together they are the BSD version of Linux's `UP,LOWER_UP`.
* `ether b6:02:d9:97:6d:91` — the MAC. The `b6` first octet has the locally-administered bit set, which means macOS is using a **randomised private Wi-Fi MAC** for this network rather than the hardware burned-in one.
* `inet 100.129.164.121 netmask 0xfffff000` — this is the key line. BSD prints the mask in **hexadecimal**, not CIDR. `0xfffff000` = `255.255.240.0` = **/20**. Counting the `f`s is the trick: each `f` is 4 bits, five `f`s = 20 bits.
* `broadcast 100.129.175.255` — the last address in the /20, confirming the maths.
* `fe80::...%en0` — a link-local IPv6 address. Every IPv6-capable interface self-assigns one; it is only valid on the local link, which is why it is scoped with `%en0`.

`100.129.164.121` is worth calling out: it is inside `100.64.0.0/10`, which is **not** a normal private range and **not** public either. It is RFC 6598 *shared address space*, used by carrier-grade NAT (CGNAT). This connection sits behind the ISP's NAT as well as the local router's NAT.

```bash
ifconfig lo0
```

```text
lo0: flags=8049<UP,LOOPBACK,RUNNING,MULTICAST> mtu 16384
	options=1203<RXCSUM,TXCSUM,TXSTATUS,SW_TIMESTAMP>
	inet 127.0.0.1 netmask 0xff000000
	inet6 ::1 prefixlen 128
	inet6 fe80::1%lo0 prefixlen 64 scopeid 0x1
	nd6 options=201<PERFORMNUD,DAD>
```

The macOS loopback, `127.0.0.1/8` (`0xff000000` = `255.0.0.0` = /8). `mtu 16384` is huge because loopback traffic never touches a wire, so there is no physical frame size to respect.

```bash
ipconfig getifaddr en0
```

```text
100.129.164.121
```

The one-liner for "what is my LAN IP" on macOS. Perfect inside scripts, since it prints the address and nothing else.

### 1.4 Linux vs macOS — command equivalence

| Purpose | Linux (`iproute2`) | macOS / BSD |
| --- | --- | --- |
| List interfaces and IPs | `ip a` / `ip -br a` | `ifconfig` / `ifconfig -l` |
| One interface | `ip a show eth0` | `ifconfig en0` |
| Just the IPv4 address | `ip -4 -o a show eth0` | `ipconfig getifaddr en0` |
| Routing table | `ip route` | `netstat -rn` |
| Default gateway | `ip route show default` | `route -n get default` |
| ARP / neighbour cache | `ip neigh` | `arp -an` |
| Socket list | `ss -tulnp` | `netstat -an` + `lsof -i` |
| Bring interface up | `ip link set eth0 up` | `ifconfig en0 up` |

---

## Part 2 — Routing: How the Machine Decides Where to Send a Packet

### 2.1 `ip route` (Linux)

**What it does:** prints the kernel routing table — the ordered list of rules the kernel checks to pick an exit interface for each destination.
**When you reach for it:** the host has an IP but cannot reach anything, or reaches some networks and not others. Almost always a routing or gateway problem.

```bash
docker run --rm --name hw03-net --network hw03-lab nicolaka/netshoot ip route
```

```text
default via 172.23.0.1 dev eth0
172.23.0.0/16 dev eth0 proto kernel scope link src 172.23.0.3
```

Only two rules, and they cover everything:

1. `172.23.0.0/16 dev eth0 ... scope link` — anything inside this subnet is **directly reachable**. `scope link` means no gateway is needed; the kernel ARPs for the MAC and sends the frame straight out. `proto kernel` means the kernel added this route automatically when the IP was configured.
2. `default via 172.23.0.1 dev eth0` — everything else goes to the **default gateway**. `default` is shorthand for `0.0.0.0/0`, the least specific route possible, so it is only used when nothing else matches.

The kernel always uses the **longest prefix match**: `/16` beats `/0`, so local traffic never wastes a trip to the gateway.

### 2.2 `ip route get` — ask the kernel to decide for one destination

```bash
docker run --rm --name hw03-net --network hw03-lab nicolaka/netshoot ip route get 8.8.8.8
```

```text
8.8.8.8 via 172.23.0.1 dev eth0 src 172.23.0.3 uid 0
    cache
```

This is more useful than reading the whole table by hand. Instead of guessing which rule wins, the kernel tells you directly: to reach `8.8.8.8` it will go **via** `172.23.0.1`, **out** `eth0`, using **source address** `172.23.0.3`. That `src` field is what a firewall or a cloud security group on the other end will see, so this command answers "which source IP will my traffic appear to come from" in one shot.

### 2.3 `ip neigh` — the ARP table

```bash
docker run --rm --name hw03-net --network hw03-lab nicolaka/netshoot sh -c 'ping -c1 -W1 hw03-web >/dev/null 2>&1; ip neigh'
```

```text
172.23.0.2 dev eth0 lladdr 46:8a:4a:f0:b6:90 REACHABLE
```

ARP is the Layer 3 to Layer 2 bridge: IP addresses are for routing, but a frame on the wire needs a MAC. After pinging `hw03-web`, the kernel cached that `172.23.0.2` lives at MAC `46:8a:4a:f0:b6:90`, state `REACHABLE`. A neighbour stuck in `FAILED` or `INCOMPLETE` means the host is not answering ARP at all — the target is off, on a different VLAN, or blocked at Layer 2.

### 2.4 `netstat -rn` — the macOS routing table

**What it does:** same job as `ip route`. `-r` is the routing table, `-n` means show numbers instead of resolving names (much faster and does not lie to you when DNS is broken).

```bash
netstat -rn -f inet | head -12
```

```text
Routing tables

Internet:
Destination        Gateway            Flags               Netif Expire
default            100.129.160.1      UGScg                 en0
default            link#22            UCSIg               utun4
100.64/10          link#22            UCS                 utun4
100.64.37.109      100.64.37.109      UH                  utun4
100.100.100.100/32 link#22            UCS                 utun4
100.100.100.100    link#22            UHWIi               utun4
100.129.160/20     link#15            UCS                   en0
100.129.160.1/32   link#15            UCS                   en0
```

`-f inet` restricts the output to IPv4, and `head -12` is needed because the full macOS table also lists one cached host route per neighbour and runs to hundreds of lines.

**Reading this output:**

* `default 100.129.160.1 ... en0` — the default gateway is the router at `100.129.160.1`, reached over Wi-Fi.
* `100.129.160/20 link#15 en0` — the local subnet route, directly attached (`link#15` is `en0`'s interface index). This is the BSD equivalent of Linux's `scope link`.
* The `utun4` rows are a VPN tunnel claiming `100.64/10`, which is why traffic to those addresses leaves through the tunnel rather than the Wi-Fi.
* **Flags** are the part people skip and should not:
  * `U` = route is Up
  * `G` = Gateway (next hop is a router, not directly attached)
  * `H` = Host route (a single /32, not a network)
  * `S` = Static (manually or config added)
  * `C` = Cloning (generates child routes for individual hosts)
  * `I` = Scoped to an interface
  * `W` = route was auto-cloned from a parent route

  So `UGScg` on the default route reads as: up, uses a gateway, static, cloning.

### 2.5 `route -n get default` — one clean answer

```bash
route -n get default
```

```text
   route to: default
destination: default
       mask: default
    gateway: 100.129.160.1
  interface: en0
      flags: <UP,GATEWAY,DONE,STATIC,PRCLONING,GLOBAL>
 recvpipe  sendpipe  ssthresh  rtt,msec    rttvar  hopcount      mtu     expire
       0         0         0         0         0         0      1500         0
```

The macOS counterpart of `ip route get`. It skips the giant table and answers plainly: gateway `100.129.160.1`, out of `en0`, MTU 1500. This is the fastest way to get the default gateway on a Mac.

---

## Part 3 — Connectivity: `ping` and `traceroute`

### 3.1 `ping` to an IP

**What it does:** sends ICMP Echo Request packets and times the Echo Replies.
**When you reach for it:** the very first reachability test. It proves Layer 3 works end to end, with zero dependence on DNS or on any application.

```bash
ping -c 4 8.8.8.8
```

```text
PING 8.8.8.8 (8.8.8.8): 56 data bytes
64 bytes from 8.8.8.8: icmp_seq=0 ttl=116 time=115.280 ms
64 bytes from 8.8.8.8: icmp_seq=1 ttl=116 time=45.738 ms
64 bytes from 8.8.8.8: icmp_seq=2 ttl=116 time=25.917 ms
64 bytes from 8.8.8.8: icmp_seq=3 ttl=116 time=10.724 ms

--- 8.8.8.8 ping statistics ---
4 packets transmitted, 4 packets received, 0.0% packet loss
round-trip min/avg/max/stddev = 10.724/49.415/115.280/40.003 ms
```

**Reading this output:**

* `0.0% packet loss` — the path is intact. Loss above zero on a wired path is a real problem; on Wi-Fi a few percent can be normal.
* `time=` values — round-trip time. Note the first is `115 ms` and the rest drop to `10–45 ms`. That first-packet spike is typical: the ARP lookup, radio wake-up, and route cache population all happen on packet one. **Always ignore the first ping when judging latency.**
* `ttl=116` — Time To Live as it arrived. Routers start it at 64, 128, or 255 and decrement by one per hop. Arriving at 116 from a likely start of 128 means roughly **12 router hops** away. TTL also prevents routing loops: at zero the packet is dropped.
* `stddev 40.003` — jitter. High jitter matters far more than high average latency for voice, video, and chatty database protocols.

### 3.2 `ping` to a hostname — a DNS test too

```bash
ping -c 4 google.com
```

```text
PING google.com (142.251.43.142): 56 data bytes
64 bytes from 142.251.43.142: icmp_seq=0 ttl=117 time=127.090 ms
64 bytes from 142.251.43.142: icmp_seq=1 ttl=117 time=20.825 ms
64 bytes from 142.251.43.142: icmp_seq=2 ttl=117 time=32.485 ms
64 bytes from 142.251.43.142: icmp_seq=3 ttl=117 time=20.672 ms

--- google.com ping statistics ---
4 packets transmitted, 4 packets received, 0.0% packet loss
round-trip min/avg/max/stddev = 20.672/50.268/127.090/44.611 ms
```

The first line, `PING google.com (142.251.43.142)`, already proves DNS resolved. This is the classic triage pair: **`ping 8.8.8.8` works but `ping google.com` fails means DNS is broken, not the network.**

### 3.3 `ping` between containers — Docker's built-in DNS

```bash
docker run --rm --name hw03-net3 --network hw03-lab nicolaka/netshoot ping -c 3 hw03-web
```

```text
PING hw03-web (172.23.0.2) 56(84) bytes of data.
64 bytes from hw03-web.hw03-lab (172.23.0.2): icmp_seq=1 ttl=64 time=0.060 ms
64 bytes from hw03-web.hw03-lab (172.23.0.2): icmp_seq=2 ttl=64 time=0.051 ms
64 bytes from hw03-web.hw03-lab (172.23.0.2): icmp_seq=3 ttl=64 time=0.036 ms

--- hw03-web statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2054ms
rtt min/avg/max/mdev = 0.036/0.049/0.060/0.009 ms
```

Three things this proves at once:

* The **container name resolved to an IP** — a user-defined Docker network gives you automatic DNS by container name. On the default `bridge` network it would not.
* The reply shows `hw03-web.hw03-lab`, the fully qualified name: container name plus network name.
* `ttl=64` unchanged and `time=0.036 ms`. TTL still at its starting value means **zero routers were crossed** — both containers are on the same bridge, so this is a pure Layer 2 hop. Sub-millisecond RTT confirms it never left the machine.

### 3.4 `traceroute`

**What it does:** discovers every router between you and the destination, by sending packets with TTL=1, then 2, then 3. Each router that decrements TTL to zero must reply "Time Exceeded", which reveals its address.
**When you reach for it:** `ping` fails or is slow and you need to know **where** on the path it breaks, or you want to confirm traffic is taking the route you expect (through a VPN, a NAT gateway, a specific region).

```bash
traceroute -m 12 -w 1 -q 1 google.com
```

```text
traceroute to google.com (142.250.206.174), 12 hops max, 40 byte packets
 1  <masked> (100.129.160.1)  82.880 ms
 2  x.x.x.x  12.794 ms
 3  x.x.x.x  20.394 ms
 4  172.28.117.90 (172.28.117.90)  18.019 ms
 5  x.x.x.x  20.272 ms
 6  *
 7  142.251.55.68 (142.251.55.68)  18.781 ms
 8  142.250.239.56 (142.250.239.56)  20.459 ms
 9  *
10  192.178.254.236 (192.178.254.236)  40.440 ms
11  72.14.232.79 (72.14.232.79)  28.073 ms
12  72.14.237.139 (72.14.237.139)  27.894 ms
```

Flags used: `-m 12` caps it at 12 hops, `-w 1` waits only 1 second per probe, `-q 1` sends one probe per hop instead of three. Without these, a traceroute with unresponsive hops takes minutes.

**Reading this output:**

* **Hop 1** is `100.129.160.1` — the same default gateway `netstat -rn` reported. The path always starts at your own router.
* **Hops 2, 3, 5** are the ISP's edge and backbone routers (masked here).
* **Hop 4, `172.28.117.90`** is an RFC 1918 private address appearing mid-path. That is normal: ISPs commonly number their internal backbone links with private space, and those addresses are not reachable from the internet.
* **Hops 6 and 9 show `*`** — no reply within the timeout. This is the single most misread part of traceroute. A `*` almost never means a broken link. It means that router is configured not to send ICMP Time Exceeded, or rate-limits it. **Traffic still passed through it**, which is proven by hops 7 onwards answering. Only a `*` on *every* hop from some point to the end indicates a genuine break.
* **Hops 7 to 12** are Google's own backbone. Latency stays flat at 18–40 ms, so there is no congested hop.
* Notice hop 1 at `82 ms` is slower than hop 12 at `27 ms`. That is not a slow router — routers de-prioritise generating ICMP replies for themselves. **Judge the path by the final hop, not by intermediate spikes.**

### 3.5 `traceroute` from inside a container

```bash
docker run --rm --name hw03-net5 --network hw03-lab nicolaka/netshoot traceroute -m 6 -w 1 -q 1 1.1.1.1
```

```text
traceroute to 1.1.1.1 (1.1.1.1), 6 hops max, 46 byte packets
 1  172.23.0.1 (172.23.0.1)  0.005 ms
 2  *
 3  *
 4  *
 5  *
 6  *
```

An honest and instructive result. Hop 1 is the Docker bridge gateway. Everything after that is `*` because Docker Desktop on macOS runs containers inside a Linux VM whose NAT layer does not relay the ICMP Time Exceeded messages back into the container.

**The lesson:** `traceroute` is unreliable inside containers and behind aggressive NAT. The container clearly *has* connectivity — the same containers resolved DNS and fetched HTTP successfully — so a `*`-filled traceroute is not evidence of a network fault. Confirm with `curl` or `nc` before concluding anything.

---

## Part 4 — DNS: `dig`, `nslookup`, `host`

### 4.1 `dig` — a full A record lookup

**What it does:** queries DNS and prints the complete protocol response — every section, every TTL, and which server answered.
**When you reach for it:** any time a name does not resolve, resolves to the wrong address, or you need to check whether a DNS change has propagated. It is the tool of choice because it shows you everything, not a summary.

```bash
dig github.com A
```

```text
; <<>> DiG 9.10.6 <<>> github.com A
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 20929
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 8, ADDITIONAL: 8

;; QUESTION SECTION:
;github.com.			IN	A

;; ANSWER SECTION:
github.com.		20	IN	A	20.207.73.82

;; AUTHORITY SECTION:
github.com.		156498	IN	NS	dns2.p08.nsone.net.
github.com.		156498	IN	NS	dns3.p08.nsone.net.
github.com.		156498	IN	NS	ns-1283.awsdns-32.org.
github.com.		156498	IN	NS	ns-1707.awsdns-21.co.uk.
github.com.		156498	IN	NS	ns-520.awsdns-01.net.
github.com.		156498	IN	NS	dns4.p08.nsone.net.
github.com.		156498	IN	NS	dns1.p08.nsone.net.
github.com.		156498	IN	NS	ns-421.awsdns-52.com.

;; ADDITIONAL SECTION:
dns2.p08.nsone.net.	45064	IN	A	198.51.45.8
dns3.p08.nsone.net.	61782	IN	A	198.51.44.72
ns-1283.awsdns-32.org.	64554	IN	A	205.251.197.3
ns-1707.awsdns-21.co.uk. 44096	IN	A	205.251.198.171
ns-520.awsdns-01.net.	115682	IN	A	205.251.194.8
dns4.p08.nsone.net.	45064	IN	A	198.51.45.72
dns1.p08.nsone.net.	143758	IN	A	198.51.44.8
ns-421.awsdns-52.com.	76623	IN	A	205.251.193.165

;; Query time: 58 msec
;; SERVER: 100.100.100.100#53(100.100.100.100)
;; WHEN: Thu Sep 17 21:39:40 IST 2026
;; MSG SIZE  rcvd: 395
```

**Reading each section:**

**HEADER line** — `status: NOERROR` is the one to check first. The common failure codes are:

| Status | Meaning |
| --- | --- |
| `NOERROR` | Query succeeded. An empty ANSWER section still means the name exists but has no record of that type. |
| `NXDOMAIN` | The name does not exist at all. Usually a typo or a record that was never created. |
| `SERVFAIL` | The resolver tried and failed — upstream is down, or DNSSEC validation failed. |
| `REFUSED` | The server exists but will not answer you. Often an ACL on an internal resolver. |

**`flags: qr rd ra`** —
* `qr` = this is a Query Response,
* `rd` = Recursion Desired (I asked the server to do the full lookup for me),
* `ra` = Recursion Available (the server is willing to).
Notably **`aa` is absent**, so this is *not* an authoritative answer — it came from a cache.

**QUESTION SECTION** — echoes exactly what was asked: `github.com.` `IN` (Internet class) `A` (IPv4 address record). The trailing dot is the DNS root; every fully qualified name really ends in one.

**ANSWER SECTION** — the actual result:

```text
github.com.		20	IN	A	20.207.73.82
```

Five fields: **name**, **TTL in seconds**, **class**, **record type**, **value**. So `github.com` resolves to `20.207.73.82`, and this answer may be cached for **20 more seconds**. That low TTL is deliberate — GitHub uses geo-based routing and wants to be able to move traffic quickly. `20.207.73.82` is a Microsoft Azure address in the India region, which is why it was returned to a client in India; someone in the US would get a different IP for the same name.

**AUTHORITY SECTION** — the eight nameservers that are authoritative for `github.com`. Four are NS1 (`nsone.net`) and four are AWS Route 53 (`awsdns`). Running two independent DNS providers is a deliberate resilience pattern: the 2016 Dyn outage took down single-provider sites, and this is the fix.

**ADDITIONAL SECTION** — free glue: the A records of those nameservers, so a resolver does not need a second round trip to find them.

**Footer** — `Query time: 58 msec` (fast, so probably cached) and `SERVER: 100.100.100.100#53` tells you **which resolver answered**, on the standard DNS port **53**. Here that is a VPN's internal DNS resolver. This line is the one people forget, and it is often the whole answer to "why do I get a different result than my colleague".

### 4.2 `dig +short` — for scripts

```bash
dig +short github.com A
```

```text
20.207.73.82
```

Just the value. This is the form to use inside shell scripts, health checks, and CI pipelines.

### 4.3 `dig` a CNAME chain

```bash
dig www.github.com
```

```text
; <<>> DiG 9.10.6 <<>> www.github.com
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 23132
;; flags: qr rd ra; QUERY: 1, ANSWER: 2, AUTHORITY: 0, ADDITIONAL: 1

;; OPT PSEUDOSECTION:
; EDNS: version: 0, flags:; udp: 512
;; QUESTION SECTION:
;www.github.com.			IN	A

;; ANSWER SECTION:
www.github.com.		3257	IN	CNAME	github.com.
github.com.		60	IN	A	20.207.73.82

;; Query time: 77 msec
;; SERVER: 100.100.100.100#53(100.100.100.100)
;; WHEN: Thu Sep 17 21:39:42 IST 2026
;; MSG SIZE  rcvd: 73
```

`ANSWER: 2` because the answer is a **chain**. An `A` record was requested, but `www.github.com` is a `CNAME` (alias) pointing at `github.com`, so the resolver followed it and returned both records. This is exactly how a DNS record for an AWS load balancer or a CDN endpoint looks, and it is why the two hops can have different TTLs (3257 vs 60): the alias rarely changes, the target IP changes often.

### 4.4 Querying a specific resolver

```bash
dig @8.8.8.8 +noall +answer github.com A
```

```text
github.com.		26	IN	A	20.207.73.82
```

`@8.8.8.8` bypasses the configured resolver and asks Google Public DNS directly. `+noall +answer` strips everything except the answer section.

This is the standard way to **prove whether a DNS problem is yours or theirs**. If `dig @8.8.8.8 name` works but `dig name` does not, the fault is in your local resolver or `/etc/resolv.conf`, not in the zone.

### 4.5 Reverse lookup

```bash
dig -x 8.8.8.8 +short
```

```text
dns.google.
```

`-x` does a reverse (PTR) lookup: IP back to name. Internally it queries `8.8.8.8.in-addr.arpa`. Useful for identifying an unknown IP in a log file or a firewall deny entry. Note that forward and reverse DNS are separate zones, so a reverse record may be missing or may not match — some mail servers reject senders whose reverse DNS does not match, which makes this a real production check.

### 4.6 `nslookup`

**What it does:** the older, cross-platform DNS query tool. Present on Linux, macOS, and Windows.
**When you reach for it:** quick checks, and any time you are on a Windows box where `dig` is not installed.

```bash
nslookup github.com
```

```text
Server:		100.100.100.100
Address:	100.100.100.100#53

Non-authoritative answer:
Name:	github.com
Address: 20.207.73.82
```

Same information as `dig`, much less of it. `Server` is the resolver used. **"Non-authoritative answer"** means it came from that resolver's cache rather than from `github.com`'s own nameservers — which is normal and expected for almost every lookup you will ever do. `dig` conveys the same thing by the absence of the `aa` flag.

`nslookup` is fine for a quick check, but it hides TTLs, the authority section, and the record type, so `dig` is the better habit for debugging.

### 4.7 `host`

**What it does:** the simplest of the three. One line per record.
**When you reach for it:** when you just want the answer.

```bash
host github.com
```

```text
github.com has address 20.207.73.82
github.com mail is handled by 0 github-com.mail.protection.outlook.com.
```

Human-readable output with no DNS jargon. Note it volunteered the **MX record** too — `host` returns A, AAAA, and MX by default. The `0` is the MX priority, where lower wins. This tells you GitHub's inbound mail runs on Microsoft 365.

### 4.8 DNS inside a container

```bash
docker run --rm --name hw03-net6 --network hw03-lab nicolaka/netshoot cat /etc/resolv.conf
```

```text
# Generated by Docker Engine.
# This file can be edited; Docker Engine will not make further changes once it
# has been modified.

nameserver 127.0.0.11
options ndots:0

# Based on host file: '/etc/resolv.conf' (internal resolver)
# ExtServers: [host(192.168.65.7)]
# Overrides: []
# Option ndots from: internal
```

`/etc/resolv.conf` is the file that tells any Unix machine which DNS server to use. Inside a container on a user-defined network it points at **`127.0.0.11`**, Docker's embedded DNS server. That address is a loopback address, so it only exists inside this container's network namespace. Docker resolves container names locally and forwards anything else to the host's real resolvers (`ExtServers`).

```bash
docker run --rm --name hw03-net2 --network hw03-lab nicolaka/netshoot dig hw03-web
```

```text
; <<>> DiG 9.20.23 <<>> hw03-web
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 47114
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 0

;; QUESTION SECTION:
;hw03-web.			IN	A

;; ANSWER SECTION:
hw03-web.		600	IN	A	172.23.0.2

;; Query time: 1 msec
;; SERVER: 127.0.0.11#53(127.0.0.11)
;; WHEN: Thu Sep 17 16:13:26 UTC 2026
;; MSG SIZE  rcvd: 50
```

The container name `hw03-web` is a real DNS A record resolving to `172.23.0.2`, served by `127.0.0.11` in **1 msec**. This is precisely the mechanism behind Docker Compose service names and, scaled up, behind Kubernetes Service DNS — you never hardcode an IP, you use the name and let the platform's DNS point it at whatever is currently running.

---

## Part 5 — Ports and Sockets

### 5.1 `ss -tulnp` (Linux)

**What it does:** lists sockets. `ss` = socket statistics, the modern replacement for `netstat` on Linux (it reads kernel netlink directly instead of parsing `/proc`, so it is much faster on busy hosts).
**When you reach for it:** "is my service actually listening, and on which address?" This is the first command after a deploy when something returns connection refused.

The flags, which are worth learning as one word:

| Flag | Meaning |
| --- | --- |
| `-t` | TCP sockets |
| `-u` | UDP sockets |
| `-l` | listening only |
| `-n` | numeric, do not resolve ports to names |
| `-p` | show the owning process |

```bash
docker run --rm --name hw03-net --network container:hw03-web --pid container:hw03-web nicolaka/netshoot ss -tulnp
```

```text
Netid State  Recv-Q Send-Q Local Address:Port  Peer Address:PortProcess
udp   UNCONN 0      0         127.0.0.11:37326      0.0.0.0:*
tcp   LISTEN 0      511          0.0.0.0:80         0.0.0.0:*    users:(("nginx",pid=1,fd=6))
tcp   LISTEN 0      4096      127.0.0.11:34617      0.0.0.0:*
tcp   LISTEN 0      511             [::]:80            [::]:*    users:(("nginx",pid=1,fd=7))
```

`--network container:hw03-web` puts the netshoot container **inside the nginx container's network namespace**, and `--pid container:hw03-web` shares its process namespace. This is the standard trick for debugging a container that has no tools installed — you never need to install `curl` or `ss` into a production image.

**Reading this output:**

* `tcp LISTEN 0.0.0.0:80` with `users:(("nginx",pid=1,fd=6))` — nginx is listening on **port 80 on all IPv4 addresses**. `0.0.0.0` is the critical detail: had it said `127.0.0.1:80`, the container would answer itself and refuse everyone else. That single difference is the cause of a large share of "works in the container, fails from outside" incidents.
* The `[::]:80` line is the same socket for IPv6.
* `pid=1` — nginx is PID 1, the container's init process. When PID 1 exits, the container stops.
* `Send-Q 511` on a listening socket is **not** a queue length, it is the **accept backlog**: how many completed connections the kernel will hold before refusing new ones. nginx's default is 511. A `Recv-Q` climbing above zero on a listener means the application is not calling `accept()` fast enough.
* `127.0.0.11` on both TCP and UDP is Docker's embedded DNS server, the same one `/etc/resolv.conf` pointed at.

Without the shared PID namespace, the Process column is empty:

```bash
docker run --rm --name hw03-net --network container:hw03-web nicolaka/netshoot ss -tulnp
```

```text
Netid State  Recv-Q Send-Q Local Address:Port  Peer Address:PortProcess
udp   UNCONN 0      0         127.0.0.11:37326      0.0.0.0:*
tcp   LISTEN 0      511          0.0.0.0:80         0.0.0.0:*
tcp   LISTEN 0      4096      127.0.0.11:34617      0.0.0.0:*
tcp   LISTEN 0      511             [::]:80            [::]:*
```

The sockets are visible because the **network** namespace is shared, but the process names are not, because the **PID** namespace is not. That is namespace isolation made concrete: a container is not a small VM, it is a process with a selected set of namespaces.

### 5.2 `ss -s` — socket summary

```bash
docker run --rm --name hw03-net --network container:hw03-web nicolaka/netshoot ss -s
```

```text
Total: 35
TCP:   65 (estab 0, closed 62, orphaned 0, timewait 0)

Transport Total     IP        IPv6
RAW	  0         0         0
UDP	  1         1         0
TCP	  3         2         1
INET	  4         3         1
FRAG	  0         0         0
```

A one-screen health check. In production the numbers that matter are **`timewait`** and **`orphaned`**. Tens of thousands of sockets in `timewait` usually means a client is opening a new TCP connection per request instead of reusing one, and you are heading for port exhaustion.

### 5.3 `netstat -tulnp` (Linux) — the older equivalent

```bash
docker run --rm --name hw03-net --network container:hw03-web nicolaka/netshoot netstat -tulnp
```

```text
Active Internet connections (only servers)
Proto Recv-Q Send-Q Local Address           Foreign Address         State       PID/Program name
tcp        0      0 0.0.0.0:80              0.0.0.0:*               LISTEN      -
tcp        0      0 127.0.0.11:34617        0.0.0.0:*               LISTEN      -
tcp        0      0 :::80                   :::*                    LISTEN      -
udp        0      0 127.0.0.11:37326        0.0.0.0:*                           -
```

Same information, older format, same flag letters. `netstat` is deprecated on Linux (it lives in `net-tools`, often not installed on slim images) but you will still meet it constantly in older runbooks. The `-` under PID here is again the PID namespace, not a permissions problem.

### 5.4 `netstat -an` on macOS

macOS has no `ss`, and its `netstat` does **not** accept the Linux `-tulnp` flags. The BSD form is:

```bash
netstat -an -f inet -p tcp | grep -i listen | head -15
```

```text
tcp46      0      0  *.61891                *.*                    LISTEN
tcp46      0      0  *.61890                *.*                    LISTEN
tcp4       0      0  *.57741                *.*                    LISTEN
tcp4       0      0  127.0.0.1.19322        *.*                    LISTEN
tcp4       0      0  127.0.0.1.35876        *.*                    LISTEN
tcp4       0      0  127.0.0.1.37370        *.*                    LISTEN
tcp4       0      0  127.0.0.1.4040         *.*                    LISTEN
tcp4       0      0  127.0.0.1.62128        *.*                    LISTEN
tcp4       0      0  127.0.0.1.52066        *.*                    LISTEN
tcp4       0      0  127.0.0.1.37175        *.*                    LISTEN
tcp4       0      0  *.39376                *.*                    LISTEN
tcp4       0      0  127.0.0.1.54515        *.*                    LISTEN
tcp4       0      0  127.0.0.1.55175        *.*                    LISTEN
tcp4       0      0  *.5000                 *.*                    LISTEN
tcp4       0      0  *.7000                 *.*                    LISTEN
```

Two BSD quirks to notice:

* The port is separated by a **dot**, not a colon: `127.0.0.1.4040` means IP `127.0.0.1`, port `4040`.
* `*` means all addresses (BSD's way of writing `0.0.0.0`), and `tcp46` means one socket serving both IPv4 and IPv6.

The important distinction is still address scope. `127.0.0.1.4040` is bound to loopback and is unreachable from any other machine. `*.5000` is bound to every interface and **is** reachable from the LAN.

The big gap: BSD `netstat` will not tell you **which process** owns a socket. For that you need `lsof`.

### 5.5 `lsof -i` — which process owns which port

**What it does:** `lsof` = *list open files*. Since a socket is a file descriptor on Unix, `-i` filters to network sockets and shows the owning command and PID.
**When you reach for it:** "port 8080 is already in use" — this is the command that names the culprit. It is the macOS answer to `ss -tulnp`.

```bash
lsof -nP -iTCP -sTCP:LISTEN | head -15
```

```text
COMMAND     PID USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
rapportd    425 aman   10u  IPv4 0xfc0f0126ef5bb9c7      0t0  TCP *:57741 (LISTEN)
rapportd    425 aman   11u  IPv6 0x4d931fbbd5ff44bf      0t0  TCP *:57741 (LISTEN)
rapportd    425 aman   18u  IPv6 0x501542798902f247      0t0  TCP *:61890 (LISTEN)
rapportd    425 aman   20u  IPv6 0x560330a76a5b1d27      0t0  TCP *:61891 (LISTEN)
ControlCe   552 aman    9u  IPv4 0x47e044a193c6c417      0t0  TCP *:7000 (LISTEN)
ControlCe   552 aman   10u  IPv6 0xa9f70e2ee9af322e      0t0  TCP *:7000 (LISTEN)
ControlCe   552 aman   11u  IPv4 0x925a3171ffd61fd6      0t0  TCP *:5000 (LISTEN)
ControlCe   552 aman   12u  IPv6 0xc5c2b891dee1ce0e      0t0  TCP *:5000 (LISTEN)
DrSprinto  1517 aman   44u  IPv4 0xe544dda509289c28      0t0  TCP 127.0.0.1:37370 (LISTEN)
Code\x20H  7691 aman   45u  IPv4 0x2ab39c5f49dc6eb0      0t0  TCP 127.0.0.1:37175 (LISTEN)
Code\x20H  7691 aman  111u  IPv4 0x89847d84a8806721      0t0  TCP 127.0.0.1:62128 (LISTEN)
Code\x20H  8360 aman   24u  IPv4 0xefd8d54c0827116e      0t0  TCP 127.0.0.1:52066 (LISTEN)
Code\x20H 21137 aman   38u  IPv4 0x355abc70a40f05ed      0t0  TCP 127.0.0.1:35876 (LISTEN)
Code\x20H 21788 aman   64u  IPv4 0x8ecab073688acd5d      0t0  TCP 127.0.0.1:19322 (LISTEN)
```

Flags: `-n` skips hostname resolution, `-P` skips port-name resolution (so you see `443`, not `https`), `-iTCP` limits to TCP, `-sTCP:LISTEN` limits to listening state. `-nP` is worth always using — it makes the command return instantly instead of waiting on reverse DNS.

**Reading this output:** now every port has a name attached. `ControlCe` (macOS Control Center, which hosts AirPlay Receiver) is holding **ports 5000 and 7000** — this is the well-known reason a Flask app on port 5000 mysteriously fails to bind on a Mac. `Code\x20H` is a VS Code Helper process. `FD` values like `10u` mean file descriptor 10, opened for read/write.

Established connections work the same way:

```bash
lsof -nP -iTCP -sTCP:ESTABLISHED | head -10
```

```text
COMMAND     PID USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
DrSprinto  1517 aman   63u  IPv4  0x9e29a8fedc3a239      0t0  TCP 127.0.0.1:37370->127.0.0.1:56811 (ESTABLISHED)
Tailscale  1522 aman    6u  IPv4 0xf6b564044668056a      0t0  TCP 127.0.0.1:59819->127.0.0.1:54515 (ESTABLISHED)
DrSprinto  1611 aman   20u  IPv4 0xd21d7612d3866932      0t0  TCP 127.0.0.1:56811->127.0.0.1:37370 (ESTABLISHED)
Code\x20H  7691 aman   71u  IPv4 0xd2ac08aa91605247      0t0  TCP 127.0.0.1:37175->127.0.0.1:54247 (ESTABLISHED)
codex      8157 aman   17u  IPv4  0x7d658de89d4261d      0t0  TCP 100.129.164.121:58919->172.64.155.209:443 (ESTABLISHED)
Slack\x20 11564 aman   24u  IPv4 0x4016ecfcb62483ce      0t0  TCP 100.129.164.121:59058->13.126.138.201:443 (ESTABLISHED)
Slack\x20 11564 aman   25u  IPv4 0x41acef54624f2ac5      0t0  TCP 100.129.164.121:58883->151.101.208.106:443 (ESTABLISHED)
Slack\x20 11564 aman   29u  IPv4 0x1040108c1c44baf2      0t0  TCP 100.129.164.121:59107->34.195.221.192:443 (ESTABLISHED)
Slack\x20 11564 aman   32u  IPv4 0x865e30e82bf5b097      0t0  TCP 100.129.164.121:59138->65.1.97.76:443 (ESTABLISHED)
```

Each line is a full TCP 4-tuple: `local IP:local port -> remote IP:remote port`. That 4-tuple is what uniquely identifies a connection, and it is why one server port can serve thousands of clients at once.

The local ports (`58919`, `59058`, `59107`) are **ephemeral ports** — high-numbered ports the kernel picks at random for outbound connections. The remote port is always `443`, so every one of these is outbound HTTPS. Slack alone holds four connections to four different servers, which is normal for a modern app talking to a CDN plus several backend regions.

### 5.6 Tying the host port back to the container

```bash
lsof -nP -iTCP:8080 -sTCP:LISTEN
```

```text
COMMAND     PID USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
com.docke 98796 aman  179u  IPv6 0x8260d965b3dce30f      0t0  TCP *:8080 (LISTEN)
```

The process listening on 8080 on the Mac is **not nginx** — it is `com.docker.backend`. Docker's userland proxy holds the host port and forwards every connection into the container's namespace. This is what `-p 8080:80` actually builds, and seeing it makes the port-publishing model concrete rather than magic.

### 5.7 `nc -zv` — is a port open?

**What it does:** netcat with `-z` (scan only, send no data) and `-v` (verbose) tests whether a TCP port accepts connections.
**When you reach for it:** checking a firewall or security group rule without needing a client for that protocol. It answers Layer 4 reachability while `ping` only answers Layer 3.

```bash
nc -zv -G 3 github.com 443
nc -zv -G 3 github.com 3306
```

```text
Connection to github.com port 443 [tcp/https] succeeded!
nc: connectx to github.com port 3306 (tcp) failed: Operation timed out
```

Two different outcomes, and the difference matters:

* Port **443 succeeded** — the TCP handshake completed, so something is listening and nothing in between blocked it.
* Port **3306 timed out**. Note it did *not* say "connection refused". The distinction is the useful part:
  * **Connection refused** = the packet reached the host and the host actively sent a TCP RST. Nothing is listening on that port, but the host is reachable and the firewall let you through.
  * **Timed out** = no reply at all. A firewall is silently dropping the packet, which is the standard, deliberate behaviour of a cloud security group or a WAF.

Recognising "refused vs timeout" on sight is the fastest way to split an application problem (refused: service is down) from a network problem (timeout: firewall rule missing).

---

## Part 6 — HTTP with `curl`

### 6.1 `curl -I` — headers only

**What it does:** sends an HTTP `HEAD` request and prints only the response status line and headers, never the body.
**When you reach for it:** health checks, verifying a redirect, checking cache and security headers, confirming which server or CDN answered — all without downloading a megabyte of HTML.

```bash
curl -sI https://example.com
```

```text
HTTP/2 200
date: Thu, 17 Sep 2026 16:10:29 GMT
content-type: text/html
server: cloudflare
last-modified: Tue, 15 Sep 2026 23:38:37 GMT
allow: GET, HEAD
accept-ranges: bytes
age: 3555
cf-cache-status: HIT
cf-ray: a3c9619fdc91560f-MAA
```

(`-s` silences the progress meter, which otherwise prints over the output.)

**Reading this output:**

* **`HTTP/2 200`** — the status line. `HTTP/2` means the connection negotiated HTTP/2 rather than 1.1 (visible in the `curl -v` ALPN exchange below), and `200` is success. The status code families are worth knowing cold: `2xx` success, `3xx` redirect, `4xx` your request was wrong, `5xx` the server broke.
* `server: cloudflare` — you are talking to a CDN edge, not the origin.
* `cf-cache-status: HIT` and `age: 3555` — this response came from Cloudflare's cache and has been sitting there for 3555 seconds. A `MISS` would mean the edge had to fetch it from origin. When a deploy "does not show up", this pair of headers is usually the explanation.
* `cf-ray: ...-MAA` — Cloudflare's request ID. The `MAA` suffix is the IATA code for **Mumbai**, so the nearest edge served it. Quote this ID in a support ticket and they can find the exact request.
* `allow: GET, HEAD` — this endpoint is read-only.

### 6.2 `curl -v` — the whole conversation

**What it does:** verbose mode. Shows DNS resolution, TCP connection, the full TLS handshake, the request sent, and the response received.
**When you reach for it:** when the request fails and you need to know *which layer* failed — DNS, TCP, TLS, or HTTP. Every line prefix tells you who is speaking: `*` is curl's own commentary, `>` is data sent, `<` is data received.

```bash
curl -v -s -o /dev/null https://example.com
```

```text
* Host example.com:443 was resolved.
* IPv6: 2606:4700:10::6814:179a, 2606:4700:10::ac42:93f3
* IPv4: 104.20.23.154, 172.66.147.243
*   Trying 104.20.23.154:443...
*   Trying [2606:4700:10::6814:179a]:443...
* Immediate connect fail for 2606:4700:10::6814:179a: No route to host
*   Trying [2606:4700:10::ac42:93f3]:443...
* Immediate connect fail for 2606:4700:10::ac42:93f3: No route to host
* Connected to example.com (104.20.23.154) port 443
* ALPN: curl offers h2,http/1.1
* (304) (OUT), TLS handshake, Client hello (1):
} [316 bytes data]
*  CAfile: /etc/ssl/cert.pem
*  CApath: none
* (304) (IN), TLS handshake, Server hello (2):
{ [122 bytes data]
* (304) (IN), TLS handshake, Unknown (8):
{ [19 bytes data]
* (304) (IN), TLS handshake, Certificate (11):
{ [3686 bytes data]
* (304) (IN), TLS handshake, CERT verify (15):
{ [79 bytes data]
* (304) (IN), TLS handshake, Finished (20):
{ [36 bytes data]
* (304) (OUT), TLS handshake, Finished (20):
} [36 bytes data]
* SSL connection using TLSv1.3 / AEAD-CHACHA20-POLY1305-SHA256 / [blank] / UNDEF
* ALPN: server accepted h2
* Server certificate:
*  subject: CN=example.com
*  start date: Jul 29 22:10:08 2026 GMT
*  expire date: Oct 27 22:17:21 2026 GMT
*  subjectAltName: host "example.com" matched cert's "example.com"
*  issuer: C=US; O=SSL Corporation; CN=Cloudflare TLS Issuing ECC CA 3
*  SSL certificate verify ok.
* using HTTP/2
* [HTTP/2] [1] OPENED stream for https://example.com/
* [HTTP/2] [1] [:method: GET]
* [HTTP/2] [1] [:scheme: https]
* [HTTP/2] [1] [:authority: example.com]
* [HTTP/2] [1] [:path: /]
* [HTTP/2] [1] [user-agent: curl/8.7.1]
* [HTTP/2] [1] [accept: */*]
> GET / HTTP/2
> Host: example.com
> User-Agent: curl/8.7.1
> Accept: */*
>
* Request completely sent off
< HTTP/2 200
< date: Thu, 17 Sep 2026 16:10:18 GMT
< content-type: text/html
< server: cloudflare
< last-modified: Tue, 15 Sep 2026 23:38:37 GMT
< allow: GET, HEAD
< accept-ranges: bytes
< age: 3544
< cf-cache-status: HIT
< cf-ray: a3c961595b5eac6d-MAA
<
{ [559 bytes data]
* Connection #0 to host example.com left intact
```

**Walking the layers, in order:**

1. **DNS (Layer 7 service, but step one).** `Host example.com:443 was resolved` into two IPv6 and two IPv4 addresses. Multiple A records is standard load distribution.
2. **TCP (Layer 4).** curl tries IPv4 and IPv6 in parallel — this is **Happy Eyeballs** (RFC 8305). Both IPv6 attempts fail instantly with `No route to host` because this network has no IPv6 route, and the IPv4 attempt wins: `Connected to example.com (104.20.23.154) port 443`. The three-way handshake succeeded. Had the network been broken, everything below this line would never have printed.
3. **TLS (between Layer 4 and 7).** `ALPN: curl offers h2,http/1.1` — Application-Layer Protocol Negotiation, where the client proposes protocols during the handshake so no extra round trip is needed. Then the handshake in order: Client hello → Server hello → Certificate → CERT verify → Finished. The result: `TLSv1.3 / AEAD-CHACHA20-POLY1305-SHA256`.
4. **Certificate validation.** `subject: CN=example.com` and `subjectAltName: host "example.com" matched cert's "example.com"` — the name in the URL matches the certificate, `expire date: Oct 27 22:17:21 2026 GMT` is in the future, and the issuer chains to a trusted CA in `/etc/ssl/cert.pem`. So `SSL certificate verify ok.` This block is exactly where you look when you get `SSL certificate problem`: an expired cert, a name mismatch, or a missing intermediate will fail on one of these specific lines.
5. **HTTP (Layer 7).** `ALPN: server accepted h2`, so HTTP/2 it is. Lines beginning `>` are the request curl sent; lines beginning `<` are the response. Note HTTP/2 pseudo-headers (`:method`, `:scheme`, `:authority`, `:path`) — in HTTP/2 the request line is replaced by these binary header fields, and `:authority` is the HTTP/2 form of the `Host` header.
6. `Connection #0 ... left intact` — curl kept the connection alive rather than tearing it down, ready for reuse.

### 6.3 `curl` against the lab container

Through the published host port:

```bash
curl -sI http://localhost:8080
```

```text
HTTP/1.1 200 OK
Server: nginx/1.31.6
Date: Thu, 17 Sep 2026 16:13:46 GMT
Content-Type: text/html
Content-Length: 896
Last-Modified: Tue, 15 Sep 2026 14:18:52 GMT
Connection: keep-alive
ETag: "6aa953cc-380"
Accept-Ranges: bytes
```

And container to container, on port 80 by name:

```bash
docker run --rm --name hw03-net4 --network hw03-lab nicolaka/netshoot curl -sI http://hw03-web
```

```text
HTTP/1.1 200 OK
Server: nginx/1.31.6
Date: Thu, 17 Sep 2026 16:13:28 GMT
Content-Type: text/html
Content-Length: 896
Last-Modified: Tue, 15 Sep 2026 14:18:52 GMT
Connection: keep-alive
ETag: "6aa953cc-380"
Accept-Ranges: bytes
```

The same nginx, reached two different ways. From the host it is `localhost:8080` because of the port publish; from a peer container it is `hw03-web:80` because of Docker DNS and direct bridge routing. Understanding that these are two distinct paths to one service is the core of Docker and Kubernetes networking. Note this is `HTTP/1.1`, not HTTP/2 — plain nginx over cleartext HTTP does not negotiate h2, while Cloudflare over TLS did.

---

## Part 7 — Public vs Private IP, and CIDR

### 7.1 Public vs private

Every IPv4 address is 32 bits, written as four octets of 8 bits: `0.0.0.0` to `255.255.255.255`, about 4.3 billion addresses. That was never going to be enough, so RFC 1918 reserved three blocks that **may be reused by everyone** and are **never routed on the public internet**.

| Type | Range | CIDR | Addresses | Typical use |
| --- | --- | --- | --- | --- |
| Private (Class A) | 10.0.0.0 – 10.255.255.255 | `10.0.0.0/8` | ~16.7 M | Large corporate networks, AWS/Azure VPCs |
| Private (Class B) | 172.16.0.0 – 172.31.255.255 | `172.16.0.0/12` | ~1 M | Docker default bridges, mid-size networks |
| Private (Class C) | 192.168.0.0 – 192.168.255.255 | `192.168.0.0/16` | 65,536 | Home and small office routers |
| Loopback | 127.0.0.0 – 127.255.255.255 | `127.0.0.0/8` | — | The machine itself |
| Link-local | 169.254.0.0 – 169.254.255.255 | `169.254.0.0/16` | — | DHCP failed (APIPA); also cloud metadata at `169.254.169.254` |
| CGNAT / shared | 100.64.0.0 – 100.127.255.255 | `100.64.0.0/10` | ~4 M | ISP carrier-grade NAT (RFC 6598) |
| Public | everything else | — | — | Routable on the internet |

**Private** addresses are free, reusable, and not reachable from the internet. Thousands of homes all use `192.168.1.1`. To reach the internet they go through **NAT** on the router, which rewrites the private source address to the router's single public address and remembers the mapping so replies find their way back.

**Public** addresses are globally unique, allocated by regional registries, and cost money.

Both appeared in this lab:

* The Docker container: `172.23.0.3/16` — private, only exists inside this Mac.
* The host Wi-Fi: `100.129.164.121/20` — CGNAT shared space, so this connection is behind the ISP's NAT *as well as* the local router's.
* `github.com` at `20.207.73.82` — public, globally routable Azure address.

The security implication is the one that matters day to day: **a resource on a private subnet is not reachable from the internet, no matter what its security group says.** That is why cloud architectures put databases in private subnets and only load balancers in public ones.

### 7.2 Subnet masks and CIDR

A subnet mask splits a 32-bit address into a **network part** and a **host part**. The mask's `1` bits mark the network, the `0` bits mark hosts.

CIDR notation (`/24`) just counts the `1` bits, so it says the same thing as a dotted mask, more briefly.

| CIDR | Dotted mask | Network bits | Host bits | Total addresses | Usable hosts |
| --- | --- | --- | --- | --- | --- |
| `/8` | 255.0.0.0 | 8 | 24 | 16,777,216 | 16,777,214 |
| `/16` | 255.255.0.0 | 16 | 16 | 65,536 | 65,534 |
| `/20` | 255.255.240.0 | 20 | 12 | 4,096 | 4,094 |
| `/24` | 255.255.255.0 | 24 | 8 | 256 | 254 |
| `/26` | 255.255.255.192 | 26 | 6 | 64 | 62 |
| `/30` | 255.255.255.252 | 30 | 2 | 4 | 2 |

The formulas:

* total addresses = **2^(32 − prefix)**
* usable hosts = **2^(32 − prefix) − 2**

The **minus 2** is because two addresses in every subnet are reserved: the **network address** (all host bits `0`) identifies the subnet itself, and the **broadcast address** (all host bits `1`) reaches everyone on it. Neither can be assigned to a machine.

### 7.3 Worked example — `197.23.45.10` with mask `255.255.255.0`

This is the example from `session4-networking/ip.md`, worked end to end and verified with `ipcalc`.

**Step 1 — write both in binary.**

```text
IP      197.23.45.10     11000101.00010111.00101101.00001010
Mask    255.255.255.0    11111111.11111111.11111111.00000000
```

**Step 2 — count the mask bits.** Twenty-four `1`s, so this is a **/24**. Network part = first 24 bits, host part = last 8 bits.

**Step 3 — network address.** AND the IP with the mask, which means keeping the network bits and zeroing the host bits.

```text
11000101.00010111.00101101.00000000  =  197.23.45.0
```

**Step 4 — broadcast address.** Set every host bit to `1`.

```text
11000101.00010111.00101101.11111111  =  197.23.45.255
```

**Step 5 — usable range and count.** Host bits = 8, so 2^8 = 256 total, 2^8 − 2 = **254 usable**, from `197.23.45.1` to `197.23.45.254`.

**Step 6 — verify with a tool.**

```bash
docker run --rm --name hw03-net nicolaka/netshoot ipcalc -bnmp 197.23.45.10/24
```

```text
NETMASK=255.255.255.0
BROADCAST=197.23.45.255
NETWORK=197.23.45.0
PREFIX=24
```

The hand calculation matches exactly. Note also that `197` falls in 192–223, so by the old classful scheme this is a **Class C** address, and /24 is its natural default mask.

### 7.4 A second example where the boundary is not on a byte

`/24` is easy because the split lands on a dot. `/26` is where people go wrong, because the network boundary falls **inside** the last octet.

For `192.168.10.75/26`: the mask is 26 bits, so the last octet contributes 2 network bits and 6 host bits. `255.255.255.192` (since `11000000` = 192). Block size = 2^6 = **64**, so the /26 subnets of `192.168.10.0` start at `.0`, `.64`, `.128`, `.192`.

`75` falls between 64 and 127, so the network is `192.168.10.64` and the broadcast is `192.168.10.127`.

```bash
docker run --rm --name hw03-net nicolaka/netshoot ipcalc -bnmp 192.168.10.75/26
```

```text
NETMASK=255.255.255.192
BROADCAST=192.168.10.127
NETWORK=192.168.10.64
PREFIX=26
```

Confirmed. Usable range `192.168.10.65` to `192.168.10.126`, which is **62 hosts**.

The shortcut worth memorising: **block size = 256 − (last octet of the mask)**. For `255.255.255.192` that is 256 − 192 = 64, and subnets start at every multiple of 64. This is how you do subnetting in your head in an interview.

### 7.5 The Docker network, checked the same way

```bash
docker run --rm --name hw03-net nicolaka/netshoot ipcalc -bnmp 172.23.0.3/16
```

```text
NETMASK=255.255.0.0
BROADCAST=172.23.255.255
NETWORK=172.23.0.0
PREFIX=16
```

This matches what `docker network inspect` reported (`"Subnet":"172.23.0.0/16"`) and what `ip route` showed as the link-scope route. Docker hands each network a /16 out of `172.16.0.0/12`, which is why it is easy to collide with a corporate VPN using the same range — a genuinely common production incident, fixed by pinning Docker to a different subnet.

### 7.6 Why subnetting matters in DevOps

It is not academic. Every cloud VPC design is a subnetting exercise:

* A VPC of `10.0.0.0/16` gives 65,536 addresses.
* Split into `/24`s for public subnets (`10.0.1.0/24`, `10.0.2.0/24`) — one per availability zone, holding load balancers and NAT gateways.
* Split into larger `/20`s for private subnets holding application pods and databases.
* Get the sizing wrong and you cannot add nodes later, because **you cannot resize a subnet in place**. In Kubernetes this bites hard: with the AWS VPC CNI every pod consumes a real subnet IP, so a `/24` per subnet caps you at 254 pods.
* Security groups and firewall rules are written in CIDR. `0.0.0.0/0` means "the entire internet", and knowing that on sight is what stops you from opening SSH to the world.

---

## Part 8 — OSI vs TCP/IP, and Where Each Command Sits

### 8.1 The two models

The **OSI model** has seven layers and is the teaching and troubleshooting vocabulary. The **TCP/IP model** has four layers and is what the internet actually implements.

| OSI layer | OSI name | TCP/IP layer | What happens there | Data unit | Examples |
| --- | --- | --- | --- | --- | --- |
| 7 | Application | Application | What the user's software speaks | Data | HTTP, HTTPS, DNS, SSH, FTP, SMTP |
| 6 | Presentation | Application | Encoding, encryption, compression | Data | TLS/SSL, JPEG, JSON, UTF-8 |
| 5 | Session | Application | Establishing and managing sessions | Data | TLS session resumption, RPC, sockets |
| 4 | Transport | Transport | End-to-end delivery, ports, reliability | Segment (TCP) / Datagram (UDP) | TCP, UDP |
| 3 | Network | Internet | Logical addressing and routing between networks | Packet | IP, ICMP, routing tables |
| 2 | Data Link | Network Access | Addressing on the local link | Frame | Ethernet, MAC, ARP, VLANs, switches |
| 1 | Physical | Network Access | Actual signals | Bits | Cables, radio, NICs, hubs |

The key difference: OSI splits the top three layers into Application, Presentation, and Session, while TCP/IP merges them into one Application layer. OSI also splits the bottom two where TCP/IP merges them into Network Access. The numbers still get used every day — "it's a Layer 4 load balancer" or "that's a Layer 7 rule" — which is why the model is worth knowing even though nothing implements it literally.

### 8.2 Where every command in this lab operates

| Command | Layer | What it actually tests |
| --- | --- | --- |
| `ifconfig`, `ip a` | 2 + 3 | Interface state and MAC (L2), assigned IP (L3) |
| `ip neigh`, `arp -an` | 2 | IP-to-MAC resolution on the local link |
| `ping` | 3 | ICMP reachability between IP addresses |
| `traceroute` | 3 | The router path, hop by hop, using TTL |
| `ip route`, `netstat -rn` | 3 | How the kernel chooses an exit path |
| `ss`, `netstat -an`, `lsof -i` | 4 | TCP/UDP sockets, ports, connection state |
| `nc -zv` | 4 | Whether a TCP port accepts a connection |
| `dig`, `nslookup`, `host` | 7 (over 4) | DNS, an application protocol running on UDP/TCP 53 |
| `curl -I`, `curl -v` | 7 (and 5/6 for TLS) | HTTP request and response; TLS handshake and certificate |

### 8.3 Troubleshooting bottom-up — the practical payoff

This is the reason the model is worth memorising. When something is unreachable, walk the layers in order and stop at the first failure, instead of guessing:

| Step | Layer | Command | If it fails |
| --- | --- | --- | --- |
| 1 | L1/L2 | `ip a` — is the interface UP with an IP? | Cable, driver, DHCP, or the container was never attached to a network |
| 2 | L2 | `ip neigh` — is the gateway's MAC resolved? | Layer 2 problem: VLAN, switch port, or the gateway is down |
| 3 | L3 | `ip route` — is there a route to the destination? | Missing route or wrong default gateway |
| 4 | L3 | `ping <gateway>` then `ping 8.8.8.8` | Gateway OK but internet fails means an upstream or NAT problem |
| 5 | L3 | `traceroute <target>` — where does the path stop? | Identifies the hop where traffic dies |
| 6 | L7/DNS | `dig <name>` — does the name resolve? | If `ping 8.8.8.8` works but `dig` fails, it is purely DNS |
| 7 | L4 | `nc -zv <host> <port>` — is the port open? | Refused means service down; timeout means firewall |
| 8 | L4 | `ss -tulnp` on the server — is it listening, and on `0.0.0.0`? | Bound to `127.0.0.1` is the classic cause |
| 9 | L7 | `curl -v <url>` — does the application respond? | Now the network is proven fine; it is an app, TLS, or config issue |

Getting to step 9 with everything passing means the network is not your problem, and you can say so with evidence.

---

## Part 9 — Common Ports

Ports are 16-bit numbers (0–65535) that let one IP address run many services. They are split into **well-known** (0–1023, require root to bind), **registered** (1024–49151), and **ephemeral/dynamic** (49152–65535, what the kernel picks for outbound connections — exactly the `58919`, `59058` seen in the `lsof` output above).

| Port | Protocol | Service | What it is for | DevOps note |
| --- | --- | --- | --- | --- |
| **22** | TCP | SSH | Encrypted remote shell, also SCP/SFTP and `git+ssh` | The one port you almost always need open to a bastion. Never expose it to `0.0.0.0/0`; use a bastion, SSM, or a VPN |
| **53** | UDP + TCP | DNS | Name to IP resolution | UDP for normal queries, TCP when a response exceeds 512 bytes or for zone transfers. Blocking TCP/53 breaks large answers and DNSSEC |
| **80** | TCP | HTTP | Unencrypted web traffic | In production it should only ever redirect to 443. Used by ingress controllers and ACME HTTP-01 challenges |
| **443** | TCP | HTTPS | HTTP over TLS | The default for everything. Also carries HTTP/2 and, over UDP, HTTP/3 |
| **3306** | TCP | MySQL / MariaDB | Relational database | Never expose publicly. Private subnet plus security group only — this is the port most commonly found open by internet scanners |
| **5432** | TCP | PostgreSQL | Relational database | Same rule. Managed instances (RDS, Cloud SQL) should be private-only |
| **6379** | TCP | Redis | In-memory cache, queue, session store | Historically **no authentication by default**, which made exposed Redis a mass-exploitation target. Always bind to a private interface and enable auth |
| **27017** | TCP | MongoDB | Document database | Also had no auth by default in older versions, which caused thousands of public data breaches |

A few more you will meet constantly:

| Port | Service | Note |
| --- | --- | --- |
| 21 / 20 | FTP | Cleartext, legacy. Use SFTP (port 22) |
| 25 / 587 / 465 | SMTP | Mail. Cloud providers block 25 outbound by default to fight spam |
| 123 | NTP (UDP) | Time sync. Clock drift breaks TLS certificate validation and Kubernetes tokens |
| 3389 | RDP | Windows remote desktop. Same exposure warning as SSH |
| 8080 / 8443 | HTTP / HTTPS alt | Unprivileged alternatives — an app can bind these without root, which is why containers use them constantly |
| 2379 / 2380 | etcd | Kubernetes control plane state. Losing it loses the cluster |
| 6443 | Kubernetes API server | What `kubectl` talks to |
| 9090 / 3000 | Prometheus / Grafana | Standard monitoring stack ports |

The three rules that come out of this table:

1. Ports 0–1023 need root to bind, which is why containerised apps listen on 8080 and let a load balancer or ingress front them on 443.
2. **Database ports should never face the internet.** Not 3306, not 5432, not 6379, not 27017.
3. The commands in this lab tie back here directly — `ss -tulnp` showed nginx on **80**, `nc -zv` proved **443** open on github.com, and `dig` used **53**.

---

## Cleanup

```bash
docker rm -f hw03-web
docker network rm hw03-lab
docker ps -a --filter name=hw03- --format '{{.Names}}'
docker network ls --filter name=hw03- --format '{{.Name}}'
```

```text
hw03-web
hw03-lab
```

The two lines are the output of `docker rm -f` and `docker network rm` confirming what they removed. Both listing commands after them printed nothing, which means no `hw03-` container or network is left behind.

---

## Summary — The Commands, at a Glance

| Need | Linux | macOS |
| --- | --- | --- |
| My IP | `ip -br a` | `ipconfig getifaddr en0` |
| All interfaces | `ip a` | `ifconfig` |
| Default gateway | `ip route show default` | `route -n get default` |
| Full routing table | `ip route` | `netstat -rn` |
| Path to a destination | `ip route get <ip>` | `route -n get <ip>` |
| ARP table | `ip neigh` | `arp -an` |
| Is it reachable | `ping -c 4 <host>` | `ping -c 4 <host>` |
| Where does it break | `traceroute <host>` | `traceroute <host>` |
| Resolve a name | `dig +short <name>` | `dig +short <name>` |
| Check a specific resolver | `dig @8.8.8.8 <name>` | `dig @8.8.8.8 <name>` |
| Who owns a port | `ss -tulnp \| grep :8080` | `lsof -nP -iTCP:8080` |
| All listening ports | `ss -tuln` | `netstat -an -f inet -p tcp \| grep LISTEN` |
| Is a remote port open | `nc -zv <host> <port>` | `nc -zv <host> <port>` |
| HTTP headers | `curl -sI <url>` | `curl -sI <url>` |
| Debug the whole request | `curl -v <url>` | `curl -v <url>` |
| Subnet maths | `ipcalc -bnmp <ip>/<prefix>` | run it in a container |

### Flags worth committing to memory

* `-n` on `netstat`, `ss`, `lsof`, `traceroute` — **numeric**, skip DNS resolution. Faster, and it does not mislead you when DNS is the thing that is broken.
* `-tulnp` on `ss`/`netstat` — TCP, UDP, listening, numeric, process.
* `-c N` on `ping` — send N packets and stop. Without it, `ping` runs forever and hangs a script.
* `+short` on `dig` — value only, for scripts.
* `-sI` on `curl` — silent, headers only.
* `-nP` on `lsof` — no name resolution, no port names.

### Debugging inside containers

Two patterns from this lab that are worth carrying into real work:

```bash
docker run --rm --network container:<target> nicolaka/netshoot ss -tulnp
docker run --rm --network <network> nicolaka/netshoot dig <service>
```

The first joins the target container's network namespace so you can inspect its sockets without installing anything into its image. The second joins a network so you can test DNS and connectivity from the same vantage point your application has. In Kubernetes the equivalent is `kubectl debug` with an ephemeral container, or simply `kubectl run -it --rm netshoot --image=nicolaka/netshoot -- bash`.
