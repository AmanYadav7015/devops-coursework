# Linux Fundamentals

Answers to **`DevOps Homework.docx`** — four Linux tasks, each in its own folder.

**Completed:** 02 September 2026

| Task | Container | Screenshots | Transcripts |
|---|---|---|---|
| [Task 1 — Soft Link & Hard Link](01-soft-and-hard-links/README.md) | hw-t1 | 4 | 1 |
| [Task 2 — adduser vs useradd](02-adduser-vs-useradd/README.md) | hw-t2 | 5 | 2 |
| [Task 3 — journalctl](03-journalctl/README.md) | hw-t3 | 8 | 1 |
| [Task 4 — Linux Command Cheat Sheet](04-linux-command-cheat-sheet/README.md) | hw-t4 | 18 | 3 |

## How this was done

Every command in these answers was **actually executed** — nothing is invented or
copied out of documentation. The host machine is macOS, which has no `useradd`,
`adduser`, or `journalctl`, so the practical work ran inside disposable Docker
containers built from `ubuntu:24.04`:

| Container | Task | Notes |
|---|---|---|
| `hw-t1` | Soft & hard links | plain container |
| `hw-t2` | `adduser` vs `useradd` | `adduser` + `passwd` installed |
| `hw-t3` | `journalctl` | **real systemd as PID 1**, working `journald`, `nginx`, `cron` |
| `hw-t4` | Command cheat sheet | plain container |

Task 3 needed a genuine init system, so that container ran with
`--privileged --cgroupns=host` and `/lib/systemd/systemd` as PID 1 — which is why
`journalctl` returns real journal entries instead of an error. Task 2 was
additionally cross-checked against a real **Rocky Linux 9** container to verify
how `adduser` behaves outside the Debian family.

Each task folder contains:

```
<task>/
├── README.md            the write-up (explanation, tables, interview Q&A)
├── transcript*.md       the full terminal session, verbatim
└── screenshots/         rendered images of that session
```

## A note on the screenshots

The **text** in every screenshot is real captured output, identical to the
`transcript*.md` files beside it. The **window** is rendered (Python/PIL, Menlo)
rather than a literal screen capture — the browser extension available here
refuses `localhost`/`file://` pages, and desktop capture wasn't available. The
transcripts are the authoritative evidence.

## Findings worth flagging

Where reality contradicted the expected textbook answer, these write-ups say so:

- **`adduser` is *not* deprecated on Ubuntu 24.04.** Verified directly on
  `adduser 3.137ubuntu1`: it prints only `info:` progress lines, and the script
  contains no deprecation notice.
- **A hard link across `/root` and `/tmp` succeeded** in the container — they
  share one overlay device, so no `EXDEV`. The general rule is stated separately
  from what was actually observed.
- **`ping` worked inside the container**, contrary to the usual "containers drop
  `CAP_NET_RAW`" assumption.
- **On Rocky Linux 9, `/usr/sbin/adduser` is literally a symlink to `useradd`**
  with no `/etc/adduser.conf` — confirmed by booting the distro, not assumed.
