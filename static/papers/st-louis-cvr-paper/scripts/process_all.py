#!/usr/bin/env python3
"""
One-shot script to process all St. Louis CVR data from zip files to website database.

This script:
1. Unzips all ZIP files in ./data/ directory
2. Parses all CVR XML files into cvr-data.sqlite3
3. Generates co-approval analysis for ALL contests automatically
4. Exports to main ../data.sqlite3 with automatic office name mapping
5. Is fully idempotent - safe to re-run

Usage:
    uv run process-all
"""

import json
import logging
import os
import sqlite3
import subprocess  # nosec B404 - Controlled input
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def unzip_data_files():
    """Unzip all ZIP files in ./data/ directory."""
    data_dir = Path("./data")
    if not data_dir.exists():
        logger.error("./data directory does not exist!")
        return False

    zip_files = list(data_dir.glob("*.zip"))
    if not zip_files:
        logger.info("No ZIP files found in ./data directory")
        return True

    for zip_path in zip_files:
        extract_dir = data_dir / zip_path.stem
        if extract_dir.exists():
            logger.info(f"✓ {zip_path.name} already extracted to {extract_dir}")
            continue

        logger.info(f"📦 Extracting {zip_path.name}...")
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(extract_dir)
        logger.info(f"✓ Extracted to {extract_dir}")

    return True


def find_xml_directories():
    """Find all directories containing XML files."""
    data_dir = Path("./data")
    xml_dirs = []

    for root, _dirs, files in os.walk(data_dir):
        if any(f.endswith(".xml") for f in files):
            xml_dirs.append(Path(root))

    logger.info(f"Found {len(xml_dirs)} directories with XML files:")
    for xml_dir in xml_dirs:
        xml_count = len(list(xml_dir.glob("*.xml")))
        logger.info(f"  {xml_dir}: {xml_count} XML files")

    return xml_dirs


def parse_cvr_data(xml_dirs):
    """Parse all CVR XML files into cvr-data.sqlite3."""
    output_db = "cvr-data.sqlite3"

    # Remove existing database for fresh start
    if Path(output_db).exists():
        logger.info(f"🗑️  Removing existing {output_db}")
        Path(output_db).unlink()

    for xml_dir in xml_dirs:
        logger.info(f"📊 Processing {xml_dir}...")

        # Run cvr_parser on this directory
        cmd = [
            "uv",
            "run",
            "python",
            "cvr_parser.py",
            "--data-dir",
            str(xml_dir),
            "--output",
            output_db,
            "--batch-size",
            "5000",
        ]

        result = subprocess.run(
            cmd, capture_output=True, text=True
        )  # nosec B603 - Controlled input
        if result.returncode != 0:
            logger.error(f"Failed to process {xml_dir}: {result.stderr}")
            return False

    logger.info(f"✅ All CVR data parsed into {output_db}")
    return True


def normalize_contest_name(contest_name):
    """Convert contest name to office name format.

    Examples:
    - 'MAYOR' -> 'mayor'
    - 'COMPTROLLER' -> 'comptroller'
    - 'ALDERMAN - WARD 3' -> 'alderman-ward3'
    - 'ALDERMAN - WARD 11' -> 'alderman-ward11'
    """
    return contest_name.lower().replace(" - ", "-").replace(" ", "")


