
#main.py
#coordinate this wearable data pipeline
"""
operations for main.py
python main.py status : just checks pipeline status, like status, sources, if its been normalized,
has an audit file, and a csv file, 

python main.py export
loads previously reviewed json file, validates, and regenerates the draft csv file

python main.py collect
makes new Tavily and Gemini API requests then saves fresh json results
WILL OVERWRITE the existing garmin source, normalized, and audit files.
if any error was fixed manually, save a copy of it, because this 
will prompt the AI model again, so it can lead to the same mistake 
(it shoudlnt though, added a rule for this but double check anyways)

there is a test device used, the garmin, and now main.py is made so that
it doesnt have to be hardcoded. also uses persistent logging 

Any failures that are noted in the terminal might be because of the model being used,
if it is because of the model, just change it to another one or retry again.
"""

import argparse
import json
import shutil
import sys
import tempfile

from datetime import datetime, timezone
from pathlib import Path

from tavily import TavilyClient
from google import genai

import fetcher
import normalizer
import exporter

from targets import get_targets


# The device used when no selection is provided.
DEFAULT_DEVICE = "Garmin:Forerunner 265"

# Directory for pipeline output.
DATA_DIR = Path("data")

# Persistent log of device processing attempts.
LOG_FILE = DATA_DIR / "pipeline_log.jsonl"


def select_devices(device_names, select_all=False):
    """Find requested devices in our target list."""

    targets = get_targets()

    if select_all:
        return targets

    if not device_names:
        device_names = [DEFAULT_DEVICE]

    selected = []
    seen = set()

    for name in device_names:
        if ":" not in name:
            raise ValueError(
                f"Invalid device: {name}. Use Brand:Model."
            )

        brand, model = name.split(":", 1)

        match = next(
            (
                device for device in targets
                if device["brand"].casefold() == brand.strip().casefold()
                and device["model"].casefold() == model.strip().casefold()
            ),
            None,
        )

        if match is None:
            raise ValueError(
                f"Device not found in targets.py: {name}"
            )

        key = (match["brand"], match["model"])

        if key not in seen:
            selected.append(match)
            seen.add(key)

    return selected


def get_file_paths(device):
    """Generate the three output paths for a device."""

    brand = device["brand"].lower().replace(" ", "_")
    model = device["model"].lower().replace(" ", "_")

    prefix = f"{brand}_{model}"

    return {
        "sources": DATA_DIR / f"{prefix}_sources.json",
        "normalized": DATA_DIR / f"{prefix}_normalized.json",
        "audit": DATA_DIR / f"{prefix}_audit.json",
    }


def log_result(device, status, error=None):
    """Append one processing event to our JSONL log."""

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "brand": device["brand"],
        "model": device["model"],
        "status": status,
        "error": error,
    }

    with open(LOG_FILE, "a", encoding="utf-8") as file:
        file.write(json.dumps(event) + "\n")


def get_failed_devices():
    """Find devices whose most recent logged attempt failed."""

    if not LOG_FILE.exists():
        return []

    # Each device's latest event replaces its previous event.
    latest_status = {}

    with open(LOG_FILE, "r", encoding="utf-8") as file:
        for line in file:
            if not line.strip():
                continue

            event = json.loads(line)

            key = (
                event["brand"].casefold(),
                event["model"].casefold(),
            )

            latest_status[key] = event["status"]

    # Return failed devices that are still in targets.py.
    failed_devices = []

    for device in get_targets():
        key = (
            device["brand"].casefold(),
            device["model"].casefold(),
        )

        if latest_status.get(key) == "failed":
            failed_devices.append(device)

    return failed_devices


def run_device_pipeline(device):
    """Perform the existing fetch and normalization workflow."""

    if not fetcher.API_KEY:
        raise ValueError("Missing TAVILY_API_KEY")

    if not normalizer.API_KEY:
        raise ValueError("Missing GEMINI_API_KEY")

    # Step 1: Search manufacturer websites.
    tavily_client = TavilyClient(api_key=fetcher.API_KEY)

    sources = fetcher.search_device(
        device,
        tavily_client,
    )

    if not sources:
        raise ValueError("No official sources found.")

    # Step 2: Extract page contents.
    sources = fetcher.extract_pages(
        sources,
        tavily_client,
    )

    has_text = any(
        source.get("full_content") or source.get("snippet")
        for source in sources
    )

    if not has_text:
        raise ValueError("No usable source text returned.")

    # Step 3: Assemble the source record.
    source_data = {
        "brand": device["brand"],
        "model": device["model"],
        "category": device["category"],
        "query": fetcher.create_search_query(device),
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources,
    }

    # Step 4: Save the fetched evidence.
    fetcher.save_results(source_data)

    # Step 5: Extract specifications with Gemini.
    gemini_client = genai.Client(
        api_key=normalizer.API_KEY
    )

    try:
        specs = normalizer.extract_specs(
            source_data,
            gemini_client,
        )

        record = normalizer.build_record(
            source_data,
            specs,
        )

        # Validate the complete record before saving it.
        exporter.validate_record(record)

    finally:
        gemini_client.close()

    # Step 6: Save the normalized record and audit.
    normalizer.save_normalized_record(
        record,
        source_data,
    )


