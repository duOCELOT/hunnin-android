#!/usr/bin/env python3
"""HUNINN Android: native Termux front-end; ESP-IDF runs inside Debian PRoot."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
CHIPS = ('esp32', 'esp32s3', 'esp32c3', 'esp32c6')

def load_config():
    path = Path(os.environ.get('HUNINN_CONFIG', Path.home()/'.config/huninn-android/config.json'))
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as error:
        raise ValueError('Instale primeiro com: bash install.sh') from error
    if data.get('container') not in ('huninn-android', 'huninn-idf'):
        raise ValueError('Container desconhecido na configuração')
    workspace = Path(data['workspace']).resolve()
    if not workspace.is_dir() or ':' in str(workspace):
        raise ValueError('Workspace inválido ou ausente')
    return data['container'], workspace

def valid_name(name):
    if not re.fullmatch(r'[a-z][a-z0-9_-]{0,47}', name):
        raise ValueError('Use nome com letras minúsculas, números, _ ou -, começando por letra')
    return name

def project(workspace, name):
    path = workspace / valid_name(name)
    if path.is_symlink() or path.resolve().parent != workspace:
        raise ValueError('Projeto deve estar diretamente no workspace')
    meta = json.loads((path/'huninn.json').read_text())
    if meta.get('chip') not in CHIPS:
        raise ValueError('Chip inválido no projeto')
    return path, meta['chip']

def new_project(workspace, name, chip):
    path = workspace/valid_name(name)
    if path.exists() or path.is_symlink():
        raise ValueError('Projeto já existe; nenhum arquivo foi substituído')
    shutil.copytree(ROOT/'templates/hello', path)
    (path/'CMakeLists.txt').write_text((path/'CMakeLists.txt').read_text().replace('@PROJECT@', name.replace('-', '_')))
    (path/'huninn.json').write_text(json.dumps({'schema': 1, 'chip': chip}, indent=2)+'\n')
    print(f'Projeto criado: {path}\nCompile com: huninn build {name}')

def guest(container, workspace, action, name='', chip='', extra=()):
    return ['proot-distro', 'login', '--shared-tmp', '--bind', f'{ROOT}:/opt/huninn-android',
            '--bind', f'{workspace}:/work/projects', container, '--', '/bin/bash',
            '/opt/huninn-android/scripts/guest.sh', action, name, chip, *extra]

def flash_plan(path, chip):
    build = (path/'build-android').resolve()
    data = json.loads((build/'flasher_args.json').read_text())
    if data.get('extra_esptool_args', {}).get('chip') != chip:
        raise ValueError('Chip do build não corresponde ao projeto; recompile')
    settings = data['flash_settings']
    mode, freq, size = (settings[k] for k in ('flash_mode', 'flash_freq', 'flash_size'))
    if mode not in ('dio', 'dout', 'qio', 'qout') or freq not in ('20m', '26m', '40m', '80m', '120m'):
        raise ValueError('Modo/frequência flash não suportados')
    if not re.fullmatch(r'(1|2|4|8|16|32|64|128)MB', size):
        raise ValueError('Defina um tamanho de flash explícito no menuconfig')
    capacity = int(size[:-2])*1024*1024
    args = ['--flash_mode', mode, '--flash_freq', freq, '--flash_size', size]
    spans = []
    for offset, filename in data['flash_files'].items():
        address = int(offset, 0)
        file = (build/filename).resolve()
        if not file.is_relative_to(build) or not file.is_file() or file.stat().st_size == 0:
            raise ValueError('Arquivo de flash ausente ou fora do build')
        end = address + file.stat().st_size
        if address < 0 or address % 4096 or end > capacity:
            raise ValueError('Segmento fora da flash ou offset desalinhado')
        spans.append((address, end))
        args += [hex(address), file.relative_to(build).as_posix()]
    if not spans or any(a[1] > z[0] for a, z in zip(sorted(spans), sorted(spans)[1:])):
        raise ValueError('Segmentos ausentes ou sobrepostos')
    print(f'Projeto: {path.name} | chip: {chip} | flash configurada: {size} | segmentos: {len(spans)}')
    return args

def callback(kind):
    """Use /dev/tty to avoid termux-usb capturing output until bridge exits."""
    directory = Path.home()/'.local/lib/huninn-android'
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / ('usb-'+kind)
    import shlex
    python = str(Path(os.environ['PREFIX'])/'bin/python')
    shell = str(Path(os.environ['PREFIX'])/'bin/sh')
    path.write_text(f'#!{shell}\nexec {shlex.quote(python)} -u {shlex.quote(str(ROOT/"usb"/(kind+".py")))} "$@" > /dev/tty 2>&1\n')
    path.chmod(0o700)
    return str(path)

def main(argv=None):
    parser = argparse.ArgumentParser(description='HUNINN Android 0.1.0 — ESP-IDF no celular, sem root')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('doctor', help='Verificar ESP-IDF e compiladores')
    commands.add_parser('list', help='Listar projetos')
    new = commands.add_parser('new', help='Criar projeto que imprime mensagem na UART')
    new.add_argument('name'); new.add_argument('--chip', choices=CHIPS, default='esp32s3')
    for action in ('build', 'config', 'edit', 'size', 'export', 'probe', 'flash'):
        p = commands.add_parser(action); p.add_argument('name')
        if action == 'flash': p.add_argument('--yes', action='store_true')
    shell = commands.add_parser('shell'); shell.add_argument('name', nargs='?', default='')
    commands.add_parser('usb-list', help='Listar USB Android')
    for action in ('usb-info', 'usb'):
        p = commands.add_parser(action); p.add_argument('device')
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        parser.print_help()
        return 0
    args = parser.parse_args(argv)
    try:
        container, workspace = load_config()
        action = args.command
        if action == 'new':
            new_project(workspace, args.name, args.chip); return 0
        if action == 'list':
            for path in sorted(workspace.iterdir()):
                if (path/'huninn.json').is_file() and not path.is_symlink(): print(path.name)
            return 0
        if action == 'usb-list': return subprocess.call(['termux-usb', '-l'])
        if action in ('usb', 'usb-info'):
            if not re.fullmatch(r'/dev/bus/usb/[0-9]{3}/[0-9]{3}', args.device):
                raise ValueError('Use o endereço retornado por huninn usb-list')
            return subprocess.call(['termux-usb', '-r', '-e', callback('bridge' if action == 'usb' else 'info'), args.device])
        name, chip, extra = getattr(args, 'name', ''), '', []
        if name:
            path, chip = project(workspace, name)
        if action == 'flash':
            extra = flash_plan(path, chip)
            print('Escrita de firmware. Confirme flash_id, BOOT e a placa correta; mantenha USB alimentada.')
            if not args.yes and input(f'Digite o nome do projeto ({name}) para gravar: ').strip() != name:
                print('Cancelado'); return 1
        return subprocess.call(guest(container, workspace, action, name, chip, extra))
    except (OSError, ValueError, KeyError, EOFError) as error:
        print(f'HUNINN: {error}', file=sys.stderr); return 1

if __name__ == '__main__':
    sys.exit(main())
