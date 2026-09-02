# Task 2 — Networking Command Reference and Explanations

**Assignment requirements** (verbatim from `DevOps Homework.docx`):

> ## Task 2
> - Create an empty Markdown (.md) file.
> - Execute the networking commands and add the output/screenshots to the file.
> - Add a short explanation of what you understood about each command.

*Every command below was executed for real on Ubuntu 24.04 (aarch64) in container `net-t1`
(started with `--cap-add=NET_ADMIN --cap-add=NET_RAW`), and every output block is pasted
verbatim from the actual run — nothing here is invented or copied from a man page.*

[← Back to Networking Fundamentals](../README.md)

---

## Interfaces & addressing

### `ip a`

```console
root@ubuntu-hw:~# ip a
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
    inet 127.0.0.1/8 scope host lo
       valid_lft forever preferred_lft forever
    inet6 ::1/128 scope host
       valid_lft forever preferred_lft forever
2: tunl0@NONE: <NOARP> mtu 1480 qdisc noop state DOWN group default qlen 1000
    link/ipip 0.0.0.0 brd 0.0.0.0
...
11: eth0@if306: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 65535 qdisc noqueue state UP group default
    link/ether 7e:bd:7f:bb:7e:79 brd ff:ff:ff:ff:ff:ff link-netnsid 0
    inet 172.17.0.7/16 brd 172.17.255.255 scope global eth0
       valid_lft forever preferred_lft forever
```
*(the middle interfaces — `gre0`, `gretap0`, `erspan0`, `ip_vti0`, `ip6_vti0`, `sit0`, `ip6tnl0`,
`ip6gre0` — are all `DOWN`, unused tunnel device templates the kernel creates by default; the
full listing is in `transcripts/net-a.txt`)*

**What I understood:** `ip a` (`ip address show`) is the modern tool for "what IP addresses does
this machine have, on which interfaces, and are they up." Each numbered block is one network
interface. `lo` is the loopback (always `127.0.0.1/8` and `::1/128`). `eth0` is the real
interface here, `UP` with IPv4 `172.17.0.7/16`. The unused tunnel interfaces (`tunl0`, `gre0`,
etc.) exist by default on every Linux box because the kernel always registers those tunnel
device types — they're not something anyone configured, and they stay `DOWN` until actually
used.

### `ip -br a`

```console
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
```

**What I understood:** `-br` = brief. Same information as `ip a`, but condensed to
`interface / state / address` on one line each — this is the version you actually want when
eyeballing a box quickly or grepping in a script, instead of scrolling through full blocks.

### `ip link`

```console
root@ubuntu-hw:~# ip link
1: lo: <LOOPBACK,UP,LOWER_UP> mtu 65536 qdisc noqueue state UNKNOWN mode DEFAULT group default qlen 1000
    link/loopback 00:00:00:00:00:00 brd 00:00:00:00:00:00
...
11: eth0@if306: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 65535 qdisc noqueue state UP mode DEFAULT group default
    link/ether 7e:bd:7f:bb:7e:79 brd ff:ff:ff:ff:ff:ff link-netnsid 0
```

**What I understood:** `ip link` shows only Layer-2 info — MAC addresses, MTU, and interface
flags/state — with **no IP addresses at all**. It's the pure "is the wire up and what's its
hardware address" view, one layer below `ip a`.

### `ip r`

```console
root@ubuntu-hw:~# ip r
default via 172.17.0.1 dev eth0
172.17.0.0/16 dev eth0 proto kernel scope link src 172.17.0.7
```

**What I understood:** `ip r` (`ip route show`) prints the kernel's routing table — the rules
the kernel uses to decide *which interface and next hop* a packet goes out through, based on
its destination. Line 2 says "anything in `172.17.0.0/16` is directly reachable on `eth0`."
Line 1, the `default` route, says "everything else goes via `172.17.0.1`" — that's the Docker
bridge gateway, the container's only way out to the rest of the world.

### `ip -br link`

```console
root@ubuntu-hw:~# ip -br link
lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP>
...
eth0@if306       UP             7e:bd:7f:bb:7e:79 <BROADCAST,MULTICAST,UP,LOWER_UP>
```

