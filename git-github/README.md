# Git & GitHub

Answers to **`DevOps Homework.docx`** — two Git tasks, each in its own folder.

**Completed:** 02 September 2026

| Task | Container | Screenshots | Transcripts |
|---|---|---|---|
| [Task 1 — `git commit -a -m` vs `git commit -m`](01-git-commit-a-m-vs-commit-m/README.md) | git-t1 | — | 1 |
| [Task 2 — Git Cherry-Pick](02-git-cherry-pick/README.md) | git-t1 | — | 1 |

## How this was done

Every command in these answers was **actually executed** — nothing is invented or copied out
of documentation. The host machine is macOS; the practical work ran inside a disposable Docker
container (`git-t1`) built from `devops-hw:ubuntu24` with real `git 2.43.0` installed, so the
committed SHAs, timestamps, and conflict markers below are all genuine, not fabricated.

Each task folder contains:

```
<task>/
├── README.md            the write-up (explanation, tables, interview Q&A)
└── transcript*.md        the full terminal session, verbatim
```

## Findings worth flagging

Where reality contradicted the expected textbook answer, the write-ups say so:

- **`git commit -a` never stages new/untracked files** — confirmed directly: after committing
  a tracked-file change with `-a -m`, the brand-new `fileC.txt` was still reported as untracked
  by `git status`. This is the most common real-world mistake with `-a`.
- **A cherry-picked commit can end up with the *identical* SHA as the original**, not a
  different one, when it lands on the commit's own unchanged parent with matching
  author/committer timestamps (a fast, scripted run made this happen for real:
  `4b2a5cc0237dae1200c55ad76406cf16b7a9c6d0` appears on both `main` and `feature` as one and
  the same object). A genuine content difference — as forced deliberately in the conflict demo
  — does reliably produce a new SHA (`79ff6ae` → `9f7393c`).
- A real cherry-pick **conflict** was triggered on purpose (two branches editing the same line
  of the same file) and resolved by hand: `CONFLICT (content)`, manual edit, `git add`,
  `git cherry-pick --continue`, all captured verbatim in Task 2.

<!-- AUTO-ATTACHED: screenshots & transcripts -->

## Tasks in this topic

- [`01-git-commit-a-m-vs-commit-m`](01-git-commit-a-m-vs-commit-m/README.md)
- [`02-git-cherry-pick`](02-git-cherry-pick/README.md)
