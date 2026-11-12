# Roteiro

## 0.1.0 — base compartilhável

Instalação Termux/PRoot, ESP-IDF fixado, projetos próprios, Nano/menuconfig/build,
exportação, diagnóstico USB e CH343. Interface de terminal; não é APK.

## Próximas etapas, ainda não implementadas

1. Teste de instalação independente em Android físico, com registro de versões,
   tempo, espaço e modelos de telefone. Validar retomada após queda de internet.
2. Assistente em uma sessão para BOOT, identificação e gravação; reduzir a troca
   manual de terminais sem esconder confirmação de escrita ou erros USB.
3. Perfis USB CP210x, CH340 e USB nativa Espressif, cada um com testes físicos.
4. Exemplos de sensores I2C, Wi-Fi e GPIO com pinagem explicitamente configurada.
5. Editor/painel local acessível pelo navegador, depois de estabilizar o CLI.
6. Publicação de releases assinadas e checagem de atualização sem substituir projetos.

A primeira edição não promete suporte universal a todos os Androids ou a todas
as placas ESP. Repetir o teste de gravação a cada novo driver, placa e telefone.
