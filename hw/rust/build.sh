#!/usr/bin/env bash
set -euo pipefail

# $1: rust source dir (hw/rust)
# $2: target dir (hw/target or similar)
# $3: out dir (where .a files should go)
# rest: pairs of "package-name:libname.a"

RUST_DIR="$1"
TARGET_DIR="$2"
OUT_DIR="$3"
shift 3

cd "$RUST_DIR"

if command -v lld >/dev/null 2>&1; then
    export RUSTFLAGS="${RUSTFLAGS:-} -C link-arg=-fuse-ld=lld"
fi

if [ "$VIRTMCU_USE_ASAN" = "1" ]; then
    export RUSTFLAGS="${RUSTFLAGS:-} -C link-arg=-fsanitize=address -C link-arg=-fsanitize=undefined"
fi

echo "Building Rust workspace in $RUST_DIR with target-dir $TARGET_DIR"
cargo build --release --workspace --target-dir "$TARGET_DIR" -j1

for pair in "$@"; do
    _pkg="${pair%%:*}"
    lib="${pair#*:}"
    echo "Copying $TARGET_DIR/release/$lib to $OUT_DIR/$lib"
    cp "$TARGET_DIR/release/$lib" "$OUT_DIR/$lib"
done

echo "Listing outputs in $OUT_DIR:"
ls -lh "$OUT_DIR"/*.a
