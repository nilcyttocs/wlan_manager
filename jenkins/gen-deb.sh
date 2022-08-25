#!/bin/bash

set -e

dir=`readlink -f .`
pdir="$(dirname "$dir")"

pushd () {
    command pushd "$@" > /dev/null
}

popd () {
    command popd "$@" > /dev/null
}

pushd ${pdir}
./build.sh
popd

cp ${pdir}/*.deb .