def generate_co_approval_analysis(contest_name, cvr_conn):
    """Generate co-approval analysis for a specific contest."""

    # Get ballot approvals for this contest
    query = """
    SELECT 
        c.ballot_id,
        s.candidate_name
    FROM cvr_contests c
    JOIN cvr_selections s ON c.id = s.contest_record_id
    WHERE c.contest_name = ? AND s.selection_value = 1
    ORDER BY c.ballot_id
    """

    ballot_approvals = defaultdict(set)
    for row in cvr_conn.execute(query, (contest_name,)):
        ballot_approvals[row[0]].add(row[1])

    if len(ballot_approvals) < 2:
        return [], {}  # Not enough data

    # Get all candidates
    candidates = set()
    for approved_candidates in ballot_approvals.values():
        candidates.update(approved_candidates)
    candidates = list(candidates)

    if len(candidates) < 2:
        return [], {}  # Need at least 2 candidates

    # Calculate co-approval matrix
    co_approvals = []
    for i, cand_a in enumerate(candidates):
        for j, cand_b in enumerate(candidates):
            if i == j:
                continue

            # Count ballots that approved cand_a
            cand_a_ballots = [
                ballot_id
                for ballot_id, approved in ballot_approvals.items()
                if cand_a in approved
            ]

            if len(cand_a_ballots) == 0:
                continue

            # Count how many of those also approved cand_b
            both_count = sum(
                1
                for ballot_id in cand_a_ballots
                if cand_b in ballot_approvals[ballot_id]
            )

            co_approval_rate = (both_count / len(cand_a_ballots)) * 100

            co_approvals.append(
                {
                    "candidateA": cand_a,
                    "candidateB": cand_b,
                    "coApprovalCount": both_count,
                    "coApprovalRate": co_approval_rate,
                }
            )

    # Calculate voting patterns
    total_ballots = len(ballot_approvals)
    approval_distribution = Counter()

    for approved_candidates in ballot_approvals.values():
        approval_distribution[len(approved_candidates)] += 1

    bullet_voting_count = approval_distribution[1]
    full_approval_count = approval_distribution[len(candidates)]

    # Find most common combination
    combination_counts = Counter()
    for approved_candidates in ballot_approvals.values():
        if len(approved_candidates) > 0:
            combination_counts[tuple(sorted(approved_candidates))] += 1

    most_common_combination = (
        list(combination_counts.most_common(1)[0][0]) if combination_counts else []
    )

    total_approvals = sum(len(approved) for approved in ballot_approvals.values())
    average_approvals = total_approvals / total_ballots if total_ballots > 0 else 0

    # Calculate candidate-specific approval distributions
    candidate_approval_distributions = {}
    for candidate in candidates:
        # Get all ballots that approved this candidate
        candidate_ballots = [
            ballot_id
            for ballot_id, approved in ballot_approvals.items()
            if candidate in approved
        ]

        if not candidate_ballots:
            continue

        # For each of these ballots, count how many total candidates they approved
        candidate_distribution = Counter()
        for ballot_id in candidate_ballots:
            total_approvals_on_ballot = len(ballot_approvals[ballot_id])
            candidate_distribution[total_approvals_on_ballot] += 1

        candidate_approval_distributions[candidate] = dict(candidate_distribution)

    # Calculate "Anyone But X" analysis - ballots with exactly N-1 approvals
    anyone_but_analysis = {}
    num_candidates = len(candidates)
    anyone_but_ballots = 0

    for _ballot_id, approved_candidates in ballot_approvals.items():
        if len(approved_candidates) == num_candidates - 1:  # N-1 approvals
            anyone_but_ballots += 1
            # Find the one candidate that was NOT approved
            excluded_candidates = set(candidates) - approved_candidates
            if len(excluded_candidates) == 1:
                excluded_candidate = list(excluded_candidates)[0]
                anyone_but_analysis[excluded_candidate] = (
                    anyone_but_analysis.get(excluded_candidate, 0) + 1
                )

    voting_patterns = {
        "totalBallots": total_ballots,
        "bulletVotingCount": bullet_voting_count,
        "bulletVotingRate": (bullet_voting_count / total_ballots) * 100,
        "fullApprovalCount": full_approval_count,
        "fullApprovalRate": (full_approval_count / total_ballots) * 100,
        "averageApprovalsPerBallot": average_approvals,
        "mostCommonCombination": most_common_combination,
        "approvalDistribution": dict(approval_distribution),
        "candidateApprovalDistributions": candidate_approval_distributions,
        "anyoneButAnalysis": anyone_but_analysis,
    }

    return co_approvals, voting_patterns


