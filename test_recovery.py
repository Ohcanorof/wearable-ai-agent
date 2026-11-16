
# test_recovery.py
# Test backup recovery without spending API credits.

from unittest.mock import patch
from pathlib import Path
import tempfile

import main


def simulate_failure(device):
    raise RuntimeError("Simulated API failure")


def test_recovery():
    device = {
        "brand": "TestBrand",
        "model": "Test Model",
        "category": "Smartwatch",
    }

    with tempfile.TemporaryDirectory() as folder:
        # Redirect outputs into an isolated test folder.
        with patch.object(main, "DATA_DIR", Path(folder)):
            paths = main.get_file_paths(device)

            # Create an existing normalized file.
            original_text = '{"test": "original"}'
            paths["normalized"].write_text(
                original_text,
                encoding="utf-8",
            )

            # Replace the real API pipeline with a failure.
            with patch.object(
                main,
                "run_device_pipeline",
                side_effect=simulate_failure,
            ):
                try:
                    main.collect_device(
                        device,
                        overwrite=True,
                    )

                except RuntimeError:
                    pass

            # Confirm the original file was restored.
            restored = paths["normalized"].read_text(
                encoding="utf-8"
            )

            assert restored == original_text

    print("Recovery test passed!")


if __name__ == "__main__":
    test_recovery()
