#!/usr/bin/env bash

# Detects project type: Rust, Go, Python, or C/C++ (CMake)
detect_project_type() {
    if [ -f "Cargo.toml" ]; then
        echo "rust"
    elif [ -f "go.mod" ] || [ -f "main.go" ] || find . -name "*.go" | grep -q .; then
        echo "go"
    elif [ -f "CMakeLists.txt" ] ; then
        echo "cmake"
    elif [ -f "Makefile" ] ; then
        echo "make"
    elif find . -name "*.cpp" | grep -q .; then
        echo "cpp"
    elif find . -name "*.c" | grep -q .; then
        echo "c"
    elif [ -f "requirements.txt" ] || [ -f "pyproject.toml" ] || find . -name "*.py" | grep -q .; then
        echo "python"
    else
        echo "Unknown project type"
    fi
}

detect_project_type
