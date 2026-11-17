#!/bin/sh
# Compile resize.cpp to resize.wasm. Needs clang with the wasm32 target and wasm-ld.
set -e
cd "$(dirname "$0")"
clang++ --target=wasm32 -O3 -ffreestanding -fno-exceptions -fno-rtti -nostdlib \
  -Wl,--no-entry -Wl,--export-memory -Wl,--initial-memory=1048576 -Wl,--max-memory=1073741824 -Wl,--strip-all \
  resize.cpp -o resize.wasm
ls -l resize.wasm
