# Redrob Candidate Ranker 🤖

AI-powered Intelligent Candidate Discovery & Ranking Engine  
Built for **India Runs Hackathon by Redrob AI**

## What it does
Takes a Job Description and ranks 100,000 candidates intelligently 
using a hybrid scoring system — not just keyword matching.

## How it works
- **Career Relevance** (60%) — checks if candidate actually built 
  ranking/retrieval/embeddings systems
- **Skill Match** (40%) — weighted by proficiency, endorsements, 
  duration, and verified assessment scores
- **Behavioral Multiplier** — down-weights inactive/unresponsive candidates
- **Honeypot Detection** — filters out fake/impossible profiles automatically

## How to run
```bash
pip install -r requirements.txt
python rank.py --candidates ./data/candidates.jsonl --out ./submission.csv
```

## Tech Stack
Python · pandas · openpyxl

## Results
- Ranked 100,000 candidates in **14.5 seconds**
- Output validated with validate_submission.py ✅

## Live Demo
https://girish-palli-redrob-candidate-ranker-app-vdzevr.streamlit.app/

## Author
Girish Kumar Palli | B.Tech CSE @ ANITS
