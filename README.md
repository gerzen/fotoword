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
- Writes central `metadata.tsv` used as source of truth with columns:
  `filename,title,description,keywords,category`
  using tab delimiter for spreadsheet-friendly import.
- Skip-existing mode enabled by default (based on existing `filename` values in `metadata.tsv`)

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

Run in current folder (auto-scans `.` and writes to `./out`):

```bash
python ./fotoword.py
```

Install `fotoword` command for direct terminal use:

```bash
mkdir -p ~/.local/bin
ln -sf "$(pwd)/fotoword" ~/.local/bin/fotoword
```

Then ensure `~/.local/bin` is on your `PATH`, and run inside any picture folder:

```bash
fotoword
```

### CLI Flags
- `--input` (optional, default `.`): directory with JPG/JPEG files
- `--out` (optional, default `<input>/out`): output directory for CSVs
- `--model` (optional, default `llava:7b`): Ollama model name
- `--keywords` (optional, default `50`): target number of keywords
- `--analysis-max-side` (optional, default `1536`): max width/height for resized analysis copy sent to model
- `--skip-existing` (default true): skip filenames already present in `metadata.tsv`
- `--no-skip-existing`: disable skipping
- `--config` (optional, default bundled `config/defaults.json`): config path
- `--recursive` (optional): recurse into subdirectories
- `--dry-run` (optional): print files to process and exit

## Default Config
`config/defaults.json`:

```json
{
  "ollama_url": "http://localhost:11434",
  "agencies_dir": "agencies",
  "agencies": ["adobe", "dreamstime", "shutterstock"]
}
```

Each agency gets its own CSV, and header order is controlled by `config/agencies/<agency>.json`.
Legacy config format with top-level `platforms` is still supported.
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
- `keywords` are exported as unique single-word terms only (max 50).
- `Category 1/2/3` are auto-assigned numeric IDs based on the Dreamstime `Image Legend` category list (up to 3 IDs).
- `Editorial` is set to `1` for `_ED` images and `0` otherwise; other licensing flags default to `0`, and document ID fields remain empty.
- Shutterstock exports include an `Editorial` column set to `yes` for `_ED` images and `no` otherwise.

## Behavior Notes
- Only `.jpg` and `.jpeg` files are processed.
- `filename` column uses file basename only, not full path.
- Large images are resized to an analysis copy (max side `--analysis-max-side`) before sending to Ollama; originals are untouched.
- Keywords are normalized to lowercase, deduplicated, and capped to `--keywords`.
- To re-run recognition for a specific image, remove its row from `out/metadata.tsv` and run `fotoword` again.
- If a filename already exists in `metadata.tsv`, `fotoword` reuses that metadata and rebuilds agency CSVs from it.
- You can edit the `keywords` column in `metadata.tsv` and rerun `fotoword` to update agency CSV outputs without re-running model inference.
- Keywords use a 3-pass pipeline: pass1 generates 10 strong unique single words, pass2 adds emotional/creative terms excluding pass1 words (and retries if pass2 yields fewer than 15), and pass3 adds sensory terms (colors/sounds/scents) if still below target.
- Filenames ending in `_CO` are treated as commercial images; filenames ending in `_ED` are treated as editorial images. Other filenames default to commercial handling.
- Commercial descriptions are built in a fixed structure: subject(s) + activity + location type + environment + daytime + mood + purposes. `metadata.tsv` keeps the full description; if the text would overflow 750 characters, it is shortened at the last comma before the limit for Adobe/Dreamstime exports and the removed tail is preserved in parentheses in the full metadata/Shutterstock version.
- Editorial descriptions follow this template: `City, Country - Month DD, YYYY. IPTC Title. Model Description.` The city, country, and title come from IPTC metadata, the date comes from image metadata, and the model is prompted with the remaining character budget so the final description stays within 750 characters.
- If model output is invalid JSON, the tool retries once.
- If Ollama is unreachable, the tool exits before writing CSV rows.
- Failures on individual files are logged and processing continues.

## Project Structure
- `fotoword.py`: thin entrypoint
- `fotoword_app/cli.py`: CLI parsing and run orchestration
- `fotoword_app/engine.py`: shared image/model/CSV processing
- `fotoword_app/config.py`: config loading and validation
- `fotoword_app/agencies/`: agency-specific rules and row builders
- `config/agencies/*.json`: per-agency output column config

## Example

```bash
python fotoword.py \
  --input ./photos \
  --out ./out \
  --model llava:7b \
  --keywords 50 \
  --recursive
```
