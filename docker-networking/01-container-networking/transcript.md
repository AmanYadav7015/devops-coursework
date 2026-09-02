# Docker networking — three containers, three networks

> Real session — every command was executed and the output is verbatim.

[← Back](README.md)

---

```console
[aman@macos ~]$ docker network create dn-net-frontend
ea4d7b8926525c5f1f5cb3dd2963fe858e5e1725acb7e6789f443aab38272f5d

[aman@macos ~]$ docker network create dn-net-backend
efaadd42a79b4a9d574d9075c3e46b1828ad3b22701eac801816272653a698ad

[aman@macos ~]$ docker network create dn-net-database
47d143c2fc66c5ffa51ea40a5e1ad27f5cf99a3cab36aa2b11faf6ffc42d981e

[aman@macos ~]$ docker network ls
NETWORK ID     NAME                     DRIVER    SCOPE
871ee7c20374   bridge                   bridge    local
efaadd42a79b   dn-net-backend           bridge    local
47d143c2fc66   dn-net-database          bridge    local
ea4d7b892652   dn-net-frontend          bridge    local
d74a51eb7ed1   host                     host      local
6e9b53a4668b   mirror-control_default   bridge    local
3e9a572dd575   none                     null      local


# --- inspect all 3, extract just the assigned subnet (real values, driver-allocated) ---
[aman@macos ~]$ docker network inspect dn-net-frontend dn-net-backend dn-net-database --format '{{.Name}}: subnet={{range .IPAM.Config}}{{.Subnet}} gateway={{.Gateway}}{{end}}'
dn-net-frontend: subnet=172.19.0.0/16 gateway=172.19.0.1
dn-net-backend: subnet=172.20.0.0/16 gateway=172.20.0.1
dn-net-database: subnet=172.21.0.0/16 gateway=172.21.0.1


# --- full inspect of one network, to show the real JSON shape (driver, IPAM, options) ---
[aman@macos ~]$ docker network inspect dn-net-frontend
[
    {
        "Name": "dn-net-frontend",
        "Id": "ea4d7b8926525c5f1f5cb3dd2963fe858e5e1725acb7e6789f443aab38272f5d",
        "Created": "2026-09-02T17:30:01.512390835Z",
        "Scope": "local",
        "Driver": "bridge",
        "EnableIPv4": true,
        "EnableIPv6": false,
        "IPAM": {
            "Driver": "default",
            "Options": {},
            "Config": [
                {
                    "Subnet": "172.19.0.0/16",
                    "Gateway": "172.19.0.1"
                }
            ]
        },
        "Internal": false,
        "Attachable": false,
        "Ingress": false,
        "ConfigFrom": {
            "Network": ""
        },
        "ConfigOnly": false,
        "Options": {
            "com.docker.network.enable_ipv4": "true",
            "com.docker.network.enable_ipv6": "false"
        },
        "Labels": {},
        "Containers": {},
        "Status": {
            "IPAM": {
                "Subnets": {
                    "172.19.0.0/16": {
                        "IPsInUse": 3,
                        "DynamicIPsAvailable": 65533
                    }
                }
            }
        }
    }
]
```

### Running the 3 containers

