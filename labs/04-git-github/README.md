# Assignment 4 — Git / GitHub

Two hands-on tasks:

1. `git commit -a -m "message"` vs `git commit -m "message"` — what `-a` really does, proved with a live experiment.
2. `git cherry-pick` — move one single commit from a feature branch onto `main`, including a real merge conflict and how to get out of it.

Every command below was actually executed and every block marked **Output** is the real terminal output, including the real commit SHAs. The work was done in a throwaway sandbox repository (`git init` in a temporary folder) so that nothing touched a real project.

Environment:

```text
macOS 26.5.2 (Darwin arm64)
git version 2.50.1 (Apple Git-155)
```

---

# Task 1 — `git commit -a -m` vs `git commit -m`

## The one-line answer

`-a` means "automatically stage every **already-tracked** file that was modified or deleted, then commit". It does **not** touch untracked (brand new) files. `git add` is still mandatory for anything Git has never seen before.

## Step 1: Create the sandbox repo

```bash
mkdir -p git-demo/task1-commit-a
cd git-demo/task1-commit-a
git init -b main
git config user.name "Aman Yadav"
git config user.email "nirajgeorgian@gmail.com"
```

Git replies with `Initialized empty Git repository in <your path>/git-demo/task1-commit-a/.git/`. The two `git config` lines set the identity used for the commits below. `-b main` names the initial branch `main` instead of `master`.

## Step 2: Create two files and commit them so they become *tracked*

```bash
echo "server=web01" > app.conf
echo "old deploy notes" > deploy-notes.txt
git status --short
```

Output:

```text
?? app.conf
?? deploy-notes.txt
```

`??` means untracked. Git knows the files exist on disk but is not following them yet.

```bash
git add .
git commit -m "initial commit: app.conf and deploy-notes.txt"
git log --oneline
```

Output:

```text
[main (root-commit) 1bdf9b0] initial commit: app.conf and deploy-notes.txt
 2 files changed, 2 insertions(+)
 create mode 100644 app.conf
 create mode 100644 deploy-notes.txt

1bdf9b0 initial commit: app.conf and deploy-notes.txt
```

Both files are now **tracked**. This matters for everything that follows.

## Step 3: Make three different kinds of change at once

This is the experiment. One modification, one deletion, one brand new file:

```bash
echo "server=web02" > app.conf                                # MODIFY a tracked file
rm deploy-notes.txt                                           # DELETE a tracked file
printf '#!/bin/bash\necho "deploying"\n' > new-script.sh      # CREATE an untracked file
git status
```

Output:

```text
On branch main
Changes not staged for commit:
  (use "git add/rm <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   app.conf
	deleted:    deploy-notes.txt

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	new-script.sh

no changes added to commit (use "git add" and/or "git commit -a")
```

Read that last line carefully — Git is literally telling us the two ways forward: `git add` or `git commit -a`.

## Step 4: Plain `git commit -m` with nothing staged commits NOTHING

```bash
git commit -m "try to commit without staging"
echo "EXIT=$?"
```

Output:

```text
On branch main
Changes not staged for commit:
  (use "git add/rm <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   app.conf
	deleted:    deploy-notes.txt

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	new-script.sh

no changes added to commit (use "git add" and/or "git commit -a")
EXIT=1
```

Exit code 1, no commit created. `git commit -m` only commits **what is already in the staging area (index)**. The staging area was empty, so there was nothing to commit.

## Step 5: Now run `git commit -a -m` and watch what it grabs

```bash
git commit -a -m "update app.conf and drop deploy-notes.txt"
```

Output:

```text
[main 4bdaf9a] update app.conf and drop deploy-notes.txt
 2 files changed, 1 insertion(+), 2 deletions(-)
 delete mode 100644 deploy-notes.txt
```

Two files changed — the modification **and** the deletion were auto-staged. Note that `-a` handles `rm` correctly: you do not need `git rm`.

## Step 6: Proof that the untracked file was left behind

```bash
git status --short
```

Output:

```text
?? new-script.sh
```

```bash
git status
```

Output:

```text
On branch main
Untracked files:
  (use "git add <file>..." to include in what will be committed)
	new-script.sh

nothing added to commit but untracked files present (use "git add" to track)
```

And the commit itself contains no trace of `new-script.sh`:

```bash
git show --stat HEAD
```

Output:

