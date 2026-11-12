#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
container=huninn-android
check=false
for arg in "$@"; do
    case $arg in
        --check) check=true ;;
        --reuse-huninn-idf) container=huninn-idf ;;
        --help|-h) echo 'bash install.sh [--check] [--reuse-huninn-idf]'; exit 0 ;;
        *) echo "Opção desconhecida: $arg" >&2; exit 2 ;;
    esac
done
fail() { echo "HUNINN Android: $*" >&2; exit 1; }
command -v pkg >/dev/null && [[ -n ${PREFIX:-} && -d $PREFIX/bin ]] || fail 'Abra o Termux, fora do Debian.'
[[ $(uname -m) == aarch64 && $(dpkg --print-architecture) == aarch64 ]] || fail 'Esta edição requer Termux ARM64 (aarch64).'
case "$root" in /storage/*|/sdcard/*|/mnt/media_rw/*|*:*) fail 'Extraia o pacote no armazenamento privado do Termux, dentro de ~.' ;; esac
[[ -f $root/bin/huninn.py && -f $root/VERSION ]] || fail 'Pacote incompleto.'
workspace="$HOME/huninn-projects"
launcher="$PREFIX/bin/huninn"
config="$HOME/.config/huninn-android/config.json"
rootfs="$PREFIX/var/lib/proot-distro/containers/$container/rootfs"
marker="$rootfs/root/.huninn-android-managed"
[[ $container != huninn-idf ]] || marker="$rootfs/root/.huninn-idf-managed"
if [[ -e $launcher || -L $launcher ]]; then
    [[ -f $launcher && ! -L $launcher ]] && grep -qx '# HUNINN Android managed launcher v1' "$launcher" || fail "Comando $launcher já existe e não pertence a este instalador."
fi
[[ ! -e $PREFIX/var/lib/proot-distro/installed-rootfs/$container ]] || fail 'Container legado preservado. É necessário PRoot-Distro com imagens OCI.'
[[ ! -e $rootfs || -f $marker ]] || fail 'Container existente não gerenciado; preservado.'
[[ $container != huninn-idf || -f $marker ]] || fail 'Não foi encontrado o ambiente huninn-idf gerenciado anterior.'
minimum=10485760
[[ $container != huninn-idf ]] || minimum=2097152
available=$(df -Pk "$root" | awk 'END {print $4}')
[[ $available =~ ^[0-9]+$ && $available -ge $minimum ]] || fail 'Espaço insuficiente: reserve 10 GiB para instalação nova ou 2 GiB ao reutilizar o SDK.'
echo "Pré-verificação OK: ARM64, container $container, pacote em armazenamento privado."
$check && exit 0
pkg install -y proot-distro git python termux-api
help=$(proot-distro install --help 2>&1) || fail "Não foi possível consultar PRoot-Distro: $help"
[[ $help == *--name* ]] || fail 'Atualize proot-distro; requer suporte a imagens OCI.'
mkdir -p "$workspace"
workspace=$(cd "$workspace" && pwd -P)
case "$workspace" in /storage/*|/sdcard/*|/mnt/media_rw/*|*:*) fail 'Workspace deve ficar em armazenamento privado.' ;; esac
if [[ -f $config ]]; then
    python - "$config" "$container" "$workspace" <<'PY'
import json,sys
old=json.load(open(sys.argv[1]))
if old.get('container') != sys.argv[2] or old.get('workspace') != sys.argv[3]:
    raise SystemExit('Configuração existente diferente: preservada. Use as mesmas opções da instalação anterior.')
PY
fi
if [[ ! -d $rootfs ]]; then
    proot-distro install --name "$container" debian:bookworm
    [[ -d $rootfs/root ]] || fail 'Container não criou o rootfs esperado.'
    printf '%s\n' 'HUNINN Android managed Debian v1' > "$marker"
fi
mirror=${HUNINN_GITHUB_ASSETS:-dl.espressif.com/github_assets}
case "$mirror" in dl.espressif.com/github_assets|github.com) ;; *) fail 'Use o espelho oficial dl.espressif.com/github_assets ou github.com.' ;; esac
proot-distro login --shared-tmp --bind "$root:/opt/huninn-android" "$container" -- \
    env "IDF_GITHUB_ASSETS=$mirror" /bin/bash /opt/huninn-android/scripts/setup-debian.sh
mkdir -p "$(dirname "$config")"
python - "$config" "$container" "$workspace" <<'PY'
import json,os,sys,tempfile
from pathlib import Path
path=Path(sys.argv[1])
fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.config-')
with os.fdopen(fd,'w') as f:
    json.dump({'schema':1,'container':sys.argv[2],'workspace':sys.argv[3]},f,indent=2)
os.replace(tmp,path)
PY
tmp=$(mktemp "$PREFIX/bin/.huninn.XXXXXX")
trap 'rm -f -- "$tmp"' EXIT
{
    printf '#!%s/bin/bash\n' "$PREFIX"
    printf '%s\n' '# HUNINN Android managed launcher v1'
    printf 'exec %q %q "$@"\n' "$PREFIX/bin/python" "$root/bin/huninn.py"
} > "$tmp"
chmod 755 "$tmp"
mv -- "$tmp" "$launcher"
echo 'Instalação concluída. Execute: huninn doctor'
echo 'Primeiro projeto: huninn new meu-projeto --chip esp32s3'
echo 'Depois: huninn build meu-projeto'
echo 'USB requer também o aplicativo Termux:API e adaptador compatível. Leia docs/usb.md.'
