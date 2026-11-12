# HUNINN Android

**Crie, edite e compile projetos ESP32 no celular, sem Windows e sem root.**

Edição independente do firmware HUNINN. Versão **0.1.0 experimental**, com
interface de terminal em português. Não é APK nem uma distribuição oficial da
Espressif. Usa Termux ARM64, Debian Bookworm via PRoot e ESP-IDF **5.5.6** fixado.

```text
huninn new meu-projeto --chip esp32s3
huninn edit meu-projeto
huninn config meu-projeto
huninn build meu-projeto
```

## O que já existe

- Instalador com verificação de arquitetura, espaço e proteção de ambientes existentes.
- SDK dentro de um container separado chamado `huninn-android`.
- Opção para reutilizar o antigo `huninn-idf` instalado pelo projeto HUNINN.
- Projetos próprios em `~/huninn-projects`, fora do pacote e do SDK.
- Editor Nano, menuconfig, compilação, relatório de tamanho e exportação de binários.
- Retentativas de download e espelho oficial da Espressif para as ferramentas.
- Recuperação conservadora de submódulos cujo checkout foi interrompido e está vazio.
- Diagnóstico USB e ponte **CH343 `1a86:55d3`** com velocidade fixa de 115200.
- Comandos para identificar a flash e gravar os segmentos gerados pelo build.

## Requisitos

