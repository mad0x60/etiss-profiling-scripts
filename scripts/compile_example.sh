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

RISCV_GCC_NAME=riscv64-unknown-elf
RISCV_GCC_PREFIX=$RV_TOOLCHAIN_DIR

echo TOOLCHAIN=$TOOLCHAIN

if [[ "$TOOLCHAIN" == "gcc" ]]
then
    CMAKE_TOOLCHAIN_FILE=$ETISS_EXAMPLES_DIR/rv32gc-toolchain.cmake
elif [[ "$TOOLCHAIN" == "llvm" ]]
then
    export PATH=$(pwd)/install/llvm/bin:$PATH
    CMAKE_TOOLCHAIN_FILE=$ETISS_EXAMPLES_DIR/rv32gc-llvm-toolchain.cmake
else
    echo "Unknown toolchain: $TOOLCHAIN"
    exit 1
fi

cd $ETISS_EXAMPLES_DIR
test -d build/ && rm -rf build/ || :
cmake -S . -B build -DCMAKE_BUILD_TYPE=$BUILD_TYPE -DCMAKE_TOOLCHAIN_FILE=$CMAKE_TOOLCHAIN_FILE -DCMAKE_INSTALL_PREFIX=$ETISS_EXAMPLES_DIR/build/install -DSIMULATION_RUNS_COUNT=$NUM_RUNS -DRISCV_ARCH=$ARCH -DRISCV_ABI=$ABI -DRISCV_TOOLCHAIN_PREFIX=$RISCV_GCC_PREFIX -DRISCV_TOOLCHAIN_BASENAME=$RISCV_GCC_NAME
cmake --build build -j8 -t $PROG
cmake --install build
cd -
