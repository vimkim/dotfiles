_default:
    just --choose -f {{ justfile() }} -d  {{ invocation_directory() }}

hello:
    echo "hello from rust just!"

prepare:
    echo '' > .envrc
    echo 'export RUST_BACKTRACE="full"' >> .envrc
    direnv allow

cargo-add:
    cargo add $(gum input)

test:
    cargo test

test-ignored:
    cargo test -- --ignored

build:
    cargo build

binary-name := `cargo metadata --format-version 1 | jq -r '.packages[].targets[] | select( .kind | map(. == "bin") | any ) | select ( .src_path | contains(".cargo/registry") | . != true ) | .name'`

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
