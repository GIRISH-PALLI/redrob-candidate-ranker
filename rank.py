"""
rank.py
Candidate ranking system for the Redrob Hackathon — Intelligent Candidate
Discovery & Ranking Challenge.

Ranks candidates against the Senior AI Engineer JD without rewarding
keyword-stuffing. Combines career relevance, verified skill match,
location/experience fit, and behavioral trust signals. Detects and
excludes honeypot (impossible) profiles.

Usage:
    python rank.py --candidates ./data/candidates.jsonl --out ./submission.csv

Constraints honored: CPU-only, no network calls, no GPU. Designed to run
100K candidates well within 5 minutes / 16GB RAM.
"""

import json
import csv
import argparse
import time
from datetime import date


# ── Configuration ────────────────────────────────────────────────────────

# Core competencies the JD says are non-negotiable ("things you absolutely
# need"). Matched against career_history text and skills, not just skill names.
REQUIRED_SKILLS = [
    "embeddings", "retrieval", "vector database", "ranking",
    "rag", "nlp", "python", "search", "recommendation",
]

# JD: "People who have only worked at consulting firms ... in their entire
# career" — explicit disqualifier unless prior product-company experience exists.
CONSULTING_FIRMS = {
    "tcs", "infosys", "wipro", "accenture", "cognizant", "capgemini",
    "mindtree", "hcl", "tech mahindra", "ltimindtree",
}

# JD: preferred locations for this Pune/Noida hybrid role.
PREFERRED_LOCATIONS = {
    "pune", "noida", "delhi ncr", "delhi", "gurugram", "gurgaon",
    "mumbai", "hyderabad", "bangalore", "bengaluru",
}

TODAY = date(2026, 6, 27)


# ── Step 1: Load data ────────────────────────────────────────────────────

def load_candidates(path: str) -> list[dict]:
    """Stream-read a .jsonl file (one JSON object per line) into a list of dicts."""
    candidates = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            candidates.append(json.loads(line))
    return candidates


def _parse_date(date_str):
    """Parse an ISO date string ('YYYY-MM-DD') into a date object, else None."""
    if not date_str:
        return None
    try:
        y, m, d = date_str.split("-")
        return date(int(y), int(m), int(d))
    except (ValueError, AttributeError):
        return None


# ── Step 2: Honeypot / trap detection ────────────────────────────────────

def is_honeypot(candidate: dict) -> bool:
    """
    Flag candidates with internally inconsistent or impossible profiles.

    Checks:
    1. A skill claimed at 'expert' proficiency with under 6 months of
       declared duration_months (can't be an expert in <6 months).
    2. Sum of career_history duration_months wildly exceeds
       years_of_experience claimed in profile (more than ~30% over,
       allowing for overlap/rounding).
    3. years_of_experience implausibly large relative to the candidate's
       earliest career_history start_date (e.g. claims more years of
       experience than time elapsed since their first recorded job).
    """
    profile = candidate.get("profile", {})
    years_exp = profile.get("years_of_experience", 0) or 0

    # Check 1: expert skill claimed with near-zero duration
    for skill in candidate.get("skills", []):
        if skill.get("proficiency") == "expert" and skill.get("duration_months", 999) < 6:
            return True

    # Check 2 & 3: career history consistency
    history = candidate.get("career_history", [])
    if history:
        total_months = sum(h.get("duration_months", 0) for h in history)
        # Allow generous slack (40%) for overlapping roles / rounding in synthetic data
        if years_exp > 0 and total_months > years_exp * 12 * 1.4:
            return True

        start_dates = [_parse_date(h.get("start_date")) for h in history]
        start_dates = [d for d in start_dates if d is not None]
        if start_dates:
            earliest = min(start_dates)
            years_since_earliest = (TODAY - earliest).days / 365.25
            # Claimed experience shouldn't exceed time since their first job by a lot
            if years_exp > years_since_earliest + 2:
                return True

    return False


# ── Step 3: Scoring components ───────────────────────────────────────────