def export_to_main_database():
    """Export all co-approval data to main database with automatic mapping."""
    cvr_db = "cvr-data.sqlite3"
    main_db = "../../data.sqlite3"

    if not Path(cvr_db).exists():
        logger.error(f"CVR database {cvr_db} does not exist!")
        return False

    if not Path(main_db).exists():
        logger.error(f"Main database {main_db} does not exist!")
        return False

    cvr_conn = sqlite3.connect(cvr_db)
    main_conn = sqlite3.connect(main_db)

    def create_candidate_name_mapping(contest_name, main_report_id, cvr_candidates):
        """Create mapping from CVR names (ALL CAPS) to proper database names."""
        # Get proper candidate names from main database
        proper_candidates = main_conn.execute(
            "SELECT name FROM candidates WHERE report_id = ?", (main_report_id,)
        ).fetchall()
        proper_names = [row[0] for row in proper_candidates]

        # Create mapping by normalized matching
        mapping = {}

        def normalize_for_match(name):
            return (
                name.upper()
                .replace('"', '"')
                .replace('"', '"')
                .replace(".", "")
                .replace(" ", "")
            )

        for cvr_name in cvr_candidates:
            normalized_cvr = normalize_for_match(cvr_name)
            for proper_name in proper_names:
                normalized_proper = normalize_for_match(proper_name)
                if normalized_cvr == normalized_proper:
                    mapping[cvr_name] = proper_name
                    break

        return mapping

    # Create tables if they don't exist
    main_conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS co_approvals (
            id INTEGER PRIMARY KEY,
            report_id INTEGER,
            candidate_a TEXT,
            candidate_b TEXT,
            co_approval_count INTEGER,
            co_approval_rate REAL,
            FOREIGN KEY(report_id) REFERENCES reports(id)
        );
        
        CREATE TABLE IF NOT EXISTS voting_patterns (
            id INTEGER PRIMARY KEY,
            report_id INTEGER,
            total_ballots INTEGER,
            bullet_voting_count INTEGER,
            bullet_voting_rate REAL,
            full_approval_count INTEGER,
            full_approval_rate REAL,
            average_approvals_per_ballot REAL,
            most_common_combination TEXT,
            approval_distribution TEXT,
            candidate_approval_distributions TEXT,
            anyone_but_analysis TEXT,
            FOREIGN KEY(report_id) REFERENCES reports(id)
        );
        
        CREATE TABLE IF NOT EXISTS cvr_ballots (
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            cvr_guid TEXT NOT NULL,
            batch_sequence INTEGER,
            sheet_number INTEGER,
            precinct_name TEXT,
            precinct_id TEXT,
            is_blank BOOLEAN,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source, cvr_guid)
        );
        
        CREATE TABLE IF NOT EXISTS cvr_contests (
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            ballot_id INTEGER,
            contest_name TEXT NOT NULL,
            contest_id TEXT NOT NULL,
            undervotes INTEGER,
            FOREIGN KEY(ballot_id) REFERENCES cvr_ballots(id)
        );
        
        CREATE TABLE IF NOT EXISTS cvr_selections (
            id INTEGER PRIMARY KEY,
            source TEXT NOT NULL,
            contest_record_id INTEGER,
            candidate_name TEXT NOT NULL,
            candidate_id TEXT NOT NULL,
            selection_value INTEGER,
            FOREIGN KEY(contest_record_id) REFERENCES cvr_contests(id)
        );
        
        CREATE INDEX IF NOT EXISTS idx_cvr_source_guid ON cvr_ballots(source, cvr_guid);
        CREATE INDEX IF NOT EXISTS idx_cvr_source_precinct ON cvr_ballots(source, precinct_id);
        CREATE INDEX IF NOT EXISTS idx_cvr_source_contest ON cvr_contests(source, contest_id);
        CREATE INDEX IF NOT EXISTS idx_cvr_source_ballot_contest ON cvr_contests(source, ballot_id, contest_id);
        CREATE INDEX IF NOT EXISTS idx_cvr_source_candidate ON cvr_selections(source, candidate_id);
        CREATE INDEX IF NOT EXISTS idx_cvr_source_contest_selection ON cvr_selections(source, contest_record_id, candidate_id);
    """
    )

    # Add anyone_but_analysis column if it doesn't exist (migration for existing databases)
    try:
        main_conn.execute(
            "ALTER TABLE voting_patterns ADD COLUMN anyone_but_analysis TEXT"
        )
        logger.info(
            "✓ Added anyone_but_analysis column to existing voting_patterns table"
        )
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            logger.info("✓ anyone_but_analysis column already exists")
        else:
            logger.warning(f"Could not add anyone_but_analysis column: {e}")
            # Continue anyway - might not be a critical error

    # Get all contests from CVR
    contests = cvr_conn.execute(
        "SELECT DISTINCT contest_name FROM cvr_contests"
    ).fetchall()

    for (contest_name,) in contests:
        logger.info(f"🔄 Processing {contest_name}...")

        # Normalize contest name to match office field
        office_name = normalize_contest_name(contest_name)

        # Find matching report (with date constraint for St. Louis)
        report_result = main_conn.execute(
            "SELECT id FROM reports WHERE office = ? AND date = ?",
            (office_name, "2025-03-04"),
        ).fetchone()

        if not report_result:
            logger.warning(
                f"  No matching report found for contest '{contest_name}' -> office '{office_name}'"
            )
            continue

        report_id = report_result[0]
        logger.info(f"  ✓ Found report_id: {report_id}")

        # Generate co-approval analysis
        co_approvals, voting_patterns = generate_co_approval_analysis(
            contest_name, cvr_conn
        )

        # Get CVR candidates to create name mapping
        cvr_candidates_query = """
        SELECT DISTINCT s.candidate_name 
        FROM cvr_contests c
        JOIN cvr_selections s ON c.id = s.contest_record_id
        WHERE c.contest_name = ?
        """
        cvr_candidate_names = [
            row[0] for row in cvr_conn.execute(cvr_candidates_query, (contest_name,))
        ]

        # Create name mapping and update both co-approvals and voting patterns
        name_mapping = create_candidate_name_mapping(
            contest_name, report_id, cvr_candidate_names
        )

        # Update co-approvals to use proper database names
        for ca in co_approvals:
            ca["candidateA"] = name_mapping.get(ca["candidateA"], ca["candidateA"])
            ca["candidateB"] = name_mapping.get(ca["candidateB"], ca["candidateB"])

        # Convert candidateApprovalDistributions to use proper database names
        if voting_patterns and "candidateApprovalDistributions" in voting_patterns:
            mapped_distributions = {}
            for cvr_name, distribution in voting_patterns[
                "candidateApprovalDistributions"
            ].items():
                proper_name = name_mapping.get(cvr_name, cvr_name)
                mapped_distributions[proper_name] = distribution

            voting_patterns["candidateApprovalDistributions"] = mapped_distributions

        # Convert anyoneButAnalysis to use proper database names
        if voting_patterns and "anyoneButAnalysis" in voting_patterns:
            mapped_anyone_but = {}
            for cvr_name, count in voting_patterns["anyoneButAnalysis"].items():
                proper_name = name_mapping.get(cvr_name, cvr_name)
                mapped_anyone_but[proper_name] = count

            voting_patterns["anyoneButAnalysis"] = mapped_anyone_but

        if not co_approvals:
            logger.warning(f"  No co-approval data generated for {contest_name}")
            continue

        # Clear existing data for this report (idempotent)
        main_conn.execute("DELETE FROM co_approvals WHERE report_id = ?", (report_id,))
        main_conn.execute(
            "DELETE FROM voting_patterns WHERE report_id = ?", (report_id,)
        )

        # Insert co-approval data
        for ca in co_approvals:
            main_conn.execute(
                """
                INSERT INTO co_approvals (report_id, candidate_a, candidate_b, co_approval_count, co_approval_rate)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    report_id,
                    ca["candidateA"],
                    ca["candidateB"],
                    ca["coApprovalCount"],
                    ca["coApprovalRate"],
                ),
            )

        # Insert voting patterns
        main_conn.execute(
            """
            INSERT INTO voting_patterns (
                report_id, total_ballots, bullet_voting_count, bullet_voting_rate,
                full_approval_count, full_approval_rate, average_approvals_per_ballot,
                most_common_combination, approval_distribution, candidate_approval_distributions,
                anyone_but_analysis
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                report_id,
                voting_patterns["totalBallots"],
                voting_patterns["bulletVotingCount"],
                voting_patterns["bulletVotingRate"],
                voting_patterns["fullApprovalCount"],
                voting_patterns["fullApprovalRate"],
                voting_patterns["averageApprovalsPerBallot"],
                json.dumps(voting_patterns["mostCommonCombination"]),
                json.dumps(voting_patterns["approvalDistribution"]),
                json.dumps(voting_patterns["candidateApprovalDistributions"]),
                json.dumps(voting_patterns["anyoneButAnalysis"]),
            ),
        )

        # Update the reports table with accurate ballot count from CVR
        logger.info(
            f"  Updating report ballot count to {voting_patterns['totalBallots']}"
        )
        main_conn.execute(
            """
            UPDATE reports 
            SET ballotCount = ? 
            WHERE id = ?
        """,
            (voting_patterns["totalBallots"], report_id),
        )

        # Update candidate vote counts from CVR data
        logger.info("  Updating candidate vote counts from CVR data")

        # Get candidate vote counts from CVR
        candidate_votes_query = """
            SELECT s.candidate_name, COUNT(*) as approvals 
            FROM cvr_ballots b 
            JOIN cvr_contests c ON b.id = c.ballot_id 
            JOIN cvr_selections s ON c.id = s.contest_record_id 
            WHERE c.contest_name = ? AND s.selection_value = 1 
            GROUP BY s.candidate_name
        """

        cvr_candidate_votes = cvr_conn.execute(
            candidate_votes_query, (contest_name,)
        ).fetchall()

        # Update each candidate's vote count using the name mapping
        for cvr_name, vote_count in cvr_candidate_votes:
            proper_name = name_mapping.get(cvr_name, cvr_name)
            logger.info(f"    Updating {proper_name}: {vote_count} votes")

            main_conn.execute(
                """
                UPDATE candidates 
                SET votes = ? 
                WHERE report_id = ? AND name = ?
            """,
                (vote_count, report_id, proper_name),
            )

            # Verify the update worked
            updated_count = main_conn.execute(
                """
                SELECT votes FROM candidates 
                WHERE report_id = ? AND name = ?
            """,
                (report_id, proper_name),
            ).fetchone()

            if updated_count and updated_count[0] != vote_count:
                logger.warning(
                    f"    Vote count mismatch for {proper_name}: expected {vote_count}, got {updated_count[0]}"
                )

        logger.info(
            f"  ✅ Exported {len(co_approvals)} co-approval entries and voting patterns"
        )

    # Export CVR tables to main database
    logger.info("\n📦 Exporting CVR tables to main database...")
    source = "st_louis"

    # Delete existing St. Louis CVR data (idempotent)
    main_conn.execute("DELETE FROM cvr_selections WHERE source = ?", (source,))
    main_conn.execute("DELETE FROM cvr_contests WHERE source = ?", (source,))
    main_conn.execute("DELETE FROM cvr_ballots WHERE source = ?", (source,))

    # Copy ballots
    logger.info("  Copying cvr_ballots...")
    ballots = cvr_conn.execute(
        "SELECT cvr_guid, batch_sequence, sheet_number, precinct_name, precinct_id, is_blank, created_at FROM cvr_ballots"
    ).fetchall()
    main_conn.executemany(
        "INSERT INTO cvr_ballots (source, cvr_guid, batch_sequence, sheet_number, precinct_name, precinct_id, is_blank, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [(source,) + ballot for ballot in ballots],
    )
    logger.info(f"  ✓ Copied {len(ballots)} ballots")

    # Create mapping from old ballot IDs to new ballot IDs
    ballot_id_map = {}
    for old_id, (cvr_guid,) in enumerate(
        cvr_conn.execute("SELECT cvr_guid FROM cvr_ballots ORDER BY id").fetchall(), 1
    ):
        new_id = main_conn.execute(
            "SELECT id FROM cvr_ballots WHERE source = ? AND cvr_guid = ?",
            (source, cvr_guid),
        ).fetchone()[0]
        ballot_id_map[old_id] = new_id

    # Copy contests
    logger.info("  Copying cvr_contests...")
    contest_id_map = {}
    cursor = main_conn.cursor()
    for row in cvr_conn.execute(
        "SELECT id, ballot_id, contest_name, contest_id, undervotes FROM cvr_contests ORDER BY id"
    ).fetchall():
        old_id, ballot_id, contest_name, contest_id, undervotes = row
        new_ballot_id = ballot_id_map[ballot_id]
        cursor.execute(
            "INSERT INTO cvr_contests (source, ballot_id, contest_name, contest_id, undervotes) VALUES (?, ?, ?, ?, ?)",
            (source, new_ballot_id, contest_name, contest_id, undervotes),
        )
        # Get the last inserted rowid
        new_id = cursor.lastrowid
        contest_id_map[old_id] = new_id

    logger.info(f"  ✓ Copied {len(contest_id_map)} contests")

    # Copy selections
    logger.info("  Copying cvr_selections...")
    selections = []
    for row in cvr_conn.execute(
        "SELECT id, contest_record_id, candidate_name, candidate_id, selection_value FROM cvr_selections ORDER BY id"
    ).fetchall():
        old_id, contest_record_id, candidate_name, candidate_id, selection_value = row
        new_contest_id = contest_id_map[contest_record_id]
        selections.append(
            (source, new_contest_id, candidate_name, candidate_id, selection_value)
        )

    main_conn.executemany(
        "INSERT INTO cvr_selections (source, contest_record_id, candidate_name, candidate_id, selection_value) VALUES (?, ?, ?, ?, ?)",
        selections,
    )
    logger.info(f"  ✓ Copied {len(selections)} selections")

    main_conn.commit()
    cvr_conn.close()
    main_conn.close()

    logger.info("🎉 All data exported to main database!")
    return True


def main():
    """Main entry point."""
    logger.info("🚀 Starting complete St. Louis CVR processing...")

    # Step 1: Unzip data files
    logger.info("\n" + "=" * 60)
    logger.info("STEP 1: Unzipping data files")
    logger.info("=" * 60)
    if not unzip_data_files():
        logger.error("❌ Failed to unzip data files")
        return 1

    # Step 2: Find XML directories
    logger.info("\n" + "=" * 60)
    logger.info("STEP 2: Finding XML files")
    logger.info("=" * 60)
    xml_dirs = find_xml_directories()
    if not xml_dirs:
        logger.error("❌ No XML files found!")
        return 1

    # Step 3: Parse CVR data
    logger.info("\n" + "=" * 60)
    logger.info("STEP 3: Parsing CVR data")
    logger.info("=" * 60)
    if not parse_cvr_data(xml_dirs):
        logger.error("❌ Failed to parse CVR data")
        return 1

    # Step 4: Export to main database
    logger.info("\n" + "=" * 60)
    logger.info("STEP 4: Exporting to main database")
    logger.info("=" * 60)
    if not export_to_main_database():
        logger.error("❌ Failed to export to main database")
        return 1

    logger.info("\n" + "🎉" * 20)
    logger.info("✅ COMPLETE! All St. Louis CVR data processed successfully!")
    logger.info("🎉" * 20)
    return 0


if __name__ == "__main__":
    exit(main())
