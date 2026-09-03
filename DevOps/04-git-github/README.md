# Git / GitHub — Homework

Both tasks below were performed in throwaway local repositories. Every block is
**real captured terminal output**.

---

## Task 1 — `git commit -m` vs `git commit -a -m`

### The concept: Git's three areas

```
  Working Directory  ->  Staging Area (Index)  ->  Repository (.git)
       your edits           git add                  git commit
```

A normal commit only ever records **what is in the staging area**. `git add`
moves changes into it; `git commit` writes it into history. This two-step design
is deliberate — it lets you commit *some* of your edits and leave the rest.

### What `-a` actually does

`-a` (short for `--all`) tells Git: *"before committing, automatically stage
every modified or deleted file that is **already tracked**."* It is a shortcut
for `git add -u` followed by `git commit`.

### The difference in one table

| | `git commit -m "msg"` | `git commit -a -m "msg"` |
|---|---|---|
| Commits staged changes | Yes | Yes |
| Auto-stages **modified tracked** files | **No** | **Yes** |
| Auto-stages **deleted tracked** files | **No** | **Yes** |
| Auto-stages **new/untracked** files | **No** | **No** — still needs `git add` |
| Typical use | Precise, selective commits | Quick "commit everything I changed" |
| Risk | None | Can sweep in edits you meant to keep back |

> **The one thing to remember:** `-a` means "all **tracked** files", **not**
> "all files". A brand new file is invisible to `-a` until you `git add` it once.

### Session

```console
====================================================================
 TASK 1: git commit -m   VS   git commit -a -m
====================================================================
$ git init -q -b main task1-demo

$ cd task1-demo && git config user.name 'astro-dude' && git config user.email 'sagittariusshaurya5@gmail.com' && echo 'repo ready on branch main'
repo ready on branch main

$ echo 'version 1' > file.txt

$ git add file.txt

$ git commit -q -m 'Initial commit' && git log --oneline
0766b1f Initial commit

--------------------------------------------------------------------
 SCENARIO A: modify a TRACKED file, then use plain 'git commit -m'
--------------------------------------------------------------------
$ echo 'version 2' > file.txt

$ git status --short
 M file.txt

--- 'M ' in column 1 = staged, ' M' in column 2 = modified but NOT staged
$ git commit -m 'Try to commit without staging'
On branch main
Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
	modified:   file.txt

no changes added to commit (use "git add" and/or "git commit -a")

--- ^ NOTHING was committed. Git refused because nothing is in the staging area.
$ git log --oneline
0766b1f Initial commit

--------------------------------------------------------------------
 SCENARIO B: same change, but now with 'git commit -a -m'
--------------------------------------------------------------------
$ git status --short
 M file.txt

$ git commit -a -m 'Commit tracked change with -a'
[main fb0278a] Commit tracked change with -a
 1 file changed, 1 insertion(+), 1 deletion(-)

$ git log --oneline
fb0278a Commit tracked change with -a
0766b1f Initial commit

$ git status --short

--- ^ working tree is clean: -a staged and committed the tracked file in one step
--------------------------------------------------------------------
 SCENARIO C: the CRITICAL limitation - -a IGNORES UNTRACKED files
--------------------------------------------------------------------
$ echo 'brand new file' > untracked.txt

$ echo 'version 3' > file.txt

$ git status --short
 M file.txt
?? untracked.txt

--- '??' means untracked. 'file.txt' is tracked and modified.
$ git commit -a -m 'Attempt to commit both files with -a'
[main 033633c] Attempt to commit both files with -a
 1 file changed, 1 insertion(+), 1 deletion(-)

$ git show --stat --oneline HEAD
033633c Attempt to commit both files with -a
 file.txt | 2 +-
 1 file changed, 1 insertion(+), 1 deletion(-)

--- ^ ONLY file.txt was committed. untracked.txt was silently skipped.
$ git status --short
?? untracked.txt

--- ^ untracked.txt is STILL sitting there uncommitted.
--------------------------------------------------------------------
 SCENARIO D: untracked files need an explicit 'git add'
--------------------------------------------------------------------
$ git add untracked.txt

$ git status --short
A  untracked.txt

$ git commit -m 'Add the new file after explicitly staging it'
[main 056e7bf] Add the new file after explicitly staging it
 1 file changed, 1 insertion(+)
 create mode 100644 untracked.txt

$ git status
On branch main
nothing to commit, working tree clean

$ git log --oneline
056e7bf Add the new file after explicitly staging it
033633c Attempt to commit both files with -a
fb0278a Commit tracked change with -a
0766b1f Initial commit

--------------------------------------------------------------------
 SCENARIO E: -a also picks up DELETIONS of tracked files
--------------------------------------------------------------------
$ rm untracked.txt

$ git status --short
 D untracked.txt

$ git commit -a -m 'Delete a tracked file using -a'
[main 5ea7d24] Delete a tracked file using -a
 1 file changed, 1 deletion(-)
 delete mode 100644 untracked.txt

$ git show --stat --oneline HEAD
5ea7d24 Delete a tracked file using -a
 untracked.txt | 1 -
 1 file changed, 1 deletion(-)

$ git log --oneline
5ea7d24 Delete a tracked file using -a
056e7bf Add the new file after explicitly staging it
033633c Attempt to commit both files with -a
fb0278a Commit tracked change with -a
0766b1f Initial commit

```

