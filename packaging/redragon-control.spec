Name:           redragon-control
Version:        0.1.0
Release:        3%{?dist}
Summary:        Painel GNOME para o mouse Redragon M711
License:        GPL-3.0-or-later
URL:            https://github.com/dokutan/mouse_m908
Source0:        %{name}-%{version}.tar.gz
Source1:        https://github.com/dokutan/mouse_m908/archive/refs/tags/v3.5.tar.gz#/mouse_m908-3.5.tar.gz

BuildRequires:  gcc-c++
BuildRequires:  make
BuildRequires:  pkgconfig(libusb-1.0)
BuildRequires:  python3
BuildRequires:  desktop-file-utils
BuildRequires:  appstream
Requires:       python3-gobject
Requires:       gtk4
Requires:       libadwaita
Requires(posttrans): systemd-udev
Requires(postun): systemd-udev

%global _udevrulesdir %{_prefix}/lib/udev/rules.d

%description
Interface GTK 4 e libadwaita para configurar DPI, polling rate, perfis e
iluminação RGB do mouse Redragon M711 Cobra. Inclui o backend mouse_m908 3.5.

%prep
%autosetup -n %{name}-%{version} -a 1

%build
%make_build -C mouse_m908-3.5 \
    CC="%{__cxx} %{build_cxxflags}" \
    LIBS="$(pkg-config --libs libusb-1.0) %{build_ldflags}"

%check
python3 -m unittest discover -s tests -v
desktop-file-validate packaging/io.github.redragon.Control.desktop
appstreamcli validate --no-net packaging/io.github.redragon.Control.metainfo.xml

%install
install -d %{buildroot}%{_datadir}/%{name}
cp -a redragon_control run.py %{buildroot}%{_datadir}/%{name}/
find %{buildroot}%{_datadir}/%{name} -type f -name '*.py' -exec chmod 0644 {} +
chmod 0755 %{buildroot}%{_datadir}/%{name}/run.py

install -Dpm 0755 packaging/redragon-control %{buildroot}%{_bindir}/redragon-control
install -Dpm 0755 mouse_m908-3.5/mouse_m908 %{buildroot}%{_libexecdir}/%{name}/mouse_m908
install -Dpm 0644 packaging/70-redragon-m711.rules %{buildroot}%{_udevrulesdir}/70-redragon-m711.rules
install -Dpm 0644 packaging/io.github.redragon.Control.desktop %{buildroot}%{_datadir}/applications/io.github.redragon.Control.desktop
install -Dpm 0644 packaging/io.github.redragon.Control.metainfo.xml %{buildroot}%{_metainfodir}/io.github.redragon.Control.metainfo.xml
install -Dpm 0644 packaging/io.github.redragon.Control.svg %{buildroot}%{_datadir}/icons/hicolor/scalable/apps/io.github.redragon.Control.svg

find %{buildroot}%{_datadir}/%{name} -type d -name __pycache__ -prune -exec rm -rf {} +

%posttrans
/usr/bin/udevadm control --reload-rules >/dev/null 2>&1 || :
/usr/bin/udevadm trigger --action=add --subsystem-match=usb \
    --attr-match=idVendor=04d9 --attr-match=idProduct=fc30 >/dev/null 2>&1 || :

%postun
/usr/bin/udevadm control --reload-rules >/dev/null 2>&1 || :

%files
%license mouse_m908-3.5/LICENSE
%doc README.md
%{_bindir}/redragon-control
%{_libexecdir}/%{name}/mouse_m908
%{_datadir}/%{name}/
%{_udevrulesdir}/70-redragon-m711.rules
%{_datadir}/applications/io.github.redragon.Control.desktop
%{_metainfodir}/io.github.redragon.Control.metainfo.xml
%{_datadir}/icons/hicolor/scalable/apps/io.github.redragon.Control.svg

%changelog
* Mon Aug 17 2026 Redragon Control contributors - 0.1.0-3
- Lê automaticamente a memória do mouse e preserva localmente o último estado aplicado

* Mon Aug 17 2026 Redragon Control contributors - 0.1.0-2
- Aplica a regra udev imediatamente em mouses que já estejam conectados

* Mon Aug 17 2026 Redragon Control contributors - 0.1.0-1
- Primeiro pacote RPM para o Redragon M711 Cobra
