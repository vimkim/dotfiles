_default:
    just --choose -f {{ justfile() }} -d  {{ invocation_directory() }}

hello:
    echo "hello from rust just!"

add:
    cargo add $(gum input)

tests:
    cargo test --all

build:
    cargo build

run:
    cargo run -- -E

run-hello:
    echo "hello world" | cargo run -- -E 'hello'

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