def collect_device(device, overwrite=False):
    """Process one device while protecting existing files."""

    paths = get_file_paths(device)
    device_name = f"{device['brand']} {device['model']}"

    print(f"\nProcessing: {device_name}")

    # Skip completed records unless explicitly requested.
    if paths["normalized"].exists() and not overwrite:
        print("SKIPPED: Normalized data already exists.")
        return "skipped"

    # TemporaryDirectory removes its backups automatically.
    with tempfile.TemporaryDirectory() as temp_folder:
        backup_folder = Path(temp_folder)

        # Record which files existed before this attempt.
        originals = {
            name: path.exists()
            for name, path in paths.items()
        }

        # Back up every existing file we might modify.
        for name, path in paths.items():
            if originals[name]:
                shutil.copy2(
                    path,
                    backup_folder / path.name,
                )

        try:
            # Run the existing data collection pipeline.
            run_device_pipeline(device)

        except Exception:
            # Restore files that existed before the run.
            for name, path in paths.items():
                if originals[name]:
                    shutil.copy2(
                        backup_folder / path.name,
                        path,
                    )

                elif path.exists():
                    # Remove newly created partial output.
                    path.unlink()

            raise

    print(f"SUCCESS: {device_name}")
    return "success"


def collect_batch(devices, overwrite=False):
    """Process multiple devices and log their outcomes."""

    results = {
        "success": [],
        "skipped": [],
        "failed": [],
    }

    for index, device in enumerate(devices, start=1):
        name = f"{device['brand']} {device['model']}"

        print(f"\n--- Device {index}/{len(devices)} ---")

        try:
            status = collect_device(
                device,
                overwrite=overwrite,
            )

            results[status].append(name)
            log_result(device, status)

        except Exception as error:
            results["failed"].append(name)

            print(f"FAILED: {name}")
            print(f"Reason: {error}")

            log_result(
                device,
                "failed",
                error=str(error),
            )

    print("\n=== Batch Summary ===")
    print(f"Selected: {len(devices)}")
    print(f"Successful: {len(results['success'])}")
    print(f"Skipped: {len(results['skipped'])}")
    print(f"Failed: {len(results['failed'])}")

    return results


def export_device(device):
    """Validate and export one saved device record."""

    paths = get_file_paths(device)

    if not paths["normalized"].is_file():
        raise FileNotFoundError(
            f"File not found: {paths['normalized']}"
        )

    data = exporter.load_json(paths["normalized"])
    record = exporter.validate_record(data)

    # Ensure the record corresponds to the intended device.
    if (
        record["Brand"] != device["brand"]
        or record["Model"] != device["model"]
        or record["Category"] != device["category"]
    ):
        raise ValueError(
            "Record does not match the selected target."
        )

    exporter.check_audit(paths["normalized"])
    exporter.export_csv(record)


def show_status(devices):
    """Show output files and their existence."""

    for device in devices:
        paths = get_file_paths(device)

        print(
            f"\nStatus: {device['brand']} {device['model']}"
        )

        for name, path in paths.items():
            status = "FOUND" if path.exists() else "MISSING"
            print(f"{name}: {status} ({path})")

    print(f"\nProcessing log: {LOG_FILE}")

    if LOG_FILE.exists():
        print("Log status: FOUND")
    else:
        print("Log status: MISSING")


def main():
    """Parse command-line options and run the pipeline."""

    parser = argparse.ArgumentParser(
        description="Wearable AI data pipeline"
    )

    parser.add_argument(
        "command",
        choices=["collect", "export", "status"],
    )

    parser.add_argument(
        "--device",
        action="append",
        help='Device formatted as "Brand:Model".',
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Select all devices from targets.py.",
    )

    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry devices whose latest logged attempt failed.",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace saved device data, with backup recovery.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview selection without API requests.",
    )

    args = parser.parse_args()

    # Prevent conflicting selection options.
    selection_count = sum([
        bool(args.device),
        args.all,
        args.retry_failed,
    ])

    if selection_count > 1:
        parser.error(
            "Choose --device, --all, or --retry-failed."
        )

    if args.retry_failed and args.command != "collect":
        parser.error("--retry-failed only supports collect.")

    if args.overwrite and args.command != "collect":
        parser.error("--overwrite only supports collect.")

    if args.retry_failed:
        devices = get_failed_devices()
    else:
        devices = select_devices(
            args.device,
            select_all=args.all,
        )

    if args.dry_run:
        print("\nSelected devices:")

        for device in devices:
            print(f"- {device['brand']} {device['model']}")

        print(f"Total: {len(devices)}")
        return

    if args.command == "collect":
        # Retry failed devices even if old files still exist.
        overwrite = args.overwrite or args.retry_failed

        if not devices:
            print("No devices selected for collection.")
            return

        results = collect_batch(
            devices,
            overwrite=overwrite,
        )

        if results["failed"]:
            sys.exit(1)

    elif args.command == "export":
        if len(devices) != 1:
            parser.error(
                "Batch CSV export comes in Module 6.3."
            )

        export_device(devices[0])

    elif args.command == "status":
        show_status(devices)


if __name__ == "__main__":
    main()

