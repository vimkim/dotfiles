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

These are proposed working rules implementing the user's preferences, rather
than requirements imposed by Git:

1. For a task that changes repository files, inspect existing worktrees and
   changes, then create or reuse its topic branch in a sibling directory such
   as `../chezmoi-task-name`. Start new independent tasks from `main`.
2. Do the work and focused verification there. Preserve unrelated user changes
   in every checkout; a new worktree is not permission to reset or clean the
   original checkout.
3. Commit all intended task changes before requesting review. Report the
   worktree, branch, commit, validation, and any limitations. Commit subsequent
   review fixes before asking for review again.
4. At normal handoff, leave no staged changes, tracked modifications, or
   non-ignored untracked files in the task worktree. Grilling sessions and
   errors are the user's exceptions; explain unfinished work when an error
   prevents completion. This is a handoff requirement, not a demand to commit
   after every individual edit.
5. Put narrowly scoped patterns for disposable generated outputs in
   `.gitignore`, and commit those patterns. Keep requested deliverables tracked;
   do not conceal unfinished source changes or user files with ignore rules.
6. Wait for the user's explicit approval of the current committed work before
   merging into `main`. Approval to merge is separate from permission to push
   or deploy dotfiles.
7. After a successful merge, remove the merged task worktree and local topic
   branch as part of completion. Verify the entire branch tip was merged and
   inspect uncommitted and ignored files first; preserve valuable files and
   report blocked cleanup instead of forcing removal. Remote branch deletion
   requires explicit authorization for that remote action.

For verification, `git status --porcelain=v1 --untracked-files=all` exposes both
tracked changes and individual untracked files; ignored outputs are omitted
unless requested. `.gitignore` applies to intentionally untracked files and
does not hide changes to already tracked files.
[Git: git-status](https://git-scm.com/docs/git-status),
[Git: gitignore](https://git-scm.com/docs/gitignore)

## Merge choices and safeguards

`git merge --ff-only <approved-commit>` moves `main` to the reviewed commit
without another commit and refuses divergent history. `--no-ff` creates a merge
commit, retaining an explicit integration point but adding history. Ordinary
`git merge` may choose either behavior. [Git: git-merge](https://git-scm.com/docs/git-merge)

Recommended default: fast-forward only. If `main` has advanced incompatibly,
integrate it in the task branch, resolve conflicts, verify and commit the result,
then obtain approval for that updated result. This keeps review attached to the
actual result instead of silently broadening what the user approved. GitHub
also supports dismissing approvals when the reviewed diff changes, although
that hosted setting is optional and does not enforce local conversation review.
[GitHub: About protected branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)

Perform integration in the worktree holding `main`, after checking that it is
clean. Git normally rejects checking out the same branch in another worktree.
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
