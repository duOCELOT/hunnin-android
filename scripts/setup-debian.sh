#!/usr/bin/env bash
set -eo pipefail
[[ $(uname -m) == aarch64 && ( -f /root/.huninn-android-managed || -f /root/.huninn-idf-managed ) ]] || { echo 'Execute install.sh no Termux.' >&2; exit 1; }
retry() {
    local attempt
    for attempt in 1 2 3; do
        if "$@"; then return 0; fi
        echo "Falha na tentativa $attempt/3; downloads já concluídos serão reutilizados." >&2
        [[ $attempt == 3 ]] || sleep 2
    done
    return 1
}
export DEBIAN_FRONTEND=noninteractive
retry apt-get update
retry apt-get install -y ca-certificates git wget flex bison gperf python3 python3-pip python3-venv cmake ninja-build ccache libffi-dev libssl-dev dfu-util libusb-1.0-0 build-essential pkg-config unzip xz-utils nano
sdk=/opt/esp/esp-idf-v5.5.6
commit=880a203ae603d08a94d06aa01e0d6761958e5e9e
mkdir -p /opt/esp
clone_sdk() {
    local staging
    staging=$(mktemp -d /opt/esp/.huninn-sdk-download.XXXXXX)
    if git clone --branch v5.5.6 --depth 1 https://github.com/espressif/esp-idf.git "$staging"; then
        mv "$staging" "$sdk"
    else
        rm -rf -- "$staging"  # Only this invocation's temporary clone, never an existing SDK.
        return 1
    fi
}
[[ -e $sdk ]] || retry clone_sdk
[[ -d $sdk/.git && $(git -C "$sdk" rev-parse HEAD) == "$commit" ]] || { echo 'SDK existente inesperado; preservado.' >&2; exit 1; }
[[ -z $(git -C "$sdk" status --porcelain --untracked-files=no --ignore-submodules=all) ]] || { echo 'SDK possui alterações próprias; preservado.' >&2; exit 1; }
update_submodules() {
    python3 /opt/huninn-android/scripts/recover-empty-submodules.py "$sdk" || return 1
    git -C "$sdk" submodule update --init --recursive --depth 1 --jobs 1 || return 1
    python3 /opt/huninn-android/scripts/recover-empty-submodules.py "$sdk" || return 1
}
retry update_submodules
[[ -z $(git -C "$sdk" status --porcelain --untracked-files=no) ]] || { echo 'Submódulos ainda possuem alterações; preservados. Consulte docs/troubleshooting.md.' >&2; exit 1; }
export IDF_TOOLS_PATH=/opt/esp/tools-v5.5.6
retry "$sdk/install.sh" esp32,esp32s3,esp32c3,esp32c6
. "$sdk/export.sh"
xtensa-esp-elf-gcc --version
riscv32-esp-elf-gcc --version
idf.py --version
