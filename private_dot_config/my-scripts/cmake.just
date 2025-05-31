set shell := ["nu", "-c"]

prepare:
    ln -s ~/.config/my-scripts/cmake/envrc.sh .envrc

configure:
    cmake --preset $env.PRESET_MODE

cmake-preset-mode-select:
    ~/.config/my-scripts/bin/cmake-preset-mode-select.sh

configure-build: configure build

build: cmake-build-install-all

cmake-build-install-all:
    cmake --build --preset $env.PRESET_MODE --target install

build-debug:
    cmake --build --preset mydebug --target install

build-profile:
    cmake --build --preset myprofile --target install
