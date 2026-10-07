# Dotfile Helper Vocabulary

## Language

**Sorted listing family**:
The related `ls-by-size`, `ls-by-name`, `ls-by-time`, and `ls-by-extension` commands for ordering directory entries, together with `ls-tree`, `ls-dirs`, and `ls-files` for structural and filtered views.

**Listing time**:
The last modification time of an entry, used by `ls-by-time`.
_Avoid_: Creation time, access time

**Automatic listing paging**:
A listing view that stays directly visible when it fits on one terminal screen and allows navigation when it exceeds that screen.

**Directory picker recency**:
The last modification time of the directory itself. Changes to entries directly inside it can update this time; editing an existing file's contents need not.
_Avoid_: Creation time, newest descendant modification

**Directory picker name**:
The directory's own name, excluding ancestor paths and descriptive attributes displayed alongside it.

**Directory picker metadata**:
Descriptive attributes shown alongside a directory's name to help choose it, separate from the name used for searching.