- Android com Termux **ARM64** (`uname -m` e `dpkg --print-architecture`: `aarch64`).
- Termux de fonte oficial, por exemplo [F-Droid](https://f-droid.org/packages/com.termux/).
- Para USB: aplicativo [Termux:API](https://f-droid.org/packages/com.termux.api/)
  **da mesma fonte do Termux**, cabo de dados/OTG e uma interface USB compatível.
- Internet para a primeira instalação e dependências de projetos.
- Pelo menos 10 GiB livres; reserve 12–15 GiB para SDK e builds. Ao reutilizar o
  SDK anterior, o instalador exige pelo menos 2 GiB livres adicionais.
- Manter o pacote e os projetos no armazenamento privado do Termux, não em Downloads.

O Android pode limitar memória, processos em segundo plano ou alimentação USB.
O compilador usa dois jobs por padrão. Os chips aceitos no projeto são ESP32,
ESP32-S3, ESP32-C3 e ESP32-C6. O hardware comprovado nesta etapa é **ESP32-S3 via
CH343**; as outras combinações não foram validadas fisicamente.

## Instalar pelo GitHub

Repositório: [duOCELOT/hunnin-android](https://github.com/duOCELOT/hunnin-android).
O nome do repositório é `hunnin-android`; o comando instalado continua `huninn`.

No Termux, para uma instalação nova:

```bash
pkg update
pkg install git
git clone https://github.com/duOCELOT/hunnin-android.git ~/huninn-android
cd ~/huninn-android
bash install.sh --check
bash install.sh
huninn doctor
```

Se você já tem o SDK `huninn-idf`, substitua as duas linhas `bash install.sh`
pelas opções `--reuse-huninn-idf` descritas abaixo. Se o repositório estiver
privado, use o ZIP pelo navegador autenticado; não digite sua senha do GitHub
no Termux.

## Instalar pelo ZIP, sem senha do GitHub no Termux

Baixe o [ZIP da branch main](https://github.com/duOCELOT/hunnin-android/archive/refs/heads/main.zip)
pelo navegador. O arquivo se chama `hunnin-android-main.zip` e contém código e documentação;
o SDK e os compiladores oficiais são baixados na instalação.

No Termux, para uma instalação nova:

```bash
pkg update
pkg install unzip
termux-setup-storage
unzip ~/storage/downloads/hunnin-android-main.zip -d ~
cd ~/hunnin-android-main
bash install.sh --check
bash install.sh
huninn doctor
```

Se a pasta de destino já existir, preserve a cópia e seus projetos antes de
extrair outra versão por cima. O pacote deve permanecer no local instalado;
se mover a pasta, execute o instalador novamente para atualizar o comando.

**Para quem já instalou o SDK pelo projeto HUNINN**, use estas opções em vez da
instalação padrão:

```bash
bash install.sh --reuse-huninn-idf --check
bash install.sh --reuse-huninn-idf
```

Essa opção reutiliza o container marcado como gerenciado e os compiladores.
O comando antigo `huninn-idf`, seus arquivos de firmware e seus `sdkconfig`
continuam separados. O novo comando chama-se **`huninn`**. Nas próximas
reexecuções do instalador, mantenha a mesma opção de reutilização.

O comando só é publicado após a instalação concluir. Se ela parar antes disso,
`huninn: command not found` é esperado: resolva o erro e execute o instalador de
novo. Não apague todo o SDK para tentar corrigir um download.

## Primeiro projeto

```bash
huninn new meu-projeto --chip esp32s3
huninn edit meu-projeto
huninn config meu-projeto
huninn build meu-projeto
huninn size meu-projeto
```

O exemplo imprime uma mensagem na UART a cada dois segundos. **Não aciona GPIOs**,
pois LEDs, motores e sensores têm pinagens diferentes em cada placa. Em Nano,
salve com Ctrl+O, Enter, e saia com Ctrl+X. No Termux, a tecla Ctrl da barra extra
ou Volume para baixo pode ser usada como modificador.

Em `huninn config`, confira tamanho e modo da flash, PSRAM e qualquer configuração
específica da placa. O exemplo usa os padrões do ESP-IDF, incluindo flash de 2 MB;
não supõe que todas as placas sejam a N16R8 do projeto original.

Não rode `set-target` para simplesmente trocar de computador: pode recriar a
configuração. Cada projeto guarda seu chip em `huninn.json`, e os builds Android
usam `build-android/`.

## Gravar pelo Android

Leia [o fluxo USB completo](docs/usb.md). Nesta versão, são duas sessões Termux:

```text
Sessão 1: huninn usb-list
          huninn usb-info /dev/bus/usb/001/002
          huninn usb /dev/bus/usb/001/002
Sessão 2: huninn probe meu-projeto
          [reiniciar a ponte na sessão 1]
          huninn flash meu-projeto
```

O endereço é só exemplo: use a listagem atual. BOOT/RESET é manual. A ponte
aceita um comando por execução e aguarda até 180 segundos por conexão. A
confirmação de gravação exige digitar o nome do projeto; `--yes` é oferecido para
automação consciente. O comando `probe` não grava firmware.

O driver é específico para CH343 `1a86:55d3` com descritores CDC-ACM compatíveis.
CP210x, CH340, FTDI e USB nativa Espressif **não estão implementados** nesta ponte.
Outras placas podem ser compiladas/exportadas, mas exigem um gravador compatível.

## Comandos

| Comando | Função |
|---|---|
| `huninn doctor` | Verificar SDK e compilador |
| `huninn list` | Listar projetos |
| `huninn new NOME --chip esp32s3` | Criar um projeto novo |
| `huninn edit NOME` | Editar `main/main.c` no Nano |
| `huninn config NOME` | Abrir menuconfig |
| `huninn build NOME` | Compilar |
| `huninn size NOME` | Relatório de tamanho |
| `huninn export NOME` | Gerar `build-android/merged-binary.bin` |
| `huninn shell [NOME]` | Terminal Debian com ESP-IDF |
| `huninn usb-list` | Listar dispositivos Android USB |
| `huninn usb-info ENDEREÇO` | Ler VID/PID sem gravar |
| `huninn usb ENDEREÇO` | Abrir ponte CH343 local |
| `huninn probe NOME` | Identificar chip e flash através da ponte |
| `huninn flash NOME` | Gravar build após confirmação |

O arquivo merged é gravado em 0x0 por ferramenta compatível e contém preenchimento
entre segmentos; pode sobrescrever NVS. O comando `huninn flash` usa segmentos
individuais e não executa `erase_flash`. Mudanças de partição ainda podem afetar
os dados antigos. A configuração de placa e o conteúdo do seu firmware continuam
sendo responsabilidade do projeto.

## Validação e limites

- 26 testes automatizados de instalador simulado, criação de projetos, argumentos
  de gravação, recuperação conservadora de checkout e transporte USB simulado.
- O exemplo ESP32-S3 foi compilado com ESP-IDF 5.5.6 no ambiente Linux de validação.
- No projeto de origem, o usuário instalou ESP-IDF 5.5.6 e compilou no Android;
  identificou ESP32-S3/8 MB PSRAM/16 MB flash via CH343 e gravou bootloader,
  aplicativo e partições com hashes verificados. Este é o fundamento da ponte.
- **O instalador independente desta edição ainda precisa de teste completo em
  um Android físico.** Não confundir o fluxo original validado com esta nova embalagem.
- O CLI não é IDE gráfica, não sincroniza contas e não sobe seu código para a nuvem.

Veja [solução de problemas](docs/troubleshooting.md), [roteiro de evolução](docs/roadmap.md)
e [contribuição](CONTRIBUTING.md). A licença do código deste pacote é MIT; cada
ferramenta e dependência baixada mantém sua própria licença.
