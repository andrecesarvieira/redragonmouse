# Redragon Control para Linux

Aplicativo GNOME nativo (GTK 4 + libadwaita) para o kit **Redragon S118**:

- mouse **M711 Cobra** (`04d9:fc30`);
- teclado **K552 Kumara ABNT2** (`320f:5000`, controlador EVision via HID direto).

## Recursos

### Mouse M711

- cinco perfis na memória interna;
- cinco níveis de DPI, de 100 a 10.000 DPI;
- polling rate de 125, 250, 500 ou 1000 Hz;
- RGB, brilho e velocidade;
- dez controles programáveis, incluindo teclas, atalhos, fire, snipe e macros;
- 15 slots de macro.

### Teclado K552

- efeitos RGB do firmware EVision;
- cor, brilho, velocidade e direção;
- editor visual por tecla;
- ações e macros por tecla armazenadas no perfil;
- perfis Principal, Jogos e Trabalho.

O mouse usa o backend GPLv3 [`mouse_m908`](https://github.com/dokutan/mouse_m908), versão 3.5. O teclado usa comunicação HID direta com o controlador EVision, sem OpenRGB ou outro serviço externo. Os arquivos locais ficam em `~/.config/redragon-control` e permanecem salvos quando o aplicativo é fechado.

## Fedora

Para preparar o ambiente de desenvolvimento:

```bash
make setup
make run
```

O instalador adiciona regras udev restritas aos dois VID/PID. Reconecte os dispositivos na primeira configuração.

Testes sem acesso ao hardware:

```bash
make test
```

## Pacote RPM

O RPM é construído em um contêiner Fedora 44 rootless:

```bash
make rpm
sudo dnf install ./dist/redragon-control-0.2.0-4.fc44.x86_64.rpm
```

O pacote instala o aplicativo, a entrada no menu do GNOME, `mouse_m908`, o backend HID EVision integrado e as regras udev do M711 e do K552.

## Persistência

O botão **Salvar perfil** guarda uma cópia local sem acessar o hardware. **Aplicar configurações** envia as alterações aos dispositivos e também atualiza a cópia local. Os perfis do M711 são gravados na memória interna; os efeitos compatíveis do K552 são armazenados automaticamente pelo controlador EVision.

## Segurança

Nenhum pacote USB é enviado sem um clique explícito em **Aplicar configurações**. As regras udev usam `uaccess`, liberando o hardware somente ao usuário da sessão local.
