#!/usr/bin/env python3
"""
St. Louis Cast Vote Record (CVR) Parser

Parses XML CVR files and stores them in SQLite database with optimizations
for processing hundreds of thousands of files.
"""

import logging
import sqlite3
import time
import xml.etree.ElementTree as ET  # nosec B405 - Trusted election data
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Optional

import click
from tqdm import tqdm

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class CvrParser:
    """High-performance CVR XML parser with SQLite storage."""

    def __init__(self, db_path: str, batch_size: int = 5000):
        self.db_path = Path(db_path)
        self.batch_size = batch_size
        self.processed = 0
        self.errors = 0
        self.start_time = time.time()

        # Batch storage for bulk inserts
        self.ballot_batch = []
        self.contest_batch = []
        self.selection_batch = []

        # Statistics tracking
        self.stats = {
            "precincts": defaultdict(int),
            "contests": defaultdict(int),
            "candidates": defaultdict(int),
        }

        self.setup_database()

    def setup_database(self) -> None:
        """Initialize database with optimized settings and schema."""
        logger.info(f"Setting up database: {self.db_path}")

        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = -64000")  # 64MB cache
        conn.execute("PRAGMA temp_store = memory")
        conn.execute("PRAGMA mmap_size = 268435456")  # 256MB mmap

        # Create tables
        conn.executescript(
            """
        CREATE TABLE IF NOT EXISTS cvr_ballots (
            id INTEGER PRIMARY KEY,
            cvr_guid TEXT UNIQUE NOT NULL,
            batch_sequence INTEGER,
            sheet_number INTEGER,
            precinct_name TEXT,
            precinct_id TEXT,
            is_blank BOOLEAN,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS cvr_contests (
            id INTEGER PRIMARY KEY,
            ballot_id INTEGER,
            contest_name TEXT NOT NULL,
            contest_id TEXT NOT NULL,
            undervotes INTEGER,
            FOREIGN KEY(ballot_id) REFERENCES cvr_ballots(id)
        );
        
        CREATE TABLE IF NOT EXISTS cvr_selections (
            id INTEGER PRIMARY KEY,
            contest_record_id INTEGER,
            candidate_name TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            selection_value INTEGER,
            FOREIGN KEY(contest_record_id) REFERENCES cvr_contests(id)
        );
        
        -- Create indexes for better query performance
        CREATE INDEX IF NOT EXISTS idx_cvr_guid ON cvr_ballots(cvr_guid);
        CREATE INDEX IF NOT EXISTS idx_precinct ON cvr_ballots(precinct_id);
        CREATE INDEX IF NOT EXISTS idx_contest ON cvr_contests(contest_id);
        CREATE INDEX IF NOT EXISTS idx_ballot_contest ON cvr_contests(ballot_id, contest_id);
        CREATE INDEX IF NOT EXISTS idx_candidate ON cvr_selections(candidate_id);
        CREATE INDEX IF NOT EXISTS idx_contest_selection ON cvr_selections(contest_record_id, candidate_id);
        """
        )

        conn.commit()
        conn.close()

    def parse_xml_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Parse a single CVR XML file and return structured data."""
        try:
            tree = ET.parse(file_path)  # nosec B314 - Trusted election data
            root = tree.getroot()

            # Handle namespace
            ns = (
                {"cvr": "http://tempuri.org/CVRDesign.xsd"}
                if root.tag.startswith("{")
                else {}
            )

            def find_with_ns(element, tag):
                """Find element with or without namespace."""
                if ns:
                    return element.find(f"cvr:{tag}", ns)
                else:
                    return element.find(tag)

            def findall_with_ns(element, tag):
                """Find all elements with or without namespace."""
                if ns:
                    return element.findall(f"cvr:{tag}", ns)
                else:
                    return element.findall(tag)

            # Extract ballot information
            cvr_guid = find_with_ns(root, "CvrGuid").text
            batch_sequence = int(find_with_ns(root, "BatchSequence").text)
            sheet_number = int(find_with_ns(root, "SheetNumber").text)
            is_blank = find_with_ns(root, "IsBlank").text.lower() == "true"

            precinct_split = find_with_ns(root, "PrecinctSplit")
            precinct_name = find_with_ns(precinct_split, "Name").text
            precinct_id = find_with_ns(precinct_split, "Id").text

            # Extract contests and selections
            contests_elem = find_with_ns(root, "Contests")
            contests = []

            for contest_elem in findall_with_ns(contests_elem, "Contest"):
                contest_name = find_with_ns(contest_elem, "Name").text
                contest_id = find_with_ns(contest_elem, "Id").text
                undervotes_elem = find_with_ns(contest_elem, "Undervotes")
                undervotes = (
                    int(undervotes_elem.text) if undervotes_elem is not None else 0
                )

                # Extract options/selections
                options_elem = find_with_ns(contest_elem, "Options")
                selections = []

                if options_elem is not None:
                    for option_elem in findall_with_ns(options_elem, "Option"):
                        candidate_name = find_with_ns(option_elem, "Name").text
                        candidate_id = find_with_ns(option_elem, "Id").text
                        selection_value = int(find_with_ns(option_elem, "Value").text)

                        selections.append(
                            {
                                "candidate_name": candidate_name,
                                "candidate_id": candidate_id,
                                "selection_value": selection_value,
                            }
                        )

                contests.append(
                    {
                        "contest_name": contest_name,
                        "contest_id": contest_id,
                        "undervotes": undervotes,
                        "selections": selections,
                    }
                )

            return {
                "cvr_guid": cvr_guid,
                "batch_sequence": batch_sequence,
                "sheet_number": sheet_number,
                "precinct_name": precinct_name,
                "precinct_id": precinct_id,
                "is_blank": is_blank,
                "contests": contests,
            }

        except Exception as e:
            self.errors += 1
            logger.error(f"Error parsing {file_path}: {e}")
            return None

    def add_to_batch(self, ballot_data: Dict[str, Any]) -> None:
        """Add parsed ballot data to batch for bulk insert."""
        # Add ballot record
        ballot_record = (
            ballot_data["cvr_guid"],
            ballot_data["batch_sequence"],
            ballot_data["sheet_number"],
            ballot_data["precinct_name"],
            ballot_data["precinct_id"],
            ballot_data["is_blank"],
        )
        self.ballot_batch.append(ballot_record)

        # Track statistics
        self.stats["precincts"][ballot_data["precinct_name"]] += 1

        # Add contests and selections (we'll handle relationships after ballot insert)
        ballot_index = len(self.ballot_batch) - 1

        for contest in ballot_data["contests"]:
            self.stats["contests"][contest["contest_name"]] += 1

            contest_record = (
                ballot_index,  # Will be replaced with actual ballot_id after insert
                contest["contest_name"],
                contest["contest_id"],
                contest["undervotes"],
            )
            contest_index = len(self.contest_batch)
            self.contest_batch.append(contest_record)

            for selection in contest["selections"]:
                self.stats["candidates"][selection["candidate_name"]] += 1

                selection_record = (
                    contest_index,  # Will be replaced with actual contest_record_id
                    selection["candidate_name"],
                    selection["candidate_id"],
                    selection["selection_value"],
                )
                self.selection_batch.append(selection_record)

    def flush_batch(self) -> None:
        """Write current batch to database."""
        if not self.ballot_batch:
            return

        conn = sqlite3.connect(self.db_path)
        conn.execute("BEGIN TRANSACTION")

        try:
            # Insert ballots and track which ones were actually inserted
            cursor = conn.executemany(
                "INSERT OR IGNORE INTO cvr_ballots (cvr_guid, batch_sequence, sheet_number, precinct_name, precinct_id, is_blank) VALUES (?, ?, ?, ?, ?, ?)",
                self.ballot_batch,
            )

            # Only process contests/selections for newly inserted ballots
            if cursor.rowcount == 0:
                # No new ballots were inserted, skip contest/selection processing
                return

            # Get mapping of cvr_guid to ballot_id for newly inserted ballots
            guid_to_ballot_id = {}
            for ballot_record in self.ballot_batch:
                cvr_guid = ballot_record[0]
                result = conn.execute(
                    "SELECT id FROM cvr_ballots WHERE cvr_guid = ?", (cvr_guid,)
                ).fetchone()
                if result:
                    guid_to_ballot_id[cvr_guid] = result[0]

            # Update contest records with actual ballot IDs, but only for new ballots
            updated_contest_batch = []
            contest_id_mapping = {}

            for i, (ballot_index, contest_name, contest_id, undervotes) in enumerate(
                self.contest_batch
            ):
                ballot_record = self.ballot_batch[ballot_index]
                cvr_guid = ballot_record[0]

                # Only add contest if the ballot was newly inserted
                if cvr_guid in guid_to_ballot_id:
                    actual_ballot_id = guid_to_ballot_id[cvr_guid]

                    # Check if this contest already exists for this ballot
                    existing = conn.execute(
                        "SELECT id FROM cvr_contests WHERE ballot_id = ? AND contest_id = ?",
                        (actual_ballot_id, contest_id),
                    ).fetchone()

                    if not existing:
                        updated_contest_batch.append(
                            (actual_ballot_id, contest_name, contest_id, undervotes)
                        )
                        contest_id_mapping[i] = len(updated_contest_batch) - 1

            # Insert contests only if we have any
            if updated_contest_batch:
                cursor = conn.executemany(
                    "INSERT INTO cvr_contests (ballot_id, contest_name, contest_id, undervotes) VALUES (?, ?, ?, ?)",
                    updated_contest_batch,
                )

                # Get the contest record IDs for selections
                updated_selection_batch = []
                contest_records = {}

                for i, (ballot_id, _contest_name, contest_id, _undervotes) in enumerate(
                    updated_contest_batch
                ):
                    result = conn.execute(
                        "SELECT id FROM cvr_contests WHERE ballot_id = ? AND contest_id = ?",
                        (ballot_id, contest_id),
                    ).fetchone()
                    if result:
                        contest_records[i] = result[0]

                # Build selection records only for contests that were processed
                for (
                    orig_contest_index,
                    candidate_name,
                    candidate_id,
                    selection_value,
                ) in self.selection_batch:
                    if orig_contest_index in contest_id_mapping:
                        new_contest_index = contest_id_mapping[orig_contest_index]
                        if new_contest_index in contest_records:
                            actual_contest_record_id = contest_records[
                                new_contest_index
                            ]
                            updated_selection_batch.append(
                                (
                                    actual_contest_record_id,
                                    candidate_name,
                                    candidate_id,
                                    selection_value,
                                )
                            )

                # Insert selections only if we have any
                if updated_selection_batch:
                    conn.executemany(
                        "INSERT INTO cvr_selections (contest_record_id, candidate_name, candidate_id, selection_value) VALUES (?, ?, ?, ?)",
                        updated_selection_batch,
                    )

            conn.execute("COMMIT")

        except Exception as e:
            conn.execute("ROLLBACK")
            logger.error(f"Error writing batch to database: {e}")
            raise

        finally:
            conn.close()

            # Clear batches
            self.ballot_batch.clear()
            self.contest_batch.clear()
            self.selection_batch.clear()

    def process_directory(self, data_dir: Path) -> None:
        """Process all XML files in the given directory."""
        xml_files = list(data_dir.glob("*.xml"))
        logger.info(f"Found {len(xml_files)} XML files to process")

        with tqdm(xml_files, desc="Processing CVR files", unit="files") as pbar:
            for file_path in pbar:
                ballot_data = self.parse_xml_file(file_path)

                if ballot_data:
                    self.add_to_batch(ballot_data)
                    self.processed += 1

                    # Flush batch when it reaches the batch size
                    if len(self.ballot_batch) >= self.batch_size:
                        self.flush_batch()

                # Update progress bar
                pbar.set_postfix(
                    {
                        "processed": self.processed,
                        "errors": self.errors,
                        "rate": f"{self.processed / (time.time() - self.start_time):.1f}/s",
                    }
                )

        # Flush any remaining records
        self.flush_batch()

    def show_summary(self) -> None:
        """Display processing summary and database statistics."""
        total_time = time.time() - self.start_time

        print("\n" + "=" * 60)
        print("PROCESSING SUMMARY")
        print("=" * 60)
        print(f"Files processed: {self.processed:,}")
        print(f"Errors: {self.errors:,}")
        print(f"Processing time: {total_time:.2f} seconds")
        print(f"Average rate: {self.processed / total_time:.2f} files/second")

        # Database statistics
        conn = sqlite3.connect(self.db_path)

        ballot_count = conn.execute("SELECT COUNT(*) FROM cvr_ballots").fetchone()[0]
        contest_count = conn.execute("SELECT COUNT(*) FROM cvr_contests").fetchone()[0]
        selection_count = conn.execute(
            "SELECT COUNT(*) FROM cvr_selections"
        ).fetchone()[0]

        print("\nDATABASE STATISTICS")
        print("-" * 30)
        print(f"Total ballots: {ballot_count:,}")
        print(f"Total contests: {contest_count:,}")
        print(f"Total selections: {selection_count:,}")

        # Top precincts
        print("\nTOP 10 PRECINCTS")
        print("-" * 30)
        top_precincts = sorted(
            self.stats["precincts"].items(), key=lambda x: x[1], reverse=True
        )[:10]
        for precinct, count in top_precincts:
            print(f"{precinct}: {count:,} ballots")

        # Contest summary
        print("\nCONTESTS")
        print("-" * 30)
        for contest, count in sorted(self.stats["contests"].items()):
            print(f"{contest}: {count:,} instances")

        conn.close()


@click.command()
@click.option(
    "--data-dir",
    "-d",
    type=click.Path(exists=True, path_type=Path),
    default=Path("data"),
    help="Directory containing CVR XML files",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    default=Path("cvr-data.sqlite3"),
    help="Output SQLite database file",
)
@click.option(
    "--batch-size",
    "-b",
    type=int,
    default=5000,
    help="Batch size for database operations",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def main(data_dir: Path, output: Path, batch_size: int, verbose: bool):
    """Parse St. Louis Cast Vote Record XML files into SQLite database."""

    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("Starting CVR parsing...")
    logger.info(f"Data directory: {data_dir}")
    logger.info(f"Output database: {output}")
    logger.info(f"Batch size: {batch_size}")

    parser = CvrParser(str(output), batch_size)

    try:
        parser.process_directory(data_dir)
        parser.show_summary()

    except KeyboardInterrupt:
        logger.info("Processing interrupted by user")
        parser.flush_batch()  # Save any pending work
        parser.show_summary()

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()
