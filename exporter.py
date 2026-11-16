
# exporter.py
# pt 4 of this whole ai agent thing: validate normalized wearable data and export a draft CSV

import json
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from targets import CSV_COLUMNS, ALLOWED_CATEGORIES


#keep the first output labeled as a draft
OUTPUT_FILE = Path("data/wearable_specs_draft.csv")

"""this is similar to the pydantic model from normalizer.py, but we use it here to 
indipendently inspect a completed record before we export it."""
class WearableRecord(BaseModel):
    """Define the valid structure for one wearable record."""

    #reject missing required fields and unexpected columns
    model_config = ConfigDict(extra="forbid")

    Test_Date: date
    Device_Name: str = Field(min_length=1)
    Brand: str = Field(min_length=1)
    Model: str = Field(min_length=1)
    Category: str

    Price_USD: float | None = Field(ge=0, le=10000)
    Battery_Life_Hours: float | None = Field(ge=0, le=8760)

    Heart_Rate_Accuracy_Percent: float | None = Field(
        ge=0, le=100
    )

    Step_Count_Accuracy_Percent: float | None = Field(
        ge=0, le=100
    )

    Sleep_Tracking_Accuracy_Percent: float | None = Field(
        ge=0, le=100
    )

    Water_Resistance_Rating: str | None
    User_Satisfaction_Rating: float | None

    GPS_Accuracy_Meters: float | None = Field(ge=0)

    Connectivity_Features: str | None
    Health_Sensors_Count: int | None = Field(ge=0, le=100)
    App_Ecosystem_Support: str | None
    Performance_Score: float | None

    @field_validator(
        "Price_USD",
        "Battery_Life_Hours",
        "Heart_Rate_Accuracy_Percent",
        "Step_Count_Accuracy_Percent",
        "Sleep_Tracking_Accuracy_Percent",
        "User_Satisfaction_Rating",
        "GPS_Accuracy_Meters",
        "Health_Sensors_Count",
        "Performance_Score",
        mode="before",
    )
    @classmethod
    def reject_non_numeric_values(cls, value):
        """Reject strings and booleans in numeric columns."""

        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
        ):
            raise ValueError("Expected a number or null.")

        return value

    #custom checks, we can use stuff from targets.py instead of making another list again
    @field_validator("Category")
    @classmethod
    def validate_category(cls, value):
        """Ensure category matches our target definitions."""

        if value not in ALLOWED_CATEGORIES:
            raise ValueError(f"Invalid category: {value}")

        return value

    @model_validator(mode="after")
    def validate_device_name(self):
        """Ensure the device name matches its brand and model."""

        expected = f"{self.Brand} {self.Model}"

        if self.Device_Name != expected:
            raise ValueError(
                f"Expected Device_Name to be '{expected}'"
            )

        return self


def load_json(filepath):
    """Read one normalized record from a JSON file."""

    with open(filepath, "r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise ValueError("Expected one JSON device object.")

    return data

"""
checks if the supplied dictionary against WearableRecord, and returns
the validated vals as a dictionary ready for json compat output
"""
def validate_record(data):
    """Validate the record with our Pydantic schema."""

    record = WearableRecord.model_validate(data)

    #convert validated values back into a dictionary
    #json mode converts the date into YYYY-MM-DD
    return record.model_dump(mode="json")

#quality checks
def check_audit(input_path):
    """Warn if the matching source audit is not verified."""

    audit_path = input_path.with_name(
        input_path.name.replace(
            "_normalized.json",
            "_audit.json",
        )
    )

    if audit_path == input_path or not audit_path.exists():
        print("Warning: No matching audit file found.")
        return

    with open(audit_path, "r", encoding="utf-8") as file:
        audit = json.load(file)

    status = audit.get("review_status", "unknown")

    if status != "verified":
        print(
            f"Warning: Source review status is '{status}'."
        )
        print("The exported CSV is not fact-verified.")

"""
main Pandas functionality, pd.DataFrame() converts the python data into a table, where record 
is turned into rows, and then we start enforcing column order that was 
already defined in targets.py
"""
def export_csv(record, output_path=OUTPUT_FILE):
    """Export a validated record using our exact csv schema"""

    output_path = Path(output_path)

    #ensure the destination directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    #create a table containing our record
    dataframe = pd.DataFrame([record])

    #enforce the column order from targets.py
    dataframe = dataframe[CSV_COLUMNS]

    #write the CSV file
    dataframe.to_csv(
        output_path,
        index=False,
        na_rep="",
        encoding="utf-8-sig",
    )

    print(f"CSV saved to: {output_path}")
    print(f"Rows exported: {len(dataframe)}")
    print(f"Columns exported: {len(dataframe.columns)}")

    return dataframe


def main():
    """Load, validate, and export our normalized Garmin record."""

    #use the test device by default
    input_path = Path(
        sys.argv[1]
        if len(sys.argv) > 1
        else "data/garmin_forerunner_265_normalized.json"
    )

    if not input_path.is_file():
        raise FileNotFoundError(
            f"File not found: {input_path}"
        )

    print(f"Loading: {input_path}")

    #read the JSON
    data = load_json(input_path)

    #validate its structure and values
    try:
        record = validate_record(data)

    except ValidationError as error:
        print("Record failed validation:")
        print(error)
        raise

    print("Schema validation passed.")

    #check whether the evidence was reviewed
    check_audit(input_path)

    #create the CSV
    export_csv(record)


if __name__ == "__main__":
    main()
