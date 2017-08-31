#!/bin/sh
set -e -x
base="$PWD"
name="osmo-stp"
. "$(dirname "$0")/jenkins-build-common.sh"

build_repo libosmocore --disable-doxygen
build_repo libosmo-abis
build_repo libosmo-netif --disable-doxygen
build_repo libosmo-sccp

create_bin_tgz osmo-stp