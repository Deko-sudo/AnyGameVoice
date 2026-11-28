#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

if ! command -v wasm-bindgen >/dev/null 2>&1; then
  printf '%s\n' 'Install wasm-bindgen-cli 0.2.125 to build the Rust UI.' >&2
  exit 1
fi
if [ "$(wasm-bindgen --version)" != 'wasm-bindgen 0.2.125' ]; then
  printf '%s\n' 'The Rust UI requires wasm-bindgen-cli 0.2.125.' >&2
  exit 1
fi
cargo build --locked --manifest-path ui-rust/Cargo.toml --target wasm32-unknown-unknown --release
wasm-bindgen --target web --no-typescript --out-dir ui/rust-ui --out-name anygamevoice_ui \
  ui-rust/target/wasm32-unknown-unknown/release/anygamevoice_ui.wasm