### What the output proves

- **Scenario A** — `file.txt` was modified but not staged. Plain `git commit -m`
  refused: *"no changes added to commit (use "git add" and/or "git commit -a")"*.
  `git log` was unchanged — **no commit was created**. Git's own error message
  literally points at the two solutions.
- **Scenario B** — the identical change with `git commit -a -m` succeeded
  immediately: `1 file changed, 1 insertion(+), 1 deletion(-)`, and
  `git status` went clean. One step instead of two.
- **Scenario C is the important one.** With *both* a modified tracked file and a
  new untracked file present, `git commit -a -m` committed **only `file.txt`**.
  `git show --stat` confirms a single file in the commit, and `git status`
  still shows `?? untracked.txt` afterwards. **`-a` silently skipped it** — no
  warning, no error. This is exactly how people lose a new file out of a commit
  and don't notice until CI fails.
- **Scenario D** — `git add untracked.txt` changed its status from `??` to
  `A `, and only then did it get committed (`create mode 100644 untracked.txt`).
- **Scenario E** — after `rm untracked.txt`, status showed ` D`, and
  `git commit -a` **did** pick the deletion up (`delete mode 100644`). Deletions
  of tracked files count as modifications to `-a`.

### Reading `git status --short`

Two columns: **column 1 = staging area**, **column 2 = working directory**.

| Code | Meaning |
|---|---|
| `M ` | Modified **and staged** |
| ` M` | Modified, **not staged** |
| `MM` | Staged, then modified again |
| `A ` | New file, staged |
| ` D` | Deleted, not staged |
| `??` | Untracked — invisible to `-a` |

### Interview answer

> `git commit -m` commits only what you have already staged with `git add`.
> `git commit -a -m` adds an implicit `git add -u` first, so it stages and
> commits every **tracked** file that was modified or deleted, in one step. The
> critical limitation is that `-a` does **not** pick up untracked files — a new
> file must be `git add`-ed at least once before `-a` will ever see it. I use
> `-a` for quick iteration on files Git already knows about, and plain
> `git add` + `git commit` when I want a precise, reviewable commit.

---

## Task 2 — Git Cherry-Pick

### What cherry-pick is

`git cherry-pick <hash>` takes the **diff introduced by one specific commit**
and replays it on top of your current branch, as a **new commit**.

Merge and rebase move whole branches. Cherry-pick moves **one commit**. That is
the entire distinction, and it is the reason it exists: the classic real-world
case is a **hotfix committed on a feature branch that has to reach production
now**, while the rest of that unfinished branch must stay out.

The exercise below models exactly that: three commits on a feature branch, of
which only the critical bugfix is wanted on `main`.

### Session