```console
# --- frontend: nginx, attached to dn-net-frontend at creation time ---
[aman@macos ~]$ docker run -d --name dn-frontend --network dn-net-frontend nginx:alpine
594a438be3e8cd4f48235130ae187bd5315eb318bade0f99a747b971294352d4


# --- database: mysql:8, attached to dn-net-database, throwaway local root password ---
[aman@macos ~]$ docker run -d --name dn-database --network dn-net-database -e MYSQL_ROOT_PASSWORD=DemoRootPass123 mysql:8
Unable to find image 'mysql:8' locally
8: Pulling from library/mysql
26eb9d6698f0: Pulling fs layer
c1a8d43326b8: Pulling fs layer
8a905d3b3fdf: Pulling fs layer
d3c86b417a74: Pulling fs layer
b12e28485eff: Pulling fs layer
ac21e899ba1c: Pulling fs layer
bec4c5f6b46d: Pulling fs layer
3d7f10ed4edf: Pulling fs layer
19c1e4d5e56d: Pulling fs layer
1ff71ea7626e: Pulling fs layer
64896815bd4e: Download complete
b12e28485eff: Download complete
26eb9d6698f0: Download complete
d3c86b417a74: Download complete
1ff71ea7626e: Download complete
8a905d3b3fdf: Download complete
541dad502f35: Download complete
3d7f10ed4edf: Download complete
ac21e899ba1c: Download complete
c1a8d43326b8: Download complete
8a905d3b3fdf: Pull complete
3d7f10ed4edf: Pull complete
c1a8d43326b8: Pull complete
d3c86b417a74: Pull complete
1ff71ea7626e: Pull complete
ac21e899ba1c: Pull complete
bec4c5f6b46d: Download complete
b12e28485eff: Pull complete
bec4c5f6b46d: Pull complete
19c1e4d5e56d: Download complete
26eb9d6698f0: Pull complete
19c1e4d5e56d: Pull complete
Digest: sha256:b3b90af2a6552ae30c266fdb7d5dd55f3afb72404bb78d37fe8a23eb857fd3fb
Status: Downloaded newer image for mysql:8
caef3413b478ff428175e33b5e673651db3c7678c6c46cafd11516e8154777fb


# --- backend: alpine, kept alive with 'sleep infinity', started on dn-net-frontend ---
[aman@macos ~]$ docker run -d --name dn-backend --network dn-net-frontend alpine:latest sleep infinity
Unable to find image 'alpine:latest' locally
latest: Pulling from library/alpine
aa3ec251a2db: Download complete
df8ce8557afe: Download complete
Digest: sha256:28bd5fe8b56d1bd048e5babf5b10710ebe0bae67db86916198a6eec434943f8b
Status: Downloaded newer image for alpine:latest
d068a8c8ff64e08891a0eb80f240359bc818e881dc3eba46980e32d7ba7d51df


# --- Assignment: 'Add the backend container to 2 networks.'                       ---
# --- backend is already on dn-net-frontend (shares with frontend); now connect it  ---
# --- to dn-net-database too (shares with database) -> backend can DNS-resolve both ---
[aman@macos ~]$ docker network connect dn-net-database dn-backend

[aman@macos ~]$ docker ps --filter 'name=dn-' --format 'table {{.Names}}	{{.Image}}	{{.Status}}	{{.Networks}}'
NAMES         IMAGE           STATUS              NETWORKS
dn-backend    alpine:latest   Up 12 seconds       dn-net-database,dn-net-frontend
dn-database   mysql:8         Up 16 seconds       dn-net-database
dn-frontend   nginx:alpine    Up About a minute   dn-net-frontend


# --- give mysql:8 time to complete first-run initialisation, then confirm readiness ---
[aman@macos ~]$ docker logs dn-database 2>&1 | grep -c 'ready for connections'
4

# --- last lines of the real log, showing mysqld genuinely listening on 3306 ---
[aman@macos ~]$ docker logs dn-database --tail 8
2026-09-02T17:31:05.368959Z 0 [System] [MY-010116] [Server] /usr/sbin/mysqld (mysqld 8.4.11) starting as process 1
2026-09-02T17:31:05.373457Z 1 [System] [MY-013576] [InnoDB] InnoDB initialization has started.
2026-09-02T17:31:05.524628Z 1 [System] [MY-013577] [InnoDB] InnoDB initialization has ended.
2026-09-02T17:31:05.659333Z 0 [Warning] [MY-010068] [Server] CA certificate ca.pem is self signed.
2026-09-02T17:31:05.659356Z 0 [System] [MY-013602] [Server] Channel mysql_main configured to support TLS. Encrypted connections are now supported for this channel.
2026-09-02T17:31:05.660471Z 0 [Warning] [MY-011810] [Server] Insecure configuration for --pid-file: Location '/var/run/mysqld' in the path is accessible to all OS users. Consider choosing a different directory.
2026-09-02T17:31:05.667999Z 0 [System] [MY-011323] [Server] X Plugin ready for connections. Bind-address: '::' port: 33060, socket: /var/run/mysqld/mysqlx.sock
2026-09-02T17:31:05.668054Z 0 [System] [MY-010931] [Server] /usr/sbin/mysqld: ready for connections. Version: '8.4.11'  socket: '/var/run/mysqld/mysqld.sock'  port: 3306  MySQL Community Server - GPL.
```

