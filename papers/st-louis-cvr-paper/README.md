# St. Louis CVR paper bundle

This folder packages the current manuscript draft together with the backing data and local processing scripts used to generate the reported figures.

## Structure

- `manuscript/`
  - `st-louis-cvr-paper.tex` — LaTeX manuscript
  - `st-louis-cvr-paper.bib` — bibliography
  - `st-louis-cvr-paper.pdf` — compiled reading copy

- `data/raw/`
  - `CVRExport-8-27-2025.zip` — raw Hart Verity cast vote record export used by the local pipeline

- `data/derived/`
  - `report.csv` — report metadata row for the mayoral contest (`report_id = 39`)
  - `candidates.csv` — candidate totals used in the paper
  - `co_approvals.csv` — pairwise conditional co-approval results used in the paper
  - `voting_patterns.csv` — derived ballot-pattern summary row
  - `approval_distribution.json` — approvals-per-ballot distribution
  - `candidate_approval_distributions.json` — candidate-conditioned approval-count distributions
  - `anyone_but_analysis.json` — counts for ballots approving all but one candidate

- `scripts/`
  - `cvr_parser.py` — XML-to-SQLite parser for St. Louis CVR files
  - `process_all.py` — end-to-end pipeline to unzip, parse, analyze, and export
  - `st-louis-pipeline-README.md` — copied pipeline documentation

## Notes

- The manuscript uses the local project pipeline rather than only the public blog post.
- The key mayoral contest in the main SQLite database is `report_id = 39`.
- The raw CVR export contains 34,982 mayor contest records; the derived report uses 34,945 nonblank mayor ballots for summary statistics.

## Rebuild PDF

If `tectonic` is installed:

```bash
cd manuscript
tectonic st-louis-cvr-paper.tex
```