```console
====================================================================
 TASK 2: GIT CHERRY-PICK
====================================================================
--------------------------------------------------------------------
 STEP 1: create the repo and make 4 commits on main
--------------------------------------------------------------------
$ git init -q -b main cherry-demo

$ cd cherry-demo && git config user.name 'astro-dude' && git config user.email 'sagittariusshaurya5@gmail.com' && echo ready
ready

$ echo '# My Project' > README.md && git add . && git commit -q -m 'C1: Add README' && echo committed
committed

$ echo 'print("hello")' > app.py && git add . && git commit -q -m 'C2: Add app.py' && echo committed
committed

$ echo 'flask==3.0.0' > requirements.txt && git add . && git commit -q -m 'C3: Add requirements.txt' && echo committed
committed

$ echo 'venv/' > .gitignore && git add . && git commit -q -m 'C4: Add .gitignore' && echo committed
committed

--------------------------------------------------------------------
 STEP 2: view the commits with git log
--------------------------------------------------------------------
$ git log --oneline
e93fb6e C4: Add .gitignore
86c82e8 C3: Add requirements.txt
87ea489 C2: Add app.py
4b66bc6 C1: Add README

$ git log --oneline --graph --all
* e93fb6e C4: Add .gitignore
* 86c82e8 C3: Add requirements.txt
* 87ea489 C2: Add app.py
* 4b66bc6 C1: Add README

$ git log --pretty=format:'%h | %an | %s' -n 4
e93fb6e | astro-dude | C4: Add .gitignore
86c82e8 | astro-dude | C3: Add requirements.txt
87ea489 | astro-dude | C2: Add app.py
4b66bc6 | astro-dude | C1: Add README
--------------------------------------------------------------------
 STEP 3: create a new branch and switch to it
--------------------------------------------------------------------
$ git checkout -b feature-branch
Switched to a new branch 'feature-branch'

$ git branch
* feature-branch
  main

--------------------------------------------------------------------
 STEP 4: make 3 commits on feature-branch
--------------------------------------------------------------------
$ echo 'def login(): pass' > auth.py && git add . && git commit -q -m 'F1: Add authentication module' && echo committed
committed

$ echo 'CRITICAL BUGFIX: fix divide by zero' > bugfix.txt && git add . && git commit -q -m 'F2: Fix critical divide-by-zero bug' && echo committed
committed

$ echo 'experimental feature, not ready' > experimental.txt && git add . && git commit -q -m 'F3: Add experimental feature (NOT ready for main)' && echo committed
committed

--------------------------------------------------------------------
 STEP 5: use git log to identify the specific commit we want
--------------------------------------------------------------------
$ git log --oneline
53f298d F3: Add experimental feature (NOT ready for main)
c3b3c81 F2: Fix critical divide-by-zero bug
19a75ce F1: Add authentication module
e93fb6e C4: Add .gitignore
86c82e8 C3: Add requirements.txt
87ea489 C2: Add app.py
4b66bc6 C1: Add README

$ git log --oneline --graph --all
* 53f298d F3: Add experimental feature (NOT ready for main)
* c3b3c81 F2: Fix critical divide-by-zero bug
* 19a75ce F1: Add authentication module
* e93fb6e C4: Add .gitignore
* 86c82e8 C3: Add requirements.txt
* 87ea489 C2: Add app.py
* 4b66bc6 C1: Add README

--- We want ONLY F2 (the critical bugfix) on main.
--- We do NOT want F1 or F3 (experimental) yet.
$ git log --oneline --grep='Fix critical'
c3b3c81 F2: Fix critical divide-by-zero bug

--------------------------------------------------------------------
 STEP 6: capture that commit's hash
--------------------------------------------------------------------
$ git log --format='%H %s' | grep 'F2:'
c3b3c81fcbb63fd9a1b3ff3371e104080951ab36 F2: Fix critical divide-by-zero bug

$ BUGFIX_HASH=$(git log --format='%H' --grep='F2:')
$ echo $BUGFIX_HASH
c3b3c81fcbb63fd9a1b3ff3371e104080951ab36

$ git show --stat --oneline c3b3c81fcbb63fd9a1b3ff3371e104080951ab36
c3b3c81 F2: Fix critical divide-by-zero bug
 bugfix.txt | 1 +
 1 file changed, 1 insertion(+)

--------------------------------------------------------------------
 STEP 7: switch back to main and confirm the fix is NOT there
--------------------------------------------------------------------
$ git checkout main
Switched to branch 'main'

$ git log --oneline
e93fb6e C4: Add .gitignore
86c82e8 C3: Add requirements.txt
87ea489 C2: Add app.py
4b66bc6 C1: Add README

$ ls
README.md
app.py
requirements.txt

$ test -f bugfix.txt && echo 'bugfix.txt present' || echo 'bugfix.txt is NOT on main yet'
bugfix.txt is NOT on main yet

--------------------------------------------------------------------
 STEP 8: CHERRY-PICK the single commit onto main
--------------------------------------------------------------------
$ git cherry-pick c3b3c81fcbb63fd9a1b3ff3371e104080951ab36
[main 70efc17] F2: Fix critical divide-by-zero bug
 Date: Thu Sep 3 22:19:44 2026 +0530
 1 file changed, 1 insertion(+)
 create mode 100644 bugfix.txt

--------------------------------------------------------------------
 STEP 9: VERIFY the change is now on main
--------------------------------------------------------------------
$ git log --oneline
70efc17 F2: Fix critical divide-by-zero bug
e93fb6e C4: Add .gitignore
86c82e8 C3: Add requirements.txt
87ea489 C2: Add app.py
4b66bc6 C1: Add README

$ ls
README.md
app.py
bugfix.txt
requirements.txt

$ cat bugfix.txt
CRITICAL BUGFIX: fix divide by zero

$ test -f bugfix.txt && echo 'SUCCESS: bugfix.txt is now on main'
SUCCESS: bugfix.txt is now on main

--- confirm we did NOT drag along F1 or F3:
$ test -f auth.py && echo 'auth.py present (WRONG)' || echo 'auth.py absent - correct, F1 was not picked'
auth.py absent - correct, F1 was not picked

$ test -f experimental.txt && echo 'experimental.txt present (WRONG)' || echo 'experimental.txt absent - correct, F3 was not picked'
experimental.txt absent - correct, F3 was not picked

--------------------------------------------------------------------
 STEP 10: the resulting history - note the NEW hash for the same change
--------------------------------------------------------------------
$ git log --oneline --graph --all
* 70efc17 F2: Fix critical divide-by-zero bug
| * 53f298d F3: Add experimental feature (NOT ready for main)
| * c3b3c81 F2: Fix critical divide-by-zero bug
| * 19a75ce F1: Add authentication module
|/  
* e93fb6e C4: Add .gitignore
* 86c82e8 C3: Add requirements.txt
* 87ea489 C2: Add app.py
* 4b66bc6 C1: Add README

$ git log --format='%h | %s' -n 2
70efc17 | F2: Fix critical divide-by-zero bug
e93fb6e | C4: Add .gitignore

--- The cherry-picked commit has a DIFFERENT hash from c3b3c81fcbb63fd9a1b3ff3371e104080951ab36
--- ...but the SAME content. Compare the patches:
$ git show c3b3c81fcbb63fd9a1b3ff3371e104080951ab36 --format='' --stat
 bugfix.txt | 1 +
 1 file changed, 1 insertion(+)

$ git show main --format='' --stat
 bugfix.txt | 1 +
 1 file changed, 1 insertion(+)

$ git branch -v
  feature-branch 53f298d F3: Add experimental feature (NOT ready for main)
* main           70efc17 F2: Fix critical divide-by-zero bug

```