```text
commit 4bdaf9a937ebe8db8bc27bd2ca943fa930269a63
Author: Aman Yadav <nirajgeorgian@gmail.com>
Date:   Thu Sep 17 21:39:53 2026 +0530

    update app.conf and drop deploy-notes.txt

 app.conf         | 2 +-
 deploy-notes.txt | 1 -
 2 files changed, 1 insertion(+), 2 deletions(-)
```

**This is the whole point of the assignment.** `git commit -a -m` swept up `app.conf` and `deploy-notes.txt` because Git was already tracking them, and silently ignored `new-script.sh` because it was new. If this had been a real deployment, the script would never have reached the remote and the build would fail with "file not found".

## Step 7: `git add` + `git commit -m` picks the new file up

```bash
git add new-script.sh
git status --short
```

Output:

```text
A  new-script.sh
```

`A` in the **left** column means "added to the staging area". Left column = index/staged, right column = working directory.

```bash
git commit -m "add new-script.sh"
git show --stat HEAD
git status
```

Output:

```text
[main 16f7a83] add new-script.sh
 1 file changed, 2 insertions(+)
 create mode 100644 new-script.sh

commit 16f7a83aeea38342b387289d2895ac0ff846bffa
Author: Aman Yadav <nirajgeorgian@gmail.com>
Date:   Thu Sep 17 21:40:01 2026 +0530

    add new-script.sh

 new-script.sh | 2 ++
 1 file changed, 2 insertions(+)

On branch main
nothing to commit, working tree clean
```

## Step 8: Once a file is tracked, `-a` does pick it up

The file is only invisible to `-a` **once**, on its very first commit. After that it behaves like any other tracked file:

```bash
printf '#!/bin/bash\necho "deploying v2"\n' > new-script.sh
git status --short
git commit -a -m "bump script to v2"
```

Output:

```text
 M new-script.sh

[main a281b04] bump script to v2
 1 file changed, 1 insertion(+), 1 deletion(-)
```

Now `M` appears in the **right** column (modified in working directory, not staged) and `-a` handled it without any `git add`.

## Step 9: The dangerous gotcha — `-a` sweeps up changes you did not intend to ship

Here we edit two tracked files but only *want* to commit one of them:

```bash
echo "port=8080" >> app.conf
echo 'echo "debug line I did not want to ship"' >> new-script.sh
git status --short
git add app.conf
git status --short
```

Output:

```text
 M app.conf
 M new-script.sh

M  app.conf
 M new-script.sh
```

Only `app.conf` is staged. That is exactly what we wanted. Then a reflex `-a` ruins it:

```bash
git commit -a -m "add port to app.conf"
git show --stat HEAD
```

Output:

```text
[main 9dcf95c] add port to app.conf
 2 files changed, 2 insertions(+)

commit 9dcf95cc04c8a2af9d1090dff8ba013f1db389c0
Author: Aman Yadav <nirajgeorgian@gmail.com>
Date:   Thu Sep 17 21:40:11 2026 +0530

    add port to app.conf

 app.conf      | 1 +
 new-script.sh | 1 +
 2 files changed, 2 insertions(+)
```

The commit message says "add port to app.conf" but the commit also contains a stray debug line in `new-script.sh`. `-a` overrode the careful staging. This is how debug statements and commented-out code end up in production history.

## Comparison table

| | `git commit -m "msg"` | `git commit -a -m "msg"` |
|---|---|---|
| Commits staged changes | Yes | Yes |
| Modified **tracked** files, unstaged | Ignored | Auto-staged and committed |
| Deleted **tracked** files | Ignored | Auto-staged and committed |
| **Untracked** (new) files | Ignored | **Still ignored** |
| Needs `git add` first | Yes, for everything | Only for new files |
| Respects partial staging (`git add -p`) | Yes | No — it overrides it |
| Equivalent long form | `git commit --message` | `git commit --all --message` |
| Roughly equals | — | `git add -u && git commit -m` |
| Safe for careful, reviewed commits | Yes | Risky |
| Good for quick "fix typo" commits | Verbose | Fastest |

The mental model: `git commit -a` is the same as running `git add -u` (update tracked files only) and then committing. It is **not** `git add -A` and it is **not** `git add .`, both of which do include new files.

## Gotchas worth remembering

