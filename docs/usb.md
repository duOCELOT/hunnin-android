# USB sem root: CH343 + Termux:API

1. Instale Termux e Termux:API da mesma fonte. Conecte a placa por USB-UART usando
   cabo de dados/OTG. A permissão deve ser aceita no Android.
2. No Termux: `huninn usb-list`. Copie o endereço atual, por exemplo `/dev/bus/usb/001/002`.
3. Execute `huninn usb-info /dev/bus/usb/001/002`. Esta ponte requer **1a86:55d3**.
4. Segure BOOT, pressione e solte RESET, depois solte BOOT. Não desconecte o cabo.
   Confira novamente `huninn usb-list`: reset/reconexão pode mudar o endereço.
5. Na primeira sessão: `huninn usb /dev/bus/usb/001/002`, usando o endereço atual.
   Espere **CH343 ready**. A saída vai diretamente para `/dev/tty`, evitando o
   buffering do callback Termux:API.
6. Na segunda sessão: `huninn probe meu-projeto`. Deve identificar o chip correto
   e o tamanho real da flash. Esse comando não grava nem apaga o firmware.
7. Confira que o tamanho da flash escolhido em `huninn config meu-projeto` é
   apropriado à placa e recompile se mudar. A ferramenta rejeita segmentos fora
   do tamanho configurado, mas não substitui a identificação física da memória.
8. Reinicie a ponte na primeira sessão: ela atende uma conexão por execução.
   Se a placa continua no bootloader, não precisa resetar de novo.
9. Na segunda sessão: `huninn flash meu-projeto`. Confira projeto, chip e tamanho
   e digite o nome do projeto quando solicitado. Aguarde os hashes verificados.
10. Pressione RESET sem BOOT para executar o aplicativo novo.

O comando mantém 115200 baud e usa `--no-stub --before no_reset --after no_reset`.
O protocolo `socket://` não controla DTR/RTS nem altera a velocidade real do UART.
A ponte liga somente em `127.0.0.1:3333`; outros processos locais ainda podem
acessá-la. Não exponha essa porta por encaminhamento de rede.

Se o driver `cdc_acm` ocupa a interface, a ponte usa a transferência temporária
USBDEVFS_DISCONNECT_CLAIM, condicionada ao nome exato do driver. Ao encerrar,
libera as interfaces e tenta reconectar o driver. Nunca destaca `usbfs` (outro
app) nem drivers desconhecidos. Se Android/SELinux negar, informa o erro e para.

## Interpretar erros

| Mensagem | Próximo passo |
|---|---|
| `Connection refused` | Ponte ausente/expirada. Reinicie-a antes de cada comando. |
| `No such device` | Confira a lista USB e o cabo; não reutilize um endereço antigo. |
| `No serial data received` | Confira BOOT/RESET, porta USB-UART e saída da ponte. |
| `Device or resource busy` + `usbfs` | Feche o outro aplicativo/ponte que usa a interface. |
| `Android refused CDC handoff` | Envie a mensagem completa; não tente root ou permissões globais. |
| Não aparece saída | Teste `termux-usb -r -e "$PREFIX/bin/echo" ENDEREÇO`; deve imprimir um fd. Não passe esse número manualmente à ponte. |
| `/dev/tty` indisponível | Execute em uma sessão interativa do Termux, não em tarefa sem terminal. |

O fd entregue pelo Android só é válido dentro do processo iniciado pelo callback.
PRoot não cria COM5/COM6 nem dá acesso automático a `/dev/ttyUSB0`.

Para preservar dados, não use erase total. Caso um cabo desconecte durante a
escrita, resolva a conexão, entre no bootloader e regrave os mesmos segmentos.
Não é necessário apagar toda a flash para retomar.
