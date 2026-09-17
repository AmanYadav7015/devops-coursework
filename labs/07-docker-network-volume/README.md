# Assignment 7 — Docker Network & Volume

Every command in this file was executed on the machine below and every `text` block is the real
terminal output, copied unedited.

| | |
|---|---|
| Host OS | macOS (Darwin 25.5.0, arm64 / Apple Silicon) |
| Docker Engine | 29.4.1 — server reports `linux/arm64` |
| Docker runtime | Docker Desktop (containers run inside a Linux VM) |
| Images used | `nginx:alpine`, `alpine:3.20`, `mysql:8`, `httpd:2.4` |

All resources created here are prefixed `hw07-` so they can be found and removed cleanly.
The final section shows the teardown.

---

## Table of contents

1. [Task 1 — Three containers, three networks, controlled connectivity](#task-1--three-containers-three-networks-controlled-connectivity)
2. [Task 2 — Host network with Apache (and the honest macOS result)](#task-2--host-network-with-apache-and-the-honest-macos-result)
3. [Task 3 — Bind mounts, named volumes and tmpfs](#task-3--bind-mounts-named-volumes-and-tmpfs)
4. [Task 4 — Overlay networks](#task-4--overlay-networks)
5. [Cleanup](#cleanup)

---

## Task 1 — Three containers, three networks, controlled connectivity

### The goal

Three tiers — Frontend, Backend, Database — on three separate user-defined bridge networks.
The Backend sits on **two** networks so it can talk to both neighbours, while the Frontend and the
Database share **no** network at all and therefore cannot reach each other. This is the classic
"the web tier must never touch the database directly" pattern, enforced by the network layer rather
than by application code.

### Topology

```text
                        macOS host
                            |
                    published port 8094
                            |
  +=========================|========================================+
  |                         v                                        |
  |  +------------------------------------+                          |
  |  |  hw07-frontend-net   172.20.0.0/16 |                          |
  |  |                                    |                          |
  |  |   [ hw07-frontend ]                |                          |
  |  |     nginx:alpine                   |                          |
  |  |     172.20.0.2                     |                          |
  |  |            ^                       |                          |
  |  |            | ping / HTTP  OK       |                          |
  |  |            v                       |                          |
  |  |   [ hw07-backend  ] 172.20.0.3 ----+---+                      |
  |  |     alpine:3.20                    |   |                      |
  |  +------------------------------------+   | same container,      |
  |                                           | second NIC           |
  |  +------------------------------------+   |                      |
  |  |  hw07-backend-net    172.21.0.0/16 |   |                      |
  |  |                                    |   |                      |
  |  |   [ hw07-backend  ] 172.21.0.2 <---+---+                      |
  |  |            ^                       |                          |
  |  |            | ping / MySQL 3306 OK  |                          |
  |  |            v                       |                          |
  |  |   [ hw07-database ] 172.21.0.3 ----+---+                      |
  |  |     mysql:8                        |   |                      |
  |  +------------------------------------+   | same container,      |
  |                                           | second NIC           |
  |  +------------------------------------+   |                      |
  |  |  hw07-db-net         172.22.0.0/16 |   |                      |
  |  |                                    |   |                      |
  |  |   [ hw07-database ] 172.22.0.2 <---+---+                      |
  |  |     private admin / backup segment |                          |
  |  +------------------------------------+                          |
  |                                                                  |
  |   hw07-frontend  and  hw07-database  share NO network            |
  |   =====>  name resolution fails AND direct IP is unreachable     |
  +==================================================================+


  Membership summary
  ------------------
  hw07-frontend  ->  hw07-frontend-net
  hw07-backend   ->  hw07-frontend-net  +  hw07-backend-net     (2 networks)
  hw07-database  ->  hw07-backend-net   +  hw07-db-net
```

### Step 1 — Create the three user-defined bridge networks

```bash
docker network create --driver bridge hw07-frontend-net
docker network create --driver bridge hw07-backend-net
docker network create --driver bridge hw07-db-net

docker network ls --filter name=hw07
```

Output:

```text
d373114c4a8f00099e31f86352c8f482b8351438479232439cd02a2ae76fa933
65dc5ab5f0405aafd3b8f4b340de85d8c8b942abc082bcc1d471a3852374cb13
6f886dd5d418a03ddf1cfbeb2589d5d1eb048303647eca53d399622df1d840d8

NETWORK ID     NAME                DRIVER    SCOPE
65dc5ab5f040   hw07-backend-net    bridge    local
6f886dd5d418   hw07-db-net         bridge    local
d373114c4a8f   hw07-frontend-net   bridge    local
```

Each `docker network create` prints the new network ID. Notice `SCOPE` is `local` — a bridge network
exists only on this one Docker host. That single word is the difference between this task and
Task 4, where the scope becomes `swarm`.

**Why user-defined and not the default `bridge`?** Docker's built-in `bridge` network has no
embedded DNS for container names. On a *user-defined* bridge Docker runs a DNS resolver at
`127.0.0.11` inside every attached container, and container names become resolvable hostnames. That
is what makes `ping hw07-database` work below, and it only works on user-defined networks.

### Step 2 — Start the three containers

```bash
docker run -d --name hw07-frontend --network hw07-frontend-net -p 8094:80 nginx:alpine

docker run -d --name hw07-backend  --network hw07-frontend-net alpine:3.20 sleep infinity
docker network connect hw07-backend-net hw07-backend

docker run -d --name hw07-database --network hw07-backend-net \
  -e MYSQL_ROOT_PASSWORD=hw07secret -e MYSQL_DATABASE=appdb mysql:8
docker network connect hw07-db-net hw07-database

docker ps --filter name=hw07 --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
```

Output:

```text
d0558adc595203a38b0c41e32c66964659c8952c3096ca874ac8928419d1a8e2
625378ec5b5f6657f040645b3584013909adcdaac3c1bfe85bd227a34ffa3061
962b69b661c40add51de974174c6b3b7428a3a858a0d8470926e9bae3052f903

NAMES           IMAGE          STATUS                  PORTS
hw07-database   mysql:8        Up Less than a second   3306/tcp, 33060/tcp
hw07-backend    alpine:3.20    Up Less than a second   
hw07-frontend   nginx:alpine   Up Less than a second   0.0.0.0:8094->80/tcp, [::]:8094->80/tcp
```

A container can only be attached to **one** network in `docker run`. The second (and third)
attachment is done afterwards with `docker network connect`, which hot-plugs an extra virtual NIC
into the running container. That is the mechanism behind "the backend is on two networks".

`alpine` has no long-running process of its own, so `sleep infinity` is used as PID 1 to keep the
backend container alive for the experiments.

### Step 3 — Install the network tools in the Alpine backend

```bash
docker exec hw07-backend apk add --no-cache iputils bind-tools netcat-openbsd mysql-client
```

Output (tail):

```text
(18/32) Installing iputils-ping (20240117-r0)
(20/32) Installing iputils (20240117-r0)
(28/32) Installing mariadb-client (10.11.18-r0)
(29/32) Installing mysql-client (10.11.18-r0)
(32/32) Installing netcat-openbsd (1.226-r0)
Executing busybox-1.36.1-r31.trigger
OK: 104 MiB in 46 packages
```

The stock `alpine` image ships no `ping`, no `dig` and no full `nc`. They are installed here so the
connectivity tests below are real network tests and not "command not found" errors. The same
packages are installed into the frontend later, so both ends of the test use identical tooling.

### Step 4 — Prove the membership with `docker network inspect`

```bash
for n in hw07-frontend-net hw07-backend-net hw07-db-net; do
  echo "### $n"
  docker network inspect "$n" --format '{{range .Containers}}{{.Name}} {{.IPv4Address}}
{{end}}'
done
```

Output:

```text
### hw07-frontend-net
hw07-backend 172.20.0.3/16
hw07-frontend 172.20.0.2/16

### hw07-backend-net
hw07-backend 172.21.0.2/16
hw07-database 172.21.0.3/16

### hw07-db-net
hw07-database 172.22.0.2/16
```

This is the whole topology in nine lines. `hw07-backend` appears on two networks with two different
IP addresses — `172.20.0.3` and `172.21.0.2` — because it genuinely has two NICs. `hw07-frontend`
appears only in the first list and `hw07-database` only in the second and third: they have no
network in common.

The full JSON for one network, showing the IPAM subnet and the per-container endpoint detail:

```bash
docker network inspect hw07-backend-net
```

Output:

```text
[
    {
        "Name": "hw07-backend-net",
        "Id": "65dc5ab5f0405aafd3b8f4b340de85d8c8b942abc082bcc1d471a3852374cb13",
        "Created": "2026-09-17T16:12:31.525938292Z",
        "Scope": "local",
        "Driver": "bridge",
        "EnableIPv4": true,
        "EnableIPv6": false,
        "IPAM": {
            "Driver": "default",
            "Options": {},
            "Config": [
                {
                    "Subnet": "172.21.0.0/16",
                    "Gateway": "172.21.0.1"
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
        "Containers": {
            "625378ec5b5f6657f040645b3584013909adcdaac3c1bfe85bd227a34ffa3061": {
                "Name": "hw07-backend",
                "EndpointID": "afa15a3df3fba2a03e28f558406a66e5781e524eac1fafd98f7be865c8a7432e",
                "MacAddress": "d6:a6:61:c8:21:62",
                "IPv4Address": "172.21.0.2/16",
                "IPv6Address": ""
            },
            "962b69b661c40add51de974174c6b3b7428a3a858a0d8470926e9bae3052f903": {
                "Name": "hw07-database",
                "EndpointID": "6756c884958c328ef6891c08994408644c734cd983cc7861e9e5f65b09876524",
                "MacAddress": "2e:00:3a:55:dc:29",
                "IPv4Address": "172.21.0.3/16",
                "IPv6Address": ""
            }
        },
        "Status": {
            "IPAM": {
                "Subnets": {
                    "172.21.0.0/16": {
                        "IPsInUse": 5,
                        "DynamicIPsAvailable": 65531
                    }
                }
            }
        }
    }
]
```

Each container has its own `EndpointID` and `MacAddress` *on this network*. An endpoint is the
per-network attachment object; a container with two endpoints has two MAC addresses and two IPs.
`"Internal": false` means the network has a route out to the internet through NAT;
`--internal` would have removed that. `"Attachable": false` matters only for overlay networks
(Task 4).

### Step 5 — Wait for MySQL to finish initialising

MySQL does not accept connections the moment the container reports `Up`. It has to create the data
directory, the system tables and the root user first. A readiness loop is the correct way to wait —
not a fixed `sleep`.

```bash
for i in $(seq 1 40); do
  if docker exec hw07-database mysqladmin ping -uroot -phw07secret 2>/dev/null | grep -q alive; then
    echo "attempt $i: mysqld is alive"; break
  fi
  echo "attempt $i: not ready yet"
  sleep 5
done

docker exec hw07-database mysqladmin ping -uroot -phw07secret
docker exec hw07-database mysql -uroot -phw07secret -e "SELECT VERSION(); SHOW DATABASES;"
```

Output:

```text
attempt 1: mysqld is alive

mysqladmin: [Warning] Using a password on the command line interface can be insecure.
mysqld is alive

mysql: [Warning] Using a password on the command line interface can be insecure.
VERSION()
8.4.11
Database
appdb
information_schema
mysql
performance_schema
sys
```

The `mysql:8` tag currently resolves to **8.4.11**, and it has a native `arm64` image, so it runs
natively on Apple Silicon with no emulation warning. `appdb` in the list is the database that
`MYSQL_DATABASE=appdb` asked the entrypoint to create. The password warning is expected — it is
MySQL telling you that a password on the command line is visible in the process table.

### Step 6 — Backend reaches the Frontend by container name

```bash
docker exec hw07-backend ping -c 3 hw07-frontend
docker exec hw07-backend nc -zv hw07-frontend 80
```

Output:

```text
PING hw07-frontend (172.20.0.2) 56(84) bytes of data.
64 bytes from hw07-frontend.hw07-frontend-net (172.20.0.2): icmp_seq=1 ttl=64 time=0.112 ms
64 bytes from hw07-frontend.hw07-frontend-net (172.20.0.2): icmp_seq=2 ttl=64 time=0.146 ms
64 bytes from hw07-frontend.hw07-frontend-net (172.20.0.2): icmp_seq=3 ttl=64 time=0.435 ms

--- hw07-frontend ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2049ms
rtt min/avg/max/mdev = 0.112/0.231/0.435/0.144 ms

Connection to hw07-frontend (172.20.0.2) 80 port [tcp/http] succeeded!
```

**0% packet loss.** Look closely at the reply hostname: `hw07-frontend.hw07-frontend-net`. Docker's
embedded DNS answered with the fully qualified name *including the network it resolved on*. That is
direct evidence that resolution happened through the user-defined network's DNS and not through
`/etc/hosts` or an external resolver.

### Step 7 — Backend reaches the Database by container name

```bash
docker exec hw07-backend ping -c 3 hw07-database
docker exec hw07-backend nc -zv hw07-database 3306
```

Output:

```text
PING hw07-database (172.21.0.3) 56(84) bytes of data.
64 bytes from hw07-database.hw07-backend-net (172.21.0.3): icmp_seq=1 ttl=64 time=0.163 ms
64 bytes from hw07-database.hw07-backend-net (172.21.0.3): icmp_seq=2 ttl=64 time=0.113 ms
64 bytes from hw07-database.hw07-backend-net (172.21.0.3): icmp_seq=3 ttl=64 time=0.135 ms

--- hw07-database ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2030ms
rtt min/avg/max/mdev = 0.113/0.137/0.163/0.020 ms

Connection to hw07-database (172.21.0.3) 3306 port [tcp/mysql] succeeded!
```

Same container, different network, different subnet — `172.21.0.3` this time, resolved as
`hw07-database.hw07-backend-net`. The backend is reaching both tiers, each over the correct NIC,
without ever knowing an IP address.

### Step 8 — Application-level proof, not just ICMP

A ping only proves layer 3. These two commands prove the applications actually serve traffic across
the networks.

```bash
docker exec hw07-backend wget -qO- http://hw07-frontend

docker run --rm --network hw07-backend-net mysql:8 \
  mysql -h hw07-database -uroot -phw07secret -e "SELECT @@hostname AS db_host, VERSION() AS ver;"
```

Output:

```text
<!DOCTYPE html>
<html>
<head>
<title>Welcome to nginx!</title>
<style>
html { color-scheme: light dark; }
body { width: 35em; margin: 0 auto;
font-family: Tahoma, Verdana, Arial, sans-serif; }

mysql: [Warning] Using a password on the command line interface can be insecure.
db_host	ver
962b69b661c4	8.4.11
```

Real HTTP from nginx, and a real SQL result set from MySQL. `db_host` returns `962b69b661c4`, which
is the first twelve characters of the `hw07-database` container ID printed in Step 2 — the query
demonstrably ran on that container, reached over `hw07-backend-net`.

One honest aside worth recording. The first attempt used the Alpine `mysql-client` package, which is
actually MariaDB's client, and it failed:

```text
ERROR 1045 (28000): Plugin caching_sha2_password could not be loaded:
Error loading shared library /usr/lib/mariadb/plugin/caching_sha2_password.so: No such file or directory
```

That is **not** a networking failure — it is an authentication-plugin failure, which can only happen
*after* a successful TCP connection and a completed MySQL protocol handshake. MySQL 8 defaults to
`caching_sha2_password` and the MariaDB client does not ship that plugin. Using the official
`mysql:8` client image, as above, fixes it.

### Step 9 — The isolation proof: Frontend must NOT reach the Database

The same tools are installed in the frontend so the comparison is fair:

```bash
docker exec hw07-frontend apk add --no-cache iputils bind-tools netcat-openbsd
docker inspect hw07-frontend --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} -> {{$v.IPAddress}}
{{end}}'
```

Output:

```text
OK: 67.1 MiB in 90 packages

hw07-frontend-net -> 172.20.0.2
```

The frontend is on exactly one network. Now the tests:

```bash
docker exec hw07-frontend nslookup hw07-database   ; echo "exit=$?"
docker exec hw07-frontend ping -c 2 hw07-database  ; echo "exit=$?"
docker exec hw07-frontend nc -zv -w 5 hw07-database 3306 ; echo "exit=$?"
docker exec hw07-frontend nc -zv -w 5 172.21.0.3   3306  ; echo "exit=$?"
docker exec hw07-frontend ping -c 2 hw07-backend   ; echo "exit=$?"
```

Output:

```text
### A. Frontend -> Database by name (DNS lookup)
Server:		127.0.0.11
Address:	127.0.0.11#53

** server can't find hw07-database: NXDOMAIN

exit=1

### B. Frontend -> Database by name (ping)
ping: hw07-database: Name does not resolve
exit=2

### C. Frontend -> Database by name (nc to 3306)
nc: getaddrinfo for host "hw07-database" port 3306: Name does not resolve
exit=1

### D. Frontend -> Database by raw IP 172.21.0.3 (bypassing DNS)
nc: connect to 172.21.0.3 port 3306 (tcp) timed out: Operation in progress
exit=1

### E. control: Frontend -> Backend by name (same network, must work)
PING hw07-backend (172.20.0.3) 56(84) bytes of data.
64 bytes from hw07-backend.hw07-frontend-net (172.20.0.3): icmp_seq=1 ttl=64 time=0.069 ms
64 bytes from hw07-backend.hw07-frontend-net (172.20.0.3): icmp_seq=2 ttl=64 time=0.043 ms

--- hw07-backend ping statistics ---
2 packets transmitted, 2 received, 0% packet loss, time 2003ms
rtt min/avg/max/mdev = 0.043/0.056/0.069/0.013 ms
exit=0
```

This is the most important output in Task 1. Read it in order:

- **A** — the DNS server is `127.0.0.11`, Docker's embedded resolver, and it answers **NXDOMAIN**.
  The resolver only publishes the names of containers that share a network with the asker. From the
  frontend's point of view the database simply does not exist as a name.
- **B and C** — `ping` and `nc` both fail at name resolution, before a single packet is sent.
- **D** is the test that makes the proof airtight. Bypassing DNS entirely and dialling the raw IP
  `172.21.0.3` does **not** get refused — it **times out**. A refusal would mean the packet reached
  the host and was rejected; a timeout means the packet was never delivered at all. Each bridge
  network is a separate Linux bridge with its own `iptables`/`nftables` rules, and the
  `DOCKER-ISOLATION` chains drop traffic between bridges. So this is genuine layer-3 isolation, not
  merely a missing DNS entry. An attacker who compromised the frontend and hardcoded the database IP
  still could not get through.
- **E** is the control. If A–D failed because the tools were broken, E would fail too. It succeeds,
  so the tools work and only the isolated path fails.

### Optional: the same topology as a Compose file

`docker-compose.yml` in this folder expresses exactly the same topology declaratively. Compose
attaches a service to any number of networks in one file, so no `network connect` step is needed.

```bash
docker compose config --quiet && echo "compose file is valid"
docker compose up -d
docker compose ps --format 'table {{.Name}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
```

Output:

```text
compose file is valid

 Network hw07-db-net Created 
 Network hw07-frontend-net Creating 
 Network hw07-frontend-net Created 
 Container hw07-database Creating 
 Container hw07-frontend Creating 
 Container hw07-database Created 
 Container hw07-backend Creating 
 Container hw07-frontend Created 
 Container hw07-backend Created 
 Container hw07-frontend Starting 
 Container hw07-database Starting 
 Container hw07-frontend Started 
 Container hw07-database Started 
 Container hw07-backend Starting 
 Container hw07-backend Started 

NAME            IMAGE          STATUS                                     PORTS
hw07-backend    alpine:3.20    Up Less than a second                      
hw07-database   mysql:8        Up Less than a second (health: starting)   3306/tcp, 33060/tcp
hw07-frontend   nginx:alpine   Up Less than a second                      0.0.0.0:8094->80/tcp, [::]:8094->80/tcp
```

Compose created the three networks and wired each service into the right ones in a single command,
with no `docker network connect` step — the `backend` service simply lists two entries under
`networks:`. The membership is identical to the manual build:

```bash
for n in hw07-frontend-net hw07-backend-net hw07-db-net; do
  echo "### $n"
  docker network inspect "$n" --format '{{range .Containers}}{{.Name}} {{.IPv4Address}}
{{end}}'
done
```

Output:

```text
### hw07-frontend-net
hw07-backend 172.22.0.3/16
hw07-frontend 172.22.0.2/16

### hw07-backend-net
hw07-backend 172.20.0.3/16
hw07-database 172.20.0.2/16

### hw07-db-net
hw07-database 172.21.0.2/16
```

The subnets are allocated in a different order than the manual run (`172.22` for the frontend network
this time) because Docker's IPAM hands out the next free `/16` as networks are created — the subnet
numbers are never something to depend on. The *membership* is what matters and it matches exactly.

The `healthcheck:` block on the database replaces the manual readiness loop from Step 5:

```bash
docker compose ps --format 'table {{.Name}}\t{{.Status}}'
```

Output:

```text
NAME            STATUS
hw07-backend    Up 10 seconds
hw07-database   Up 10 seconds (healthy)
hw07-frontend   Up 10 seconds
```

And the connectivity and isolation behave identically under Compose:

```bash
docker exec hw07-backend  sh -c 'nc -z -w 3 hw07-frontend 80   && echo "backend -> frontend:80 OK"'
docker exec hw07-backend  sh -c 'nc -z -w 3 hw07-database 3306 && echo "backend -> database:3306 OK"'
docker exec hw07-frontend sh -c 'nc -z -w 3 hw07-database 3306' || echo "frontend -> database:3306 FAILED (as designed)"
```

Output:

```text
backend -> frontend:80 OK
backend -> database:3306 OK
nc: bad address 'hw07-database'
frontend -> database:3306 FAILED (as designed)
```

These are freshly created containers with only BusyBox `nc` — no extra packages installed — and the
result is the same: the backend reaches both neighbours by name, and the frontend cannot even resolve
the database. `depends_on` controls *start order* only, which is why the healthcheck is still needed
if something must wait for MySQL to be genuinely ready.

---

## Task 2 — Host network with Apache (and the honest macOS result)

### What was asked

Pull the Apache image, run it with `--network host`, and reach the site on port 80.

### The attempt

```bash
docker pull httpd:2.4
docker network ls --filter driver=host
docker run -d --name hw07-apache-host --network host httpd:2.4
docker ps -a --filter name=hw07-apache-host --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
```

Output:

```text
Status: Downloaded newer image for httpd:2.4

NETWORK ID     NAME      DRIVER    SCOPE
d74a51eb7ed1   host      host      local

3bb72889a1b457c92835d8a97921c6e6adf3fbd133e5ee23e41a98af4c95a987

NAMES              STATUS                  PORTS
hw07-apache-host   Up Less than a second   
```

The container starts, exits nothing, logs nothing, and the `PORTS` column is **empty** — there is no
`0.0.0.0:80->80/tcp` mapping, because host networking does not map ports, it shares a namespace.

### Now try to actually reach it from macOS

```bash
curl -sS -m 8 -i http://localhost:80/
curl -sS -m 8 http://127.0.0.1:80/
sudo lsof -nP -iTCP:80 -sTCP:LISTEN
```

Output:

```text
curl: (7) Failed to connect to localhost port 80 after 0 ms: Couldn't connect to server

curl: (7) Failed to connect to 127.0.0.1 port 80 after 0 ms: Couldn't connect to server

### Is anything listening on macOS port 80?
(no output — nothing is listening)
```

**It does not work.** `curl: (7)` after 0 ms is an immediate connection refusal, and `lsof` confirms
no process on macOS holds port 80. This is the real result on this machine and it is not a mistake in
the command.

### Why it fails — proving the cause rather than guessing

Apache is running. The question is *where*.

```bash
docker exec hw07-apache-host httpd -v
docker exec hw07-apache-host hostname
docker exec hw07-apache-host sh -c 'cat /proc/net/tcp6 | awk "{print \$2, \$4}"' | grep ':0050'
```

Output:

```text
Server version: Apache/2.4.68 (Unix)
Server built:   Aug 25 2026 00:21:09

docker-desktop

00000000000000000000000000000000:0050 0A
```

Three findings, in order of importance:

1. `hostname` returns **`docker-desktop`**, not the container's own ID and not the Mac's hostname.
   The container really did join the host network namespace — it is just that "the host" is the
   Docker Desktop **Linux VM**, not macOS.
2. `/proc/net/tcp6` shows a socket on port `0x0050` = **80**, in state `0A` = `LISTEN`, bound to the
   wildcard address. Apache is definitely listening on port 80 — inside the VM.
3. macOS has nothing on port 80. The two facts are consistent: the listener exists in a network
   namespace that macOS is not part of.

### Confirming it from inside the VM

If the diagnosis is right, another `--network host` container — which lands in the same VM namespace —
should reach Apache on `127.0.0.1:80` even though macOS cannot.

```bash
docker run --rm --network host alpine:3.20 sh -c 'wget -qO- -T 5 http://127.0.0.1:80/'
```

Output:

```text
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
<head>
<title>It works! Apache httpd</title>
</head>
```

**"It works!"** — from inside the VM. That is the conclusive proof. `--network host` did exactly
what it promises on Linux; the namespace it shared just is not macOS's.

### The architectural reason

```text
   Linux                                macOS / Docker Desktop
   -----                                ----------------------

   +-------------------------+          +----------------------------------------+
   | Linux kernel            |          | macOS kernel (Darwin)                  |
   |                         |          |   loopback 127.0.0.1  <-- curl asks    |
   |  host netns             |          |        X  nothing listening here       |
   |   eth0, lo              |          |                                        |
   |   :80 <== container     |          |   +--------------------------------+   |
   |          --network host |          |   | Linux VM  (hostname            |   |
   |                         |          |   |            "docker-desktop")   |   |
   |  curl localhost:80  OK  |          |   |   VM host netns                |   |
   +-------------------------+          |   |     :80 <== container          |   |
                                        |   |            --network host      |   |
   One kernel, one namespace.           |   +--------------------------------+   |
   "host" == the machine you typed on.  +----------------------------------------+

                                        Two kernels. "host" == the VM, not the Mac.
                                        Nothing bridges VM :80 to macOS :80 unless
                                        Docker Desktop is told to.
```

Docker Desktop does ship an opt-in **host networking** feature (Settings -> Resources -> Network ->
"Enable host networking") which adds a userspace forwarder so some host-network traffic reaches
macOS. On this machine that key is not present in Docker Desktop's settings store:

```bash
grep -i -E 'hostNetworking|host-networking' \
  ~/Library/Group\ Containers/group.com.docker/settings-store.json
```

Output:

```text
key not present in settings-store.json
```

So the feature is not enabled here, and the behaviour observed above is the expected behaviour.
The same limitation applies to Docker Desktop for Windows and to Rancher Desktop / Colima / Podman
Machine on macOS — anything where the Linux kernel lives in a VM.

### The practical alternative: publish the port

On macOS the portable answer is `-p`, which makes Docker Desktop open a **real socket on macOS** and
forward it into the VM and into the container.

```bash
docker rm -f hw07-apache-host
docker run -d --name hw07-apache-p80 -p 80:80 httpd:2.4
docker ps --filter name=hw07-apache-p80 --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
curl -sS -m 8 http://localhost:80/
sudo lsof -nP -iTCP:80 -sTCP:LISTEN
```

Output:

```text
3cb8462b5d806ea25bfe260f9c5785d91ac957b217f64db7ffe5cb224d404804

NAMES             STATUS         PORTS
hw07-apache-p80   Up 2 seconds   0.0.0.0:80->80/tcp, [::]:80->80/tcp

<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
<head>
<title>It works! Apache httpd</title>
</head>
<body>
<p>It works!</p>
</body>
</html>

COMMAND     PID USER   FD   TYPE             DEVICE SIZE/OFF NODE NAME
com.docke 98796 aman  140u  IPv6 0xe7da8395a2c5e262      0t0  TCP *:80 (LISTEN)
```

**Apache is now served on port 80 as the assignment asked.** The `lsof` line is the clean contrast
with the failed attempt: this time a real macOS process — `com.docker` (Docker Desktop's VM
networking proxy) — holds `*:80`. With `--network host` that line was absent. `-p` creates a macOS
listener; `--network host` does not.

The same container was also verified on a non-privileged port:

```bash
docker run -d --name hw07-apache-published -p 8095:80 httpd:2.4
curl -sS -i -m 8 http://localhost:8095/
```

Output:

```text
NAMES                   IMAGE       STATUS                  PORTS
hw07-apache-published   httpd:2.4   Up Less than a second   0.0.0.0:8095->80/tcp, [::]:8095->80/tcp

HTTP/1.1 200 OK
Date: Thu, 17 Sep 2026 16:16:35 GMT
Server: Apache/2.4.68 (Unix)
Last-Modified: Fri, 07 Nov 2025 08:23:08 GMT
ETag: "bf-642fce432f300"
Accept-Ranges: bytes
Content-Length: 191
Content-Type: text/html

<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
<head>
<title>It works! Apache httpd</title>
</head>
```

### What host networking actually gives you on real Linux

On a native Linux Docker host, `--network host` is genuinely useful and behaves very differently
from bridge networking.

| | Bridge (default) | Host (`--network host`) |
|---|---|---|
| Network namespace | Container gets its own | Container **shares the host's** |
| IP address | Private, e.g. `172.17.0.2` | The host's own IP — no separate address |
| Reaching a service | Requires `-p 8080:80` | Bind port 80, it *is* host port 80 |
| NAT / `iptables` DNAT | Yes, every packet is translated | **None** |
| `docker-proxy` userspace hop | Yes (for published ports) | None |
| Throughput / latency | Slight NAT overhead | Near bare-metal |
| Port conflicts | Impossible between containers | **Two containers cannot both bind :80** |
| Isolation | Strong — separate netns and firewall view | **None** — container sees every host interface |
| Container-name DNS | Yes, on user-defined bridges | No — you are on the host's resolver |
| Works on Docker Desktop / macOS | Yes | Only with the opt-in feature, and only into the VM |

**Use host networking when:**

- Throughput or latency matters and NAT is measurably expensive — high packet-rate proxies,
  load balancers, media servers, trading systems.
- The workload must see the **real client IP** rather than the bridge gateway address.
- The service needs a large or dynamic port range (SIP/RTP, FTP passive mode, game servers) where
  enumerating `-p` mappings is impractical.
- The container is a node-level agent that must observe the host's interfaces — Prometheus
  `node_exporter`, a CNI plugin, `tcpdump`-style monitoring, a DHCP or mDNS responder.
- A protocol needs real multicast or broadcast on the host LAN.

**The trade-offs you accept:**

- **No port isolation.** Only one process on the whole machine can hold a given port. Two replicas
  of the same container cannot run side by side.
- **No network isolation.** The container can reach every host loopback service — including an
  unauthenticated admin port, a local database bound to `127.0.0.1`, or the Docker socket's TCP
  listener. A compromise inside the container becomes a compromise of the host's network position.
- **No container-name DNS.** Service discovery has to come from somewhere else.
- **Not portable.** The command works on a Linux CI runner and fails on a developer's Mac, which is
  exactly what this task demonstrated.
- **Kubernetes equivalent** is `hostNetwork: true` in the pod spec, and it carries the same warnings;
  it is normally reserved for DaemonSets like ingress controllers and CNI agents.

---

## Task 3 — Bind mounts, named volumes and tmpfs

### Step 1 — Create the host folder and the page

```bash
cd homework/07-docker-network-volume
cat > bind-mount/index.html <<'EOF'
<!DOCTYPE html>
<html>
<head><title>HW07 Bind Mount</title></head>
<body>
<h1>Hello students</h1>
</body>
</html>
EOF
cat bind-mount/index.html
```

Output:

```text
<!DOCTYPE html>
<html>
<head><title>HW07 Bind Mount</title></head>
<body>
<h1>Hello students</h1>
</body>
</html>
```

### Step 2 — Mount it into nginx

```bash
docker run -d --name hw07-nginx-bind -p 8096:80 \
  -v "$(pwd)/bind-mount":/usr/share/nginx/html:ro nginx:alpine

docker ps --filter name=hw07-nginx-bind --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
curl -sS -m 8 http://localhost:8096/
```

Output:

```text
c0d412598d702dea8ef5a9168c0b3f6eb379c67d6afe0777ce0d7d182c7d55c0

NAMES             STATUS         PORTS
hw07-nginx-bind   Up 2 seconds   0.0.0.0:8096->80/tcp, [::]:8096->80/tcp

<!DOCTYPE html>
<html>
<head><title>HW07 Bind Mount</title></head>
<body>
<h1>Hello students</h1>
</body>
</html>
```

**"Hello students" is served over HTTP.** The `nginx:alpine` image ships its own default page at
`/usr/share/nginx/html`; the bind mount covers that directory entirely, so the image's page is hidden
(not deleted) and the host folder is served instead. The `:ro` suffix mounts it read-only — good
practice for static content a container should never modify.

`$(pwd)` is required because Docker needs an **absolute** host path; a relative path is interpreted
as a named volume, which is a very common beginner trap.

### Step 3 — Change the file on the host, do NOT restart the container

```bash
docker inspect hw07-nginx-bind --format 'StartedAt={{.State.StartedAt}} RestartCount={{.RestartCount}}'

cat > bind-mount/index.html <<'EOF'
<!DOCTYPE html>
<html>
<head><title>HW07 Bind Mount</title></head>
<body>
<h1>Hello students - edited on the host, no restart</h1>
<p>Bind mounts are live: the container reads the host directory directly.</p>
</body>
</html>
EOF

curl -sS -m 8 http://localhost:8096/
docker inspect hw07-nginx-bind --format 'StartedAt={{.State.StartedAt}} RestartCount={{.RestartCount}} Running={{.State.Running}}'
```

Output:

```text
### container has NOT been restarted:
StartedAt=2026-09-17T16:16:58.044190179Z RestartCount=0

### curl #2 (immediately after the edit, container untouched)
<!DOCTYPE html>
<html>
<head><title>HW07 Bind Mount</title></head>
<body>
<h1>Hello students - edited on the host, no restart</h1>
<p>Bind mounts are live: the container reads the host directory directly.</p>
</body>
</html>

### still the same container process:
StartedAt=2026-09-17T16:16:58.044190179Z RestartCount=0 Running=true
```

**This is the point of the exercise.** `StartedAt` is byte-for-byte identical before and after, and
`RestartCount` is still `0` — the container was never restarted, never reloaded, never touched. Yet
the new content is served immediately.

That is because a bind mount is not a copy. The kernel mounts the host directory at that path inside
the container's mount namespace, so `open()` from nginx lands on the very same inode the editor wrote
to. There is nothing to synchronise. This is why bind mounts are the standard tool for local
development with hot reload.

### Step 4 — Confirm the mount and the read-only flag

```bash
docker inspect hw07-nginx-bind --format '{{json .Mounts}}' | python3 -m json.tool
docker exec hw07-nginx-bind sh -c 'echo hacked > /usr/share/nginx/html/index.html'
```

Output:

```text
[
    {
        "Type": "bind",
        "Source": "/Users/aman/Desktop/devops-heros/homework/07-docker-network-volume/bind-mount",
        "Destination": "/usr/share/nginx/html",
        "Mode": "ro",
        "RW": false,
        "Propagation": "rprivate"
    }
]

sh: can't create /usr/share/nginx/html/index.html: Read-only file system
```

`"Type": "bind"` with the literal host path as `Source` — compare this with the named volume below,
where `Type` is `volume` and there is no host path. `"RW": false` is enforced by the kernel, not by
nginx: the write attempt from inside the container is rejected with **"Read-only file system"**. The
host can still edit the file freely, which is exactly the asymmetry `:ro` is for.

### Step 5 — Named volume, for comparison

```bash
docker volume create hw07-data
docker volume ls --filter name=hw07
docker volume inspect hw07-data
```

Output:

```text
hw07-data

DRIVER    VOLUME NAME
local     hw07-data

[
    {
        "CreatedAt": "2026-09-17T16:17:22Z",
        "Driver": "local",
        "Labels": null,
        "Mountpoint": "/var/lib/docker/volumes/hw07-data/_data",
        "Name": "hw07-data",
        "Options": null,
        "Scope": "local"
    }
]
```

The `Mountpoint` is inside Docker's own storage area. On macOS that path exists **inside the Linux
VM**, not on the Mac filesystem — `ls /var/lib/docker/volumes` in Terminal finds nothing. The data is
reached through Docker, which is the whole idea: the volume is a Docker-managed object, not a folder
you are meant to poke at.

Now prove it outlives its container:

```bash
docker run -d --name hw07-nginx-vol -v hw07-data:/usr/share/nginx/html nginx:alpine
docker exec hw07-nginx-vol sh -c 'echo "<h1>Hello students from a NAMED VOLUME</h1>" > /usr/share/nginx/html/index.html'
docker exec hw07-nginx-vol cat /usr/share/nginx/html/index.html

docker rm -f hw07-nginx-vol

docker run --rm -v hw07-data:/data alpine:3.20 cat /data/index.html
```

Output:

```text
<h1>Hello students from a NAMED VOLUME</h1>

hw07-nginx-vol

<h1>Hello students from a NAMED VOLUME</h1>
```

The nginx container that wrote the file was **force-removed**, and a completely different container
built from a different image (`alpine`, mounting at a different path `/data`) still reads the data
back. The volume's lifecycle is independent of any container. This is why databases use named
volumes: `docker rm -f` on the database container is survivable, `docker volume rm` is not.

### Step 6 — tmpfs, for comparison

```bash
docker run -d --name hw07-tmpfs --tmpfs /cache:rw,size=32m alpine:3.20 sleep infinity
docker exec hw07-tmpfs sh -c 'echo "scratch data" > /cache/scratch.txt; cat /cache/scratch.txt'
docker exec hw07-tmpfs sh -c 'df -h /cache; mount | grep /cache'

docker restart hw07-tmpfs
docker exec hw07-tmpfs sh -c 'ls -la /cache; cat /cache/scratch.txt'
docker volume ls --filter name=hw07
```

Output:

```text
scratch data

Filesystem                Size      Used Available Use% Mounted on
tmpfs                    32.0M      4.0K     32.0M   0% /cache
tmpfs on /cache type tmpfs (rw,nosuid,nodev,noexec,relatime,size=32768k)

hw07-tmpfs

total 4
drwxr-xr-x    2 root     root            40 Sep 17 16:17 .
drwxr-xr-x    1 root     root          4096 Sep 17 16:17 ..
cat: can't open '/cache/scratch.txt': No such file or directory

DRIVER    VOLUME NAME
local     hw07-data
```

The file was written and read back fine; a plain `docker restart` **erased it**. `/cache` is a real
`tmpfs` filesystem capped at 32 MB and mounted `nosuid,nodev,noexec`, so it lives in the VM's RAM and
is destroyed with the container's mount namespace. Note the last command: `hw07-tmpfs` never appears
in `docker volume ls`, because a tmpfs mount is not a volume object at all. Use it for secrets you do
not want written to disk, and for scratch or cache directories where losing the data is free.

### Comparison table

| | Bind mount | Named volume | tmpfs mount |
|---|---|---|---|
| Flag | `-v /abs/host/path:/in/container` | `-v myvol:/in/container` | `--tmpfs /path` |
| Long form | `--mount type=bind,src=…,dst=…` | `--mount type=volume,src=…,dst=…` | `--mount type=tmpfs,dst=…` |
| Where the data lives | Anywhere on the host filesystem you choose | `/var/lib/docker/volumes/<name>/_data`, managed by Docker | Host RAM (swap-backed) |
| Managed by Docker | No — Docker only mounts it | Yes — a first-class object | Partly — no object at all |
| Shows in `docker volume ls` | No | **Yes** | No |
| Created automatically | Must exist (Linux) / auto-created (Desktop) | Yes, on first use | Yes |
| Survives `docker rm` | Yes (it is host data) | **Yes** | **No** |
| Survives `docker restart` | Yes | Yes | **No** |
| Survives a host reboot | Yes | Yes | No |
| Host can edit it directly | **Yes — live, no restart** | Not conveniently (inside the VM on macOS) | No |
| Container writes visible on host | Yes, immediately | Only via Docker | N/A |
| Portable across hosts | No — depends on an absolute host path | Yes — recreate by name | Yes |
| Backup | Ordinary host tools (`tar`, `rsync`, git) | `docker run --rm -v vol:/d -v $PWD:/b alpine tar czf /b/v.tgz /d` | Nothing to back up |
| Performance on macOS | Slower — crosses the VM file-sharing boundary | Fast — native to the VM's filesystem | Fastest — RAM |
| Remote/cloud drivers | No | **Yes** — NFS, CIFS, cloud plugins | No |
| Permission / ownership pain | Common (host UID vs container UID) | Rare — Docker seeds ownership from the image | None |
| Pre-populated from the image | No — the mount hides whatever was there | **Yes**, if the volume is empty on first mount | No |
| Read-only variant | `:ro` | `:ro` | `--tmpfs /p:ro` |
| Typical use | Source code in dev, config files, certs, static sites | Database data, uploads, anything stateful in prod | Secrets, session scratch, caches, `/tmp` |
| Avoid when | Shipping to production, or a teammate has a different path | You need to edit the files by hand from the host | The data must survive anything |

**Rule of thumb:** bind mount for things a human edits, named volume for things a program persists,
tmpfs for things nobody should keep.

One detail from the table worth calling out, because it surprises people: a **named volume that is
empty on first mount is pre-populated from the image's contents at that path**, whereas a **bind mount
always hides** whatever the image had there. Mounting an empty named volume onto
`/usr/share/nginx/html` gives you nginx's default page; mounting an empty host directory gives you a
403.

---

## Task 4 — Overlay networks

This task was **demonstrated for real**, not only researched. A single-node Swarm was initialised on
this machine, overlay networks were created and used, and Swarm was then torn down — the last section
shows the host restored to its original state.

### What an overlay network is

The bridge networks in Task 1 are `Scope: local`. They exist on one Docker host and stop at its
boundary. An **overlay** network is `Scope: swarm`: it is a single flat layer-2 segment that spans
**many** Docker hosts, so a container on host A and a container on host B get addresses out of the
same subnet, resolve each other by name, and behave as though they were plugged into the same switch —
even if the hosts are in different racks, data centres or cloud regions.

The physical network underneath (the **underlay**) never sees those container addresses. It only ever
carries ordinary UDP between the hosts' real IPs. The container addresses live inside those UDP
packets.

### Why it needs Swarm (or an external key-value store)

An overlay network is distributed state. Every participating host has to agree on which subnet the
network uses, which IP and MAC each container holds, which host each container currently lives on,
and the encryption keys. Something has to store and replicate that. Docker offers two options:

- **Swarm mode** (the modern, built-in way). `docker swarm init` starts a Raft-replicated store inside
  the manager nodes and a gossip protocol between all nodes, and the overlay driver uses it. Nothing
  external to install.
- **An external key-value store** (the older, "Docker Engine in cluster mode" way): Consul, etcd or
  ZooKeeper, configured via `--cluster-store` / `--cluster-advertise` on the daemon. This path is
  deprecated but it is why overlay networking is sometimes described as needing a KV store.

Proof that the dependency is real — this is the exact error before Swarm was initialised:

```bash
docker info --format 'Swarm: {{.Swarm.LocalNodeState}}'
docker network create -d overlay hw07-overlay-fail
```

Output:

```text
Swarm: inactive

Error response from daemon: This node is not a swarm manager. Use "docker swarm init" or "docker swarm join" to connect this node to swarm and try again.
```

The overlay driver refuses to create anything without a control plane.

### Initialising Swarm

```bash
docker swarm init
docker info --format 'Swarm: {{.Swarm.LocalNodeState}} | Managers: {{.Swarm.Managers}} | Nodes: {{.Swarm.Nodes}}'
docker node ls
```

Output:

```text
Swarm initialized: current node (9l8yhj1qkoe2uq3sm4vdrvqa9) is now a manager.

To add a worker to this swarm, run the following command:

    docker swarm join --token SWMTKN-1-<redacted> 192.168.65.3:2377

To add a manager to this swarm, run 'docker swarm join-token manager' and follow the instructions.

Swarm: active | Managers: 1 | Nodes: 1

ID                            HOSTNAME         STATUS    AVAILABILITY   MANAGER STATUS   ENGINE VERSION
9l8yhj1qkoe2uq3sm4vdrvqa9 *   docker-desktop   Ready     Active         Leader           29.4.1
```

The worker join token is a cluster credential, so it is redacted here as `SWMTKN-1-<redacted>`; the
real command prints the full value. The `join` command with its `SWMTKN-…` token is how a second host
would enter the cluster. `2377` is
the cluster-management port; the advertise address `192.168.65.3` is the Docker Desktop VM's address.
The node is `Leader` because it is the only manager.

Swarm init also creates two networks by itself:

```bash
docker network ls --filter driver=overlay
docker network ls --filter name=docker_gwbridge
```

Output:

```text
NETWORK ID     NAME      DRIVER    SCOPE
2hvy9nn06vy4   ingress   overlay   swarm

NETWORK ID     NAME              DRIVER    SCOPE
4e3cbbb8f5aa   docker_gwbridge   bridge    local
```

- **`ingress`** — the special overlay that implements the routing mesh (explained below).
- **`docker_gwbridge`** — a plain *local* bridge that gives every overlay-attached container its
  route **out** to the internet. An overlay carries only east-west container-to-container traffic;
  north-south egress goes through this gateway bridge instead.

### Creating overlay networks, plain and encrypted

```bash
docker network create -d overlay --attachable hw07-overlay
docker network create -d overlay --attachable --opt encrypted hw07-overlay-enc
docker network ls --filter name=hw07-overlay
```

Output:

```text
rn232pk9uohh0ak74m2uvl8m4
1z79483oodtc23yq6n7wfvtz4

NETWORK ID     NAME               DRIVER    SCOPE
rn232pk9uohh   hw07-overlay       overlay   swarm
1z79483oodtc   hw07-overlay-enc   overlay   swarm
```

`SCOPE` is **`swarm`**, not `local` — the defining difference from Task 1. The IDs are Swarm object
IDs, not the 64-hex local network IDs.

`--attachable` is worth knowing: by default an overlay accepts only **Swarm services**, and a plain
`docker run --network hw07-overlay` is rejected. `--attachable` also allows standalone containers,
which is what makes the DNS demo below possible.

```bash
docker network inspect hw07-overlay-enc
```

Output (trimmed to the interesting fields):

```text
{
    "Name": "hw07-overlay-enc",
    "Scope": "swarm",
    "Driver": "overlay",
    "IPAM": {
        "Driver": "default",
        "Options": null,
        "Config": [
            {
                "Subnet": "10.0.2.0/24",
                "Gateway": "10.0.2.1"
            }
        ]
    },
    "Attachable": true,
    "Ingress": false,
    "Options": {
        "com.docker.network.driver.overlay.vxlanid_list": "4098",
        "encrypted": ""
    },
    "Labels": null
}
```

Two things to notice. The subnet comes from Swarm's default `10.0.0.0/8` pool, not the `172.x` range
bridges use. And `com.docker.network.driver.overlay.vxlanid_list: "4098"` is the **VXLAN Network
Identifier (VNI)** assigned to this network — the tag that keeps its traffic separate from every
other overlay's traffic on the wire.

```bash
for n in ingress hw07-overlay hw07-overlay-enc; do
  printf '%-18s VNI=%-5s encrypted=%s\n' "$n" \
    "$(docker network inspect $n --format '{{index .Options "com.docker.network.driver.overlay.vxlanid_list"}}')" \
    "$(docker network inspect $n --format '{{range $k,$v := .Options}}{{if eq $k "encrypted"}}yes{{end}}{{end}}' | grep -q yes && echo yes || echo no)"
done
```

Output:

```text
ingress            VNI=4096  encrypted=no
hw07-overlay       VNI=4097  encrypted=no
hw07-overlay-enc   VNI=4098  encrypted=yes
```

VNIs are handed out sequentially from 4096. Each overlay gets its own, and only the network created
with `--opt encrypted` carries the `encrypted` option.

### How the VXLAN tunnel actually carries the traffic

Look inside the Docker Desktop VM at the interface the overlay driver built:

```bash
docker run --rm --privileged --pid=host --net=host alpine:3.20 sh -c '
apk add --no-cache iproute2 util-linux >/dev/null 2>&1
nsenter -t 1 -m -n ls -1 /run/docker/netns
for ns in $(nsenter -t 1 -m -n ls -1 /run/docker/netns); do
  nsenter -t 1 -m -- nsenter --net=/run/docker/netns/$ns ip -d link show | grep -A2 vxlan
done'
```

Output (trimmed):

```text
1-2hvy9nn06v
1-rn232pk9uo
...

netns 1-2hvy9nn06v:
190: vxlan0@if190: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1450 qdisc noqueue master br0 state UNKNOWN mode DEFAULT
    link/ether 02:0a:cb:5d:18:7e brd ff:ff:ff:ff:ff:ff link-netnsid 0 promiscuity 1  allmulti 1 minmtu 68 maxmtu 65535
    vxlan id 4096 srcport 0 0 dstport 4789 proxy l2miss l3miss ttl auto ageing 300 udpcsum noudp6zerocsumtx noudp6zerocsumrx

netns 1-rn232pk9uo:
230: vxlan0@if230: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1450 qdisc noqueue master br0 state UNKNOWN mode DEFAULT
    link/ether 86:05:bf:a3:93:33 brd ff:ff:ff:ff:ff:ff link-netnsid 0 promiscuity 1  allmulti 1 minmtu 68 maxmtu 65535
    vxlan id 4097 srcport 0 0 dstport 4789 proxy l2miss l3miss ttl auto ageing 300 udpcsum noudp6zerocsumtx noudp6zerocsumrx
```

This is the mechanism, in the kernel's own words. Note the namespace names: `1-2hvy9nn06v` and
`1-rn232pk9uo` contain the network IDs of `ingress` and `hw07-overlay` — Docker creates a dedicated
**sandbox network namespace per overlay network**, holding a bridge `br0` and a `vxlan0` device
enslaved to it. And on the `vxlan0` line:

- `vxlan id 4096` / `vxlan id 4097` — the VNI, matching the `vxlanid_list` option exactly.
- `dstport 4789` — the IANA VXLAN port. **UDP 4789 must be open between hosts**, together with
  TCP/UDP 7946 for gossip and TCP 2377 for cluster management. Forgetting 4789 in a security group is
  the single most common cause of "my overlay containers cannot reach each other".
- `mtu 1450` — 1500 minus the 50-byte VXLAN header. Relevant when the underlay itself is a tunnel:
  if the physical path has a smaller MTU you get mysterious hangs on large payloads.
- `proxy l2miss l3miss` — the kernel asks userspace (Docker) to resolve unknown MAC/IP addresses
  instead of flooding the network. Docker answers from the Swarm control plane, so there is no
  broadcast storm and no multicast requirement.

Putting it together, an overlay packet from container A on host 1 to container B on host 2:

```text
  Host 1  (real IP 10.1.0.11)                    Host 2  (real IP 10.1.0.12)
  +----------------------------------+           +----------------------------------+
  | container A   10.0.1.7           |           | container B   10.0.1.8           |
  |     | veth                       |           |     ^ veth                       |
  |     v                            |           |     |                            |
  |  br0  (overlay sandbox netns)    |           |  br0  (overlay sandbox netns)    |
  |     |                            |           |     ^                            |
  |     v                            |           |     |                            |
  |  vxlan0  VNI 4097                |           |  vxlan0  VNI 4097                |
  |     |  encapsulate               |           |     |  decapsulate               |
  |     v                            |           |     |                            |
  |  eth0 10.1.0.11                  |           |  eth0 10.1.0.12                  |
  +-----|----------------------------+           +-----^----------------------------+
        |                                              |
        +======= UDP dst port 4789, over the ==========+
                 ordinary physical network
                 (the "underlay")

  What is on the wire:

  +----------------+------------+-------------+------------------------------------+
  | Outer Ethernet | Outer IP   | Outer UDP   | VXLAN hdr | INNER Ethernet + IP +   |
  | host1 -> host2 | 10.1.0.11  | dport 4789  | VNI=4097  | payload: 10.0.1.7 ->    |
  |                | -> .0.12   |             |           |          10.0.1.8       |
  +----------------+------------+-------------+-----------+-------------------------+
                                                           \__ the original frame,
                                                               untouched
```

The whole original layer-2 frame is wrapped in UDP. Routers in between only see host-to-host UDP and
route it normally; they never learn that `10.0.1.x` exists. The VNI lets one pair of hosts carry many
independent overlays over the same UDP port without them mixing.

### The ingress network and the routing mesh

`ingress` is a pre-created overlay with `"Ingress": true`:

```bash
docker network inspect ingress
```

Output (trimmed):

```text
{
    "Name": "ingress",
    "Scope": "swarm",
    "Driver": "overlay",
    "IPAM": {
        "Driver": "default",
        "Options": null,
        "Config": [
            {
                "Subnet": "10.0.0.0/24",
                "Gateway": "10.0.0.1"
            }
        ]
    },
    "Attachable": false,
    "Ingress": true
}
```

It exists to implement the **routing mesh**. When a service publishes a port, *every* node in the
Swarm starts listening on that port, whether or not it runs a task of that service. A request landing
on a node with no local task is forwarded over the `ingress` overlay to a node that has one. That is
why you can point a cloud load balancer at all your nodes without tracking which one holds which
replica.

```text
                 client / external load balancer
                     |          |          |
                  :8095      :8095      :8095
                     v          v          v
               +---------+ +---------+ +---------+
               | node 1  | | node 2  | | node 3  |
               | task A  | | no task | | task B  |
               +----|----+ +----|----+ +----|----+
                    |           |           |
                    |      forwarded over the ingress
                    |      overlay to a node that has one
                    +-----------+-----------+
                                |
                        IPVS picks a task
```

`"Attachable": false` — you cannot join `ingress` by hand; it is Swarm's own plumbing. Note also that
`ingress` handles the published-port path only. Service-to-service traffic inside the cluster uses
your own overlay networks and never touches it.

### A real service on the overlay

```bash
docker service create --name hw07-web --network hw07-overlay --replicas 2 -p 8095:80 nginx:alpine
docker service ls
docker service ps hw07-web --format 'table {{.Name}}\t{{.Node}}\t{{.DesiredState}}\t{{.CurrentState}}'
curl -sS -m 8 -o /dev/null -w 'HTTP %{http_code} from http://localhost:8095/\n' http://localhost:8095/
docker network inspect hw07-overlay --format '{{range .Containers}}{{.Name}} {{.IPv4Address}}
{{end}}'
```

Output:

```text
verify: Service na1rekmsjq2ttlo8icntpeiuu converged

ID             NAME       MODE         REPLICAS   IMAGE          PORTS
na1rekmsjq2t   hw07-web   replicated   2/2        nginx:alpine   *:8095->80/tcp

NAME         NODE             DESIRED STATE   CURRENT STATE
hw07-web.1   docker-desktop   Running         Running 5 seconds ago
hw07-web.2   docker-desktop   Running         Running 5 seconds ago

HTTP 200 from http://localhost:8095/

hw07-web.1.wuny1bcciel6m6si6pdxhf005 10.0.1.7/24
hw07-web.2.yj4l1p6d2ieafi90sa0n2jzms 10.0.1.8/24
hw07-overlay-endpoint 10.0.1.9/24
```

Both replicas are `Running` with real overlay addresses `10.0.1.7` and `10.0.1.8`, and `HTTP 200`
confirms the routing mesh is serving. The published port shows as `*:8095->80/tcp` — the `*` means
*every node*, which is the routing mesh notation, not the `0.0.0.0:8095->80/tcp` a plain container
shows.

`hw07-overlay-endpoint` is the network's own sandbox endpoint, the plumbing that terminates the
tunnel on this node.

### Service discovery and the virtual IP

```bash
docker run --rm --name hw07-probe --network hw07-overlay alpine:3.20 sh -c '
  apk add --no-cache bind-tools >/dev/null 2>&1
  nslookup hw07-web
  nslookup tasks.hw07-web
  wget -qS -O /dev/null http://hw07-web/'
```

Output:

```text
--- VIP for service name hw07-web ---
Non-authoritative answer:
Name:	hw07-web
Address: 10.0.1.6

--- individual task IPs (tasks.<service>) ---
Non-authoritative answer:
Name:	tasks.hw07-web
Address: 10.0.1.7
Name:	tasks.hw07-web
Address: 10.0.1.8

--- HTTP through the service VIP ---
  HTTP/1.1 200 OK
  Server: nginx/1.31.6
  Date: Thu, 17 Sep 2026 16:19:07 GMT
```

This is Swarm's service discovery, working end to end:

- `hw07-web` resolves to **one** address, `10.0.1.6`, which is neither replica. That is the service's
  **virtual IP (VIP)**. Connections to it are load-balanced across the healthy tasks by IPVS in the
  kernel — so clients never cache a task IP and never need to be told when a task is rescheduled onto
  a different host.
- `tasks.hw07-web` resolves to **all** task IPs (`10.0.1.7` and `10.0.1.8`) — DNS round-robin mode,
  which you ask for with `--endpoint-mode dnsrr` when a client wants to do its own balancing or needs
  stable per-replica addresses (Cassandra, Elasticsearch, and similar).
- The `HTTP/1.1 200 OK` from `nginx/1.31.6` proves traffic really flows through the VIP.

And this all worked from a plain `docker run` container, which is what `--attachable` bought.

### Encryption with `--opt encrypted`

By default overlay traffic is **not** encrypted — the VXLAN payload travels the underlay in
cleartext. The control plane (the gossip and Raft traffic between nodes) is always encrypted with
mutual TLS, but your application's data is not.

`--opt encrypted` turns on **IPsec ESP** between every pair of nodes, with AES-GCM and keys that
Swarm rotates roughly every twelve hours. The option showed up in the inspect output above as
`"encrypted": ""`.

Things to know before switching it on:

- It is a **create-time** option. You cannot encrypt an existing overlay; you recreate it.
- Cost is roughly a 10–20% throughput hit, less on CPUs with AES-NI or ARM crypto extensions.
- It is **not supported on Windows nodes**, so a mixed cluster cannot use it.
- The `ingress` network cannot be encrypted this way. To encrypt ingress traffic you have to remove
  and recreate the ingress network, and in practice you terminate TLS at the edge instead.
- It protects host-to-host traffic on the wire. It does **not** authenticate containers to each
  other — any container on the network can still talk to any other. Use it when the underlay is
  untrusted (cross-AZ, cross-datacentre, a provider network you do not control), and use mTLS at the
  application layer when you need real service identity.

### Comparison: bridge vs overlay vs macvlan vs host vs none

| | `bridge` | `overlay` | `macvlan` | `host` | `none` |
|---|---|---|---|---|---|
| Scope | Single host | **Multiple hosts** | Single host | Single host | Single host |
| Needs Swarm / KV store | No | **Yes** | No | No | No |
| Container-name DNS | Yes (user-defined only) | Yes, plus service VIPs | No | No | No |
| Encapsulation | None — Linux bridge | **VXLAN, UDP 4789** | None — real L2 frames | None | N/A |
| Container IP | Private `172.x` | Swarm pool `10.x` | An address on your **physical LAN** | The host's IP | None |
| Visible on the physical LAN | No, NAT'd | No, tunnelled | **Yes, directly** | Yes (is the host) | No |
| MTU | 1500 | 1450 (50-byte header) | 1500 | 1500 | N/A |
| Built-in encryption | No | **Yes, `--opt encrypted`** | No | No | N/A |
| Load balancing | No | **Yes — VIP + IPVS + routing mesh** | No | No | No |
| Typical use | Local multi-container apps | Multi-host clusters, Swarm services | Appliances needing a LAN IP | Max performance, node agents | Fully offline jobs |

### Concrete use cases for overlay networks

- **Multi-host Swarm applications.** The obvious one: an `api` service on three nodes talking to a
  `db` service on two others, all by name, with no host IPs anywhere in the config.
- **Rolling updates without reconfiguration.** `docker service update --image api:v2` reschedules
  tasks onto whatever nodes have room. Their IPs change; the service name and VIP do not, so callers
  never notice.
- **Tenant and tier isolation across a cluster.** Put `frontend` + `api` on one overlay and `api` +
  `db` on another, exactly like Task 1 but spanning many machines. The frontend physically cannot
  route to the database even if the two land on the same node.
- **Crossing an untrusted underlay.** Hosts in different availability zones, different cloud
  providers, or an on-prem-to-cloud hybrid. Add `--opt encrypted` and the traffic is protected without
  touching the application.
- **Keeping addressing stable across heterogeneous networks.** Each cloud has its own VPC CIDRs; the
  overlay gives containers one consistent subnet regardless of where they run.
- **Publishing without a service registry.** The ingress routing mesh means an external load balancer
  can target every node uniformly, with no health-check logic tracking which node holds which replica.
- **Scaling stateful sets with stable identities.** `tasks.<service>` DNS round-robin gives each
  replica a discoverable address, which is what clustered databases and search engines need.

### A note on Kubernetes

Docker overlay networking is Swarm's answer to the same problem Kubernetes solves with a CNI plugin.
The concepts map closely: Flannel's VXLAN backend and Calico's IPIP/VXLAN modes use the same
encapsulation on the same UDP port, Cilium can do it with eBPF or switch to native routing, and
Kubernetes `Service` ClusterIPs play the role of Swarm's VIPs — kube-proxy in IPVS mode even uses the
same kernel load balancer. Understanding overlay here transfers directly to reasoning about pod
networking there.

---

## Cleanup

Swarm was torn down first, then every `hw07-` resource.

```bash
docker service rm hw07-web
docker network rm hw07-overlay hw07-overlay-enc
docker swarm leave --force
docker info --format 'Swarm: {{.Swarm.LocalNodeState}}'
docker network ls --filter driver=overlay
docker network rm docker_gwbridge
```

Output:

```text
hw07-web
hw07-overlay
hw07-overlay-enc

Node left the swarm.

Swarm: inactive

NETWORK ID   NAME      DRIVER    SCOPE

docker_gwbridge
```

Swarm is `inactive` again and no overlay networks remain. `docker_gwbridge` was created by
`docker swarm init` and did not exist beforehand, so it was removed too, leaving the host exactly as
it was found.

```bash
docker compose down

docker rm -f hw07-nginx-bind hw07-apache-p80 hw07-apache-published \
             hw07-apache-host hw07-tmpfs hw07-nginx-vol

docker network rm hw07-frontend-net hw07-backend-net hw07-db-net
docker volume rm hw07-data
```

Output:

```text
 Container hw07-database Stopping 
 Container hw07-database Stopped 
 Container hw07-database Removing 
 Container hw07-database Removed 
 Network hw07-backend-net Removing 
 Network hw07-frontend-net Removing 
 Network hw07-db-net Removing 
 Network hw07-db-net Removed 
 Network hw07-backend-net Removed 
 Network hw07-frontend-net Removed 

hw07-nginx-bind
hw07-apache-p80
Error response from daemon: No such container: hw07-apache-published
Error response from daemon: No such container: hw07-apache-host
Error response from daemon: No such container: hw07-tmpfs
Error response from daemon: No such container: hw07-nginx-vol

Error response from daemon: network hw07-frontend-net not found
Error response from daemon: network hw07-backend-net not found
Error response from daemon: network hw07-db-net not found

hw07-data
```

`docker compose down` already removed the three containers and the three networks it owned, so the
follow-up commands report "No such container" and "network not found" for those — that is the
expected, idempotent outcome and not an error to fix. The containers created outside Compose
(`hw07-nginx-bind`, `hw07-apache-p80`) and the named volume were removed by name.

### Final verification

```bash
docker ps -a       | grep hw07 || echo "(none)"
docker network ls  | grep hw07 || echo "(none)"
docker volume ls   | grep hw07 || echo "(none)"
docker info --format 'Swarm: {{.Swarm.LocalNodeState}}'
docker network ls --format '{{.Name}}'
```

Output:

```text
=== VERIFY: containers ===
(none)
=== VERIFY: networks ===
(none)
=== VERIFY: volumes ===
(none)
=== VERIFY: swarm ===
Swarm: inactive
=== VERIFY: full network list ===
bridge
host
mirror-control_default
mirror-test-site_default
none
```

No `hw07-` container, network or volume remains, Swarm is off, and the only networks left are the
Docker built-ins plus unrelated projects that were already on the machine. Nothing was pruned
globally — every resource was removed by name.

To rebuild the whole Task 1 topology in one command at any time:

```bash
cd homework/07-docker-network-volume
docker compose up -d
```

---

## Command reference

| Command | What it does |
|---|---|
| `docker network create --driver bridge NAME` | Create a user-defined bridge with container-name DNS |
| `docker network connect NET CONTAINER` | Hot-plug a second NIC into a running container |
| `docker network disconnect NET CONTAINER` | Detach a container from a network |
| `docker network inspect NET` | Subnet, gateway, and every attached container with its IP |
| `docker network inspect NET --format '{{range .Containers}}{{.Name}}{{end}}'` | Just the membership list |
| `docker run --network host` | Share the host's network namespace (Linux; VM-only on Desktop) |
| `docker run -p HOST:CONTAINER` | Publish a port through NAT — the portable option |
| `docker run -v /abs/host/path:/in/container:ro` | Bind mount, read-only |
| `docker volume create NAME` / `ls` / `inspect` / `rm` | Manage named volumes |
| `docker run -v NAME:/in/container` | Mount a named volume |
| `docker run --tmpfs /path:rw,size=32m` | RAM-backed scratch space |
| `docker inspect C --format '{{json .Mounts}}'` | Show what is mounted where, and `ro`/`rw` |
| `docker swarm init` / `docker swarm leave --force` | Start / stop Swarm mode |
| `docker network create -d overlay --attachable NAME` | Multi-host overlay that plain containers may join |
| `docker network create -d overlay --opt encrypted NAME` | Overlay with IPsec between nodes |
| `docker service create --network NET -p P:C IMAGE` | Run a replicated service on an overlay |
| `docker service ps NAME` | Which node each task is running on |