### What the output proves

**The history before the cherry-pick** (Step 5) — one straight line, because
`feature-branch` was created from the tip of `main`:

```
* 53f298d F3: Add experimental feature (NOT ready for main)
* c3b3c81 F2: Fix critical divide-by-zero bug        <-- we want ONLY this one
* 19a75ce F1: Add authentication module
* e93fb6e C4: Add .gitignore
* 86c82e8 C3: Add requirements.txt
* 87ea489 C2: Add app.py
* 4b66bc6 C1: Add README
```

**The history after** (Step 10) — the branches have visibly diverged, and the
same change now exists in two places under two different hashes:

```
* 70efc17 F2: Fix critical divide-by-zero bug        <-- main: the cherry-picked copy
| * 53f298d F3: Add experimental feature (NOT ready for main)
| * c3b3c81 F2: Fix critical divide-by-zero bug      <-- feature-branch: the original
| * 19a75ce F1: Add authentication module
|/
* e93fb6e C4: Add .gitignore
...
```

Three things this confirms:

1. **The change arrived on `main`.** `bugfix.txt` exists and contains
   `CRITICAL BUGFIX: fix divide by zero`, and `git log` on `main` shows the F2
   commit sitting directly on top of C4.
2. **Nothing else came with it.** `auth.py` (F1) and `experimental.txt` (F3) are
   both **absent** from `main` — verified explicitly with `test -f`. Only the
   one selected commit was transplanted.
