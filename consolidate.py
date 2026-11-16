
#consolidate.py
#combine validated device data and report quality

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

import exporter
from main import get_file_paths
from targets import get_targets, CSV_COLUMNS


#final draft outputs
DATA_DIR = Path("data")
CSV_OUTPUT = DATA_DIR / "wearable_specs_draft.csv"
REPORT_OUTPUT = DATA_DIR / "quality_report.json"

#the first five fields describe the target device
#the remaining twelve are the specifications we evaluate
SPEC_COLUMNS = CSV_COLUMNS[5:]


def load_device_record(device):
    """Load one device's normalized JSON and validate it."""

    paths = get_file_paths(device)
    normalized_path = paths["normalized"]

    if not normalized_path.is_file():
        return None, "missing", "No normalized JSON file."

    try:
        # Reuse Module 4 instead of writing new validation
        data = exporter.load_json(normalized_path)
        record = exporter.validate_record(data)

        # Verify that this file contains the expected device
        if (
            record["Brand"] != device["brand"]
            or record["Model"] != device["model"]
            or record["Category"] != device["category"]
        ):
            raise ValueError(
                "Record identity does not match the target."
            )

        return record, "valid", None

    except (ValueError, OSError) as error:
        return None, "invalid", str(error)


def get_audit_status(device):
    """Read the review status for a device's sources."""

    paths = get_file_paths(device)
    audit_path = paths["audit"]

    if not audit_path.is_file():
        return "missing"

    try:
        with open(audit_path, "r", encoding="utf-8") as file:
            audit = json.load(file)

        if not isinstance(audit, dict):
            return "invalid"

        expected_name = f"{device['brand']} {device['model']}"

        if audit.get("device_name") != expected_name:
            return "identity_mismatch"

        return audit.get("review_status", "unknown")

    except (OSError, ValueError):
        return "invalid"


def collect_records(devices):
    """Collect all valid records and record missing/invalid ones."""

    records = []
    device_results = []

    for device in devices:
        name = f"{device['brand']} {device['model']}"

        record, status, error = load_device_record(device)

        audit_status = get_audit_status(device)

        result = {
            "device": name,
            "status": status,
            "audit_status": audit_status,
            "error": error,
        }

        if record is not None:
            records.append(record)

            print(f"VALID: {name}")

        else:
            print(f"{status.upper()}: {name}")

        device_results.append(result)

    return records, device_results


def calculate_completeness(records):
    """Calculate how complete the specification fields are."""

    completeness = {}

    total = len(records)

    for column in SPEC_COLUMNS:
        # Count records where the value is not missing
        populated = sum(
            record[column] is not None
            and record[column] != ""
            for record in records
        )

        missing = total - populated

        percent = (
            round(populated / total * 100, 2)
            if total > 0
            else 0.0
        )

        completeness[column] = {
            "populated": populated,
            "missing": missing,
            "completeness_percent": percent,
        }

    return completeness


def build_quality_report(devices, records, device_results):
    """Build a summary of dataset quality and coverage."""

    valid_count = sum(
        item["status"] == "valid"
        for item in device_results
    )

    missing_count = sum(
        item["status"] == "missing"
        for item in device_results
    )

    invalid_count = sum(
        item["status"] == "invalid"
        for item in device_results
    )

    verified_count = sum(
        item["status"] == "valid"
        and item["audit_status"] == "verified"
        for item in device_results
    )

    report = {
        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),

        "target_devices": len(devices),
        "valid_records": valid_count,
        "missing_records": missing_count,
        "invalid_records": invalid_count,
        "records_with_verified_audit": verified_count,

        "record_coverage_percent": round(
            valid_count / len(devices) * 100, 2
        ) if devices else 0.0,

        "field_completeness": calculate_completeness(records),
        "device_results": device_results,
    }

    return report


def save_outputs(records, report):
    """Save the combined CSV and quality report."""

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not records:
        print("No valid records found. CSV was not generated.")
    else:
        #convert all validated records into one DataFrame
        dataframe = pd.DataFrame(records)

        #enforce the original 17-column schema.
        dataframe = dataframe[CSV_COLUMNS]

        #save a CSV with empty cells for unknown values
        dataframe.to_csv(
            CSV_OUTPUT,
            index=False,
            na_rep="",
            encoding="utf-8-sig",
        )

        print(f"\nCSV saved to: {CSV_OUTPUT}")
        print(f"Rows: {len(dataframe)}")
        print(f"Columns: {len(dataframe.columns)}")

    #save the quality report separately
    with open(REPORT_OUTPUT, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=4, ensure_ascii=False)

    print(f"Quality report saved to: {REPORT_OUTPUT}")


def print_summary(report):
    """Display the most useful quality metrics."""

    print("\n=== Dataset Quality Summary ===")

    print(f"Targets: {report['target_devices']}")
    print(f"Valid: {report['valid_records']}")
    print(f"Missing: {report['missing_records']}")
    print(f"Invalid: {report['invalid_records']}")
    print(
        f"Records with verified audits: "
        f"{report['records_with_verified_audit']}"
    )

    print(
        f"Record coverage: "
        f"{report['record_coverage_percent']}%"
    )

    print("\nField completeness:")

    for field, stats in report["field_completeness"].items():
        print(
            f"{field}: "
            f"{stats['populated']}/{report['valid_records']} "
            f"({stats['completeness_percent']}%)"
        )


def main():
    """Run consolidation for collected target devices."""

    parser = argparse.ArgumentParser(
        description="Consolidate wearable specification records."
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Include all targets, including missing devices.",
    )

    args = parser.parse_args()

    targets = get_targets()

    #all existing records are considered in either mode
    # --all additionally reports the full target coverage
    if args.all:
        devices = targets
    else:
        devices = [
            device for device in targets
            if get_file_paths(device)["normalized"].is_file()
        ]

    if not devices:
        print("No collected device records found.")
        return

    #load and validate device records
    records, device_results = collect_records(devices)

    #calculate dataset quality statistics
    report = build_quality_report(
        devices,
        records,
        device_results,
    )

    #save CSV and quality report
    save_outputs(records, report)

    #display a summary in the terminal
    print_summary(report)


if __name__ == "__main__":
    main()
