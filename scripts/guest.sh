#!/usr/bin/env bash
set -eo pipefail
export IDF_TOOLS_PATH=/opt/esp/tools-v5.5.6
export IDF_PY_BUILD_JOBS=${IDF_PY_BUILD_JOBS:-2}
. /opt/esp/esp-idf-v5.5.6/export.sh
mode=${1:?}; name=${2:-}; chip=${3:-}; shift 3
cd /work/projects
if [[ -n $name ]]; then
    [[ $name =~ ^[a-z][a-z0-9_-]{0,47}$ ]] || exit 2
    cd -- "$name"
fi
case "$mode" in
    doctor) uname -m; python --version; xtensa-esp-elf-gcc --version; idf.py --version ;;
    shell) exec /bin/bash --noprofile --norc ;;
    edit) exec nano main/main.c ;;
    config) exec idf.py -B build-android -DIDF_TARGET="$chip" menuconfig ;;
    build|size) exec idf.py -B build-android -DIDF_TARGET="$chip" "$mode" ;;
    export)
        idf.py -B build-android -DIDF_TARGET="$chip" merge-bin
        echo "Imagem: /work/projects/$name/build-android/merged-binary.bin; offset 0x0. A imagem completa pode sobrescrever NVS."
        ;;
    probe|flash)
        serial=(python -m esptool --chip "$chip" --port socket://127.0.0.1:3333 --baud 115200 --before no_reset --after no_reset --no-stub)
        if [[ $mode == probe ]]; then exec "${serial[@]}" flash_id; fi
        cd build-android
        exec "${serial[@]}" write_flash "$@"
        ;;
    *) echo 'Ação desconhecida' >&2; exit 2 ;;
esac