- `-a` never stages a new file. First commit of any file always needs `git add`.
- `-a` throws away your partial staging. If you used `git add -p` to split a messy working tree into clean commits, `-a` undoes that in one keystroke.
- `-a` respects `.gitignore` the same way — ignored files stay ignored either way.
- `git commit -am "msg"` is the same thing with the flags combined. Careful: `git commit -m -a "msg"` would use `-a` as the message text.
- Habit to build: run `git status` before every commit, and prefer `git add <specific files>` when the change matters.

---

# Task 2 — `git cherry-pick`: taking one commit from a branch

## What cherry-pick is for

A merge brings over **an entire branch**. A cherry-pick brings over **one commit** (or a chosen few). The classic real-world case: a hotfix was committed on a long-running feature branch that is nowhere near ready to merge, but production needs that one fix right now.

Key fact demonstrated below: cherry-pick **replays the change and creates a brand new commit with a different SHA**. It does not move or copy the original commit.

## Step 1: Build a repo with three commits on `main`

```bash
mkdir -p git-demo/task2-cherry-pick
cd git-demo/task2-cherry-pick
git init -b main
git config user.name "Aman Yadav"
git config user.email "nirajgeorgian@gmail.com"

echo "# Yatri App" > README.md
git add README.md
git commit -m "C1: add README with project title"

printf '#!/bin/bash\napt-get install -y nginx\n' > install.sh
git add install.sh
git commit -m "C2: add install.sh for nginx setup"

printf 'app: yatri\nreplicas: 2\n' > config.yml
git add config.yml
git commit -m "C3: add config.yml with replica count"
```

Output:

```text
[main (root-commit) 661a37f] C1: add README with project title
 1 file changed, 1 insertion(+)
 create mode 100644 README.md
[main 09ec869] C2: add install.sh for nginx setup
 1 file changed, 2 insertions(+)
 create mode 100644 install.sh
[main d3e5755] C3: add config.yml with replica count
 1 file changed, 2 insertions(+)
 create mode 100644 config.yml
```

## Step 2: `git log --oneline` on main

```bash
git log --oneline
```

Output:

```text
d3e5755 C3: add config.yml with replica count
09ec869 C2: add install.sh for nginx setup
661a37f C1: add README with project title
```

## Step 3: Create a new branch and make three commits on it

```bash
git checkout -b feature/monitoring

printf '#!/bin/bash\ncurl -f http://localhost/health || exit 1\n' > health-check.sh
git add health-check.sh
git commit -m "F1: add health-check.sh"

printf '# Alert Rules\n- CPU above 80 percent for 5 minutes\n- Disk above 90 percent\n' > alerts.md
git add alerts.md
git commit -m "F2: add alerts.md with alert rules"

printf '{\n  "dashboard": "yatri-overview",\n  "panels": 6\n}\n' > dashboard.json
git add dashboard.json
git commit -m "F3: add grafana dashboard.json"
```

Output:

```text
Switched to a new branch 'feature/monitoring'
[feature/monitoring 981c1c3] F1: add health-check.sh
 1 file changed, 2 insertions(+)
 create mode 100644 health-check.sh
[feature/monitoring 773172c] F2: add alerts.md with alert rules
 1 file changed, 3 insertions(+)
 create mode 100644 alerts.md
[feature/monitoring 1716e73] F3: add grafana dashboard.json
 1 file changed, 4 insertions(+)
 create mode 100644 dashboard.json
```

## Step 4: `git log` to identify the ONE commit we want

```bash
git log --oneline
```

Output:

```text
1716e73 F3: add grafana dashboard.json
773172c F2: add alerts.md with alert rules
981c1c3 F1: add health-check.sh
d3e5755 C3: add config.yml with replica count
09ec869 C2: add install.sh for nginx setup
661a37f C1: add README with project title
```

To see only the commits that exist on the branch and not on main, use the double-dot range:

```bash
git log main..feature/monitoring
```

Output:

```text
commit 1716e7327539b0785188e624af5032abd80fdced
Author: Aman Yadav <nirajgeorgian@gmail.com>
Date:   Thu Sep 17 21:40:37 2026 +0530

    F3: add grafana dashboard.json

commit 773172c36ce1ada7c0a4f96d05e26ff6ab80cbc5
Author: Aman Yadav <nirajgeorgian@gmail.com>
Date:   Thu Sep 17 21:40:37 2026 +0530

    F2: add alerts.md with alert rules

commit 981c1c3436d54902b468897b5f6e4fedabff0ba1
Author: Aman Yadav <nirajgeorgian@gmail.com>
Date:   Thu Sep 17 21:40:37 2026 +0530

    F1: add health-check.sh
```

