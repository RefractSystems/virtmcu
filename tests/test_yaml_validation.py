import os
import subprocess
import tempfile
import unittest

import yaml


class TestYamlValidation(unittest.TestCase):
    def test_missing_peripheral_validation(self):
        """
        Tests that yaml2qemu fails if a peripheral in YAML is missing in the DTB.
        We simulate this by providing a YAML with a peripheral type that FdtEmitter skips.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_path = os.path.join(tmpdir, "test.yaml")
            dtb_path = os.path.join(tmpdir, "test.dtb")

            # Create a YAML with one valid peripheral and one 'Unknown' type which FdtEmitter skips
            test_yaml = {
                "machine": {"cpus": [{"name": "cpu0", "type": "cortex-a15"}]},
                "peripherals": [
                    {"name": "uart0", "type": "UART.PL011", "address": 0x10000000},
                    {
                        "name": "broken_dev",
                        "type": "UART.UnknownUART",  # FdtEmitter will skip this because of '.'
                        "address": 0x20000000,
                    },
                ],
            }

            with open(yaml_path, "w") as f:
                yaml.dump(test_yaml, f)

            # Run yaml2qemu
            # It should fail because 'broken_dev' will be missing in DTB
            cmd = ["python3", "-m", "tools.yaml2qemu", yaml_path, "--out-dtb", dtb_path]

            result = subprocess.run(cmd, capture_output=True, text=True)

            self.assertNotEqual(result.returncode, 0, "yaml2qemu should have failed")
            self.assertIn(
                "ERROR: The following peripherals from YAML are missing in the generated DTB: broken_dev", result.stderr
            )
            self.assertIn("FAILED: DTB validation failed.", result.stdout)

    def test_successful_validation(self):
        """
        Tests that yaml2qemu succeeds when all peripherals are correctly mapped.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            yaml_path = os.path.join(tmpdir, "test.yaml")
            dtb_path = os.path.join(tmpdir, "test.dtb")

            test_yaml = {
                "machine": {"cpus": [{"name": "cpu0", "type": "cortex-a15"}]},
                "peripherals": [{"name": "uart0", "type": "UART.PL011", "address": 0x10000000}],
            }

            with open(yaml_path, "w") as f:
                yaml.dump(test_yaml, f)

            cmd = ["python3", "-m", "tools.yaml2qemu", yaml_path, "--out-dtb", dtb_path]

            result = subprocess.run(cmd, capture_output=True, text=True)

            self.assertEqual(result.returncode, 0, f"yaml2qemu failed: {result.stderr}")
            self.assertIn("✓ Validation successful.", result.stdout)


if __name__ == "__main__":
    unittest.main()
