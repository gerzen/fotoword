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
    "dreamstime": ["filename", "title", "description", "keywords"],
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
