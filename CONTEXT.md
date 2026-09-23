# Dotfiles

This repository defines the source state for personal tools and configuration deployed through chezmoi.

## Language

**Project Candidate**:
A visible, non-ignored directory between one level and the configured maximum depth beneath a search root. It does not need a project marker or version-control metadata, and discovery does not follow directory symlinks.
_Avoid_: Repository, Git repository

**Search Root**:
An explicit top-level directory beneath which project candidates are discovered. The default roots are `~/gh`, `~/temp`, and `~/tmp`; `FIND_PROJECT_ROOTS` replaces them.
_Avoid_: Project directory
