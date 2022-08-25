#!/bin/bash
set -e

rm -fr *.deb
cp control pinormos-wlan-manager/wlan-manager-deb/DEBIAN/.
pinormos-wlan-manager/gen-deb.sh
