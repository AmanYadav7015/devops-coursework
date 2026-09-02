# Git — cherry-pick + conflict resolution

> Real session captured in container `git-t1`.
> Every command was executed; the output is verbatim.

[← Back](README.md)

---

```console
# ==== Fresh repo, 4 commits on main ====
root@ubuntu-hw:~# rm -rf ~/task2-repo && mkdir -p ~/task2-repo && cd ~/task2-repo && git init
Initialized empty Git repository in /root/task2-repo/.git/
root@ubuntu-hw:~# cd ~/task2-repo && echo "line1: config for prod" > config.txt && git add config.txt && git commit -m "main: add config.txt"
[main (root-commit) 1cbb940] main: add config.txt
 1 file changed, 1 insertion(+)
 create mode 100644 config.txt
root@ubuntu-hw:~# cd ~/task2-repo && echo "def app():" > app.py && echo "    return 'v1'" >> app.py && git add app.py && git commit -m "main: add app.py"
[main c836926] main: add app.py
 1 file changed, 2 insertions(+)
 create mode 100644 app.py
root@ubuntu-hw:~# cd ~/task2-repo && echo "# Project Docs" > README.md && git add README.md && git commit -m "main: add README.md"
[main 02783bb] main: add README.md
 1 file changed, 1 insertion(+)
 create mode 100644 README.md
root@ubuntu-hw:~# cd ~/task2-repo && echo "utils go here" > utils.py && git add utils.py && git commit -m "main: add utils.py"
[main b498e68] main: add utils.py
 1 file changed, 1 insertion(+)
 create mode 100644 utils.py
root@ubuntu-hw:~# cd ~/task2-repo && git log --oneline --graph --decorate --all
* b498e68 (HEAD -> main) main: add utils.py
* 02783bb main: add README.md
* c836926 main: add app.py
* 1cbb940 main: add config.txt

# ==== Create a new branch ====
root@ubuntu-hw:~# cd ~/task2-repo && git checkout -b feature
Switched to a new branch 'feature'
root@ubuntu-hw:~# cd ~/task2-repo && git branch
* feature
  main

# ==== 3 commits on feature ====
root@ubuntu-hw:~# cd ~/task2-repo && echo "def login(): pass" > auth.py && git add auth.py && git commit -m "feature: add auth.py with login stub"
[feature 4b2a5cc] feature: add auth.py with login stub
 1 file changed, 1 insertion(+)
 create mode 100644 auth.py
root@ubuntu-hw:~# cd ~/task2-repo && echo "def app():" > app.py && echo "    return 'v2-feature'" >> app.py && git add app.py && git commit -m "feature: bump app.py to v2"
[feature 2b245e9] feature: bump app.py to v2
 1 file changed, 1 insertion(+), 1 deletion(-)
root@ubuntu-hw:~# cd ~/task2-repo && echo "CACHE_TTL=300" > cache_config.txt && git add cache_config.txt && git commit -m "feature: add cache_config.txt"
[feature e09a35d] feature: add cache_config.txt
 1 file changed, 1 insertion(+)
 create mode 100644 cache_config.txt
root@ubuntu-hw:~# cd ~/task2-repo && git log --oneline
e09a35d feature: add cache_config.txt
2b245e9 feature: bump app.py to v2
4b2a5cc feature: add auth.py with login stub
b498e68 main: add utils.py
02783bb main: add README.md
c836926 main: add app.py
1cbb940 main: add config.txt
root@ubuntu-hw:~# cd ~/task2-repo && git log --oneline --graph --decorate --all
* e09a35d (HEAD -> feature) feature: add cache_config.txt
* 2b245e9 feature: bump app.py to v2
* 4b2a5cc feature: add auth.py with login stub
* b498e68 (main) main: add utils.py
* 02783bb main: add README.md
* c836926 main: add app.py
* 1cbb940 main: add config.txt

# --- identify ONE specific commit to cherry-pick: the auth.py commit ---
root@ubuntu-hw:~# cd ~/task2-repo && git log --oneline -3
e09a35d feature: add cache_config.txt
2b245e9 feature: bump app.py to v2
4b2a5cc feature: add auth.py with login stub
root@ubuntu-hw:~# cd ~/task2-repo && AUTH_SHA=$(git log --format=%H -1 --grep="add auth.py") && echo "AUTH_SHA=$AUTH_SHA" && echo "$AUTH_SHA" > /root/auth_sha.txt
AUTH_SHA=4b2a5cc0237dae1200c55ad76406cf16b7a9c6d0

# ==== Switch back to main and cherry-pick that commit ====
root@ubuntu-hw:~# cd ~/task2-repo && git checkout main
Switched to branch 'main'
root@ubuntu-hw:~# cd ~/task2-repo && ls
README.md
app.py
config.txt
utils.py
root@ubuntu-hw:~# cd ~/task2-repo && git cherry-pick $(cat /root/auth_sha.txt)
[main 4b2a5cc] feature: add auth.py with login stub
 Date: Wed Sep 2 17:27:46 2026 +0000
 1 file changed, 1 insertion(+)
 create mode 100644 auth.py
root@ubuntu-hw:~# cd ~/task2-repo && git log --oneline --graph --decorate --all
* e09a35d (feature) feature: add cache_config.txt
* 2b245e9 feature: bump app.py to v2
* 4b2a5cc (HEAD -> main) feature: add auth.py with login stub
* b498e68 main: add utils.py
* 02783bb main: add README.md
* c836926 main: add app.py
* 1cbb940 main: add config.txt

# ==== Verify the change landed on main ====
root@ubuntu-hw:~# cd ~/task2-repo && ls
README.md
app.py
auth.py
config.txt
utils.py
root@ubuntu-hw:~# cd ~/task2-repo && cat auth.py
def login(): pass
root@ubuntu-hw:~# cd ~/task2-repo && NEW_SHA=$(git log --format=%H -1) && echo "NEW_SHA=$NEW_SHA" && echo "$NEW_SHA" > /root/new_sha.txt
NEW_SHA=4b2a5cc0237dae1200c55ad76406cf16b7a9c6d0
root@ubuntu-hw:~# cd ~/task2-repo && git show --stat $(cat /root/new_sha.txt)
commit 4b2a5cc0237dae1200c55ad76406cf16b7a9c6d0
Author: DevOps Student <student@example.com>
Date:   Wed Sep 2 17:27:46 2026 +0000

    feature: add auth.py with login stub

 auth.py | 1 +
 1 file changed, 1 insertion(+)

# --- prove the OTHER two feature commits are NOT on main ---
root@ubuntu-hw:~# cd ~/task2-repo && ls
README.md
app.py
auth.py
config.txt
utils.py
root@ubuntu-hw:~# cd ~/task2-repo && cat app.py
def app():
    return 'v1'
root@ubuntu-hw:~# cd ~/task2-repo && test -f cache_config.txt && echo "cache_config.txt EXISTS (unexpected)" || echo "cache_config.txt is ABSENT on main (expected)"
cache_config.txt is ABSENT on main (expected)
root@ubuntu-hw:~# cd ~/task2-repo && git log main --oneline
4b2a5cc feature: add auth.py with login stub
b498e68 main: add utils.py
02783bb main: add README.md
c836926 main: add app.py
1cbb940 main: add config.txt

# --- compare SHAs: original commit on feature vs the new commit on main ---
root@ubuntu-hw:~# cd ~/task2-repo && echo "ORIGINAL (on feature): $(cat /root/auth_sha.txt)"
ORIGINAL (on feature): 4b2a5cc0237dae1200c55ad76406cf16b7a9c6d0
root@ubuntu-hw:~# cd ~/task2-repo && echo "CHERRY-PICKED (on main): $(cat /root/new_sha.txt)"
CHERRY-PICKED (on main): 4b2a5cc0237dae1200c55ad76406cf16b7a9c6d0
root@ubuntu-hw:~# cd ~/task2-repo && git branch --contains $(cat /root/auth_sha.txt)
  feature
* main

# ==== BONUS: cherry-pick conflict demo ====
# --- Set up a genuine conflict: both branches edit the SAME line of config.txt ---
root@ubuntu-hw:~# cd ~/task2-repo && git checkout feature
Switched to branch 'feature'
root@ubuntu-hw:~# cd ~/task2-repo && echo "line1: config for STAGING (feature branch edit)" > config.txt
root@ubuntu-hw:~# cd ~/task2-repo && git add config.txt && git commit -m "feature: change config.txt for staging"
[feature 79ff6ae] feature: change config.txt for staging
 1 file changed, 1 insertion(+), 1 deletion(-)
root@ubuntu-hw:~# cd ~/task2-repo && CONFLICT_SHA=$(git log --format=%H -1) && echo "CONFLICT_SHA=$CONFLICT_SHA" && echo "$CONFLICT_SHA" > /root/conflict_sha.txt
CONFLICT_SHA=79ff6aec014d35b4ad97b17c2652dbca2a9b7433
root@ubuntu-hw:~# cd ~/task2-repo && git checkout main
Switched to branch 'main'
root@ubuntu-hw:~# cd ~/task2-repo && echo "line1: config for PRODUCTION-v2 (main branch edit)" > config.txt
root@ubuntu-hw:~# cd ~/task2-repo && git add config.txt && git commit -m "main: change config.txt for production v2"
[main 60d5ee0] main: change config.txt for production v2
 1 file changed, 1 insertion(+), 1 deletion(-)
root@ubuntu-hw:~# cd ~/task2-repo && cat config.txt
line1: config for PRODUCTION-v2 (main branch edit)

# --- attempt the cherry-pick: this SHOULD conflict ---
root@ubuntu-hw:~# cd ~/task2-repo && export GIT_EDITOR=true && git cherry-pick $(cat /root/conflict_sha.txt)
Auto-merging config.txt
CONFLICT (content): Merge conflict in config.txt
error: could not apply 79ff6ae... feature: change config.txt for staging
hint: After resolving the conflicts, mark them with
hint: "git add/rm <pathspec>", then run
hint: "git cherry-pick --continue".
hint: You can instead skip this commit with "git cherry-pick --skip".
hint: To abort and get back to the state before "git cherry-pick",
hint: run "git cherry-pick --abort".
root@ubuntu-hw:~# cd ~/task2-repo && git status
On branch main
You are currently cherry-picking commit 79ff6ae.
  (fix conflicts and run "git cherry-pick --continue")
  (use "git cherry-pick --skip" to skip this patch)
  (use "git cherry-pick --abort" to cancel the cherry-pick operation)

Unmerged paths:
  (use "git add <file>..." to mark resolution)
	both modified:   config.txt

no changes added to commit (use "git add" and/or "git commit -a")
root@ubuntu-hw:~# cd ~/task2-repo && cat config.txt
<<<<<<< HEAD
line1: config for PRODUCTION-v2 (main branch edit)
=======
line1: config for STAGING (feature branch edit)
>>>>>>> 79ff6ae (feature: change config.txt for staging)

# --- resolve the conflict by editing the file ---
root@ubuntu-hw:~# cd ~/task2-repo && printf 'line1: config for PRODUCTION-v2 (resolved: merged main prod value with feature staging intent)\n' > config.txt
root@ubuntu-hw:~# cd ~/task2-repo && cat config.txt
line1: config for PRODUCTION-v2 (resolved: merged main prod value with feature staging intent)
root@ubuntu-hw:~# cd ~/task2-repo && git add config.txt
root@ubuntu-hw:~# cd ~/task2-repo && git status
On branch main
You are currently cherry-picking commit 79ff6ae.
  (all conflicts fixed: run "git cherry-pick --continue")
  (use "git cherry-pick --skip" to skip this patch)
  (use "git cherry-pick --abort" to cancel the cherry-pick operation)

Changes to be committed:
	modified:   config.txt

root@ubuntu-hw:~# cd ~/task2-repo && GIT_EDITOR=true git cherry-pick --continue
[main 9f7393c] feature: change config.txt for staging
 Date: Wed Sep 2 17:27:47 2026 +0000
 1 file changed, 1 insertion(+), 1 deletion(-)
root@ubuntu-hw:~# cd ~/task2-repo && git log --oneline --graph --decorate --all
* 9f7393c (HEAD -> main) feature: change config.txt for staging
* 60d5ee0 main: change config.txt for production v2
| * 79ff6ae (feature) feature: change config.txt for staging
| * e09a35d feature: add cache_config.txt
| * 2b245e9 feature: bump app.py to v2
|/  
* 4b2a5cc feature: add auth.py with login stub
* b498e68 main: add utils.py
* 02783bb main: add README.md
* c836926 main: add app.py
* 1cbb940 main: add config.txt
root@ubuntu-hw:~# cd ~/task2-repo && cat config.txt
line1: config for PRODUCTION-v2 (resolved: merged main prod value with feature staging intent)
root@ubuntu-hw:~# cd ~/task2-repo && git status
On branch main
nothing to commit, working tree clean
```
