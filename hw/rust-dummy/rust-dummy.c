/*
 * virtmcu rust-dummy QOM device.
 * 
 * Demonstrates QEMU C/Rust interoperability. The QOM boilerplate is in C,
 * while the memory read/write callbacks call into Rust.
 *
 * SPDX-License-Identifier: GPL-2.0-or-later
 */

#include "qemu/osdep.h"
#include "hw/core/sysbus.h"
#include "hw/core/qdev-properties.h"
#include "qom/object.h"

/* Rust FFI declarations */
extern uint64_t rust_dummy_read(uint64_t addr, uint32_t size);
extern void rust_dummy_write(uint64_t addr, uint64_t val, uint32_t size);

#define TYPE_RUST_DUMMY "rust-dummy"
OBJECT_DECLARE_SIMPLE_TYPE(RustDummyState, RUST_DUMMY)

struct RustDummyState {
    SysBusDevice parent_obj;
    MemoryRegion iomem;
    uint64_t base_addr;
};

static uint64_t c_bridge_read(void *opaque, hwaddr addr, unsigned size)
{
    return rust_dummy_read(addr, size);
}

static void c_bridge_write(void *opaque, hwaddr addr, uint64_t val, unsigned size)
{
    rust_dummy_write(addr, val, size);
}

static const MemoryRegionOps rust_dummy_ops = {
    .read = c_bridge_read,
    .write = c_bridge_write,
    .endianness = DEVICE_LITTLE_ENDIAN,
    .impl = {
        .min_access_size = 1,
        .max_access_size = 8,
    },
};

static void rust_dummy_realize(DeviceState *dev, Error **errp)
{
    RustDummyState *s = RUST_DUMMY(dev);
    
    memory_region_init_io(&s->iomem, OBJECT(s), &rust_dummy_ops, s,
                          "rust-dummy-regs", 0x1000);
    sysbus_init_mmio(SYS_BUS_DEVICE(s), &s->iomem);

    if (s->base_addr != UINT64_MAX) {
        sysbus_mmio_map(SYS_BUS_DEVICE(s), 0, s->base_addr);
    }
}

static const Property rust_dummy_properties[] = {
    DEFINE_PROP_UINT64("base-addr", RustDummyState, base_addr, UINT64_MAX),
};

static void rust_dummy_class_init(ObjectClass *klass, const void *data)
{
    DeviceClass *dc = DEVICE_CLASS(klass);
    dc->realize = rust_dummy_realize;
    device_class_set_props(dc, rust_dummy_properties);
    dc->user_creatable = true;
}

static const TypeInfo rust_dummy_info = {
    .name          = TYPE_RUST_DUMMY,
    .parent        = TYPE_SYS_BUS_DEVICE,
    .instance_size = sizeof(RustDummyState),
    .class_init    = rust_dummy_class_init,
};

static void rust_dummy_register_types(void)
{
    type_register_static(&rust_dummy_info);
}

type_init(rust_dummy_register_types)
module_obj(TYPE_RUST_DUMMY);
