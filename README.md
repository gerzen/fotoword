# FotoWord

Local Python CLI for generating stock-photo metadata from JPGs using a local Ollama vision model.

## Features
- Scans a folder for `.jpg` / `.jpeg` files (optional recursive mode)
- Uses local Ollama (`llava:7b` by default) to generate:
  - title
  - description
  - keywords
- Enriches prompts with EXIF metadata and IPTC metadata (if available)
- Writes append-only platform CSVs:
  - `adobe.csv`
  - `dreamstime.csv`
  - `shutterstock.csv`
- Skip-existing mode enabled by default (based on existing `filename` values in output CSVs)

## Requirements
- Python 3.9+
- Ollama running locally (`http://localhost:11434`)
- Vision model pulled, e.g.:

```bash
ollama pull llava:7b
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

```bash
python fotoword.py --input /path/to/jpgs --out /path/to/out
```

### CLI Flags
- `--input` (required): directory with JPG/JPEG files
- `--out` (optional, default `./out`): output directory for CSVs
- `--model` (optional, default `llava:7b`): Ollama model name
- `--keywords` (optional, default `40`): target number of keywords
- `--skip-existing` (default true): skip filenames already present in output CSVs
- `--no-skip-existing`: disable skipping
- `--config` (optional, default `config/defaults.json`): config path
- `--recursive` (optional): recurse into subdirectories
- `--dry-run` (optional): print files to process and exit

## Default Config
`config/defaults.json`:

```json
{
  "ollama_url": "http://localhost:11434",
  "platforms": {
    "adobe": ["Filename", "Title", "Keywords", "Category"],
    "dreamstime": [
      "Filename",
      "Image Name",
      "Description",
      "Category 1",
      "Category 2",
      "Category 3",
      "keywords",
      "Free",
      "W-EL",
      "P-EL",
      "SR-EL",
      "SR-Price",
      "Editorial",
      "MR doc Ids",
      "Pr Docs"
    ],
    "shutterstock": ["Filename", "Description", "Keywords", "Categories"]
  }
}
```

Each platform gets its own CSV, and header order is controlled by this config.
Adobe-specific mapping in current defaults:
- `Filename` <- generated filename
- `Title` <- generated description
- `Keywords` <- generated keywords
- `Category` <- generated Adobe category number (`1-21`)
Shutterstock-specific mapping in current defaults:
- `Filename` <- generated filename
- `Description` <- generated description
- `Keywords` <- generated keywords (comma-separated)
- `Categories` <- 1-2 Shutterstock categories (comma-separated)
Dreamstime-specific mapping in current defaults:
- Uses official `Image_spreadsheet_template.xls` column order.
- `Filename`, `Image Name`, `Description`, and `keywords` are filled from generated metadata.
- `Category 1/2/3` currently default to `0` (no category selected yet).
- Licensing/editorial flags default to `0`; document ID fields remain empty.

## Behavior Notes
- Only `.jpg` and `.jpeg` files are processed.
- `filename` column uses file basename only, not full path.
- Keywords are normalized to lowercase, deduplicated, and capped to `--keywords`.
- Descriptions are built in a fixed structure: subject(s) + activity + location type + environment + daytime + mood + purposes, then constrained to 175-200 characters.
- If model output is invalid JSON, the tool retries once.
- If Ollama is unreachable, the tool exits before writing CSV rows.
- Failures on individual files are logged and processing continues.

## Example

```bash
python fotoword.py \
  --input ./photos \
  --out ./out \
  --model llava:7b \
  --keywords 40 \
  --recursive
```
