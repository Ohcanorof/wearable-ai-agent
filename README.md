# Wearable AI Data Collection Pipeline

A lightweight, modular Python pipeline that collects technical specifications for wearable devices using web search, AI powered extraction, and structured data validation.

## Features

- Targeted research across six wearable technology brands
- Manufacturer-domain filtering and webpage extraction using Tavily
- Structured specification extraction using Google Gemini
- Pydantic validation for numerical values and data consistency
- Multi-device batch processing with error logging and retry support
- CSV export with 17 standardized fields
- Dataset quality reporting and missing-value analysis

## Tech Stack

Python, Tavily API, Google Gemini API, Pydantic, Pandas, and python-dotenv.

## How to Run

1. Install dependencies from `requirements.txt`.
2. Create a `.env` file containing `TAVILY_API_KEY` and `GEMINI_API_KEY`.
3. Run the following commands:

```powershell
python main.py collect --all
python consolidate.py --all
```

## Outputs

- `wearable_specs_draft.csv`: Consolidated wearable specifications
- `quality_report.json`: Dataset completeness and coverage
- Device-specific JSON files: Source evidence and normalized records
- `pipeline_log.jsonl`: Processing history

## Current Limitations

- Manufacturer specifications may omit independent accuracy measurements.
- Prices, user satisfaction ratings, and performance scores require additional research or a consistent methodology.
- Extracted data requires source verification before use in formal research.
- Temporary LLM API capacity issues can interrupt processing.

## Future Improvements

- Add targeted retrieval for pricing and independent benchmark studies.
- Implement more efficient API retries and cached normalization.
- Expand coverage to approximately 24–36 devices.
- Introduce field-level source citations and verification.
- Improve testing and data-quality reports.