**The commit we want is the middle one: `773172c36ce1ada7c0a4f96d05e26ff6ab80cbc5` ("F2: add alerts.md with alert rules").** The alert rules are urgently needed on main; the health check and the Grafana dashboard are not ready yet.

## Step 5: Switch to main and cherry-pick that single commit

```bash
git checkout main
ls
git cherry-pick 773172c
```

Output:

```text
Switched to branch 'main'

README.md
config.yml
install.sh

[main 5017f9d] F2: add alerts.md with alert rules
 Date: Thu Sep 17 21:40:37 2026 +0530
 1 file changed, 3 insertions(+)
 create mode 100644 alerts.md
```

The short SHA is enough — Git resolves `773172c` to the full hash. `HEAD~1`, a tag, or a branch name also work.

## Step 6: Verify it landed

```bash
git log --oneline
```

Output:

```text
5017f9d F2: add alerts.md with alert rules
d3e5755 C3: add config.yml with replica count
09ec869 C2: add install.sh for nginx setup
661a37f C1: add README with project title
```

```bash
ls
cat alerts.md
```

Output:

```text
README.md
alerts.md
config.yml
install.sh

# Alert Rules
- CPU above 80 percent for 5 minutes
- Disk above 90 percent
```

`alerts.md` is on main with the correct content, and — importantly — `health-check.sh` and `dashboard.json` are **not** there. Only the one commit came across.

```bash
git show HEAD
```

Output:

```text
commit 5017f9dde68c396ec0fcfdc9cd2ee0131dc771bf
Author: Aman Yadav <nirajgeorgian@gmail.com>
Date:   Thu Sep 17 21:40:37 2026 +0530

    F2: add alerts.md with alert rules

diff --git a/alerts.md b/alerts.md
new file mode 100644
index 0000000..80f24e1
--- /dev/null
+++ b/alerts.md
@@ -0,0 +1,3 @@
+# Alert Rules
+- CPU above 80 percent for 5 minutes
+- Disk above 90 percent
```

Notice the author date was preserved (21:40:37) but the commit itself is new.

## Step 7: Proof that the SHA is different but the change is identical

```bash
git log -1 --format='commit %H%nparent %p%nsubject %s' 773172c
git log -1 --format='commit %H%nparent %p%nsubject %s' 5017f9d
```

Output:

```text
commit 773172c36ce1ada7c0a4f96d05e26ff6ab80cbc5
parent 981c1c3
subject F2: add alerts.md with alert rules

commit 5017f9dde68c396ec0fcfdc9cd2ee0131dc771bf
parent d3e5755
subject F2: add alerts.md with alert rules
```

Side by side:

| | Original (on `feature/monitoring`) | Cherry-picked (on `main`) |
|---|---|---|
| Full SHA | `773172c36ce1ada7c0a4f96d05e26ff6ab80cbc5` | `5017f9dde68c396ec0fcfdc9cd2ee0131dc771bf` |
| Parent | `981c1c3` (F1) | `d3e5755` (C3) |
| Subject | F2: add alerts.md with alert rules | F2: add alerts.md with alert rules |
| File added | `alerts.md` | `alerts.md` |

A commit SHA is a hash of the tree, the **parent**, the author, the committer and the message. The parent changed, so the hash changed. The two commits are different objects that happen to contain the same diff.

Git can prove the diffs are identical using `patch-id`, which hashes only the change, ignoring parentage and metadata:

```bash
git show 773172c | git patch-id --stable
git show 5017f9d | git patch-id --stable
```

Output:

```text
0bf3e3b60bcd0d4ed21f2b524fb82140144f6850 773172c36ce1ada7c0a4f96d05e26ff6ab80cbc5
0bf3e3b60bcd0d4ed21f2b524fb82140144f6850 5017f9dde68c396ec0fcfdc9cd2ee0131dc771bf
```

First column (the patch ID) is **identical**. Second column (the commit SHA) is **different**. Same change, different commit — exactly what a cherry-pick does.

A direct diff of the two patches confirms it:

```bash
diff <(git show 773172c --format="") <(git show 5017f9d --format="")
```

This printed nothing at all and exited 0, which is `diff` saying the two patches are byte-for-byte identical once the commit headers are stripped off with `--format=""`.

## Step 8: `-x` to record where the commit came from

Because the SHA changes, six months later nobody can tell where a cherry-picked commit originated. `-x` appends a line to the message that records the source commit:

