# Worktree workflow with review before merge

Researched on 2026-09-30 against primary Git and GitHub documentation.

## What to call it

**A topic-branch workflow using Git worktrees, with review before merge** is the
precise description. Git calls a branch for one feature or related task a
*topic branch*. [Git: Branching Workflows](https://git-scm.com/book/en/v2/Git-Branching-Branching-Workflows)

The additional checkout is a *linked worktree*. Git explicitly supports sibling
paths such as `../hotfix`; worktrees share a repository while allowing different
branches to be checked out simultaneously. [Git: git-worktree](https://git-scm.com/docs/git-worktree)

The closest named collaboration model is **GitHub flow**: branch, make commits,
request review, address feedback, and merge after approval. Calling this a local
adaptation of GitHub flow is our interpretation: the requested workflow uses
conversation review and local commits, so it need not create or push a GitHub
pull request. [GitHub: GitHub flow](https://docs.github.com/en/get-started/using-github/github-flow)

It does not require the release-management structure of **Gitflow**, whose
original model uses persistent `master` and `develop` branches plus feature,
release, and hotfix branches. [Vincent Driessen: A successful Git branching model](https://nvie.com/posts/a-successful-git-branching-model/)

## Recommended policy for this user's agents

These working rules implement the user's preferences, rather than requirements
imposed by Git. The authoritative agent policy is
[`dot_codex/AGENTS.md`](../dot_codex/AGENTS.md).

1. Inspect the current branch, existing worktrees, and changes. When starting
   on `main`, `develop`, or `feature/*`, create or reuse a sibling task worktree
   with a separate topic branch based on the starting branch; merge back into
   that starting branch. On any other named branch, work directly in the
   current checkout without creating another worktree. Use the repository's
   documented or agreed destination for later integration of an existing
   topic branch.
2. Do the work and focused verification there. Preserve unrelated user changes
   in every checkout; a new worktree is not permission to reset or clean the
   original checkout.
3. Commit all intended task changes before requesting review. Report the
   worktree, branch, commit, validation, and any limitations. Commit subsequent
   review fixes before asking for review again.
4. At normal handoff, leave all task changes committed and report unrelated
   dirt without altering it. Grilling sessions and errors are the user's
   exceptions; explain unfinished work when an error prevents completion.
   This is a handoff requirement, not a demand to commit after every edit.
5. Put narrowly scoped patterns for disposable generated outputs in
   `.gitignore`, and commit those patterns. Keep requested deliverables tracked;
   do not conceal unfinished source changes or user files with ignore rules.
6. Obtain one approval of the committed work for rebase onto the current local
   destination branch and local fast-forward merge. Push and dotfile deployment
   each require separate explicit requests.
7. After every successful rebase and fast-forward merge, remove any merged
   linked task worktree and safely delete the local topic branch as part of
   completion. This includes task worktrees reused from earlier sessions.
   Verify the entire branch tip was merged and inspect uncommitted and ignored
   files first; preserve valuable files and report blocked cleanup instead of
   forcing removal. Remote branch deletion requires explicit authorization.

For verification, `git status --porcelain=v1 --untracked-files=all` exposes both
tracked changes and individual untracked files; ignored outputs are omitted
unless requested. `.gitignore` applies to intentionally untracked files and
does not hide changes to already tracked files.
[Git: git-status](https://git-scm.com/docs/git-status),
[Git: gitignore](https://git-scm.com/docs/gitignore)

## Merge choices and safeguards

`git merge --ff-only <approved-commit>` moves the destination to the reviewed commit
without another commit and refuses divergent history. `--no-ff` creates a merge
commit, retaining an explicit integration point but adding history. Ordinary
`git merge` may choose either behavior. [Git: git-merge](https://git-scm.com/docs/git-merge)

Required local policy: fast-forward only. After approval, rebase onto the current
destination branch, resolve conflicts, inspect the resulting diff, and run
proportionate checks. The same approval covers confident conflict resolution
and another rebase if the destination advances; ask again only if uncertain
about the result or a failure's impact, and report understood failures. GitHub
also supports dismissing approvals when the reviewed diff changes, although
that hosted setting does not enforce local conversation review.
[GitHub: About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)

Perform integration in the checkout holding the destination branch, after
checking that it is clean and on the expected branch. Git normally rejects
checking out the same branch in another worktree.
Do not bypass this with `--force`. [Git: git-worktree](https://git-scm.com/docs/git-worktree)

If the destination contains user changes, preserve them and report the obstacle;
do not auto-stash, reset, or commit them merely to merge. Git warns that aborting
a merge started with uncommitted changes may not restore those changes fully.
[Git: git-merge](https://git-scm.com/docs/git-merge)

For local cleanup, run `git worktree remove <task-worktree>` from outside the
worktree, then `git branch -d <task-branch>`. Git provides these commands for
removing linked worktrees and safely deleting merged branches.
[Git: git-worktree](https://git-scm.com/docs/git-worktree),
[Git: git-branch](https://git-scm.com/docs/git-branch)
