# DevOps Coursework — Aman Yadav (24bcs10183)

Answers to all seven sections of **`DevOps Homework.docx`**.
Completed 02 September 2026.

| Topic | What it covers | Screenshots | Transcripts |
|---|---|---|---|
| [Linux Fundamentals](linux-fundamentals/README.md) | Soft/hard links, user creation, journald, and a practised command cheat sheet. | 35 | 7 |
| [Shell Scripting](shell-scripting/README.md) | A system-information Bash script exercising variables, `read -p`, redirection and more. | 5 | 2 |
| [Networking Fundamentals](networking-fundamentals/README.md) | Interfaces, routing, DNS, sockets and packet capture — each command run and explained. | 8 | 4 |
| [Git / GitHub](git-github/README.md) | `commit -a -m` vs `commit -m`, and a cherry-pick exercise including a real conflict. | 7 | 2 |
| [Docker Fundamentals](docker-fundamentals/README.md) | Six Hello World web apps — Node.js, Python, Java, Apache, React and Nginx — each containerised and verified. | 12 | 3 |
| [Dockerfiles & Images](dockerfiles-and-images/README.md) | A multi-stage build shrinking 468 MB to 7.3 MB, plus three deployed application types. | 10 | 3 |
| [Docker Networking & Volumes](docker-networking/README.md) | User-defined networks and DNS resolution, host networking on macOS, bind mounts, and overlay networks. | 13 | 4 |

## Second run — `labs/`

[`labs/`](labs/README.md) is an independent re-run of all seven sections, completed **17 September 2026**
on macOS with Docker Engine 29.x. It is additive: nothing in the topic folders above was changed.

The two runs differ in what they carry as evidence. The topic folders above are screenshot-backed. The
`labs/` run is markdown-only but ships the **runnable source** — Dockerfiles, application code, a shell
script and a compose file — so each lab can be rebuilt from scratch, and it records measurements the
first run did not, notably single-stage versus multi-stage image sizes across three languages.

| Section | First run (screenshots) | Second run (source + fresh capture) |
|---|---|---|
| Linux | [linux-fundamentals](linux-fundamentals/README.md) | [labs/01-linux](labs/01-linux/README.md) |
| Shell scripting | [shell-scripting](shell-scripting/README.md) | [labs/02-shell-scripting](labs/02-shell-scripting/README.md) |
| Networking | [networking-fundamentals](networking-fundamentals/README.md) | [labs/03-networking](labs/03-networking/README.md) |
| Git / GitHub | [git-github](git-github/README.md) | [labs/04-git-github](labs/04-git-github/README.md) |
| Docker fundamentals | [docker-fundamentals](docker-fundamentals/README.md) | [labs/05-docker-hello-world](labs/05-docker-hello-world/README.md) |
| Dockerfiles & images | [dockerfiles-and-images](dockerfiles-and-images/README.md) | [labs/06-multi-stage-build](labs/06-multi-stage-build/README.md) |
| Docker networking | [docker-networking](docker-networking/README.md) | [labs/07-docker-network-volume](labs/07-docker-network-volume/README.md) |

## How this work was done

Every command in every section was **actually executed** — nothing is invented or copied from
documentation. The host is macOS, so Linux work ran inside disposable Docker containers
(Ubuntu 24.04, plus a Rocky Linux 9 container for one cross-distro check, and a systemd-enabled
container so `journalctl` returns real journal entries). Docker sections used the host's Docker
daemon directly.

Each topic folder holds one folder per task:

```
<topic>/
└── <NN-task>/
    ├── README.md        the write-up
    ├── transcript*.md   the full terminal session, verbatim
    └── screenshots/     rendered images of that session
```

## About the screenshots

The **text** in every screenshot is real captured output, identical to the `transcript*.md`
beside it. The **window** is rendered (Python/PIL, Menlo) rather than a literal screen capture —
the browser extension available during this work refused `localhost`/`file://` pages and desktop
capture wasn't available. The transcripts are the authoritative evidence.

## Findings where reality differed from the expected answer

These are documented in the relevant sections rather than smoothed over:

- **`adduser` is not deprecated on Ubuntu 24.04** — verified on `adduser 3.137ubuntu1`; it
  prints only `info:` lines and the script contains no deprecation notice.
- **A cherry-picked commit kept the *same* SHA** — because its parent was unchanged, every hash
  input matched and Git reused the object. `git branch --contains` shows it on both branches.
  The conflict demo separately produced a genuinely different SHA.
- **A hard link across `/root` and `/tmp` succeeded** — they share one overlay device, so no
  `EXDEV`.
- **`traceroute` inside Docker shows `* * *` past hop 1** — Docker Desktop's NAT tunnel doesn't
  relay intermediate routers' TTL-exceeded replies.
- **On Rocky Linux 9, `adduser` is literally a symlink to `useradd`** — confirmed by booting the
  distro rather than assuming.
- **Two real container bugs were hit and fixed**: Java's nested `$HelloHandler.class` wasn't
  copied (`NoClassDefFoundError`), and Python's buffered stdout produced empty `docker logs`
  (fixed with `PYTHONUNBUFFERED=1`).

## Submission note

Each section's brief asks for the work to be pushed to a public GitHub repository. That step
was deliberately **left to the user** — everything here is complete and ready to commit, but
publishing to the internet is the repository owner's call.

## Source documents

The original assignment documents (`DevOps Homework.docx`, `DevOps Homework (1).docx` and the
PDF export) are deliberately **not committed** to this repository. Each task's write-up quotes
its own requirements verbatim, so every section is self-contained without them.