```bash
git cherry-pick -x 1716e73
git log -1
```

Output:

```text
[main d16873a] F3: add grafana dashboard.json
 Date: Thu Sep 17 21:40:37 2026 +0530
 1 file changed, 4 insertions(+)
 create mode 100644 dashboard.json

commit d16873a2fe5a11708d15c4bcafb0629426239dd2
Author: Aman Yadav <nirajgeorgian@gmail.com>
Date:   Thu Sep 17 21:40:37 2026 +0530

    F3: add grafana dashboard.json
    
    (cherry picked from commit 1716e7327539b0785188e624af5032abd80fdced)
```

Use `-x` for anything cherry-picked into a public/shared branch such as a release branch. Skip it when cherry-picking between private local branches, where the source SHA may not exist for anyone else.

## Step 9: What a cherry-pick CONFLICT looks like

Set up a genuine conflict — the same line of `config.yml` edited differently on both sides:

```bash
git checkout -b feature/scaling
printf 'app: yatri\nreplicas: 5\n' > config.yml
git add config.yml
git commit -m "S1: scale to 5 replicas"
git log -1 --format='%H %s'

git checkout main
printf 'app: yatri\nreplicas: 10\n' > config.yml
git add config.yml
git commit -m "M4: scale to 10 replicas on main"
```

Output:

```text
Switched to a new branch 'feature/scaling'
[feature/scaling b8a918b] S1: scale to 5 replicas
 1 file changed, 1 insertion(+), 1 deletion(-)
b8a918b4e5b3c2d2b4bcbc4251de395402262664 S1: scale to 5 replicas

Switched to branch 'main'
[main 993bfa1] M4: scale to 10 replicas on main
 1 file changed, 1 insertion(+), 1 deletion(-)
```

Now cherry-pick the branch commit onto main, where the same line already says something else:

```bash
git cherry-pick b8a918b
echo "EXIT=$?"
```

Output:

```text
Auto-merging config.yml
CONFLICT (content): Merge conflict in config.yml
error: could not apply b8a918b... S1: scale to 5 replicas
hint: After resolving the conflicts, mark them with
hint: "git add/rm <pathspec>", then run
hint: "git cherry-pick --continue".
hint: You can instead skip this commit with "git cherry-pick --skip".
hint: To abort and get back to the state before "git cherry-pick",
hint: run "git cherry-pick --abort".
hint: Disable this message with "git config set advice.mergeConflict false"
EXIT=1
```

The repository is now in a paused, mid-cherry-pick state:

```bash
git status
```

Output:

```text
On branch main
You are currently cherry-picking commit b8a918b.
  (fix conflicts and run "git cherry-pick --continue")
  (use "git cherry-pick --skip" to skip this patch)
  (use "git cherry-pick --abort" to cancel the cherry-pick operation)

Unmerged paths:
  (use "git add <file>..." to mark resolution)
	both modified:   config.yml

no changes added to commit (use "git add" and/or "git commit -a")
```

The file on disk now carries conflict markers:

```bash
cat config.yml
```

Output:

```text
app: yatri
<<<<<<< HEAD
replicas: 10
=======
replicas: 5
>>>>>>> b8a918b (S1: scale to 5 replicas)
```

How to read the markers:

- `<<<<<<< HEAD` to `=======` — what is currently on the branch you are sitting on (`main`).
- `=======` to `>>>>>>>` — what the commit being cherry-picked wants.
- The label after `>>>>>>>` is the SHA and subject of the commit being applied.

List just the conflicted files:

```bash
git diff --name-only --diff-filter=U
```

Output:

```text
config.yml
```

## Step 10: Escape hatch — `git cherry-pick --abort`

If you decide this was a bad idea, `--abort` rewinds everything to exactly the state before the cherry-pick:

```bash
git cherry-pick --abort
git status
cat config.yml
git log --oneline -3
```

Output:

```text
On branch main
nothing to commit, working tree clean

app: yatri
replicas: 10

993bfa1 M4: scale to 10 replicas on main
d16873a F3: add grafana dashboard.json
5017f9d F2: add alerts.md with alert rules
```

Clean tree, conflict markers gone, `main` untouched.

## Step 11: Resolving properly — `git cherry-pick --continue`

Run it again and resolve the conflict this time:

```bash
git cherry-pick -x b8a918b
```

Output:

```text
Auto-merging config.yml
CONFLICT (content): Merge conflict in config.yml
error: could not apply b8a918b... S1: scale to 5 replicas
hint: After resolving the conflicts, mark them with
hint: "git add/rm <pathspec>", then run
hint: "git cherry-pick --continue".
hint: You can instead skip this commit with "git cherry-pick --skip".
hint: To abort and get back to the state before "git cherry-pick",
hint: run "git cherry-pick --abort".
hint: Disable this message with "git config set advice.mergeConflict false"
```

Edit the file, delete all three markers, and leave the version you actually want (here: the incoming value, 5 replicas):

```bash
printf 'app: yatri\nreplicas: 5\n' > config.yml
cat config.yml
git add config.yml
git status
```

Output:

```text
app: yatri
replicas: 5

On branch main
You are currently cherry-picking commit b8a918b.
  (all conflicts fixed: run "git cherry-pick --continue")
  (use "git cherry-pick --skip" to skip this patch)
  (use "git cherry-pick --abort" to cancel the cherry-pick operation)

Changes to be committed:
	modified:   config.yml
```

`git add` on a conflicted file is what marks it resolved. The hint changes from "fix conflicts" to "all conflicts fixed". Now finish:

```bash
git cherry-pick --continue
```

(This opens your editor with the commit message pre-filled. Save and quit to accept it, or use `GIT_EDITOR=true git cherry-pick --continue` to accept it without opening an editor.)

Output:

```text
[main ee6853c] S1: scale to 5 replicas
 Date: Thu Sep 17 21:41:20 2026 +0530
 1 file changed, 1 insertion(+), 1 deletion(-)
```

Verify:

```bash
git log --oneline -4
git show HEAD
git status
```

Output:

```text
ee6853c S1: scale to 5 replicas
993bfa1 M4: scale to 10 replicas on main
d16873a F3: add grafana dashboard.json
5017f9d F2: add alerts.md with alert rules

commit ee6853c38084882d42d83e899d706229999b6ddc
Author: Aman Yadav <nirajgeorgian@gmail.com>
Date:   Thu Sep 17 21:41:20 2026 +0530

    S1: scale to 5 replicas
    
    (cherry picked from commit b8a918b4e5b3c2d2b4bcbc4251de395402262664)

diff --git a/config.yml b/config.yml
index 52b0f46..0a07a2b 100644
--- a/config.yml
+++ b/config.yml
@@ -1,2 +1,2 @@
 app: yatri
-replicas: 10
+replicas: 5
```

```text
On branch main
nothing to commit, working tree clean
```

Two things to note. The resulting diff is `10 -> 5`, **not** the original `2 -> 5`, because the patch was replayed against main's current content — that is why conflicts happen at all. And the `-x` trailer survived the conflict resolution, so the origin is still recorded.

## Step 12: Final state of the sandbox

```bash
git log --oneline --graph --all --decorate
```

Output:

```text
* ee6853c (HEAD -> main) S1: scale to 5 replicas
* 993bfa1 M4: scale to 10 replicas on main
| * b8a918b (feature/scaling) S1: scale to 5 replicas
|/  
* d16873a F3: add grafana dashboard.json
* 5017f9d F2: add alerts.md with alert rules
| * 1716e73 (feature/monitoring) F3: add grafana dashboard.json
| * 773172c F2: add alerts.md with alert rules
| * 981c1c3 F1: add health-check.sh
|/  
* d3e5755 C3: add config.yml with replica count
* 09ec869 C2: add install.sh for nginx setup
* 661a37f C1: add README with project title
```

This graph is the whole lesson in one picture. `773172c` and `5017f9d` carry the same change, and `b8a918b` and `ee6853c` carry the same change, but they are four distinct commits on two separate lines of history. The branches were never merged — main simply grew copies of selected commits.

## Cherry-pick quick reference

| Command | What it does |
|---|---|
| `git cherry-pick <sha>` | Replay one commit onto the current branch |
| `git cherry-pick <sha1> <sha2>` | Replay several specific commits, in the order given |
| `git cherry-pick A..B` | Replay the range, excluding A, including B |
| `git cherry-pick A^..B` | Replay the range including A itself |
| `git cherry-pick -x <sha>` | Add `(cherry picked from commit ...)` to the message |
| `git cherry-pick -n <sha>` | Apply the change but do not commit — leaves it staged |
| `git cherry-pick -e <sha>` | Edit the commit message before committing |
| `git cherry-pick --continue` | Resume after resolving conflicts (`git add` first) |
| `git cherry-pick --abort` | Cancel completely, restore the pre-cherry-pick state |
| `git cherry-pick --skip` | Drop this one commit and continue with the rest of a range |
| `git cherry-pick -m 1 <sha>` | Cherry-pick a merge commit, taking parent 1 as the mainline |