3. **The hash changed: `c3b3c81` → `70efc17`.** This is the single most
   important detail about cherry-pick. A commit's hash is derived from its
   content *plus its parent and metadata*. Replaying the same diff onto a
   different parent necessarily produces a different hash — so it is a **copy,
   not a move**. The original commit is still on `feature-branch`, untouched.
   `git show --stat` on both hashes returns the identical
   `bugfix.txt | 1 +`, proving same content, different identity.

### Command reference

| Goal | Command |
|---|---|
| Pick one commit | `git cherry-pick <hash>` |
| Pick several | `git cherry-pick <h1> <h2> <h3>` |
| Pick an inclusive range | `git cherry-pick A^..B` |
| Stage the change but don't commit | `git cherry-pick -n <hash>` |
| Append the source hash to the message | `git cherry-pick -x <hash>` |
| Edit the message while picking | `git cherry-pick -e <hash>` |
| **On conflict:** resolve, then | `git add . && git cherry-pick --continue` |
| **Abort and restore** | `git cherry-pick --abort` |
| Skip the current commit | `git cherry-pick --skip` |
| Find the hash by message | `git log --oneline --grep='text'` |
| See which commits are *not* upstream | `git cherry -v main feature-branch` |

> **`-x` is worth a habit.** It appends
> `(cherry picked from commit c3b3c81...)` to the message, so six months later
> the audit trail back to the original still exists. Recommended whenever you
> pick into a release or production branch.

### Cherry-pick vs merge vs rebase

| | Brings across | History shape | Use when |
|---|---|---|---|
| `merge` | **All** commits of a branch | Preserved, adds a merge commit | Integrating finished work |
| `rebase` | All commits, replayed | Linearised, all hashes change | Tidying a branch before a PR |
| `cherry-pick` | **One (or a few) chosen commits** | New copies on the target | Hotfix or backport out of order |

### Cautions

- **Duplicate commits.** The same change now exists twice. If `feature-branch`
  is later merged into `main`, Git usually notices the identical patch and
  handles it, but it can also surface as a conflict. Cherry-picking *then*
  merging the same branch is the usual cause of "why is this conflicting with
  itself?"
- **Conflicts happen** when the target branch has drifted. Resolve exactly as
  with a merge, then `git cherry-pick --continue`.
- **Dependencies are not followed.** If F2 relied on something introduced in
  F1, cherry-picking F2 alone gives you code that compiles nowhere. Cherry-pick
  assumes the commit is self-contained — always test the result.
- **Don't use it as a substitute for merging.** Routinely cherry-picking
  instead of merging produces a history nobody can reason about.

### Interview answer

> Cherry-pick copies the diff of one specific commit onto the current branch as
> a brand new commit with a new hash. I reach for it when a fix that lives on an
> unfinished branch is needed on `main` or a release branch immediately, and the
> rest of that branch isn't ready to ship. The gotchas are that it duplicates
> the change rather than moving it, so the same work exists under two hashes,
> and that it doesn't bring across any commits the picked one depends on. I use
> `-x` so the new commit records where it was picked from.

---

## Submission summary

| Task | Requirement | Status |
|---|---|---|
| 1 | Practise `git commit -a -m "message"` | Done — Scenarios B, C, E |
| 1 | Understand the difference vs `git commit -m` | Done — table + Scenarios A–E |
| 1 | Test both and observe the difference | Done — A refused, B succeeded |
| 2 | Create 2–4 commits on main | Done — **4** (C1–C4) |
| 2 | Use `git log` to view the commits | Done — `--oneline`, `--graph`, `--pretty=format` |
| 2 | Create a new branch | Done — `feature-branch` |
| 2 | Make 2–3 commits on the new branch | Done — **3** (F1–F3) |
| 2 | Use `git log` to identify a specific commit | Done — located `c3b3c81` via `--grep` |
| 2 | Cherry-pick that commit into main | Done — `git cherry-pick c3b3c81` |
| 2 | Verify the change is on main | Done — file present, F1/F3 confirmed absent |
| — | Submit `.md` file with commands and output | This file |
