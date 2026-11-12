"""Restore only interrupted no-checkout submodules with no index/files.

Never reset modified files or revision differences; normal git update handles
revision changes. The SDK must already be the verified release.
"""
from pathlib import Path
import subprocess
import sys


def run(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args])


def recover(path):
    path = Path(path)
    if run(path, 'ls-files', '-z'):
        return False
    # A git clone --no-checkout has an empty index and absent worktree files.
    # Any file/symlink other than its .git metadata stops automatic recovery.
    for child in path.iterdir():
        if child.name == '.git':
            continue
        if child.is_symlink() or not child.is_dir() or any(child.rglob('*')):
            return False
    run(path, 'rev-parse', '--verify', 'HEAD')
    subprocess.run(['git', '-C', str(path), 'restore', '--source=HEAD', '--staged', '--worktree', '--', '.'], check=True)
    print(f'Restored interrupted checkout: {path}')
    return True


def main(sdk):
    paths = run(sdk, 'submodule', 'foreach', '--quiet', '--recursive', 'pwd -P').decode().splitlines()
    for name in paths:
        path = Path(name).resolve()
        if not path.is_relative_to(Path(sdk).resolve()):
            raise ValueError('Submodule outside SDK')
        recover(path)

if __name__ == '__main__':
    main(sys.argv[1])
