# Redragon Control para Linux

Painel GTK nativo para configurar o **Redragon M711 Cobra** (`04d9:fc30`) no Linux.

## Recursos do primeiro MVP

- cinco perfis gravados na memória interna;
- cinco níveis de DPI por perfil, de 100 a 10.000 DPI;
- polling rate de 125, 250, 500 ou 1000 Hz;
- efeito, cor, brilho e velocidade da iluminação RGB;
- leitura automática das configurações atuais ao abrir e validação antes de aplicar;
- detecção automática do mouse e diagnóstico de permissão.

O acesso USB usa o projeto GPLv3 [`mouse_m908`](https://github.com/dokutan/mouse_m908), versão 3.5, que possui suporte parcial ao M711. A interface não envia pacotes USB por conta própria.

## Fedora

Instale/compile o backend e a regra udev restrita ao M711:

```bash
make setup
```

O script mostra os comandos `sudo` normalmente e instala o binário somente em `.local/bin` dentro deste projeto. Depois, desconecte e reconecte o mouse se necessário.

Execute o painel:

```bash
make run
```

Rode os testes sem acessar o hardware:

```bash
make test
```

## Pacote RPM

Gere o RPM em um contêiner Fedora 44 rootless, sem instalar compiladores no sistema:

```bash
make rpm
# ou, caso o comando make ainda não esteja instalado:
bash scripts/build-rpm.sh
sudo dnf install ./dist/redragon-control-0.1.0-3.fc44.*.rpm
```

O pacote instala a entrada **Redragon Control** no menu do GNOME, o backend em
`/usr/libexec/redragon-control` e a regra de acesso USB. Reconecte o mouse após
a primeira instalação.

## Segurança

O painel só grava no dispositivo após um clique explícito em **Aplicar**. Não desative todos os níveis de DPI: o próprio aplicativo bloqueia essa configuração. O suporte do backend ao M711 é classificado como parcial; mantenha outro mouse disponível durante os primeiros testes.

O backend grava o bloco completo de configurações. Como remapeamento ainda não aparece nesta interface, **mapeamentos personalizados de botões podem voltar ao padrão** ao aplicar este MVP.

## Próximos passos

O protocolo também permite remapeamento de botões e macros. Eles ficaram fora deste MVP para que a primeira validação no hardware seja pequena e recuperável.