**What I understood:** the brief version of `ip link` — MAC address and flags per interface,
one line each, no addresses.

### `ifconfig`

```console
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
```

**What I understood:** `ifconfig` is the older `net-tools` equivalent of `ip a` — it's been
officially deprecated in favour of `ip` for years (`net-tools` isn't installed by default on
modern Ubuntu; it had to be installed explicitly here), but it's still everywhere in older docs
and muscle memory. Useful extra here: it shows live packet/byte counters per interface
(`RX packets`, `TX packets`) right in the default output, which `ip a` doesn't show unless you
add `-s`/`-s -s`.

### `hostname -I` / `hostname -f`

```console
root@ubuntu-hw:~# hostname -I
172.17.0.7

root@ubuntu-hw:~# hostname -f
ubuntu-hw
```

**What I understood:** `hostname -I` prints every IP address assigned to the host (handy when a
box has several interfaces). `hostname -f` is supposed to print the *fully-qualified* domain
name (e.g. `web01.internal.example.com`), but here it only printed `ubuntu-hw` — because
`/etc/hosts` maps this container's IP straight to the short name `ubuntu-hw` with no domain
suffix, so there is no FQDN configured to report; short name and "FQDN" collapse to the same
string.

### `/etc/hosts`

```console
root@ubuntu-hw:~# cat /etc/hosts
127.0.0.1	localhost
::1	localhost ip6-localhost ip6-loopback
fe00::	ip6-localnet
ff00::	ip6-mcastprefix
ff02::1	ip6-allnodes
ff02::2	ip6-allrouters
172.17.0.7	ubuntu-hw
```

**What I understood:** `/etc/hosts` is a flat, local, static hostname→IP lookup table that is
checked **before** the system even bothers asking a DNS server (per `/etc/nsswitch.conf`'s
`hosts:` line, normally `files dns`). It's how a machine always knows its own `localhost` and
its own container hostname without needing DNS. The last line, `172.17.0.7 ubuntu-hw`, was
written by Docker itself at container start so the container can resolve its own hostname.

### `/etc/resolv.conf`

```console
root@ubuntu-hw:~# cat /etc/resolv.conf
# Generated by Docker Engine.
# This file can be edited; Docker Engine will not make further changes once it
# has been modified.

nameserver 192.168.65.7

# Based on host file: '/etc/resolv.conf' (legacy)
# Overrides: []
```

