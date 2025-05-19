#!/bin/bash

set -e

if [ "$#" -gt 1 ]; then
    echo "Illegal number of parameters!"
    echo "Usage: $0 [Release|Debug]"
    exit 1
fi

BUILD_TYPE=${1:-Release}

cd etiss
cmake -S . -B build -DCMAKE_BUILD_TYPE=$BUILD_TYPE -DCMAKE_INSTALL_PREFIX=$(pwd)/../install/etiss
cmake --build build -j`nproc`
cmake --install build
cd -
