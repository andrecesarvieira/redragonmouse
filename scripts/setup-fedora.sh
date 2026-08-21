#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source_dir="$project_dir/.cache/mouse_m908"
binary_dir="$project_dir/.local/bin"
rule_source="$project_dir/packaging/70-redragon-m711.rules"
keyboard_rule_source="$project_dir/packaging/70-redragon-s118.rules"

sudo dnf install -y gcc-c++ git make libusb1-devel openrgb

if [[ -d "$source_dir/.git" ]]; then
    git -C "$source_dir" fetch --depth 1 origin tag v3.5
    git -C "$source_dir" checkout --detach v3.5
else
    mkdir -p "$(dirname "$source_dir")"
    git clone --depth 1 --branch v3.5 https://github.com/dokutan/mouse_m908.git "$source_dir"
fi

make -C "$source_dir"
mkdir -p "$binary_dir"
install -m 0755 "$source_dir/mouse_m908" "$binary_dir/mouse_m908"
sudo install -m 0644 "$rule_source" /etc/udev/rules.d/70-redragon-m711.rules
sudo install -m 0644 "$keyboard_rule_source" /etc/udev/rules.d/70-redragon-s118.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=usb --attr-match=idVendor=04d9 --attr-match=idProduct=fc30
sudo udevadm trigger --subsystem-match=usb --attr-match=idVendor=320f --attr-match=idProduct=5000
sudo udevadm trigger --subsystem-match=hidraw

printf 'Backends instalados. Reconecte o mouse e o teclado se o painel ainda indicar falta de permissão.\n'
