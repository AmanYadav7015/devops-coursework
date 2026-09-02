# Git — commit -a -m vs commit -m

> Real session captured in container `git-t1`.
> Every command was executed; the output is verbatim.

[← Back](README.md)

---

```console
# ==== Set up a fresh repo ====
root@ubuntu-hw:~# rm -rf ~/task1-repo && mkdir -p ~/task1-repo && cd ~/task1-repo && git init
Initialized empty Git repository in /root/task1-repo/.git/
root@ubuntu-hw:~# cd ~/task1-repo && git status
On branch main

No commits yet

nothing to commit (create/copy files and use "git add" to track)

# ==== Create two tracked files and make the initial commit ====
root@ubuntu-hw:~# cd ~/task1-repo && echo "Hello from file A" > fileA.txt
root@ubuntu-hw:~# cd ~/task1-repo && echo "Hello from file B" > fileB.txt
root@ubuntu-hw:~# cd ~/task1-repo && git add fileA.txt fileB.txt
root@ubuntu-hw:~# cd ~/task1-repo && git commit -m "Initial commit: add fileA.txt and fileB.txt"
[main (root-commit) f4f08eb] Initial commit: add fileA.txt and fileB.txt
 2 files changed, 2 insertions(+)
 create mode 100644 fileA.txt
 create mode 100644 fileB.txt
root@ubuntu-hw:~# cd ~/task1-repo && git log --oneline
f4f08eb Initial commit: add fileA.txt and fileB.txt

# ==== Modify a TRACKED file, and create a NEW UNTRACKED file ====
root@ubuntu-hw:~# cd ~/task1-repo && echo "A second line added to fileA" >> fileA.txt
root@ubuntu-hw:~# cd ~/task1-repo && echo "This is a brand new file" > fileC.txt
root@ubuntu-hw:~# cd ~/task1-repo && git status
On branch main
Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   fileA.txt

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	fileC.txt

no changes added to commit (use "git add" and/or "git commit -a")

# ==== Attempt 1: plain "git commit -m" with NOTHING staged ====
root@ubuntu-hw:~# cd ~/task1-repo && git commit -m "Attempt with plain commit -m, nothing staged"
On branch main
Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   fileA.txt

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	fileC.txt

no changes added to commit (use "git add" and/or "git commit -a")
root@ubuntu-hw:~# cd ~/task1-repo && git log --oneline
f4f08eb Initial commit: add fileA.txt and fileB.txt

# --- Nothing was committed: fileA's change and fileC are still pending ---
root@ubuntu-hw:~# cd ~/task1-repo && git status
On branch main
Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   fileA.txt

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	fileC.txt

no changes added to commit (use "git add" and/or "git commit -a")

# ==== Now use "git commit -a -m" ====
root@ubuntu-hw:~# cd ~/task1-repo && git commit -a -m "Update fileA.txt using commit -a -m"
[main 5bb8ae4] Update fileA.txt using commit -a -m
 1 file changed, 1 insertion(+)
root@ubuntu-hw:~# cd ~/task1-repo && git log --oneline
5bb8ae4 Update fileA.txt using commit -a -m
f4f08eb Initial commit: add fileA.txt and fileB.txt

# --- KEY TEACHING POINT: is the untracked file included? ---
root@ubuntu-hw:~# cd ~/task1-repo && git status
On branch main
Untracked files:
  (use "git add <file>..." to include in what will be committed)
	fileC.txt

nothing added to commit but untracked files present (use "git add" to track)
root@ubuntu-hw:~# cd ~/task1-repo && git show --stat HEAD
commit 5bb8ae45c57c585aaf6a63ab62952a5a11350a29
Author: DevOps Student <student@example.com>
Date:   Wed Sep 2 17:27:18 2026 +0000

    Update fileA.txt using commit -a -m

 fileA.txt | 1 +
 1 file changed, 1 insertion(+)

# ==== The correct way to include the NEW file ====
root@ubuntu-hw:~# cd ~/task1-repo && git add fileC.txt
root@ubuntu-hw:~# cd ~/task1-repo && git commit -m "Add fileC.txt (explicit git add + commit -m)"
[main cc373c9] Add fileC.txt (explicit git add + commit -m)
 1 file changed, 1 insertion(+)
 create mode 100644 fileC.txt
root@ubuntu-hw:~# cd ~/task1-repo && git status
On branch main
nothing to commit, working tree clean

# ==== Demonstrate the explicit two-step flow again with another tracked change ====
root@ubuntu-hw:~# cd ~/task1-repo && echo "A third line in fileB" >> fileB.txt
root@ubuntu-hw:~# cd ~/task1-repo && git status
On branch main
Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   fileB.txt

no changes added to commit (use "git add" and/or "git commit -a")
root@ubuntu-hw:~# cd ~/task1-repo && git add fileB.txt
root@ubuntu-hw:~# cd ~/task1-repo && git commit -m "Update fileB.txt (explicit git add + commit -m)"
[main 662e22b] Update fileB.txt (explicit git add + commit -m)
 1 file changed, 1 insertion(+)
root@ubuntu-hw:~# cd ~/task1-repo && git status
On branch main
nothing to commit, working tree clean

# ==== One more comparison: commit -a -m does NOT need git add for tracked files ====
root@ubuntu-hw:~# cd ~/task1-repo && echo "A fourth line in fileA" >> fileA.txt
root@ubuntu-hw:~# cd ~/task1-repo && git status
On branch main
Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   fileA.txt

no changes added to commit (use "git add" and/or "git commit -a")
root@ubuntu-hw:~# cd ~/task1-repo && git commit -a -m "Update fileA.txt again using commit -a -m (no git add needed)"
[main 39a5610] Update fileA.txt again using commit -a -m (no git add needed)
 1 file changed, 1 insertion(+)
root@ubuntu-hw:~# cd ~/task1-repo && git status
On branch main
nothing to commit, working tree clean

# ==== Bonus: does commit -a also pick up DELETED tracked files? ====
root@ubuntu-hw:~# cd ~/task1-repo && rm fileC.txt
root@ubuntu-hw:~# cd ~/task1-repo && git status
On branch main
Changes not staged for commit:
  (use "git add/rm <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	deleted:    fileC.txt

no changes added to commit (use "git add" and/or "git commit -a")
root@ubuntu-hw:~# cd ~/task1-repo && git commit -a -m "Delete fileC.txt using commit -a -m"
[main 4d4078c] Delete fileC.txt using commit -a -m
 1 file changed, 1 deletion(-)
 delete mode 100644 fileC.txt
root@ubuntu-hw:~# cd ~/task1-repo && git status
On branch main
nothing to commit, working tree clean
root@ubuntu-hw:~# cd ~/task1-repo && git show --stat HEAD
commit 4d4078c3f3939e33ef2c5554179575b443deefa9
Author: DevOps Student <student@example.com>
Date:   Wed Sep 2 17:27:19 2026 +0000

    Delete fileC.txt using commit -a -m

 fileC.txt | 1 -
 1 file changed, 1 deletion(-)

# ==== Final proof: exactly which files landed in which commit ====
root@ubuntu-hw:~# cd ~/task1-repo && git log --oneline --stat
4d4078c Delete fileC.txt using commit -a -m
 fileC.txt | 1 -
 1 file changed, 1 deletion(-)
39a5610 Update fileA.txt again using commit -a -m (no git add needed)
 fileA.txt | 1 +
 1 file changed, 1 insertion(+)
662e22b Update fileB.txt (explicit git add + commit -m)
 fileB.txt | 1 +
 1 file changed, 1 insertion(+)
cc373c9 Add fileC.txt (explicit git add + commit -m)
 fileC.txt | 1 +
 1 file changed, 1 insertion(+)
5bb8ae4 Update fileA.txt using commit -a -m
 fileA.txt | 1 +
 1 file changed, 1 insertion(+)
f4f08eb Initial commit: add fileA.txt and fileB.txt
 fileA.txt | 1 +
 fileB.txt | 1 +
 2 files changed, 2 insertions(+)
```