**What I understood:** `/etc/resolv.conf` is the resolver configuration — it names the DNS
server(s) (`nameserver ...`) the machine will actually query whenever something isn't found in
`/etc/hosts`. `192.168.65.7` here is not a public DNS server at all; it's Docker Desktop's
internal DNS-forwarding proxy (confirmed by the file's own comment header, `# Generated by
Docker Engine`), which then forwards real queries out to whatever DNS the Mac host itself uses.
On a normal (non-Docker-Desktop) Linux host this file would usually list a real resolver like
`8.8.8.8`, `1.1.1.1`, or an internal corporate DNS server's IP.

### CIDR notation, read directly off `ip -o -f inet a`

```console
root@ubuntu-hw:~# ip -o -f inet a
1: lo    inet 127.0.0.1/8 scope host lo\       valid_lft forever preferred_lft forever
11: eth0    inet 172.17.0.7/16 brd 172.17.255.255 scope global eth0\       valid_lft forever preferred_lft forever
```

**What I understood:** `-o` forces one line per address (no wrapping) and `-f inet` filters to
IPv4 only, which makes the CIDR field easy to point at directly: the `a.b.c.d/NN` notation
*is* CIDR (Classless Inter-Domain Routing). `NN` is the **prefix length** — how many leading
bits of the address are the fixed "network" part; the remaining `32 - NN` bits identify hosts
within that network.
- `172.17.0.7/16` → 16 network bits, 16 host bits → the network is `172.17.0.0` through
  `172.17.255.255` (65,536 addresses) — matches exactly what `ip r` showed as the directly
  connected route, `172.17.0.0/16 dev eth0`.
- `127.0.0.1/8` → only 8 network bits → the entire `127.0.0.0/8` block (not just `127.0.0.1`)
  is reserved for loopback.

  A `/16` is looser (more host addresses) than a `/24`; a `/32` means "exactly this one host,"
  which is why single-host static routes are always written as `x.x.x.x/32`.

---

## Connectivity & routing

### `ping`

```console
root@ubuntu-hw:~# ping -c 3 8.8.8.8
PING 8.8.8.8 (8.8.8.8) 56(84) bytes of data.
64 bytes from 8.8.8.8: icmp_seq=1 ttl=63 time=87.5 ms
64 bytes from 8.8.8.8: icmp_seq=2 ttl=63 time=77.4 ms

--- 8.8.8.8 ping statistics ---
3 packets transmitted, 2 received, 33.3333% packet loss, time 2005ms
rtt min/avg/max/mdev = 77.434/82.445/87.457/5.011 ms

root@ubuntu-hw:~# ping -c 3 google.com
PING google.com (142.251.221.238) 56(84) bytes of data.
64 bytes from pnbomb-bk-in-f14.1e100.net (142.251.221.238): icmp_seq=1 ttl=63 time=35.4 ms
64 bytes from pnbomb-bk-in-f14.1e100.net (142.251.221.238): icmp_seq=2 ttl=63 time=61.9 ms
64 bytes from pnbomb-bk-in-f14.1e100.net (142.251.221.238): icmp_seq=3 ttl=63 time=99.3 ms

--- google.com ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2015ms
rtt min/avg/max/mdev = 35.417/65.527/99.281/26.199 ms
```

**What I understood:** `ping` sends ICMP Echo Request packets and times the Echo Reply — the
most basic "is this thing alive and reachable" test, and the round-trip time (`time=...ms`) is
a direct read of network latency. `-c 3` limits it to 3 packets instead of running forever.
Pinging the raw IP (`8.8.8.8`) skips DNS entirely; pinging `google.com` resolves the name first,
then pings the resolved IP (shown in parentheses). Interesting real result: the raw-IP ping to
`8.8.8.8` actually **lost 1 of 3 packets (33%)** while the hostname ping right after lost none
— almost certainly noise from Docker Desktop's extra NAT hop rather than a real problem with
`8.8.8.8` itself, since the very next ping to the same general destination network had 0% loss.
`ttl=63` on every reply also tells us something: TTL starts at 64 on most Linux/Google
infrastructure and is decremented by 1 per hop, so `ttl=63` means the reply crossed **1 hop**
from this container's perspective (again — a NAT/tunnel artifact, not the real internet
distance to Google).

### `traceroute`

```console
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
```

**What I understood:** `traceroute` finds the path a packet takes by sending probes with
increasing TTL (1, 2, 3, ...) and reporting whoever sends back the "TTL exceeded" ICMP message
at each hop — hop 1 replies to a TTL=1 probe, hop 2 to TTL=2, and so on, until the destination
itself is reached. `-m 8` caps it at 8 hops max; `-w 1 -q 1` (1 second wait, 1 probe per hop)
keeps a stalled/filtered hop from hanging the command for a long time, which is exactly what
happened here — this run genuinely only got a reply from hop 1
(`172.17.0.1`, the Docker bridge gateway) and then eight rounds of `* * *`, even though the
destination is reachable (confirmed by the successful pings above). This is a real, honestly
captured limitation of running traceroute from inside Docker Desktop for Mac: outbound traffic
is NATed through a single `vpnkit` tunnel to the host, and the "TTL exceeded" replies from the
real intermediate internet routers never make it back to the container the way they would from
a normal host — so every hop past the Docker gateway shows as unanswered `*`, not because those
routers are firewalled in the traditional sense but because the path is structurally collapsed
by the VM/NAT layer.

### `mtr`

```console
root@ubuntu-hw:~# mtr --report -c 3 google.com
Start: 2026-09-02T17:28:24+0000
HOST: ubuntu-hw                   Loss%   Snt   Last   Avg  Best  Wrst StDev
  1.|-- 172.17.0.1                 0.0%     3    0.2   0.2   0.1   0.2   0.1
  2.|-- pnbomb-bk-in-f14.1e100.ne  0.0%     3   34.6  40.0  31.4  53.9  12.2
```

**What I understood:** `mtr` ("my traceroute") is a `ping` + `traceroute` hybrid — it
continuously probes every hop and reports live loss%/latency stats per hop, not just a single
snapshot. `--report -c 3` makes it run 3 cycles and print a plain summary table instead of the
interactive full-screen UI (which would count as a blocking command). It actually got further
than `traceroute` here — hop 1 is the same Docker gateway, and hop 2 resolved to a **real Google
edge node** (`pnbomb-bk-in-f14.1e100.ne...`) with 0% loss and real latency (~40ms avg). From
inside this container's view, Google's own server looks like it's "one hop past the gateway" —
again the vpnkit tunnel collapsing what is really a multi-hop internet path into two visible
hops, not a literal description of the internet's topology.

### `ip route get`

```console
root@ubuntu-hw:~# ip route get 8.8.8.8
8.8.8.8 via 172.17.0.1 dev eth0 src 172.17.0.7 uid 0
    cache
```

**What I understood:** instead of reading the whole routing table and figuring out the match
yourself, `ip route get <dest>` just asks the kernel to do the lookup and tell you the answer:
to reach `8.8.8.8`, go **via** `172.17.0.1` (the gateway), **out** `eth0`, using **source
address** `172.17.0.7`. It's the fastest way to sanity-check "which interface/gateway will this
box actually use" without doing the longest-prefix-match arithmetic by hand.

---

## DNS

### `dig`

```console
root@ubuntu-hw:~# dig google.com

; <<>> DiG 9.18.39-0ubuntu0.24.04.7-Ubuntu <<>> google.com
;; global options: +cmd
;; Got answer:
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 37038
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 0

;; QUESTION SECTION:
;google.com.			IN	A

;; ANSWER SECTION:
google.com.		103	IN	A	142.251.221.238

;; Query time: 3 msec
;; SERVER: 192.168.65.7#53(192.168.65.7) (UDP)
;; WHEN: Wed Sep 02 17:28:41 UTC 2026
;; MSG SIZE  rcvd: 54
```

**What I understood:** `dig` is the detailed, DNS-protocol-accurate lookup tool. The
**QUESTION SECTION** is exactly what was asked (`google.com`, type `A` = IPv4 address). The
**ANSWER SECTION** is what came back: `142.251.221.238`, with a **TTL of 103** (seconds) — that
number is the answer's cache lifetime: any resolver caching this record must throw it away and
re-ask after 103 seconds, which is why re-running the same query minutes apart can return a
different TTL value counting down, or a different IP entirely once it's re-fetched (Google
rotates answers across many front-end IPs). `status: NOERROR` means the query succeeded (as
opposed to `NXDOMAIN` for "doesn't exist"). Query time was 3ms because it hit Docker's local
resolver cache/proxy.

### `dig +short`

```console
root@ubuntu-hw:~# dig +short google.com
142.251.221.238
```

**What I understood:** `+short` strips away every header/section and prints just the resolved
value(s) — the version you actually want inside a shell script (`IP=$(dig +short host)`)
instead of parsing the full output.

### `dig ... MX`

```console
root@ubuntu-hw:~# dig google.com MX

;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 53897
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 0, ADDITIONAL: 0

;; QUESTION SECTION:
;google.com.			IN	MX

;; ANSWER SECTION:
google.com.		377	IN	MX	10 smtp.google.com.

;; Query time: 4367 msec
```

**What I understood:** adding a record type (`MX`) after the name asks for a different kind of
record than the default `A`. `MX` = mail exchanger — which server(s) accept email for this
domain, with a **preference number** (`10`) where lower numbers are tried first. Worth noting:
this query took **4367 msec**, dramatically slower than the earlier 3ms `A` lookup — the earlier
answer was almost certainly served from the local resolver's cache, while this one had to go
all the way out and actually ask upstream.

### `dig -x` (reverse DNS)

```console
root@ubuntu-hw:~# dig -x 8.8.8.8

;; QUESTION SECTION:
;8.8.8.8.in-addr.arpa.		IN	PTR

;; ANSWER SECTION:
8.8.8.8.in-addr.arpa.	4502	IN	PTR	dns.google.
```

**What I understood:** `-x` does the lookup backwards — given an IP, find its hostname. Under
the hood it's not a special mechanism; it's a normal DNS query for a `PTR` record against the
special reverse zone `in-addr.arpa` (the IP octets reversed: `8.8.8.8` → `8.8.8.8.in-addr.arpa`).
The answer, `dns.google.`, confirms `8.8.8.8` is Google's public DNS resolver, with a TTL of
4502 seconds (about 75 minutes) — PTR records for stable infrastructure like this tend to have
much longer TTLs than a typical website's `A` record, because they change far less often.

### `dig @1.1.1.1` (query a specific server)

```console
root@ubuntu-hw:~# dig @1.1.1.1 google.com
; (1 server found)
;; ->>HEADER<<- opcode: QUERY, status: NOERROR, id: 15174
;; flags: qr rd ra; QUERY: 1, ANSWER: 1, AUTHORITY: 4, ADDITIONAL: 4

;; QUESTION SECTION:
;google.com.			IN	A

;; ANSWER SECTION:
google.com.		24	IN	A	142.251.221.238

;; AUTHORITY SECTION:
google.com.		135087	IN	NS	ns4.google.com.
google.com.		135087	IN	NS	ns2.google.com.
google.com.		135087	IN	NS	ns1.google.com.
google.com.		135087	IN	NS	ns3.google.com.

;; ADDITIONAL SECTION:
ns4.google.com.		92167	IN	A	216.239.38.10
ns2.google.com.		147020	IN	A	216.239.34.10
ns1.google.com.		157359	IN	A	216.239.32.10
ns3.google.com.		150072	IN	A	216.239.36.10

;; SERVER: 1.1.1.1#53(1.1.1.1) (UDP)
```

**What I understood:** `@1.1.1.1` overrides `/etc/resolv.conf` entirely and sends the query
straight to Cloudflare's public resolver instead of Docker's local proxy — useful for comparing
answers or ruling out "is it my local resolver that's broken." This is also the clearest
**answer vs. authority** example captured: the **ANSWER SECTION** is the actual `A` record asked
for; the **AUTHORITY SECTION** separately lists the `NS` records — the four nameservers that are
*authoritative* for the `google.com` zone (i.e., who you'd ask directly if you wanted the
ground-truth record, bypassing caching resolvers entirely). The **ADDITIONAL SECTION** then adds
the `A` records for those nameservers themselves, so a client doesn't have to do a separate
lookup just to find *their* IPs ("glue records"). Also note the same `A` record's TTL is **24**
here versus **103** in the very first plain `dig google.com` — proof the TTL is a live countdown
being served from cache, not a fixed constant; each resolver's cache degrades independently.

### `nslookup`

```console
root@ubuntu-hw:~# nslookup google.com
Server:		192.168.65.7
Address:	192.168.65.7#53

Non-authoritative answer:
Name:	google.com
Address: 142.251.221.238
```

**What I understood:** `nslookup` is an older, terser DNS lookup tool. It clearly separates
**which server answered** (`192.168.65.7`, Docker's local resolver proxy — same one seen in
`/etc/resolv.conf`) from **the answer itself**. "Non-authoritative answer" is the same concept
as `dig`'s answer-vs-authority split, phrased differently: this reply came from a caching
resolver, not directly from `google.com`'s own authoritative nameservers.

### `host`

```console
root@ubuntu-hw:~# host google.com
google.com has address 142.251.221.238
google.com mail is handled by 10 smtp.google.com.

root@ubuntu-hw:~# host -t MX google.com
google.com mail is handled by 10 smtp.google.com.
```

**What I understood:** `host` is the tersest of the three DNS tools — one line per fact, no
sections, no headers. Plain `host google.com` conveniently prints **both** the `A` record and
the `MX` record by default without having to ask twice, whereas `-t MX` narrows it to just the
mail record — handy for quick scripting where full `dig` output would be overkill.

---

## Ports, sockets & HTTP

### `service nginx start`

```console
root@ubuntu-hw:~# service nginx start && sleep 1
 * Starting nginx nginx
   ...done.
```

**What I understood:** this container has no systemd (no real PID 1 init), so `service` falls
back to running nginx's own SysV-style init script directly, which just execs
`nginx -c /etc/nginx/nginx.conf` in the background. After this, something is actually listening
on port 80 to test the rest of the commands against.

### `ss -tuln` / `ss -tulnp`

```console
root@ubuntu-hw:~# ss -tuln
Netid State  Recv-Q Send-Q Local Address:Port Peer Address:PortProcess
tcp   LISTEN 0      511          0.0.0.0:80        0.0.0.0:*
tcp   LISTEN 0      511             [::]:80           [::]:*

root@ubuntu-hw:~# ss -tulnp
Netid State  Recv-Q Send-Q Local Address:Port Peer Address:PortProcess
tcp   LISTEN 0      511          0.0.0.0:80        0.0.0.0:*    users:(("nginx",pid=952,fd=5))
tcp   LISTEN 0      511             [::]:80           [::]:*    users:(("nginx",pid=952,fd=6))
```

**What I understood:** `ss` ("socket statistics") is the modern tool for "what's actually
listening on this machine, on which port." `-t` = TCP, `-u` = UDP, `-l` = listening sockets
only (not established connections), `-n` = show numeric ports instead of resolving service
names. `0.0.0.0:80` means nginx is bound to **all** IPv4 interfaces on port 80, and `[::]:80` is
the same for IPv6. Adding `-p` (process) required root and revealed exactly **which** process
owns the socket: `nginx`, `pid=952`, file descriptor `5`/`6` — invaluable for "something's using
port 80, but what?" troubleshooting.

### `netstat -tuln`

```console
root@ubuntu-hw:~# netstat -tuln
Active Internet connections (only servers)
Proto Recv-Q Send-Q Local Address           Foreign Address         State
tcp        0      0 0.0.0.0:80              0.0.0.0:*               LISTEN
tcp6       0      0 :::80                   :::*                    LISTEN
```

**What I understood:** the older `net-tools` equivalent of `ss -tuln`, same flags, same meaning,
slightly different formatting (`tcp6` as its own protocol row instead of `[::]`). Functionally
interchangeable with `ss` here, but `ss` is faster and is what modern distros ship by default.

### `curl -I`

```console
root@ubuntu-hw:~# curl -I http://localhost
HTTP/1.1 200 OK
Server: nginx/1.24.0 (Ubuntu)
Date: Wed, 02 Sep 2026 17:28:56 GMT
Content-Type: text/html
Content-Length: 615
Last-Modified: Wed, 02 Sep 2026 16:46:29 GMT
Connection: keep-alive
ETag: "6a9852e5-267"
Accept-Ranges: bytes
```

**What I understood:** `-I` sends a HEAD request and prints only the response headers, not the
body — the fast way to check "is this URL alive, what server is it, what content type/length
does it claim" without downloading the page. `HTTP/1.1 200 OK` confirms nginx answered
successfully, `Server: nginx/1.24.0` fingerprints the software, and `Content-Length: 615`
matches the size of nginx's default landing page.

### `curl -sv ... -o /dev/null`

```console
root@ubuntu-hw:~# curl -sv http://localhost -o /dev/null
* Host localhost:80 was resolved.
* IPv6: ::1
* IPv4: 127.0.0.1
*   Trying [::1]:80...
* Connected to localhost (::1) port 80
> GET / HTTP/1.1
> Host: localhost
> User-Agent: curl/8.5.0
> Accept: */*
>
< HTTP/1.1 200 OK
< Server: nginx/1.24.0 (Ubuntu)
< Date: Wed, 02 Sep 2026 17:28:56 GMT
< Content-Type: text/html
< Content-Length: 615
< Last-Modified: Wed, 02 Sep 2026 16:46:29 GMT
< Connection: keep-alive
< ETag: "6a9852e5-267"
< Accept-Ranges: bytes
<
{ [615 bytes data]
* Connection #0 to host localhost left intact
```

**What I understood:** `-v` (verbose) is what actually makes curl educational — `-s` silences
the normal progress meter so verbose lines aren't mixed with it, and `-o /dev/null` discards the
body since only the *exchange* matters here. `*` lines are curl's own internal steps (DNS
resolution, choosing `::1` over `127.0.0.1` since it tried IPv6 first, opening the TCP
connection). `>` lines are the **literal bytes curl sent** — the actual HTTP request line and
headers. `<` lines are the **literal bytes the server sent back** — status line and response
headers. This is the clearest way to see that HTTP itself is just plain text sent over an
already-open TCP connection.

### `nc -zv` (open port vs. closed port)

```console
root@ubuntu-hw:~# nc -zv localhost 80
Connection to localhost (::1) 80 port [tcp/http] succeeded!

root@ubuntu-hw:~# nc -zv localhost 9999
nc: connect to localhost (::1) port 9999 (tcp) failed: Connection refused
nc: connect to localhost (127.0.0.1) port 9999 (tcp) failed: Connection refused
```

**What I understood:** `-z` tells `nc` to just test the connection (zero I/O) instead of opening
an interactive session, and `-v` makes it print the result — a lightweight, scriptable port
checker. Port 80 (nginx listening) → `succeeded!`. Port 9999 (nothing listening) → a genuine
**`Connection refused`** at the TCP level — the kernel itself replied with a `RST` because no
process had that port open (as opposed to a timeout, which would mean something is silently
dropping the packets, e.g. a firewall).

### `tcpdump`

```console
root@ubuntu-hw:~# tcpdump -i lo -c 5 -n port 80 & sleep 1; curl -s localhost >/dev/null; wait
tcpdump: verbose output suppressed, use -v[v]... for full protocol decode
listening on lo, link-type EN10MB (Ethernet), snapshot length 262144 bytes
5 packets captured
20 packets received by filter
0 packets dropped by kernel
17:28:58.001261 IP6 ::1.53786 > ::1.80: Flags [S], seq 2081888073, win 65476, options [mss 65476,sackOK,TS val 109792286 ecr 0,nop,wscale 7], length 0
17:28:58.001282 IP6 ::1.80 > ::1.53786: Flags [S.], seq 653240365, ack 2081888074, win 65464, options [mss 65476,sackOK,TS val 109792286 ecr 109792286,nop,wscale 7], length 0
17:28:58.001290 IP6 ::1.53786 > ::1.80: Flags [.], ack 1, win 512, options [nop,nop,TS val 109792286 ecr 109792286], length 0
17:28:58.001340 IP6 ::1.53786 > ::1.80: Flags [P.], seq 1:73, ack 1, win 512, options [nop,nop,TS val 109792286 ecr 109792286], length 72: HTTP: GET / HTTP/1.1
17:28:58.001343 IP6 ::1.80 > ::1.53786: Flags [.], ack 73, win 511, options [nop,nop,TS val 109792286 ecr 109792286], length 0
```

**What I understood:** `tcpdump` is a raw packet capture tool — it shows what genuinely crossed
the wire (here, the loopback interface `lo`), not what an application *says* it sent. `-i lo`
picks the interface, `-c 5` self-limits the capture to exactly 5 packets so it exits on its own
(no manual `Ctrl-C` needed), `-n` skips reverse-DNS-resolving every address (faster, and avoids
noise). Running it backgrounded with `&`, waiting 1 second, then firing a real `curl` request,
then `wait`-ing for the capture to finish is what makes it deterministic instead of "capture
forever and hope something happens." The 5 packets captured are exactly one full minimal HTTP
request/response opening: a TCP handshake (packets 1–3), the actual `GET / HTTP/1.1` request
riding on packet 4, and the server's ACK of it (packet 5) — see the dedicated handshake section
below for what each line means in detail.

---

## Layer map — which command inspects which layer

| Layer (TCP/IP model) | OSI equivalent | What lives there | Commands that inspect it |
|---|---|---|---|
| Link | Layer 1–2 (Physical/Data Link) | MAC addresses, NICs, frames | `ip link`, `ip -br link`, `ifconfig` |
| Internet | Layer 3 (Network) | IP addresses, routing, ICMP | `ip a`, `ip r`, `ip route get`, `ping`, `traceroute`, `mtr` |
| Transport | Layer 4 (Transport) | TCP/UDP, ports, handshakes, connection state | `ss`, `netstat`, `nc -z`, `tcpdump` (shows SYN/ACK flags) |
| Application | Layer 5–7 (Session/Presentation/Application) | DNS, HTTP, actual protocol payloads | `dig`, `nslookup`, `host`, `curl`, `nc` (interactive), `tcpdump` (payload bytes) |

`tcpdump` is the odd one out — it straddles nearly every layer at once, since a captured frame
contains the Ethernet header (link), the IP header (internet), the TCP/UDP header (transport),
*and* the raw application payload (e.g. the literal `GET / HTTP/1.1` bytes seen above), all in
one line of output.

## Which tool for which symptom (troubleshooting table)

| Symptom | Start with | Why |
|---|---|---|
| Can't resolve the hostname at all | `dig`, `host`, `nslookup` | Confirms whether the problem is DNS (name→IP) before touching anything else. `dig @8.8.8.8 name` bypasses the local resolver to isolate "is it my resolver or the domain itself." |
| Name resolves, but nothing connects | `ping`, `traceroute`/`mtr`, `nc -zv host port` | `ping` tests basic reachability at the IP layer; `traceroute`/`mtr` shows *where* the path breaks; `nc -zv` tests whether the specific TCP port is even open, independent of any application protocol. |
| Connects, but the app protocol misbehaves (e.g. no valid HTTP response) | `curl -v`, `tcpdump` | `curl -v` shows exactly what was sent and received at the HTTP layer; `tcpdump` proves what genuinely went over the wire if you suspect curl or the app is lying/misconfigured. |
| "Something's already using this port" / service won't bind | `ss -tulnp`, `netstat -tuln` | `-p` names the exact process and PID holding the port, so you know what to stop or reconfigure. |
| DNS resolves to the wrong / stale IP | `dig` (check the TTL and compare against `dig @known-good-server`) | A short TTL that hasn't expired yet, or a resolver serving a cached record, explains "it changed in the dashboard but I still get the old IP." |
| Intermittent packet loss / slow responses | `ping -c N` (check loss %), `mtr --report` | `ping`'s loss percentage and `mtr`'s per-hop loss/latency columns pinpoint whether the problem is at the first hop, a middle hop, or the destination itself. |
| Need to know this box's own addressing/routing before debugging further | `ip a`, `ip r`, `hostname -I` | Establishes the starting facts — what IP/interface/gateway this machine itself thinks it has — before chasing a remote problem. |

## TCP three-way handshake — what was actually captured

The `tcpdump` capture above shows the full handshake for a real connection from `curl` to
`nginx` on port 80, over loopback. The three lines that matter:

```
17:28:58.001261 IP6 ::1.53786 > ::1.80: Flags [S], seq 2081888073, ...
17:28:58.001282 IP6 ::1.80 > ::1.53786: Flags [S.], seq 653240365, ack 2081888074, ...
17:28:58.001290 IP6 ::1.53786 > ::1.80: Flags [.], ack 1, ...
```

1. **`Flags [S]`** — **SYN**. The client (`::1`, ephemeral port `53786`, i.e. curl) opens the
   connection by sending a segment with the SYN flag set and an initial sequence number,
   `seq 2081888073`. This says "I want to talk, and my byte counter starts here."
2. **`Flags [S.]`** — **SYN-ACK**. The server (`::1:80`, nginx) replies with *its own* SYN
   (`seq 653240365`, its own starting byte counter) combined with an ACK
   (`ack 2081888074` — the client's initial sequence number **+1**), acknowledging the client's
   SYN in the same packet. This is why it's shown as `S.` (SYN + ACK together) rather than two
   separate lines.
3. **`Flags [.]`** — **ACK**. The client acknowledges the server's SYN (`ack 1`, relative
   sequence numbering that `tcpdump` prints by default — i.e., 1 byte past the server's initial
   sequence number). The connection is now `ESTABLISHED` on both ends.

Only after those three packets does the actual data flow — visible as the very next captured
line, `Flags [P.]` (**PSH+ACK**, "here is application data, please push it up to the
application immediately") carrying `HTTP: GET / HTTP/1.1`, followed by the server's plain `[.]`
ACK of having received it. This is a textbook demonstration of the reason HTTP/1.1 (a
request/response text protocol) can ride on top of TCP at all: TCP's handshake guarantees both
sides have a synchronized, reliable, ordered byte stream *before* a single byte of HTTP is ever
sent.

<!-- AUTO-ATTACHED: screenshots & transcripts -->
