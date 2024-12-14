_default:
    @just --choose -f {{ justfile() }} -d  {{ invocation_directory() }}

rust:
    $CHEZ_EDITOR $MY_SCRIPTS/rust.just

edit:
    $CHEZ_EDITOR $MY_SCRIPTS/edit.just
