#!/bin/bash

# Function to create project structure
create_cpp_project() {
    local project_name=$1

    # Create project directory
    mkdir -p "$project_name"
    cd "$project_name" || return

    # Create standard directory structure
    mkdir -p src include test build

    # Create main CMakeLists.txt
    cat >CMakeLists.txt <<'EOL'
cmake_minimum_required(VERSION 3.10)

# Set project name and version
project(ProjectName VERSION 1.0)

# Specify C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Add subdirectories
add_subdirectory(src)

# Enable testing
enable_testing()
add_subdirectory(test)
EOL

    # Create src/CMakeLists.txt
    cat >src/CMakeLists.txt <<'EOL'
add_library(ProjectLib
    # Add your source files here
    example.cpp
)

target_include_directories(ProjectLib
    PUBLIC
        ${PROJECT_SOURCE_DIR}/include
)

add_executable(${PROJECT_NAME} main.cpp)
target_link_libraries(${PROJECT_NAME} PRIVATE ProjectLib)
EOL

    # Create test/CMakeLists.txt
    cat >test/CMakeLists.txt <<'EOL'
add_executable(unit_tests test_main.cpp)
target_link_libraries(unit_tests PRIVATE ProjectLib)
add_test(NAME unit_tests COMMAND unit_tests)
EOL

    # Create example source files
    cat >src/main.cpp <<'EOL'
#include "example.hpp"
#include <iostream>

int main() {
    std::cout << "Hello from " << project_name() << "!\n";
    return 0;
}
EOL

    cat >src/example.cpp <<'EOL'
#include "example.hpp"

std::string project_name() {
    return "ProjectName";
}
EOL

    cat >include/example.hpp <<'EOL'
#ifndef EXAMPLE_HPP
#define EXAMPLE_HPP

#include <string>

std::string project_name();

#endif // EXAMPLE_HPP
EOL

    cat >test/test_main.cpp <<'EOL'
#include "example.hpp"
#include <cassert>

int main() {
    assert(project_name() == "ProjectName");
    return 0;
}
EOL

    # Create .gitignore
    cat >.gitignore <<'EOL'
build/
*.o
*.a
*.so
*.exe
.vscode/
.idea/
cmake-build-*/
EOL

    # Initialize git repository
    git init

    echo "Project $project_name created successfully!"
    echo "To build your project:"
    echo "1. cd build"
    echo "2. cmake .."
    echo "3. cmake --build ."
}

# Usage
# ./cpp-init.sh my_project
if [ $# -eq 0 ]; then
    echo "Usage: $0 project_name"
    exit 1
fi

create_cpp_project "$1"
