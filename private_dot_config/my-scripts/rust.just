_default:
    just --choose -f {{ justfile() }} -d  {{ invocation_directory() }}

hello:
    echo "hello from rust just!"

prepare:
    echo '' > .envrc
    echo 'export RUST_BACKTRACE="full"' >> .envrc
    direnv allow

example-fzf:
    ~/.config/my-scripts/bin/cargo-run-example.sh

cargo-add:
    cargo add $(gum input)

test:
    cargo test

test-list:
    ^cargo test -- --list

test-fzf:
    cargo test $"(^cargo test -- --list | complete | get stdout | rg 'test$' | fzf | awk -F': test' '{print $1}')"

test-ignored:
    cargo test -- --ignored

build:
    cargo build

binary-name := '(open Cargo.toml | get package.name)'

run-debug:
    cargo run

run-release:
    cargo run --release

@bench:
    cargo bench

@lint:
    rustup component add clippy
    rustup component add rustfmt
    cargo clippy -- -D warnings
    cargo clippy --tests
    cargo fmt -- --check

@fix:
    cargo fmt --all

clean:
    cargo clean
    find . -type f -name "*.orig" -exec rm {} \;
    find . -type f -name "*.bk" -exec rm {} \;
    find . -type f -name ".*~" -exec rm {} \;

build-for-uftrace:
    export RUSTFLAGS="-Z instrument-mcount -C passes=ee-instrument<post-inline>"
    export RUST_TRACE="full"
    cargo build

check-for-uftrace:
    nm ./target/debug/{{ binary-name }} | grep mcount

debug-cgdb:
    cgdb -d rust-gdb ./target/debug/{{ binary-name }}

rr-record:
    rr record ./target/debug/{{ binary-name }}

rr-replay:
    rr replay -s 50505 -k

rr-attach:
    cgdb -d rust-gdb -l 10000 -ex 'set sysroot /' -ex 'target extended-remote 127.0.0.1:50505' /home/dkubnt/.local/share/rr/slotted_page_rs-1/mmap_hardlink_4_slotted_page_rs
