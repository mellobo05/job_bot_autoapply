# 🤖 AutoApply Bot — Setup & Run Guide

## What This Bot Does (24/7)
- Scans **20 ATS platforms** every 15 minutes for remote AI/GenAI engineer jobs
- Uses **Claude AI** to match each JD against your resume (0–100% score)
- **≥80% match** → Automatically fills & submits the application
- **60–79% match** → Emails the JD to email@gmail.com for you to decide
- **<60%** → Skipped silently
- Sends **LinkedIn connection requests** to the hiring manager/recruiter after applying
- Logs **everything** in a colour-coded Excel spreadsheet

---

## Step 1 — Install Requirements

```bash
# Python 3.10+ required
pip install -r requirements.txt
playwright install chromium
```

---

## Step 2 — Add Your Files

```
job_bot/
└── data/
    ├── resume.pdf          ← PUT YOUR RESUME HERE
    └── cover_letter.txt    ← PUT YOUR COVER LETTER HERE (optional)
```

---

## Step 3 — Fill in config/settings.py

Open `config/settings.py` and fill in these fields:

```python
USER = {
    "phone":        "+91-XXXXXXXXXX",    # your phone number
    "linkedin_url": "https://linkedin.com/in/yourprofile",
    "years_exp":    "4",                 # your years of experience
}

EMAIL = {
    "from_password": "xxxx xxxx xxxx xxxx",  # Gmail App Password
    # Go to: myaccount.google.com → Security → App Passwords
    # Create one for "Mail" → copy the 16-char password
}

LINKEDIN = {
    "password": "your_linkedin_password",
}

AI = {
    "api_key": "sk-ant-XXXXXXXX",  # Your Anthropic API key
    # Get one at: console.anthropic.com
}
```

---

## Step 4 — Run the Bot

### One-time test scan:
```bash
cd job_bot
python main.py --once
```

### Run continuously 24/7:
```bash
python main.py
```

### Run in background (Linux/Mac):
```bash
nohup python main.py > logs/output.log 2>&1 &
echo "Bot running. PID: $!"
```

### Stop the bot:
```bash
# Find the process
ps aux | grep main.py
# Kill it
kill <PID>
```

---

## Step 5 — View Your Tracker
Open `data/applications_tracker.xlsx` anytime to see:
- All jobs found, matched, applied, skipped
- Colour-coded by status (green = applied, yellow = review sent, etc.)
- LinkedIn outreach status
- Response tracking

---

## Hosting 24/7 (so you don't need your laptop on)

### Option A — Railway.app (Easiest, Free tier available)
1. Push this folder to a GitHub repo
2. Go to railway.app → New Project → Deploy from GitHub
3. Set env variables (API keys) in Railway dashboard
4. Railway will run it 24/7

### Option B — VPS ($5/month — most reliable)
1. Get a Hetzner CX11 or DigitalOcean Droplet ($4–5/month)
2. SSH in, copy files, run with `nohup python main.py &`
3. Use `screen` or `tmux` for persistence

### Option C — Your own machine
Just run `python main.py` and leave the terminal open.

---

## Platforms Being Monitored

| Platform | Type |
|----------|------|
| Greenhouse (US + EU) | API scrape |
| Ashby HQ | HTML scrape |
| Workable | API scrape |
| SurelyRemote ✓ | Logged-in scrape |
| Breezy HR | Browser |
| Teamtailor | Browser |
| Jobvite | Browser |
| Rippling ATS | Browser |
| Taleo | Browser |
| SuccessFactors | Browser |
| Oracle HCM | Browser |
| ADP | Browser |
| Paylocity | Browser |
| UltiPro | Browser |
| Dayforce | Browser |
| JobScore | Browser |
| GoHire | Browser |
| Crelate | Browser |
| JobAppNetwork | Browser |
| ApplyToJob | Browser |

---

## Cost Estimate

| Item | Cost |
|------|------|
| Anthropic API (Claude) | ~$2–5/month |
| Hosting (Railway/VPS) | $0–5/month |
| **Total** | **~$2–10/month** |

---

## Important Notes

1. **LinkedIn Safety**: Bot sends max 20 connections/day (LinkedIn allows ~100/week). Staying well under limit.
2. **CAPTCHA**: Some platforms may block automated submissions — the bot logs failures and continues.
3. **Resume**: The better your resume PDF, the better the AI matching works.
4. **SurelyRemote**: Bot uses your subscription at melanieharriet05@gmail.com — make sure you're subscribed.

---

## Troubleshooting

**"Resume not found"** → Put your resume.pdf in the `data/` folder

**"Email not sending"** → Use a Gmail App Password (not your main password). Turn on 2FA first.

**"LinkedIn not working"** → Check your password is correct. If you have 2FA on LinkedIn, you may need to disable it or use a session cookie approach.

**"Low match scores"** → Add more detail to your resume: list specific technologies (LangChain, PyTorch, RAG, etc.)

**Bot crashes on a platform** → It automatically continues to the next one. Check `logs/bot.log` for details.
