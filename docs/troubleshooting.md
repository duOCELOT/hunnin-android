# Recuperação e diagnóstico

## Download ou DNS falhou

Use uma rede com internet: o Wi-Fi de uma station local pode não oferecer acesso
à internet. O instalador faz até três tentativas por etapa, preserva o que já foi
baixado e usa `dl.espressif.com/github_assets` para os arquivos de ferramentas.
Esse espelho é oficial e mantém HTTPS, checksums e restrições de pacotes Python.
Ele não substitui o GitHub para os repositórios git.

Depois de corrigir a conexão, execute novamente `bash install.sh`, mantendo
`--reuse-huninn-idf` se foi a opção inicial. Não desative TLS. Para usar a origem
GitHub em vez do espelho oficial:

```bash
HUNINN_GITHUB_ASSETS=github.com bash install.sh
```

## SDK com alterações após download interrompido

A recuperação automática só restaura submódulos com índice Git vazio e sem
arquivos de trabalho além dos metadados `.git`. Uma anotação, link simbólico ou
arquivo modificado impede essa recuperação. Nenhum `reset --hard` é executado.
Revisões de submódulos são ajustadas por `git submodule update` sem `--force`.

Se continuar bloqueado, entre no container (`proot-distro login huninn-android`,
ou `huninn-idf` como nome do container no modo de reutilização) e consulte:

```bash
git -C /opt/esp/esp-idf-v5.5.6 --no-pager status --short --untracked-files=no
```

Compartilhe nomes e mensagens de erro; não compartilhe senhas, tokens ou dumps
inteiros de `sdkconfig`. Alterações próprias devem ser preservadas e revisadas,
não descartadas como se fossem download incompleto.

## Processo encerrado pelo Android

Mantenha Termux em primeiro plano durante instalação/build. Verifique memória,
espaço e as restrições de bateria impostas pelo fabricante. Para reduzir jobs:

```bash
huninn shell meu-projeto
export IDF_PY_BUILD_JOBS=1
idf.py -B build-android build
```

Não reutilize pastas build do Windows. Mantenha fontes e `sdkconfig` do projeto,
mas use o diretório separado `build-android`.

## Atualização do pacote

Não remova `~/huninn-projects`: é onde ficam seus projetos. Atualize os arquivos
do pacote e rode o instalador novamente com a mesma opção de container. Ele
recusa um comando `huninn` de outra origem e containers sem marcador gerenciado.
A nova versão não precisa substituir nem atualizar o firmware HUNINN das stations.
