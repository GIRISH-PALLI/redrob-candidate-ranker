# Redrob Candidate Ranker

This folder contains a CPU-only baseline ranking script for the hackathon dataset.

## Layout
- `data/candidates.jsonl`: input file, kept out of git by `.gitignore`
- `docs/`: challenge reference docs and schema files
- `rank.py`: ranking pipeline
- `requirements.txt`: no third-party dependencies required

## Run
```bash
python rank.py data/candidates.jsonl
```

The script writes `output.csv` with the required `candidate_id,rank,score,reasoning` columns.
