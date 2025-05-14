#!/usr/bin/env bash

# Detects project type: Rust, Go, Python, or C/C++ (CMake)
detect_project_type() {
    if [ -f "Cargo.toml" ]; then
        echo "rust"
    elif [ -f "go.mod" ] || [ -f "main.go" ] || find . -name "*.go" | grep -q .; then
        echo "go"
    elif [ -f "requirements.txt" ] || [ -f "pyproject.toml" ] || find . -name "*.py" | grep -q .; then
        echo "python"
    elif [ -f "CMakeLists.txt" ] || find . -name "*.c" -o -name "*.cpp" | grep -q .; then
        echo "cmake"
    else
        echo "Unknown project type"
    fi
}

detect_project_type
