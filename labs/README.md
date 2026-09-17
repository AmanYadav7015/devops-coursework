# DevOps Homework — Command-Verified Lab Run

**Name:** Aman Yadav
**Roll Number:** 24bcs10183
**Year:** 2nd Year
**Batch:** A
**Run date:** 17 September 2026
**Host:** macOS (Darwin 25.5.0, arm64), Docker Engine 29.x

All seven homework sections, re-run end to end with every command actually executed on this machine.
Output blocks are verbatim terminal capture, not documentation examples.

---

## Sections

| # | Section | Write-up | What it proves |
|---|---|---|---|
| 01 | [Linux Fundamentals](01-linux/README.md) | 2,185 lines | Hard vs soft links down to inode numbers, `adduser` vs `useradd` on real Ubuntu, and genuine `journalctl` output from a booted systemd container |
| 02 | [Shell Scripting](02-shell-scripting/README.md) | 623 lines | A system-information script exercising variables, `read -p`, `mkdir`, `touch` and `>` redirection |
| 03 | [Networking Fundamentals](03-networking/README.md) | 1,369 lines | Interfaces, routing, DNS, sockets and HTTP — each command run and then interpreted |
| 04 | [Git / GitHub](04-git-github/README.md) | 978 lines | `commit -a -m` vs `commit -m`, and a cherry-pick exercise including a real merge conflict |
| 05 | [Docker Hello World](05-docker-hello-world/README.md) | 1,130 lines | Six containerised web apps — Node.js, Python, Java, Apache, React, Nginx — each built and curled |
| 06 | [Multi-Stage Builds](06-multi-stage-build/README.md) | 649 lines | Measured single-stage vs multi-stage image sizes across three languages ([submission](06-multi-stage-build/submission.md)) |
| 07 | [Docker Networking & Volumes](07-docker-network-volume/README.md) | 1,765 lines | Three-network topology with proven L3 isolation, host networking on macOS, bind mounts, and a live overlay network |

---

## Kubernetes — sessions 9 to 12

[`kubernetes/`](kubernetes/README.md) extends this run to the four Kubernetes sessions, against a live
minikube cluster (Kubernetes v1.37.0, containerd), run 17 September 2026.

| # | Session | Write-up | What it proves |
|---|---|---|---|
| 09 | [Architecture & First Cluster](kubernetes/09-architecture-first-cluster/README.md) | 1,393 lines | Control-plane anatomy, static pods proven three ways, `kubectl apply` traced with `-v=6` and etcd |
| 10 | [Core Objects, Lifecycle & Strategies](kubernetes/10-core-objects-lifecycle-strategies/README.md) | 2,016 lines | All six pod states reproduced; the four deployment strategies measured for real downtime |
| 11 | [Services, DNS & Endpoints](kubernetes/11-services-dns-endpoints/README.md) | 1,750 lines | All five service types; the `ndots:5` search-list cost captured in tcpdump |
| 12 | [Ingress, ConfigMaps & Secrets](kubernetes/12-ingress-configmaps-secrets/README.md) | 2,031 lines | Env-var vs volume update behaviour timed side by side; four distinct Ingress failures |

Note on provenance: the official homework document covers sessions 2-8 only, so these four sets were
derived from the material taught in each Kubernetes session rather than assigned. Each README says so.

The Kubernetes README also records two findings about the course material itself: the session-12 lab's
`curl http://$(minikube ip)/` step cannot work on macOS with the docker driver, and its `Ao=` test for
the base64 newline bug only holds for some passwords.

---

## How this run was done

The host is macOS, which has no `adduser`, `useradd`, `journalctl`, `ip` or `ss`. Rather than present
documentation output as if it were captured, every Linux-specific command was run inside a disposable
container and labelled as such:

- `ubuntu:24.04` for user management and the command cheat sheet
- a privileged, genuinely booted **systemd** container so `journalctl` returns real journal entries
- `nicolaka/netshoot` for `ip`, `ss` and container-side DNS

Where something could not be reproduced on this host, the write-up says so and explains why instead of
faking a result. The clearest example is Task 2 of section 07: `--network host` does not expose a port
to macOS, and the write-up proves *why* by showing the container joined the Docker Desktop VM's
namespace rather than the Mac's.

## Headline measurements

Multi-stage builds, measured rather than asserted (section 06):

| Application | Single-stage | Multi-stage | Saved |
|---|---|---|---|
| Node.js | 1.91 GB | 237 MB | 87.6% |
| Python | 1.62 GB | 223 MB | 86.2% |
| Java | 744 MB | 286 MB | 61.6% |

## Running the labs yourself

Each section's README is self-contained: it lists the exact commands in order, the output to expect,
and a cleanup block. Sections 05, 06 and 07 need a running Docker daemon. Container, network and
volume names are prefixed per section (`hw01-` … `hw07-`) so nothing collides if you run several at once.

## Redactions

Two items are masked rather than published: a Docker Swarm worker join token in section 07, and two
local process names in a `ps` listing in section 02. Both are noted inline where they appear. Everything
else is unmodified capture.