def skill_match_score(candidate: dict, required_skills: list[str]) -> float:
    """
    Score skill fit (0-1), weighted by proficiency, endorsements, and duration.
    Cross-checked against verified skill_assessment_scores: a self-claimed
    'advanced'/'expert' skill with a low assessed score is discounted —
    this is what catches self-reported keyword stuffing.
    """
    proficiency_weight = {"beginner": 1, "intermediate": 2, "advanced": 3, "expert": 4}
    skills = candidate.get("skills", [])
    assessed = candidate.get("redrob_signals", {}).get("skill_assessment_scores", {}) or {}

    if not skills:
        return 0.0

    total = 0.0
    matched = 0
    for skill in skills:
        name = (skill.get("name") or "").lower()
        if not any(req in name for req in required_skills):
            continue

        matched += 1
        prof_w = proficiency_weight.get(skill.get("proficiency", "beginner"), 1)
        endorsements = min(skill.get("endorsements", 0), 50) / 50.0  # cap influence
        duration = min(skill.get("duration_months", 0), 60) / 60.0  # cap at 5 yrs

        raw = (prof_w / 4.0) * 0.5 + endorsements * 0.25 + duration * 0.25

        # Discount if claimed proficiency doesn't match verified assessment
        assessed_score = None
        for assessed_name, score in assessed.items():
            if assessed_name.lower() in name or name in assessed_name.lower():
                assessed_score = score
                break

        if assessed_score is not None and skill.get("proficiency") in ("advanced", "expert"):
            if assessed_score < 50:
                raw *= 0.5  # claimed strong, tested weak -> discount

        total += raw

    if matched == 0:
        return 0.0
    return min(total / len(required_skills), 1.0)


def career_relevance_score(candidate: dict, disqualifying_companies: set) -> float:
    """
    Score (0-1) how strongly career_history shows real production experience
    building ranking/retrieval/embeddings/recommendation systems — not just
    title-matching. Applies JD-stated disqualifiers.
    """
    history = candidate.get("career_history", [])
    if not history:
        return 0.0

    relevance_terms = [
        "embedding", "vector database", "vector search", "retrieval",
        "ranking system", "recommendation system", "rag pipeline",
        "rag system", "nlp", "fine-tun", "llm", "machine learning model",
        "ml model", "search infrastructure", "hybrid search",
    ]

    companies = {h.get("company", "").lower() for h in history}
    all_consulting = companies and companies.issubset(disqualifying_companies)

    # Hard disqualifier: entire career at consulting/services firms
    if all_consulting:
        return 0.05

    score = 0.0
    for h in history:
        desc = (h.get("description") or "").lower()
        title = (h.get("title") or "").lower()
        hits = sum(1 for term in relevance_terms if term in desc or term in title)
        weight = min(h.get("duration_months", 0), 48) / 48.0  # longer tenure = more signal
        score += min(hits, 5) / 5.0 * weight

    # Normalize roughly by number of roles, cap at 1.0
    return min(score / max(len(history), 1), 1.0)


def location_experience_fit(candidate: dict) -> float:
    """
    Score (0-1) blending location fit (Pune/Noida-preferred, India-based,
    relocation-willing) and experience-band fit (JD targets 5-9 years but
    is explicitly flexible for strong candidates).
    """
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})

    location = (profile.get("location") or "").lower()
    country = (profile.get("country") or "").lower()
    years_exp = profile.get("years_of_experience", 0) or 0
    willing_to_relocate = signals.get("willing_to_relocate", False)

    # Location component
    if any(loc in location for loc in PREFERRED_LOCATIONS):
        loc_score = 1.0
    elif country == "india":
        loc_score = 0.7
    elif willing_to_relocate:
        loc_score = 0.4
    else:
        loc_score = 0.1  # outside India, not willing to relocate -> JD says case-by-case, no visa sponsorship

    # Experience band component (soft preference for 5-9, not a hard cutoff)
    if 5 <= years_exp <= 9:
        exp_score = 1.0
    elif 3 <= years_exp < 5 or 9 < years_exp <= 12:
        exp_score = 0.6
    else:
        exp_score = 0.3

    return 0.6 * loc_score + 0.4 * exp_score