## When to cherry-pick, and when not to

Good reasons:

- A hotfix committed on a feature branch is needed on `main` or on a release branch right now.
- Backporting a fix from `main` into `release/1.x`.
- Recovering one useful commit from a branch that is being abandoned.
- Pulling a commit off a branch that accidentally got committed to the wrong place.

Reasons to avoid it:

- Cherry-picking commit after commit from the same branch. If you want most of the branch, merge it — repeated cherry-picks create duplicate history and set you up for conflicts when that branch is eventually merged.
- Cherry-picking a commit that depends on earlier commits from the same branch. The dependency is not brought along, so the build breaks. Check for that before you pick.
- Cherry-picking a commit that others have already got through a merge — you end up with the same change twice.

---

# Interview questions

**Q1. What does `-a` in `git commit -a -m "msg"` actually do?**
It automatically stages all changes to files Git is **already tracking** — modifications and deletions — and then commits. It is equivalent to `git add -u` followed by `git commit -m`. It does **not** stage new untracked files; those still need an explicit `git add`.

**Q2. You edited three files, created one new file, then ran `git commit -a -m "work"` and pushed. What is on the remote?**
The three edited files. The new file is still sitting untracked in your working directory, and the build on the remote will fail if anything imports it. The fix: `git status` before every push.

**Q3. Is `git commit -a` the same as `git add . && git commit`?**
No. `git add .` stages new files too, `-a` does not. `git commit -a` is `git add -u` (update tracked only) plus commit.

**Q4. Cherry-pick vs merge vs rebase — explain the difference.**

| | `git cherry-pick` | `git merge` | `git rebase` |
|---|---|---|---|
| What moves | One commit (or a chosen few) | The entire branch | The entire branch |
| Result | A new commit with a new SHA on the current branch | A merge commit with two parents; both histories preserved | Your commits replayed on a new base, each with a new SHA |
| History shape | Linear, but the change now exists in two places | Branched, shows exactly what happened | Linear, looks like the work was always done on top of the target |
| Rewrites history | No — it adds a commit | No | Yes — all rebased commits get new SHAs |
| Safe on a shared branch | Yes | Yes | No — never rebase commits others have pulled |
| Conflict handling | Once, for that commit | Once, at the merge point | Potentially once per commit being replayed |
| Typical use | Backport a hotfix; grab one commit | Integrate a finished feature | Clean up your local branch before opening a PR |

**Q5. Why does a cherry-picked commit have a different SHA from the original?**
A commit hash is computed over the tree, the parent commit(s), the author, the committer and the message. The cherry-picked copy has a different parent (it sits on a different branch), so the hash is different. The **content** of the change is identical, which you can prove with `git patch-id` — both patches hash to the same patch ID while the commit SHAs differ.

**Q6. You are mid-cherry-pick with a conflict. What are your three options?**
`git cherry-pick --abort` (cancel and restore the previous state), `git cherry-pick --skip` (drop this commit and carry on with the remaining ones in a range), or fix the file, `git add` it, and `git cherry-pick --continue`.

**Q7. What does `-x` do and when would you use it?**
It appends `(cherry picked from commit <sha>)` to the commit message so the origin is traceable. Use it for cherry-picks into shared branches such as release branches; skip it for local-only branches whose SHAs mean nothing to anyone else.

**Q8. When is cherry-pick the wrong tool?**
When you want most of a branch — merge it instead. Repeated cherry-picks duplicate changes, and when the branch is finally merged those duplicates turn into conflicts. Also wrong when the commit depends on earlier commits from the same branch, since cherry-pick brings only the one diff.

**Q9. How do you find out whether a commit has already been cherry-picked into another branch?**
`git log --cherry-pick --left-right main...feature` or `git cherry -v main feature`. Both use patch IDs rather than SHAs, so they spot the equivalent commits.

**Q10. After cherry-picking the fix onto main, do you still need to merge the feature branch later?**
Yes, if the rest of the branch is still wanted. Git will usually detect the duplicated change at merge time and handle it, but the same lines touched twice can still conflict — that is the cost of cherry-picking.
