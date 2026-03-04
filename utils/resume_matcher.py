"""
Resume ↔ JD Matcher
Uses Claude/OpenAI to compare resume against job description.
Returns a match score 0-100 and keyword analysis.
"""

import re
import json
import logging
from pathlib import Path
from typing import Optional

from openai import OpenAI
import pdfplumber

logger = logging.getLogger("resume_matcher")


def extract_resume_text(resume_path: str) -> str:
    """Extract plain text from PDF resume."""
    try:
        with pdfplumber.open(resume_path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    except Exception as e:
        logger.error(f"Failed to read resume: {e}")
        return ""


def match_resume_to_jd(
    resume_text: str,
    jd_text: str,
    api_key: str,
    model: str = "claude-opus-4-6",
    resume_path: Optional[str] = None,
) -> dict:
    """
    Compare resume against a job description.

    Returns:
        {
          "score": 85,               # 0-100 match percentage
          "matched_skills": [...],
          "missing_skills": [...],
          "recommendation": "apply" | "review" | "skip",
          "summary": "...",
          "role_fit": "...",
        }
    """
    if not resume_text and resume_path:
        resume_text = extract_resume_text(resume_path)

    if not resume_text:
        return {"score": 0, "error": "Could not read resume"}

    prompt = f"""You are an expert technical recruiter and resume evaluator.

Compare this RESUME against this JOB DESCRIPTION and return a JSON match analysis.

=== RESUME ===
{resume_text[:4000]}

=== JOB DESCRIPTION ===
{jd_text[:3000]}

Return ONLY valid JSON with this exact structure (no markdown, no extra text):
{{
  "score": <integer 0-100>,
  "matched_skills": ["skill1", "skill2", ...],
  "missing_skills": ["skill1", "skill2", ...],
  "matched_requirements": ["req1", ...],
  "missing_requirements": ["req1", ...],
  "years_exp_required": "<string or null>",
  "years_exp_candidate": "<string or null>",
  "recommendation": "<apply|review|skip>",
  "summary": "<2-sentence explanation>",
  "role_fit": "<strong|moderate|weak>",
  "salary_match": "<yes|no|unknown>"
}}

Scoring guide:
- 80-100: Strong match, auto-apply appropriate
- 60-79:  Moderate match, human review needed
- <60:    Weak match, skip
"""

    try:
        client = OpenAI(api_key=api_key)
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0,
            max_tokens=1000,
        )
        raw = (completion.choices[0].message.content or "").strip()
        # Strip any accidental markdown
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"```$", "", raw).strip()
        result = json.loads(raw)
        logger.info(f"Match score: {result.get('score')}% — {result.get('recommendation')}")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}\nRaw: {raw[:300]}")
        return {"score": 0, "error": "Parse error"}
    except Exception as e:
        logger.error(f"Matching error: {e}")
        return {"score": 0, "error": str(e)}


def quick_keyword_score(resume_text: str, jd_text: str) -> int:
    """
    Fast TF-IDF-style keyword overlap score (no API needed).
    Used as a pre-filter before the expensive AI call.
    """
    ai_keywords = {
        "python","pytorch","tensorflow","llm","langchain","openai","claude",
        "gpt","transformer","fine-tuning","rag","vector","embedding","nlp",
        "machine learning","deep learning","generative ai","gen ai",
        "fastapi","docker","kubernetes","aws","gcp","azure",
        "sql","nosql","mongodb","redis","kafka","spark",
        "ci/cd","git","agile","rest api","microservices",
        "huggingface","diffusion","stable diffusion","reinforcement learning",
        "computer vision","bert","gpt-4","gemini","mistral",
    }
    resume_lower = resume_text.lower()
    jd_lower = jd_text.lower()

    jd_kws = {kw for kw in ai_keywords if kw in jd_lower}
    if not jd_kws:
        return 50  # can't judge, pass to AI

    matched = sum(1 for kw in jd_kws if kw in resume_lower)
    return int((matched / len(jd_kws)) * 100)
