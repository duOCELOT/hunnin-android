# Contribuir

Requer Python 3.11+ e Git no ambiente de teste. Os testes não precisam de Termux
nem instalam SDKs no computador:

```bash
python3 -m unittest discover -s tests -v
bash -n install.sh scripts/guest.sh scripts/setup-debian.sh
```

Inclua testes para mudanças no instalador, recuperação e transporte USB. Nunca
adicione `sdkconfig` pessoal, binários de firmware, credenciais, NVS ou imagens
com dados privados ao repositório.

Para relatar teste físico, inclua Android/Termux, chip, VID/PID, erro e etapa.
Omitir MAC/serial, senhas e tokens. Separar resultado de teste simulado de teste
real. Mudanças de transporte devem preservar timeout, liberação de interfaces,
confirmação de escrita e verificação de integridade do esptool.
