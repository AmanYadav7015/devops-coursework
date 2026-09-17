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
