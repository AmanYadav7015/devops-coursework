# Docker Networking & Volumes

Answers to **`DevOps Homework.docx`** — four Docker networking/storage tasks, each in its own
folder.

**Completed:** 02 September 2026

| Task | Containers | Networks |
|---|---|---|
| [Task 1 — Container Networking](01-container-networking/README.md) | `dn-frontend`, `dn-backend`, `dn-database` | `dn-net-frontend`, `dn-net-backend`, `dn-net-database` |
| [Task 2 — Host Network](02-host-network/README.md) | `dn-apache` | `host`, then `bridge` |
| [Task 3 — Bind Mount](03-bind-mount/README.md) | `dn-nginx-bind` | — |
| [Task 4 — Overlay Network](04-overlay-network/README.md) | `dn-overlay-a`, `dn-overlay-b` (demo only) | `dn-net-overlay-demo` |

## Assignment (verbatim)

> ## Task 1: Docker Container Networking
> - Create 3 containers: Frontend, Backend, Database
> - Use Nginx or Alpine images for the frontend and backend.
> - Use the MySQL image for the database.
> - Create 3 different Docker networks.
> - Add the backend container to 2 networks.
> - Check connectivity between the containers.
>
> ## Task 2: Host Network
> - Pull the Apache2 image from Docker Hub.
> - Create an Apache2 container using the host network.
> - Access the Apache website directly on port 80.
>
> ## Task 3: Bind Mount
> - Create a folder on your local machine.
> - Create an index.html file with `Hello students` as the content.
> - Bind mount the folder to an Nginx container.
> - Access the Nginx website and verify the content.
> - Modify the index.html file.
> - Verify that the changes are reflected without restarting the container.
>
> ## Task 4: Overlay Network
> - Research Docker overlay networks.
> - Understand their use cases.
> - Understand how overlay networks work across multiple Docker hosts.

## How this was done

Every command in these answers was **actually executed** on macOS with Docker Desktop
(Docker Engine 29.5.2, client `darwin/arm64`, server `linux/arm64`) — nothing here is invented
or copied out of documentation. Where the environment (macOS + Docker Desktop's hidden Linux
VM) genuinely behaves differently from a plain Linux Docker host — most notably Task 2 — the
write-up says so explicitly and shows the real failure alongside the real fix, rather than
reporting the textbook Linux answer as if it had been observed here.

## The macOS host-networking finding (Task 2, most important result)

**`docker run --network host` did not expose anything on macOS.** `curl http://localhost:80`
from the Mac got a genuine `Connection refused`. This is not a bug or a mistake in the demo —
it's correct, expected behaviour for Docker Desktop:

- Docker Desktop on macOS runs every container inside a hidden **Linux virtual machine**
  (confirmed directly: `docker version` shows `Client: darwin/arm64` but `Server: linux/arm64`).
- `--network host` joins the container to the **engine's own host** network namespace — and
  the engine's host is that Linux VM, not macOS. The container really did bind port 80, just
  on the VM's loopback, which macOS cannot reach.
- Proven from the inside too: `docker exec`-ing into the container and hand-rolling a raw TCP
  request with bash's `/dev/tcp` got a perfectly healthy `HTTP/1.1 200 OK` / "It works!" —
  Apache itself was never broken, only unreachable from outside the VM.
- The working fix, demonstrated immediately after: `docker run -p 80:80 ...` (explicit
  published-port mapping) worked from macOS on the first try, because `-p` explicitly asks
  Docker Desktop's own port-forwarder to bridge the VM boundary — the thing `--network host`
  skips.
- This install's Docker Desktop settings were checked directly for the newer opt-in "host
  networking" beta feature; it is not enabled here, consistent with what was observed. On a
  plain Linux Docker host (no VM in the picture) `--network host` would have worked immediately
  with no extra step.

## Network driver comparison