def behavioral_multiplier(candidate: dict) -> float:
    """
    Multiplicative trust factor (not additive) from redrob_signals.
    A strong on-paper candidate who is unresponsive/inactive/unavailable
    is down-weighted, per the JD's explicit instruction.
    """
    signals = candidate.get("redrob_signals", {})
    mult = 1.0

    if signals.get("open_to_work_flag") is False:
        mult *= 0.5

    last_active = _parse_date(signals.get("last_active_date"))
    if last_active:
        days_inactive = (TODAY - last_active).days
        if days_inactive > 180:
            mult *= 0.6
        elif days_inactive > 90:
            mult *= 0.85

    response_rate = signals.get("recruiter_response_rate")
    if response_rate is not None and response_rate < 0.1:
        mult *= 0.7

    notice_days = signals.get("notice_period_days", 0) or 0
    if notice_days > 60:
        mult *= 0.8

    return mult


# ── Step 4: Combine into final score ─────────────────────────────────────

def final_score(candidate: dict) -> float:
    """
    Returns 0.0 for honeypots. Otherwise: weighted blend of career
    relevance (0.45), skill match (0.35), location/experience fit (0.20),
    multiplied by the behavioral trust factor.
    """
    if is_honeypot(candidate):
        return 0.0

    career = career_relevance_score(candidate, CONSULTING_FIRMS)
    skills = skill_match_score(candidate, REQUIRED_SKILLS)
    loc_exp = location_experience_fit(candidate)

    # Location/experience fit is a modifier, not an independent path to a high
    # score. A candidate with zero relevant career history and zero relevant
    # skills should not outrank a relevant candidate just for being based in
    # Noida. We gate loc_exp's contribution by core relevance (career+skills),
    # so it can only amplify an already-relevant profile, not substitute for one.
    core_relevance = 0.6 * career + 0.4 * skills
    base = 0.75 * core_relevance + 0.25 * (loc_exp * core_relevance)
    return base * behavioral_multiplier(candidate)


# ── Step 5: Reasoning text ────────────────────────────────────────────────

def generate_reasoning(candidate: dict, score: float) -> str:
    """
    Build a short, specific, non-templated reasoning string using only
    fields present in the candidate's own data. No hallucinated claims.
    """
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})

    title = profile.get("current_title", "Unknown title")
    years = profile.get("years_of_experience", "?")
    location = profile.get("location", "unknown location")

    # Find the strongest matched skill for a concrete callout
    best_skill = None
    best_weight = -1
    for skill in candidate.get("skills", []):
        name = (skill.get("name") or "").lower()
        if any(req in name for req in REQUIRED_SKILLS):
            w = skill.get("endorsements", 0) + skill.get("duration_months", 0)
            if w > best_weight:
                best_weight = w
                best_skill = skill.get("name")

    parts = [f"{years} yrs experience, currently {title} ({location})."]

    if best_skill:
        parts.append(f"Relevant skill: {best_skill}.")
    else:
        parts.append("No strong direct match on core required skills.")

    notice = signals.get("notice_period_days")
    if notice and notice > 60:
        parts.append(f"Long notice period ({notice} days) noted.")

    if signals.get("open_to_work_flag") is False:
        parts.append("Not currently flagged open to work.")

    return " ".join(parts)


# ── Step 6: Pipeline ──────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", required=True, help="Path to candidates.jsonl")
    parser.add_argument("--out", required=True, help="Path to write output CSV")
    args = parser.parse_args()

    start = time.time()

    print(f"Loading candidates from {args.candidates} ...")
    candidates = load_candidates(args.candidates)
    print(f"Loaded {len(candidates)} candidates in {time.time() - start:.1f}s")

    scored = []
    for c in candidates:
        s = final_score(c)
        scored.append((c, s, round(s, 3)))

    # Sort by the rounded score that will be written to CSV; tie-break by candidate_id ascending.
    scored.sort(key=lambda x: (-x[2], x[0]["candidate_id"]))
    top_100 = scored[:100]

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        for rank, (cand, score, rounded_score) in enumerate(top_100, start=1):
            writer.writerow([
                cand["candidate_id"],
                rank,
                rounded_score,
                generate_reasoning(cand, score),
            ])

    elapsed = time.time() - start
    print(f"Wrote top 100 to {args.out}")
    print(f"Total runtime: {elapsed:.1f}s")


if __name__ == "__main__":
    main()