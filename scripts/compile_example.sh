#!/bin/bash

set -e

if [ "$#" -gt 6 ]; then
    echo "Illegal number of parameters!"
    echo "Usage: $0 [PROG] [gcc|llvm|seal5_llvm] [ARCH] [ABI] [Release|Debug] [NUM_RUNS]"
    exit 1
fi

PROG=${1:-hello_world}
TOOLCHAIN=${2:-gcc}
ARCH=${3:-rv32gc}
ABI=${4:-ilp32d}
BUILD_TYPE=${5:-Release}
NUM_RUNS=${6:-1}

RISCV_GCC_NAME=riscv32-unknown-elf
RISCV_GCC_PREFIX=$(pwd)/install/rv32gc_ilp32d

echo TOOLCHAIN=$TOOLCHAIN

if [[ "$TOOLCHAIN" == "gcc" ]]
then
    CMAKE_TOOLCHAIN_FILE=$(pwd)/etiss_riscv_examples/rv32gc-toolchain.cmake
elif [[ "$TOOLCHAIN" == "llvm" ]]
then
    export PATH=$(pwd)/install/llvm/bin:$PATH
    CMAKE_TOOLCHAIN_FILE=$(pwd)/etiss_riscv_examples/rv32gc-llvm-toolchain.cmake
else
    echo "Unknown toolchain: $TOOLCHAIN"
    exit 1
fi

cd etiss_riscv_examples/
test -d build/ && rm -rf build/ || :
cmake -S . -B build -DCMAKE_BUILD_TYPE=$BUILD_TYPE -DCMAKE_TOOLCHAIN_FILE=$CMAKE_TOOLCHAIN_FILE -DCMAKE_INSTALL_PREFIX=$(pwd)/build/install -DRISCV_ARCH=$ARCH -DRISCV_ABI=$ABI -DRISCV_TOOLCHAIN_PREFIX=$RISCV_GCC_PREFIX -DRISCV_TOOLCHAIN_BASENAME=$RISCV_GCC_NAME -DNUM_RUNS=$NUM_RUNS ..
cmake --build build -j$(nproc) -t $PROG
cmake --install build
cd -
