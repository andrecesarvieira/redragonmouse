#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
dist_dir="$project_dir/dist"
package_version="0.2.0"
mkdir -p "$dist_dir"

podman run --rm \
    --env PACKAGE_VERSION="$package_version" \
    --volume "$project_dir:/src:ro,Z" \
    --volume "$dist_dir:/out:Z" \
    docker.io/library/fedora:44 \
    bash -euxo pipefail -c '
        dnf install -y rpm-build gcc-c++ make libusb1-devel python3 \
            desktop-file-utils appstream rpmlint curl
        mkdir -p /tmp/rpmbuild/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
        mkdir -p "/tmp/redragon-control-$PACKAGE_VERSION"
        cp -a /src/redragon_control /src/tests /src/packaging /src/run.py \
            /src/README.md "/tmp/redragon-control-$PACKAGE_VERSION/"
        tar -C /tmp -czf "/tmp/rpmbuild/SOURCES/redragon-control-$PACKAGE_VERSION.tar.gz" \
            "redragon-control-$PACKAGE_VERSION"
        curl --fail --location --retry 3 \
            https://github.com/dokutan/mouse_m908/archive/refs/tags/v3.5.tar.gz \
            --output /tmp/rpmbuild/SOURCES/mouse_m908-3.5.tar.gz
        cp /src/packaging/redragon-control.spec /tmp/rpmbuild/SPECS/
        rpmbuild --define "_topdir /tmp/rpmbuild" \
            -ba /tmp/rpmbuild/SPECS/redragon-control.spec
        rpmlint /tmp/rpmbuild/RPMS/*/*.rpm /tmp/rpmbuild/SRPMS/*.src.rpm || true
        cp /tmp/rpmbuild/RPMS/*/*.rpm /tmp/rpmbuild/SRPMS/*.src.rpm /out/
    '

printf 'Pacotes criados em %s\n' "$dist_dir"