| Driver | Scope | Typical use | Notes |
|---|---|---|---|
| `bridge` (default, unnamed) | Single host | Legacy/default networking; quick one-off containers | **No DNS-by-name** between containers — only the host's external resolver is configured. Containers only reach each other by IP, or via legacy `--link` (deprecated). |
| `bridge` (user-defined, `docker network create`) | Single host | The normal choice for most single-host multi-container setups (this homework's Task 1) | Gets Docker's embedded DNS (`127.0.0.11`) — containers resolve each other **by container name**, confirmed directly in Task 1. Isolated from other bridge networks by default. |
| `host` | Single host | Maximum network performance, no NAT overhead, when you don't need port isolation | Container shares the host's (engine's) network namespace directly — no port mapping table at all. **On Docker Desktop for macOS this is the VM's namespace, not the Mac's** — see the finding above. Works as expected on native Linux hosts. |
| `none` | N/A | Fully isolated container with no networking at all (only `lo`) | Used for batch jobs, security-sensitive tasks, or when you'll wire up custom networking yourself. |
| `overlay` | **Multiple hosts** (Swarm cluster) | Multi-host clusters, cross-node service discovery, rolling deployments across nodes (Task 4) | Requires Swarm mode. Uses VXLAN to tunnel container traffic between hosts' real IPs. `docker network inspect` reports `Scope: swarm` (vs `local` for bridge). |
| `macvlan` | Single host (physical LAN) | Giving a container its own MAC/IP directly on the physical LAN, as if it were a separate physical machine — legacy apps/appliances that expect that | Not used in this homework. Bypasses the host's network stack entirely (container gets a real LAN-routable IP); the host itself typically can't talk to a macvlan container without extra config. Not supported at all on Docker Desktop for macOS (needs direct L2 access to a physical interface, which the VM doesn't expose the same way). |

## Real subnets/IPs observed (Task 1)

| Network | Subnet | Gateway |
|---|---|---|
| `dn-net-frontend` | `172.19.0.0/16` | `172.19.0.1` |
| `dn-net-backend` | `172.20.0.0/16` | `172.20.0.1` |
| `dn-net-database` | `172.21.0.0/16` | `172.21.0.1` |

Container IPs: `dn-frontend` → `172.19.0.2`; `dn-backend` → `172.19.0.3` (on
`dn-net-frontend`, `eth0`) **and** `172.21.0.3` (on `dn-net-database`, `eth1`); `dn-database` →
`172.21.0.2`. Confirmed two real interfaces (`eth0`, `eth1`) inside `dn-backend` via `ip -br a`.

DNS-by-name connectivity, confirmed directly:

```
dn-backend  -> ping dn-frontend  : SUCCESS
dn-backend  -> ping dn-database  : SUCCESS
dn-frontend -> ping dn-database  : FAILED  ("ping: bad address 'dn-database'")
```

Backend reaches both other containers by name because it shares a network with each of them
individually; frontend and database share no network with each other at all, so frontend's
embedded DNS resolver has simply never heard of `dn-database`.

## Bind mount vs named volume vs tmpfs

| | Bind mount | Named volume | tmpfs |
|---|---|---|---|
| Backed by | An existing host path **you** choose | Storage Docker manages internally | RAM only |
| Host-editable directly? | Yes — an ordinary folder | No — only through a container | No — never touches disk |
| Survives container removal? | Yes | Yes | No |
| Survives host reboot? | Yes | Yes | No |
| Typical use | Live-editing source/config from the host (Task 3) | Docker-managed persistent app data (databases, uploads) | Secrets/scratch data that must never hit disk |

Verified directly in Task 3: modifying `03-bind-mount/site/index.html` from macOS was reflected
by `curl` **immediately, with zero container restart** — because a bind mount is the same
underlying file, not a copy. `docker inspect --format '{{json .Mounts}}'` showed `Type: bind`
with `Source` pointing at the real macOS path, versus `Type: volume` with `Source` pointing at
a path *inside the Docker Desktop Linux VM* (`/var/lib/docker/volumes/.../_data`) for the named
volume created for comparison.

## Cleanup

Every container, network, and volume created for this topic was removed at the end of its
task's transcript (`docker rm -f`, `docker network rm`, `docker volume rm`). Task 4's optional
Swarm demo was fully reversed too: `docker swarm leave --force`, confirmed by
`docker info --format '{{.Swarm.LocalNodeState}}'` returning to `inactive`, plus manual removal
of the auto-created `docker_gwbridge` network that `swarm leave` left behind. The only
deliverable intentionally left behind is `03-bind-mount/site/index.html`, per the assignment.

<!-- AUTO-ATTACHED: screenshots & transcripts -->

## Tasks in this topic

- [`01-container-networking`](01-container-networking/README.md)
- [`02-host-network`](02-host-network/README.md)
- [`03-bind-mount`](03-bind-mount/README.md)
- [`04-overlay-network`](04-overlay-network/README.md)
