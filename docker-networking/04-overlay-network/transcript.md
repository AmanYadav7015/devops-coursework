# Docker networking — overlay network

> Real session — every command was executed and the output is verbatim.

[← Back](README.md)

---

```console
# Overlay networks require Swarm mode. This is a single Docker Desktop node,
# so this demo shows the mechanics (creation, driver, scope) but NOT real
# multi-host traffic — that would need a second engine.

# --- confirm swarm is inactive before we start (so we know our own baseline) ---
[aman@macos ~]$ docker info --format '{{.Swarm.LocalNodeState}}'
inactive


# --- initialise a single-node swarm (required before overlay networks can be created) ---
[aman@macos ~]$ docker swarm init
Swarm initialized: current node (7f73fk5jfqdgpybzzbr8frcbx) is now a manager.

To add a worker to this swarm, run the following command:

    docker swarm join --token SWMTKN-1-<redacted-join-token> 192.168.65.3:2377

To add a manager to this swarm, run 'docker swarm join-token manager' and follow the instructions.

[aman@macos ~]$ docker info --format '{{.Swarm.LocalNodeState}}'
active
```

### Create the overlay network and inspect it

```console
[aman@macos ~]$ docker network create --driver overlay --attachable dn-net-overlay-demo
kxd3zcj0ahq0rh8qau0zdl151

[aman@macos ~]$ docker network ls
NETWORK ID     NAME                     DRIVER    SCOPE
871ee7c20374   bridge                   bridge    local
kxd3zcj0ahq0   dn-net-overlay-demo      overlay   swarm
faa8a7263ad3   docker_gwbridge          bridge    local
d74a51eb7ed1   host                     host      local
dwxp0iexdq73   ingress                  overlay   swarm
6e9b53a4668b   mirror-control_default   bridge    local
3e9a572dd575   none                     null      local

[aman@macos ~]$ docker network inspect dn-net-overlay-demo --format 'Driver={{.Driver}} Scope={{.Scope}} Subnet={{range .IPAM.Config}}{{.Subnet}}{{end}}'
Driver=overlay Scope=swarm Subnet=10.0.1.0/24


# --- compare to a normal user-defined bridge network's scope ---
[aman@macos ~]$ docker network create dn-net-bridge-compare
4cef79879f7e9f92c06090ceb548a695f9fc0218d662fcfff7a18ab7022af2af

[aman@macos ~]$ docker network inspect dn-net-bridge-compare --format 'Driver={{.Driver}} Scope={{.Scope}}'
Driver=bridge Scope=local

[aman@macos ~]$ docker network inspect dn-net-overlay-demo --format 'Driver={{.Driver}} Scope={{.Scope}}'
Driver=overlay Scope=swarm
```

### Attach two containers to the overlay network on this single node (mechanics only -- both replicas happen to land on the same engine here, so this does NOT exercise real cross-host VXLAN traffic)

```console
[aman@macos ~]$ docker run -d --name dn-overlay-a --network dn-net-overlay-demo alpine:latest sleep infinity
f57425a1a548096d12f614d2137f858241a3d3cb72286c5fdca8050d23e200f2

[aman@macos ~]$ docker run -d --name dn-overlay-b --network dn-net-overlay-demo alpine:latest sleep infinity
bdf2a62d973c0824b7af5d7e633677fb6ae4391abca4954b007ad311ab7d5b14

[aman@macos ~]$ docker exec dn-overlay-a ping -c 2 dn-overlay-b
PING dn-overlay-b (10.0.1.4): 56 data bytes
64 bytes from 10.0.1.4: seq=0 ttl=64 time=0.106 ms
64 bytes from 10.0.1.4: seq=1 ttl=64 time=0.126 ms

--- dn-overlay-b ping statistics ---
2 packets transmitted, 2 packets received, 0% packet loss
round-trip min/avg/max = 0.106/0.116/0.126 ms
```

### Cleanup (Task 4) — remove containers/networks, then LEAVE THE SWARM so the host is restored exactly to its pre-demo state.

```console
[aman@macos ~]$ docker rm -f dn-overlay-a dn-overlay-b
dn-overlay-a
dn-overlay-b

[aman@macos ~]$ docker network rm dn-net-overlay-demo dn-net-bridge-compare
dn-net-overlay-demo
dn-net-bridge-compare

[aman@macos ~]$ docker swarm leave --force
Node left the swarm.

[aman@macos ~]$ docker info --format '{{.Swarm.LocalNodeState}}'
inactive

[aman@macos ~]$ docker network ls
NETWORK ID     NAME                     DRIVER    SCOPE
871ee7c20374   bridge                   bridge    local
faa8a7263ad3   docker_gwbridge          bridge    local
d74a51eb7ed1   host                     host      local
6e9b53a4668b   mirror-control_default   bridge    local
3e9a572dd575   none                     null      local

# --- docker_gwbridge is auto-created by 'swarm init' and is NOT auto-removed by ---
# --- 'swarm leave --force' on this install; remove it explicitly for full cleanup ---
[aman@macos ~]$ docker network rm docker_gwbridge
docker_gwbridge

[aman@macos ~]$ docker network ls
NETWORK ID     NAME                     DRIVER    SCOPE
871ee7c20374   bridge                   bridge    local
d74a51eb7ed1   host                     host      local
6e9b53a4668b   mirror-control_default   bridge    local
3e9a572dd575   none                     null      local

# --- back to the exact baseline network list from before this demo started. ---
```
