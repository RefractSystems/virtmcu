#!/bin/sh
# Generate trigger .c file for QEMU modules
OUT="$1"
OBJ="$2"
EXTRA_INC="$3"
EXTRA_C="$4"
shift 4

mkdir -p "$(dirname "$OUT")"
{
    echo '#include "qemu/osdep.h"'
    echo '#include "qemu/module.h"'
    if [ -n "$EXTRA_INC" ]; then echo "$EXTRA_INC"; fi
    if [ -n "$OBJ" ]; then echo "module_obj(\"$OBJ\");"; fi
    for o in "$@"; do
        echo "module_obj(\"$o\");"
    done
    if [ -n "$EXTRA_C" ]; then echo "$EXTRA_C"; fi
} > "$OUT"