### DNS-based connectivity — the key lesson

```console
# alpine's ping is busybox ping (no -c needed differently, -c works same).
# alpine has no bash, use sh -c via docker exec.

# --- backend -> frontend by container NAME: backend and frontend share dn-net-frontend ---
[aman@macos ~]$ docker exec dn-backend ping -c 2 dn-frontend
PING dn-frontend (172.19.0.2): 56 data bytes
64 bytes from 172.19.0.2: seq=0 ttl=64 time=0.405 ms
64 bytes from 172.19.0.2: seq=1 ttl=64 time=0.066 ms

--- dn-frontend ping statistics ---
2 packets transmitted, 2 packets received, 0% packet loss
round-trip min/avg/max = 0.066/0.235/0.405 ms


# --- backend -> database by container NAME: backend and database share dn-net-database ---
[aman@macos ~]$ docker exec dn-backend ping -c 2 dn-database
PING dn-database (172.21.0.2): 56 data bytes
64 bytes from 172.21.0.2: seq=0 ttl=64 time=0.453 ms
64 bytes from 172.21.0.2: seq=1 ttl=64 time=0.096 ms

--- dn-database ping statistics ---
2 packets transmitted, 2 packets received, 0% packet loss
round-trip min/avg/max = 0.096/0.274/0.453 ms


# --- frontend -> database by container NAME: they share NO network -> expect real failure ---
[aman@macos ~]$ docker exec dn-frontend ping -c 2 dn-database
ping: bad address 'dn-database'
```

### Which containers are attached to which network

```console
[aman@macos ~]$ docker network inspect dn-net-frontend --format 'Containers on dn-net-frontend: {{range $k,$v := .Containers}}{{$v.Name}} ({{$v.IPv4Address}}) {{end}}'
Containers on dn-net-frontend: dn-frontend (172.19.0.2/16) dn-backend (172.19.0.3/16) 

[aman@macos ~]$ docker network inspect dn-net-database --format 'Containers on dn-net-database: {{range $k,$v := .Containers}}{{$v.Name}} ({{$v.IPv4Address}}) {{end}}'
Containers on dn-net-database: dn-database (172.21.0.2/16) dn-backend (172.21.0.3/16) 

[aman@macos ~]$ docker network inspect dn-net-backend --format 'Containers on dn-net-backend: {{range $k,$v := .Containers}}{{$v.Name}} ({{$v.IPv4Address}}) {{end}}'
Containers on dn-net-backend: 

# --- dn-net-backend is genuinely empty: created per the assignment's 'create 3      ---
# --- networks', but the container-to-network wiring that produces the DNS demo      ---
# --- above only needed frontend<->net-frontend<->backend<->net-database<->database. ---
```

### Container interfaces — backend has TWO (one per attached network)

```console
# alpine images are minimal and don't ship iproute2 by default; install it for this demo.
[aman@macos ~]$ docker exec dn-backend apk add --no-cache iproute2 >/dev/null 2>&1; docker exec dn-backend ip -br a
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
eth0@if330       UP             172.19.0.3/16 
eth1@if331       UP             172.21.0.3/16 


# --- frontend (nginx:alpine) for comparison: exactly ONE non-loopback interface ---
[aman@macos ~]$ docker exec dn-frontend apk add --no-cache iproute2 >/dev/null 2>&1; docker exec dn-frontend ip -br a
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
eth0@if321       UP             172.19.0.2/16 


# --- database (mysql:8, Oracle Linux base) for comparison: also ONE interface ---
[aman@macos ~]$ docker exec dn-database bash -c 'command -v ip >/dev/null || microdnf install -y iproute >/dev/null 2>&1; ip -br a'
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
eth0@if326       UP             172.21.0.2/16 
```

