#!/bin/bash

set -e

if [ "$#" -gt 2 ]; then
    echo "Illegal number of parameters!"
    echo "Usage: $0 [PROG] [ETISS_ARCH]"
    exit 1
fi

PROG=${1:-hello_world}
ETISS_ARCH=${2:-RV32IMACFD}
# TODO: how about 64-bit core?

./install/etiss/bin/bare_etiss_processor -ietiss_riscv_examples/build/install/ini/$PROG.ini --arch.cpu=$ETISS_ARCH
