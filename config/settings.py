# ============================================================
#  AutoApply Bot — Configuration
# ============================================================

import os
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

USER = {
    "name":           "Melanie Harriet",
    "email":          "melanieharriet05@gmail.com",
    "phone":          "",
    "location":       "Remote",
    "linkedin_url":   "",
    "resume_path":    "data/resume.pdf",
    "cover_letter":   "data/cover_letter.txt",
    "target_salary":  "35 LPA",
    "currency":       "INR",
    "notice_period":  "Immediate",
    "years_exp":      "",
    "work_auth":      "Yes",
    "willing_relocate": "No",
}

TARGET_ROLES = [
    "Gen AI Engineer",
    "AI Engineer",
    "Senior Software Engineer AI",
    "AI Systems Engineer",
    "Generative AI Engineer",
    "LLM Engineer",
    "Machine Learning Engineer",
]

MATCH_AUTO_APPLY   = 80
MATCH_EMAIL_REVIEW = 60

JOB_PLATFORMS = [
    {"name": "Greenhouse",     "base": "https://boards.greenhouse.io",                      "type": "greenhouse"},
    {"name": "Greenhouse EU",  "base": "https://boards.eu.greenhouse.io",                   "type": "greenhouse"},
    {"name": "Ashby HQ",       "base": "https://jobs.ashbyhq.com",                          "type": "ashby"},
    {"name": "Breezy HR",      "base": "https://breezy.hr",                                 "type": "breezy"},
    {"name": "JobScore",       "base": "https://careers.jobscore.com",                      "type": "generic"},
    {"name": "Teamtailor",     "base": "https://app.teamtailor.com/jobs",                   "type": "teamtailor"},
    {"name": "GoHire",         "base": "https://jobs.gohire.io",                            "type": "generic"},
    {"name": "Workable",       "base": "https://apply.workable.com",                        "type": "workable"},
    {"name": "ADP",            "base": "https://myjobs.adp.com",                           "type": "generic"},
    {"name": "Paylocity",      "base": "https://recruiting.paylocity.com",                  "type": "generic"},
    {"name": "UltiPro",        "base": "https://recruiting2.ultipro.com",                   "type": "generic"},
    {"name": "Taleo",          "base": "https://phf.tbe.taleo.net",                         "type": "taleo"},
    {"name": "SuccessFactors", "base": "https://career8.successfactors.com",                "type": "sf"},
    {"name": "Oracle HCM",     "base": "https://oraclecloud.com/hcmUI/CandidateExperience", "type": "oracle"},
    {"name": "Dayforce",       "base": "https://jobs.dayforcehcm.com",                      "type": "generic"},
    {"name": "ApplyToJob",     "base": "https://applytojob.com",                           "type": "generic"},
    {"name": "Crelate",        "base": "https://jobs.crelate.com",                         "type": "generic"},
    {"name": "JobAppNetwork",  "base": "https://secure.jobappnetwork.com",                  "type": "generic"},
    {"name": "Jobvite",        "base": "https://jobvite.com/CompanyJobs/Careers",           "type": "jobvite"},
    {"name": "Rippling ATS",   "base": "https://ats.rippling.com",                         "type": "generic"},
    {"name": "SurelyRemote",   "base": "https://surelyremote.com",                         "type": "surelyremote",
     "auth_email": "melanieharriet05@gmail.com"},
]

FILTERS = {
    "remote_only":           True,
    "posted_within_hours":   24,
    "exclude_keywords": [
        "onsite","on-site","on site","hybrid","in-office",
        "clearance required","US citizen only","security clearance"
    ],
    "min_salary_lpa":        25,
    "blacklist_companies":   [],
}

EMAIL = {
    "enabled":        True,
    "smtp_server":    "smtp.gmail.com",
    "smtp_port":      587,
    "from_email":     os.getenv("JOBBOT_EMAIL_FROM", "melanieharriet05@gmail.com"),
    "from_password":  os.getenv("JOBBOT_EMAIL_PASSWORD", ""),  # Gmail App Password
    "to_email":       os.getenv("JOBBOT_EMAIL_TO", "melanieharriet05@gmail.com"),
    "subject_prefix": "[AutoApply Bot]",
}

LINKEDIN = {
    "enabled":           True,
    "email":             os.getenv("JOBBOT_LINKEDIN_EMAIL", "melanieharriet05@gmail.com"),
    "password":          os.getenv("JOBBOT_LINKEDIN_PASSWORD", ""),
    "max_connects_day":  20,
    "message_template": (
        "Hi {name}, I recently applied for the {role} position at {company} "
        "and would love to connect. I have strong experience in AI/GenAI engineering!"
    ),
}

TRACKER = {
    "path": "data/applications_tracker.xlsx",
    "columns": [
        "Date","Company","Role","Platform","Match %","Status",
        "JD URL","Applied At","Notes","HR/Recruiter",
        "LinkedIn Sent","Email Sent","Response"
    ],
}

SCHEDULER = {
    "scan_interval_minutes": 15,
    "run_24_7":              True,
    "quiet_hours":           None,
}

AI = {
    "provider": os.getenv("JOBBOT_AI_PROVIDER", "openai"),
    "model":    os.getenv("JOBBOT_AI_MODEL", "gpt-4.1-mini"),   # or any GPT-4.x model
    "api_key":  os.getenv("JOBBOT_OPENAI_API_KEY", ""),         # set your OpenAI API key here
}