### Why the default "bridge" network does NOT give DNS-by-name

```console
# Two throwaway containers on the legacy default bridge (no --network flag).
[aman@macos ~]$ docker run -d --name dn-legacy1 --network bridge alpine:latest sleep infinity
6072b9c33627d60544375daa7ffe0bdb0b95bb82b11eb2d7edb80c7cb7cf861d

[aman@macos ~]$ docker run -d --name dn-legacy2 --network bridge alpine:latest sleep infinity
5a5863f723106aa2c90290f35aba16d5e3e95d52dae9ffaa0e0941b524a16dd8

# --- raw connectivity by IP works fine on the default bridge ---
[aman@macos ~]$ LEGACY2_IP=$(docker inspect dn-legacy2 --format '{{.NetworkSettings.Networks.bridge.IPAddress}}'); echo "dn-legacy2 IP = $LEGACY2_IP"; docker exec dn-legacy1 ping -c 2 $LEGACY2_IP
dn-legacy2 IP = 172.17.0.7
PING 172.17.0.7 (172.17.0.7): 56 data bytes
64 bytes from 172.17.0.7: seq=0 ttl=64 time=0.111 ms
64 bytes from 172.17.0.7: seq=1 ttl=64 time=0.141 ms

--- 172.17.0.7 ping statistics ---
2 packets transmitted, 2 packets received, 0% packet loss
round-trip min/avg/max = 0.111/0.126/0.141 ms

# --- but ping by container NAME on the default bridge fails: no embedded DNS there ---
[aman@macos ~]$ docker exec dn-legacy1 ping -c 2 dn-legacy2
ping: bad address 'dn-legacy2'

# --- root cause: compare /etc/resolv.conf. Default bridge forwards straight to the ---
# --- Docker Desktop VM's external resolver; a user-defined network (dn-net-frontend, ---
# --- used by dn-backend) points at Docker's embedded DNS server 127.0.0.11, which is ---
# --- what actually knows other container names on that network.                      ---
[aman@macos ~]$ docker exec dn-legacy1 cat /etc/resolv.conf
# Generated by Docker Engine.
# This file can be edited; Docker Engine will not make further changes once it
# has been modified.

nameserver 192.168.65.7

# Based on host file: '/etc/resolv.conf' (legacy)
# Overrides: []

[aman@macos ~]$ docker exec dn-backend cat /etc/resolv.conf
# Generated by Docker Engine.
# This file can be edited; Docker Engine will not make further changes once it
# has been modified.

nameserver 127.0.0.11
options ndots:0

# Based on host file: '/etc/resolv.conf' (internal resolver)
# ExtServers: [host(192.168.65.7)]
# Overrides: []
# Option ndots from: internal

# --- cleanup the throwaway default-bridge demo containers ---
[aman@macos ~]$ docker rm -f dn-legacy1 dn-legacy2
dn-legacy1
dn-legacy2
```

### Cleanup (Task 1)

```console
[aman@macos ~]$ docker rm -f dn-frontend dn-backend dn-database
dn-frontend
dn-backend
dn-database

[aman@macos ~]$ docker network rm dn-net-frontend dn-net-backend dn-net-database
dn-net-frontend
dn-net-backend
dn-net-database

[aman@macos ~]$ docker network ls
NETWORK ID     NAME                     DRIVER    SCOPE
871ee7c20374   bridge                   bridge    local
d74a51eb7ed1   host                     host      local
6e9b53a4668b   mirror-control_default   bridge    local
3e9a572dd575   none                     null      local
```
