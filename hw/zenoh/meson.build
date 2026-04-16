zenoh_dir = meson.project_source_root() / '../zenoh-c'
zenoh_lib = cc.find_library('zenohc', dirs: zenoh_dir / 'lib')
zenoh_dep = declare_dependency(
  dependencies: zenoh_lib,
  compile_args: ['-I' + zenoh_dir / 'include']
)

flatcc_dir = meson.project_source_root() / '../flatcc'
flatcc_lib = cc.find_library('flatccrt', dirs: flatcc_dir / 'lib')
flatcc_dep = declare_dependency(
  dependencies: flatcc_lib,
  compile_args: ['-I' + flatcc_dir / 'include']
)

telemetry_fbs = files('telemetry.fbs')
telemetry_h = custom_target('telemetry_fbs',
  input: telemetry_fbs,
  output: ['telemetry_builder.h', 'telemetry_reader.h'],
  command: [flatcc_dir / 'bin/flatcc', '-a', '-o', '@OUTDIR@', '@INPUT@']
)

zenoh_clock_ss = ss.source_set()
zenoh_clock_ss.add(files('zenoh-clock.c', 'zenoh-netdev.c', 'zenoh-chardev.c', 'zenoh-actuator.c', 'zenoh-telemetry.c'))
zenoh_clock_ss.add(zenoh_dep, flatcc_dep)
zenoh_clock_ss.add(telemetry_h)
hw_virtmcu_modules += {'zenoh': zenoh_clock_ss}
