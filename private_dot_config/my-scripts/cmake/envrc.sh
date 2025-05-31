# .envrc

# Check if PRESET_MODE is set; if not, print a warning and set a default value
if [ -z "$PRESET_MODE" ]; then
    echo "#################################################################"
    echo "############### Warning: PRESET_MODE is not set. ################"
    echo "#################################################################"
    export PRESET_MODE="############################# WARNING ############################"
    return
fi

export CURRENT_DIR=${PWD##*/}
MY_INSTALL_DIR="$(pwd)/install_$PRESET_MODE"
MY_BUILD_DIR="$(pwd)/build_$PRESET_MODE"
export MY_INSTALL_DIR
export MY_BUILD_DIR

ln -sf build_preset_"$PRESET_MODE"/compile_commands.json .

echo "Preset Mode: $PRESET_MODE"
echo "Install Dir: $MY_INSTALL_DIR"
echo "Build Dir: $MY_BUILD_DIR"

export ASAN_OPTIONS=halt_on_error=0:log_path=./asan.log
export LSAN_OPTIONS=halt_on_error=0:log_path=./lsan.log

export CLICOLOR_FORCE=1
