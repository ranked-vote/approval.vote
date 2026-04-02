# St. Louis Cast Vote Record Parser

A high-performance Python script to parse St. Louis Cast Vote Record (CVR) Hart Verity XML files and store them in SQLite database for analysis.

## Features

- **High Performance**: Processes 1,500+ files per second using optimized batching
- **Robust Error Handling**: Gracefully handles malformed XML files and missing elements
- **Progress Tracking**: Real-time progress bar with processing statistics
- **SQLite Storage**: Efficiently stores data in normalized SQLite tables with proper indexing
- **Memory Efficient**: Uses batched processing to handle hundreds of thousands of files

## Installation

This project uses [uv](https://docs.astral.sh/uv/) for dependency management:

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync
```

## Usage

### 🚀 One-Shot Processing (Recommended)

**Process everything from zip files to website database in one command:**

```bash
# Complete processing: unzip → parse → analyze → export
uv run python process_all.py
```

This script automatically:

- ✅ Unzips all `.zip` files in `./data/` directory
- ✅ Parses all CVR XML files into `cvr-data.sqlite3`
- ✅ Generates co-approval analysis for **ALL contests**
- ✅ Exports to main `../../data.sqlite3` with automatic name mapping
- ✅ **Fully idempotent** - safe to re-run

### 📊 Manual Processing (Advanced)

```bash
# Basic usage (processes ./data/, outputs to cvr-data.sqlite3 in current directory)
uv run python cvr_parser.py

# Specify custom directories and options
uv run python cvr_parser.py --data-dir data --output my-results.sqlite3 --batch-size 2000 --verbose

# Get help
uv run python cvr_parser.py --help
```

## Command Line Options

- `--data-dir, -d`: Directory containing CVR XML files (default: `data`)
- `--output, -o`: Output SQLite database file (default: `cvr-data.sqlite3`)
- `--batch-size, -b`: Batch size for database operations (default: 5000)
- `--verbose, -v`: Enable verbose logging

## File Structure

### 🗂️ **Standardized File Naming:**

- `./data/*.zip` → ZIP files (auto-unzipped)
- `./cvr-data.sqlite3` → Processed CVR database (standardized name)
- `../data.sqlite3` → Main website database

### 🔄 **Automatic Contest Mapping:**

Contest names are automatically normalized:

- `"MAYOR"` → `"mayor"`
- `"COMPTROLLER"` → `"comptroller"`
- `"ALDERMAN - WARD 3"` → `"alderman-ward3"`
- `"ALDERMAN - WARD 11"` → `"alderman-ward11"`

**Algorithm:** `contest_name.lower().replace(' - ', '-').replace(' ', '')`

## Database Schema

The parser creates three normalized tables:

### `cvr_ballots`

- `id`: Primary key
- `cvr_guid`: Unique ballot identifier
- `batch_sequence`, `sheet_number`: Processing metadata
- `precinct_name`, `precinct_id`: Precinct information
- `is_blank`: Whether the ballot is blank
- `created_at`: Timestamp when processed

### `cvr_contests`

- `id`: Primary key
- `ballot_id`: Foreign key to `cvr_ballots`
- `contest_name`, `contest_id`: Contest information
- `undervotes`: Number of undervotes in this contest

### `cvr_selections`

- `id`: Primary key
- `contest_record_id`: Foreign key to `cvr_contests`
- `candidate_name`, `candidate_id`: Candidate information
- `selection_value`: Vote value (typically 1 for approval voting)

## Performance Optimizations

- **WAL Mode**: Uses SQLite's Write-Ahead Logging for better concurrent performance
- **Bulk Inserts**: Batches database operations for maximum throughput
- **Proper Indexing**: Automatically creates indexes for common query patterns
- **Memory Tuning**: Configures SQLite cache and memory settings for optimal performance
- **Error Recovery**: Continues processing even if individual files fail

## Example Output

```text
Processing CVR files: 100%|█████| 50/50 [00:00<00:00, 1508.20files/s]

============================================================
PROCESSING SUMMARY
============================================================
Files processed: 50
Errors: 0
Processing time: 0.03 seconds
Average rate: 1508.20 files/second

DATABASE STATISTICS
------------------------------
Total ballots: 50
Total contests: 102
Total selections: 130

TOP 10 PRECINCTS
------------------------------
Ward 02 Precinct 05: 4 ballots
Ward 10 Precinct 01: 3 ballots
...
```

## Data Directory Structure

```text
cvr/st-louis/
├── data/                  # CVR XML files
│   ├── 1_00a3fa66-...xml
│   └── ...
├── cvr_parser.py         # Main parser script
├── pyproject.toml        # Dependencies
└── README.md            # This file
```

## Co-Approval Analysis

The `process_all.py` script handles all analysis automatically, but if you need manual control:

```bash
# For manual processing only (not needed with process_all.py)
# This generates and exports all analysis in one step
uv run python process_all.py
```

This creates:

- **Co-Approval Matrix**: Shows how often voters who approved one candidate also approved another
- **Voting Patterns**: Analysis of ballot completion patterns (single vs. multiple approvals)
- **Approval Distribution**: Histogram of how many candidates voters approved

## Integration with Approval.Vote

The processed data integrates with the main [approval.vote](https://approval.vote) website, providing:

- **Interactive Co-Approval Matrix**: Hover tooltips with detailed voter statistics
- **Approval Distribution Charts**: Visual breakdown of voting patterns
- **Ranked.vote-style Design**: Professional tooltips using Tippy.js
- **Green Color Scheme**: Consistent with approval voting branding

The analysis reveals strategic voting patterns and candidate coalitions in approval voting elections.

## License

This project follows the same license as the main approval.vote project.
