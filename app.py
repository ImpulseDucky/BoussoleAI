import os
import io
import json
import re
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for, Response, stream_with_context
from openai import OpenAI
from pypdf import PdfReader

# Load .env relative to script execution path
env_path = Path(__file__).resolve().parent / '.env'
load_dotenv(env_path)

endpoint = os.environ.get('AZURE_OPENAI_ENDPOINT')
api_key = os.environ.get('AZURE_OPENAI_API_KEY')
deployment_name = os.environ.get('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-5-mini')
APP_PASSWORD = os.environ.get('APP_PASSWORD', 'boussole2026')

if not endpoint or not api_key:
    raise RuntimeError(
        f"Missing Azure OpenAI credentials. Check your .env file at: {env_path}"
    )

# Initialize standard OpenAI client pointing to Azure AI Foundry base_url
client = OpenAI(
    base_url=endpoint,  # Ends with /openai/v1
    api_key=api_key
)

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'boussole-ai-super-secret-key-2026')

# ==============================================================================
# SERVER-SIDE JSON FILE CHAT STORAGE
# ==============================================================================

STORAGE_FILE = Path(__file__).resolve().parent / 'chat_storage.json'

BOUSSOLE_SYSTEM_INSTRUCTION = """
You are Boussole AI, an elite career navigation strategist and hackathon career advisor.
Your mission is to provide concise, direct, and actionable guidance to help candidates navigate skill gaps, optimize resumes, and master interviews.

Core Operating Principles:
1. Extreme Conciseness: Keep answers short, punchy, and straight to the point. Avoid fluff, long introductions, or unnecessary elaboration. 
2. Format: Use short bullet points and brief sentences. Never write long, dense paragraphs or excessive text.
3. The Google X-Y-Z Formula: When rewriting resume bullets, enforce "Accomplished [X], as measured by [Y], by doing [Z]".
4. Voice & Tone: Professional, candid, and encouraging, but brief.
5. Branding Identity: Identify naturally as Boussole AI when introduced.
"""

WELCOME_GREETING = "Welcome to BoussoleAI Career Strategist. How can I help you navigate your professional trajectory today?"

def load_storage():
    """Loads chat sessions and active ID from server-side JSON storage."""
    if STORAGE_FILE.exists():
        try:
            with open(STORAGE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                sessions = data.get('sessions', {})
                active_id = data.get('active_id', 'default')
                if sessions:
                    return sessions, active_id
        except Exception as e:
            print(f"Error loading chat storage: {e}")
    
    default_id = "default"
    default_sessions = {
        default_id: {
            "id": default_id,
            "title": "New Conversation",
            "messages": [
                {"role": "system", "content": BOUSSOLE_SYSTEM_INSTRUCTION},
                {"role": "assistant", "content": WELCOME_GREETING}
            ]
        }
    }
    save_storage(default_sessions, default_id)
    return default_sessions, default_id

def save_storage(sessions, active_id):
    """Saves chat sessions and active ID to server-side JSON storage."""
    try:
        with open(STORAGE_FILE, 'w', encoding='utf-8') as f:
            json.dump({'sessions': sessions, 'active_id': active_id}, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving chat storage: {e}")

# ==============================================================================
# 1. STUDENT FINANCIAL AID ENGINE
# ==============================================================================

def sanitize_pii(text: str) -> tuple[str, int]:
    hkid_pattern = r'[A-Z]{1,2}\d{6}\([\dA]\)'
    text, hkid_subs = re.subn(hkid_pattern, '[HKID_REDACTED]', text, flags=re.IGNORECASE)
    
    phone_pattern = r'\b[235689]\d{7}\b'
    text, phone_subs = re.subn(phone_pattern, '[PHONE_REDACTED]', text)
    
    return text, (hkid_subs + phone_subs)

def evaluate_student_eligibility(income: float, members: int) -> dict:
    if income is None:
        return {
            "status": "ACTION_REQUIRED",
            "badge_color": "amber",
            "summary": "Incomplete Financial Details",
            "details": "Family monthly income was not found in your notes. Please update your details.",
            "policy_citation": "WFSFAA Guidelines Section 2.1 — Verification of Family Monthly Income.",
            "required_documents": [
                "1. Student Financial Declaration Form (Signed)",
                "2. Parent/Guardian Tax Returns (BIR60)",
                "3. Recent Bank Statements (Past 3 Months)"
            ],
            "grant_percentage": 0.0,
            "loan_eligible": True,
            "loan_scheme": "NLSFT (Non-Means-Tested Loan Scheme)"
        }
    
    per_capita_income = income / max(1, members)
    FULL_GRANT_THRESHOLD = 32000 / 12  # ~HKD 2,666 / mo per capita
    HALF_GRANT_THRESHOLD = 55000 / 12  # ~HKD 4,583 / mo per capita
    
    if per_capita_income <= FULL_GRANT_THRESHOLD:
        return {
            "status": "ELIGIBLE",
            "badge_color": "emerald",
            "summary": "100% Full Grant & Academic Expenses Grant Eligible",
            "details": f"Your calculated monthly per-capita income of HK${per_capita_income:,.2f} qualifies you for maximum financial assistance.",
            "policy_citation": "FASP Guidance Notes (2026/27) — Annex A: Sliding Scale Income Test.",
            "required_documents": [
                "1. Hong Kong Identity Card (Copy)",
                "2. University Student Registration Proof / Timetable",
                "3. Family Income Proof (Salary slips or employer certificate)",
                "4. Bank Account Passbook showing your name"
            ],
            "grant_percentage": 1.0,
            "loan_eligible": True,
            "loan_scheme": "NLSFT / LSFS Low-Interest Student Loan"
        }
    elif per_capita_income <= HALF_GRANT_THRESHOLD:
        return {
            "status": "ELIGIBLE_PARTIAL",
            "badge_color": "blue",
            "summary": "50% Partial Grant Eligible",
            "details": f"Your calculated per-capita income of HK${per_capita_income:,.2f} qualifies you for Tier-2 partial assistance. (Estimated 50% tuition covered)",
            "policy_citation": "FASP Guidance Notes (2026/27) — Annex A: Sliding Scale Income Test.",
            "required_documents": [
                "1. Hong Kong Identity Card (Copy)",
                "2. University Student Registration Proof",
                "3. Family Income Proof (Tax demands / salary records)",
                "4. Rent / Mortgage payment receipt (if claiming housing allowance)"
            ],
            "grant_percentage": 0.5,
            "loan_eligible": True,
            "loan_scheme": "NLSFT (Non-Means-Tested Loan for remaining tuition shortfall)"
        }
    else:
        return {
            "status": "INELIGIBLE_FASP",
            "badge_color": "rose",
            "summary": "Exceeds Standard FASP Limit (Recommend NLSFT)",
            "details": f"Per-capita income of HK${per_capita_income:,.2f} exceeds standard means-tested limits. We recommend applying for the Non-Means-Tested Loan Scheme.",
            "policy_citation": "WFSFAA Guidance Notes Section 4.3 — Non-Means-Tested Financial Assistance.",
            "required_documents": [
                "1. Non-Means-Tested Loan Scheme (NLSFT) Application Form",
                "2. Tuition Fee Debit Note from University",
                "3. Guarantor Information & Identification Document"
            ],
            "grant_percentage": 0.0,
            "loan_eligible": True,
            "loan_scheme": "NLSFT (Full Tuition Coverage Loan)"
        }

# ==============================================================================
# 2. LOGIN & UNIFIED FRONTEND TEMPLATES
# ==============================================================================

LOGIN_HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en" class="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BoussoleAI — Portal Access</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = { darkMode: 'class' };
    </script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }
    </style>
</head>
<body class="bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 min-h-screen flex items-center justify-center p-4 transition-colors bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-100/60 via-slate-50 to-slate-100 dark:from-indigo-950/40 dark:via-slate-950 dark:to-slate-950">
    <div class="bg-white/80 dark:bg-slate-900/80 backdrop-blur-md border border-slate-200/80 dark:border-slate-800/80 p-8 rounded-2xl shadow-xl max-w-sm w-full flex flex-col gap-6 relative overflow-hidden before:absolute before:top-0 before:left-0 before:right-0 before:h-1 before:bg-gradient-to-r before:from-indigo-500 before:via-purple-500 before:to-cyan-500">
        <div>
            <div class="inline-flex items-center gap-2 mb-2">
                <svg class="w-5 h-5 text-indigo-600 dark:text-indigo-400 flex-shrink-0" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.75"/>
                    <polygon points="12,6 14.5,11.5 12,10 9.5,11.5" fill="currentColor"/>
                    <polygon points="12,18 9.5,12.5 12,14 14.5,12.5" fill="currentColor" opacity="0.4"/>
                </svg>
                <h1 class="font-bold text-lg tracking-tight">
                    <span class="bg-gradient-to-r from-indigo-600 to-violet-500 dark:from-indigo-400 dark:to-violet-400 bg-clip-text text-transparent font-bold">Boussole</span><span class="bg-gradient-to-r from-violet-500 via-purple-500 to-cyan-500 bg-clip-text text-transparent font-extrabold">AI</span>
                </h1>
            </div>
            <p class="text-xs text-slate-500 dark:text-slate-400">Enter access password to continue.</p>
        </div>
        <form id="login-form" onsubmit="handleLogin(event)" class="flex flex-col gap-4">
            <div class="flex flex-col gap-1.5">
                <label class="text-xs font-medium text-slate-700 dark:text-slate-300">Password</label>
                <input type="password" id="password-input" class="w-full bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 text-sm rounded-lg px-3 py-2 border border-slate-300 dark:border-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 transition shadow-inner" placeholder="••••••••" required>
            </div>
            <div id="error-msg" class="text-xs text-rose-600 font-medium hidden"></div>
            <button type="submit" class="w-full py-2.5 bg-gradient-to-r from-slate-900 to-indigo-900 dark:from-slate-800 dark:to-indigo-950 hover:opacity-90 text-white font-semibold text-xs rounded-lg transition shadow-md">Sign In</button>
        </form>
    </div>
    <script>
        async function handleLogin(e) {
            e.preventDefault();
            const password = document.getElementById('password-input').value;
            const res = await fetch('/api/login', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ password })
            });
            const data = await res.json();
            if (data.status === 'success') {
                window.location.href = '/';
            } else {
                const errEl = document.getElementById('error-msg');
                errEl.innerText = data.message || 'Incorrect password.';
                errEl.classList.remove('hidden');
            }
        }
    </script>
</body>
</html>
"""

UNIFIED_HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en" class="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>BoussoleAI — Career & Academic Trajectory Platform</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script>
        tailwind.config = { darkMode: 'class' };
    </script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }
        .custom-scrollbar::-webkit-scrollbar { width: 6px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
        .dark .custom-scrollbar::-webkit-scrollbar-thumb { background: #334155; }
        * { box-sizing: border-box; min-width: 0; }
        body, html { overflow-x: hidden; width: 100%; height: 100%; }
        #chat-stream { overflow-x: hidden !important; word-break: break-word; overflow-wrap: anywhere; }
        .ai-markdown-body p { margin-bottom: 0.75rem !important; }
        .ai-markdown-body ul, .ai-markdown-body ol { margin-bottom: 0.75rem !important; padding-left: 1.25rem; list-style-type: disc; }
        input[type=number]::-webkit-inner-spin-button, input[type=number]::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
        
        .bg-grid-pattern {
            background-size: 28px 28px;
            background-image: radial-gradient(circle, rgba(99, 102, 241, 0.12) 1.2px, transparent 1.2px);
        }
        .dark .bg-grid-pattern {
            background-image: radial-gradient(circle, rgba(129, 140, 248, 0.15) 1.2px, transparent 1.2px);
        }
    </style>
</head>
<body class="bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 min-h-[100dvh] flex flex-col justify-between overflow-y-auto md:overflow-hidden transition-colors relative bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-100/50 via-slate-50 to-slate-100 dark:from-indigo-950/30 dark:via-slate-950 dark:to-slate-950" onload="initApp()">

    <!-- Header Navigation Bar -->
    <header class="border-b border-slate-200/80 dark:border-slate-800/80 bg-white/70 dark:bg-slate-900/70 backdrop-blur-md sticky top-0 z-50 flex-shrink-0 transition-colors shadow-sm">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between gap-4">
            
            <!-- Branding with Dual Gradient & Compass -->
            <div class="flex items-center gap-2">
                <svg class="w-5 h-5 text-indigo-600 dark:text-indigo-400 flex-shrink-0 transition-transform hover:rotate-45" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                    <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.75"/>
                    <polygon points="12,6 14.5,11.5 12,10 9.5,11.5" fill="currentColor"/>
                    <polygon points="12,18 9.5,12.5 12,14 14.5,12.5" fill="currentColor" opacity="0.4"/>
                </svg>
                <div class="flex items-center gap-2">
                    <h1 class="font-bold text-base tracking-tight">
                        <span class="bg-gradient-to-r from-indigo-600 to-violet-500 dark:from-indigo-400 dark:to-violet-400 bg-clip-text text-transparent font-bold">Boussole</span><span class="bg-gradient-to-r from-violet-500 via-purple-500 to-cyan-500 bg-clip-text text-transparent font-extrabold">AI</span>
                    </h1>
                    <span class="px-1.5 py-0.5 rounded-full text-[10px] font-semibold bg-indigo-50 dark:bg-indigo-950/60 text-indigo-600 dark:text-indigo-400 border border-indigo-200/60 dark:border-indigo-800/50">PRO</span>
                </div>
            </div>
            
            <div class="flex items-center gap-2 flex-shrink-0">
                <!-- Mobile Select -->
                <select id="mobile-view-select" onchange="switchView(this.value)" class="md:hidden text-xs font-medium px-2.5 py-1.5 rounded-md bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 border border-slate-200 dark:border-slate-700 outline-none">
                    <option value="career" data-i18n="btn_career">Career Coach</option>
                    <option value="job" data-i18n="btn_job">Job Matcher</option>
                    <option value="copilot" data-i18n="btn_copilot">Financial Aid</option>
                    <option value="bridge" data-i18n="btn_bridge">Grant-to-Career</option>
                </select>

                <!-- Desktop Navigation Pills -->
                <div class="hidden md:flex items-center bg-slate-200/50 dark:bg-slate-800/60 p-1 rounded-xl border border-slate-200/80 dark:border-slate-700/80 gap-1 backdrop-blur-sm">
                    <button onclick="switchView('career')" id="btn-career" data-i18n="btn_career" class="text-xs font-medium px-3 py-1.5 rounded-lg bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-sm transition">
                        Career Coach
                    </button>
                    <button onclick="switchView('job')" id="btn-job" data-i18n="btn_job" class="text-xs font-medium px-3 py-1.5 rounded-lg text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition">
                        Job Matcher
                    </button>
                    <button onclick="switchView('copilot')" id="btn-copilot" data-i18n="btn_copilot" class="text-xs font-medium px-3 py-1.5 rounded-lg text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition">
                        Financial Aid
                    </button>
                    <button onclick="switchView('bridge')" id="btn-bridge" data-i18n="btn_bridge" class="text-xs font-medium px-3 py-1.5 rounded-lg text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition">
                        Grant-to-Career
                    </button>
                </div>

                <!-- Language Selector -->
                <select id="lang-select" onchange="changeLanguage(this.value)" class="text-xs font-medium px-2 py-1.5 rounded-lg bg-white/80 dark:bg-slate-800/80 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700 transition outline-none cursor-pointer">
                    <option value="en">English</option>
                    <option value="zh-tw">繁體中文</option>
                    <option value="zh-cn">简体中文</option>
                </select>

                <!-- Dark / Light Text Mode Switcher -->
                <button onclick="toggleTheme()" id="theme-toggle" class="px-2.5 py-1.5 rounded-lg bg-white/80 dark:bg-slate-800/80 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700 transition text-xs font-medium flex items-center justify-center">
                    <span id="theme-label">Dark</span>
                </button>

                <!-- Logout -->
                <a href="/api/logout" class="text-xs font-medium px-2.5 py-1.5 rounded-lg bg-white/80 dark:bg-slate-800/80 hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700 transition" title="Sign out">Sign out</a>
            </div>
        </div>
    </header>

    <!-- MAIN APP CONTAINER WITH GRID PATTERN -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 w-full flex-1 flex flex-col overflow-y-auto md:overflow-hidden bg-grid-pattern">

        <!-- VIEW 1: CAREER COACH -->
        <div id="view-career" class="flex-1 flex flex-col md:flex-row gap-4 h-full overflow-y-auto md:overflow-hidden">
            <aside class="w-full md:w-72 flex flex-col gap-3 flex-shrink-0 overflow-y-auto max-h-[240px] md:max-h-none custom-scrollbar">
                
                <!-- Chat History Panel -->
                <div class="bg-white/80 dark:bg-slate-900/80 backdrop-blur-md rounded-2xl border border-slate-200/80 dark:border-slate-800/80 p-3.5 shadow-sm flex flex-col gap-2">
                    <div class="flex items-center justify-between">
                        <h2 class="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider" data-i18n="chat_history_title">Conversations</h2>
                        <button onclick="createNewChat()" data-i18n="new_chat_btn" class="text-xs text-indigo-600 dark:text-indigo-400 hover:underline font-semibold transition">+ New</button>
                    </div>
                    <div id="chat-history-list" class="flex flex-col gap-1 max-h-[140px] overflow-y-auto custom-scrollbar">
                        <!-- Dynamic items -->
                    </div>
                </div>

                <!-- Resume Upload -->
                <div class="bg-white/80 dark:bg-slate-900/80 backdrop-blur-md rounded-2xl border border-slate-200/80 dark:border-slate-800/80 p-3.5 shadow-sm flex flex-col gap-2">
                    <h2 class="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider" data-i18n="upload_resume_title">Resume Context</h2>
                    <label for="pdf-file-input" class="cursor-pointer flex items-center justify-center p-2.5 border border-dashed border-slate-300 dark:border-slate-700 hover:border-indigo-500 dark:hover:border-indigo-400 rounded-xl bg-slate-50/50 dark:bg-slate-950/50 transition text-center">
                        <span id="upload-status-text" data-i18n="upload_resume_label" class="text-xs text-slate-600 dark:text-slate-400 font-medium truncate">Attach PDF/TXT Resume</span>
                    </label>
                    <input id="pdf-file-input" type="file" accept=".pdf,.txt" class="hidden" onchange="handleFileUpload(event)">
                </div>

                <!-- Playbooks -->
                <div class="bg-white/80 dark:bg-slate-900/80 backdrop-blur-md rounded-2xl border border-slate-200/80 dark:border-slate-800/80 p-3.5 shadow-sm flex flex-col gap-2">
                    <h2 class="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider" data-i18n="playbooks_title">Action Templates</h2>
                    <div class="grid grid-cols-1 gap-1.5">
                        <button onclick="applyPreset('roast')" data-i18n="preset_roast" class="text-left p-2 rounded-xl bg-slate-50/80 dark:bg-slate-950/80 border border-slate-200/60 dark:border-slate-800/60 hover:border-indigo-500/40 hover:bg-slate-100 dark:hover:bg-slate-800 transition text-xs text-slate-700 dark:text-slate-300 font-medium truncate">Resume Audit</button>
                        <button onclick="applyPreset('gap')" data-i18n="preset_gap" class="text-left p-2 rounded-xl bg-slate-50/80 dark:bg-slate-950/80 border border-slate-200/60 dark:border-slate-800/60 hover:border-indigo-500/40 hover:bg-slate-100 dark:hover:bg-slate-800 transition text-xs text-slate-700 dark:text-slate-300 font-medium truncate">Skill Gap Analysis</button>
                        <button onclick="applyPreset('behavioral')" data-i18n="preset_behavioral" class="text-left p-2 rounded-xl bg-slate-50/80 dark:bg-slate-950/80 border border-slate-200/60 dark:border-slate-800/60 hover:border-indigo-500/40 hover:bg-slate-100 dark:hover:bg-slate-800 transition text-xs text-slate-700 dark:text-slate-300 font-medium truncate">Interview Prep</button>
                        <button onclick="applyPreset('roadmap')" data-i18n="preset_roadmap" class="text-left p-2 rounded-xl bg-slate-50/80 dark:bg-slate-950/80 border border-slate-200/60 dark:border-slate-800/60 hover:border-indigo-500/40 hover:bg-slate-100 dark:hover:bg-slate-800 transition text-xs text-slate-700 dark:text-slate-300 font-medium truncate">90-Day Plan</button>
                    </div>
                </div>

                <!-- Actions -->
                <div id="sidebar-actions" class="bg-white/80 dark:bg-slate-900/80 backdrop-blur-md rounded-2xl border border-slate-200/80 dark:border-slate-800/80 p-3.5 shadow-sm flex flex-col gap-2">
                    <h2 class="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider" data-i18n="chat_actions_title">Session Options</h2>
                    <div class="flex flex-col gap-1.5">
                        <button onclick="exportMarkdown()" id="export-btn" data-i18n="export_btn" class="text-left p-2 rounded-xl bg-slate-50/80 dark:bg-slate-950/80 border border-slate-200/60 dark:border-slate-800/60 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-medium transition truncate">
                            Export Conversation
                        </button>
                        <button onclick="deleteActiveChat()" data-i18n="delete_btn" class="text-left p-2 rounded-xl bg-slate-50/80 dark:bg-slate-950/80 border border-slate-200/60 dark:border-slate-800/60 hover:bg-rose-50 dark:hover:bg-rose-950/40 hover:text-rose-600 text-slate-700 dark:text-slate-300 text-xs font-medium transition truncate">
                            Delete Current Session
                        </button>
                    </div>
                </div>
            </aside>

            <!-- Chat Main Panel with Top Gradient Line -->
            <section class="flex-1 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md rounded-2xl border border-slate-200/80 dark:border-slate-800/80 shadow-md flex flex-col overflow-hidden h-full min-h-[480px] md:min-h-0 min-w-0 relative before:absolute before:top-0 before:left-0 before:right-0 before:h-1 before:bg-gradient-to-r before:from-indigo-500 before:via-purple-500 before:to-cyan-500">
                <div id="chat-stream" class="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar text-sm pt-5">
                    <!-- Messages -->
                </div>

                <!-- Input Bar -->
                <div class="p-3 border-t border-slate-200/80 dark:border-slate-800/80 bg-slate-50/50 dark:bg-slate-950/50 flex-shrink-0 flex flex-col gap-2">
                    <form id="chat-form" class="flex gap-2 items-center">
                        <textarea id="user-input" rows="1" class="flex-1 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 text-sm rounded-xl px-3.5 py-2.5 border border-slate-300 dark:border-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 custom-scrollbar resize-none min-h-[42px] shadow-inner" placeholder="Ask a question or select an action template..." required></textarea>
                        <button type="submit" id="send-button" data-i18n="send_btn" class="px-4 py-2.5 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-medium rounded-xl text-xs transition shadow-md">Send</button>
                    </form>
                    <div class="text-[11px] text-slate-500 dark:text-slate-400 px-1">
                        <span data-i18n="tip_enter">Press Enter to send, Shift + Enter for line break.</span>
                    </div>
                </div>
            </section>
        </div>

        <!-- VIEW 2: JOB COMPARISON PAGE -->
        <div id="view-job" class="hidden flex-1 flex flex-col gap-4 overflow-y-auto custom-scrollbar">
            <div class="bg-white/80 dark:bg-slate-900/80 backdrop-blur-md rounded-2xl border border-slate-200/80 dark:border-slate-800/80 p-6 shadow-md flex flex-col gap-6 max-w-5xl mx-auto w-full relative overflow-hidden before:absolute before:top-0 before:left-0 before:right-0 before:h-1 before:bg-gradient-to-r before:from-indigo-500 before:via-purple-500 before:to-cyan-500">
                <div>
                    <h2 class="text-base font-bold text-slate-900 dark:text-white" data-i18n="job_view_title">Role Compatibility & Match Analysis</h2>
                    <p class="text-xs text-slate-500 dark:text-slate-400 mt-0.5" data-i18n="job_view_subtitle">Evaluate target positions against your resume profile.</p>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <!-- Column A: Inputs -->
                    <div class="flex flex-col gap-4">
                        <h3 class="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider" data-i18n="job_col1_title">1. Resume & Target Positions</h3>
                        
                        <div class="flex flex-col gap-1.5">
                            <label class="text-xs font-medium text-slate-700 dark:text-slate-300" data-i18n="job_upload_label">Upload CV Document:</label>
                            <label for="job-file-input" class="cursor-pointer flex items-center justify-center p-2.5 border border-dashed border-slate-300 dark:border-slate-700 hover:border-indigo-500 rounded-xl bg-slate-50/50 dark:bg-slate-950/50 transition text-center">
                                <span id="job-upload-status" data-i18n="job_upload_status" class="text-xs text-slate-600 dark:text-slate-400 font-medium truncate">Attach Resume (PDF/TXT)</span>
                            </label>
                            <input id="job-file-input" type="file" accept=".pdf,.txt" class="hidden" onchange="handleJobFileUpload(event)">
                        </div>

                        <div class="flex flex-col gap-1.5">
                            <label class="text-xs font-medium text-slate-700 dark:text-slate-300" data-i18n="job_paste_label">Or Resume Text:</label>
                            <textarea id="job-cv-text" rows="4" class="w-full bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 text-xs rounded-xl p-3 border border-slate-300 dark:border-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 custom-scrollbar resize-none shadow-inner" placeholder="Paste resume text..."></textarea>
                        </div>

                        <button onclick="recommendJobs()" id="recommend-jobs-btn" data-i18n="job_recommend_btn" class="w-full py-2 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 font-medium text-xs rounded-xl border border-slate-200 dark:border-slate-700 transition">
                            Suggest Target Roles from CV
                        </button>

                        <div class="flex flex-col gap-2">
                            <div class="flex justify-between items-center">
                                <label class="text-xs font-medium text-slate-700 dark:text-slate-300" data-i18n="job_target_label">Target Positions:</label>
                                <button onclick="addJobInputBox()" data-i18n="job_add_role_btn" class="text-xs text-indigo-600 dark:text-indigo-400 font-semibold hover:underline">+ Add Position</button>
                            </div>
                            <div id="job-inputs-list" class="flex flex-col gap-2">
                                <div class="job-input-item flex flex-col gap-2 p-3 rounded-xl bg-slate-50/70 dark:bg-slate-950/70 border border-slate-200/80 dark:border-slate-800/80">
                                    <input type="text" placeholder="Job Title (e.g. Software Engineer)" data-i18n-placeholder="job_title_ph" class="job-title-input w-full bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 text-xs rounded-lg px-2.5 py-1.5 border border-slate-300 dark:border-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500">
                                    <textarea rows="2" placeholder="Job description (optional)..." data-i18n-placeholder="job_desc_ph" class="job-desc-input w-full bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 text-xs rounded-lg p-2.5 border border-slate-300 dark:border-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 custom-scrollbar resize-none"></textarea>
                                </div>
                            </div>
                        </div>

                        <button onclick="runJobMatch()" id="job-submit-btn" data-i18n="job_submit_btn" class="w-full py-2.5 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-medium text-xs rounded-xl transition shadow-md">
                            Run Match Evaluation
                        </button>
                    </div>

                    <!-- Column B: Results -->
                    <div class="flex flex-col gap-3 bg-slate-50/70 dark:bg-slate-950/70 p-4 rounded-xl border border-slate-200/80 dark:border-slate-800/80 overflow-y-auto custom-scrollbar">
                        <div class="flex justify-between items-center">
                            <h3 class="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider" data-i18n="job_history_title">2. Analysis Results</h3>
                            <button onclick="clearJobHistory()" data-i18n="job_clear_btn" class="text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 transition">Clear</button>
                        </div>
                        
                        <div id="job-placeholder-state" class="flex-1 flex flex-col items-center justify-center text-center p-6 text-slate-500 dark:text-slate-400 text-xs gap-1 min-h-[200px]">
                            <p data-i18n="job_history_empty">Submit your resume and target job titles to generate fit metrics and keyword gaps.</p>
                        </div>

                        <div id="job-history-container" class="flex flex-col gap-3">
                            <!-- Results inject here -->
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- VIEW 3: STUDENT FINANCIAL AID PORTAL -->
        <div id="view-copilot" class="hidden flex-1 grid grid-cols-1 md:grid-cols-3 gap-4 h-auto md:h-full overflow-y-auto md:overflow-hidden custom-scrollbar">
            <!-- Left Inputs -->
            <section class="bg-white/80 dark:bg-slate-900/80 backdrop-blur-md rounded-2xl border border-slate-200/80 dark:border-slate-800/80 p-5 shadow-sm flex flex-col gap-4 h-[460px] md:h-full overflow-y-auto custom-scrollbar">
                <h2 class="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider" data-i18n="copilot_col1_title">1. Financial Assessment</h2>
                <div class="grid grid-cols-2 gap-2">
                    <button onclick="loadScenario('full_grant', 10000, 4)" data-i18n="scenario_full" class="p-2 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs text-slate-800 dark:text-slate-200 text-left hover:bg-slate-100 dark:hover:bg-slate-800 transition truncate">Full Grant Profile</button>
                    <button onclick="loadScenario('partial_grant', 18000, 4)" data-i18n="scenario_partial" class="p-2 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs text-slate-800 dark:text-slate-200 text-left hover:bg-slate-100 dark:hover:bg-slate-800 transition truncate">Partial Grant Profile</button>
                    <button onclick="loadScenario('ineligible', 24000, 3)" data-i18n="scenario_high" class="p-2 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs text-slate-800 dark:text-slate-200 text-left hover:bg-slate-100 dark:hover:bg-slate-800 transition truncate">Standard Profile</button>
                    <button onclick="loadScenario('missing_income', null, 2)" data-i18n="scenario_incomplete" class="p-2 rounded-xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800 text-xs text-slate-800 dark:text-slate-200 text-left hover:bg-slate-100 dark:hover:bg-slate-800 transition truncate">Incomplete Profile</button>
                </div>
                <textarea id="case-notes" rows="4" class="w-full bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 text-xs rounded-xl p-3 border border-slate-300 dark:border-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 custom-scrollbar resize-none shadow-inner" placeholder="Enter household financial details..." data-i18n-placeholder="copilot_notes_ph"></textarea>
                
                <button onclick="processCase()" id="process-btn" data-i18n="copilot_calc_btn" class="w-full py-2.5 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-medium text-xs rounded-xl transition shadow-md">Evaluate Eligibility</button>

                <!-- Parameter Adjustment -->
                <div class="pt-3 border-t border-slate-200 dark:border-slate-800 flex flex-col gap-3">
                    <span class="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider" data-i18n="copilot_whatif_title">Adjust Metrics</span>
                    
                    <div class="flex flex-col gap-1.5">
                        <div class="flex justify-between items-center text-xs text-slate-700 dark:text-slate-300">
                            <span data-i18n="copilot_income_label">Monthly Household Income (HKD):</span>
                            <input id="income-input-box" type="number" min="0" max="100000" step="100" value="10000" class="w-24 bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 font-semibold text-xs rounded-lg px-2 py-1 border border-slate-300 dark:border-slate-800 text-right focus:outline-none focus:ring-1 focus:ring-indigo-500" oninput="syncFromBox('income')">
                        </div>
                        <input id="income-slider" type="range" min="0" max="50000" step="500" value="10000" class="w-full accent-indigo-600 cursor-pointer" oninput="syncFromSlider('income')">
                    </div>

                    <div class="flex flex-col gap-1.5">
                        <div class="flex justify-between items-center text-xs text-slate-700 dark:text-slate-300">
                            <span data-i18n="copilot_members_label">Household Members:</span>
                            <input id="members-input-box" type="number" min="1" max="15" step="1" value="4" class="w-20 bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 font-semibold text-xs rounded-lg px-2 py-1 border border-slate-300 dark:border-slate-800 text-right focus:outline-none focus:ring-1 focus:ring-indigo-500" oninput="syncFromBox('members')">
                        </div>
                        <input id="members-slider" type="range" min="1" max="8" step="1" value="4" class="w-full accent-indigo-600 cursor-pointer" oninput="syncFromSlider('members')">
                    </div>
                </div>
            </section>

            <!-- Privacy Shield -->
            <section class="bg-white/80 dark:bg-slate-900/80 backdrop-blur-md rounded-2xl border border-slate-200/80 dark:border-slate-800/80 p-5 shadow-sm flex flex-col gap-3 h-[420px] md:h-full overflow-y-auto custom-scrollbar">
                <h2 class="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider" data-i18n="copilot_privacy_title">2. Compliance & Privacy Audit</h2>
                <div id="pii-status" class="hidden p-2.5 rounded-xl bg-slate-50/80 dark:bg-slate-950/80 border border-slate-200 dark:border-slate-800 text-xs flex justify-between items-center">
                    <span class="text-slate-600 dark:text-slate-400" data-i18n="copilot_protected_label">Redacted Items:</span>
                    <span id="pii-count" class="font-semibold text-indigo-600 dark:text-indigo-400">0</span>
                </div>
                <div id="sanitized-text" data-i18n="copilot_awaiting_input" class="flex-1 bg-slate-50/70 dark:bg-slate-950/70 p-3 rounded-xl border border-slate-200/80 dark:border-slate-800/80 text-xs text-slate-600 dark:text-slate-400 font-mono overflow-y-auto custom-scrollbar min-h-[220px]">Awaiting input...</div>
            </section>

            <!-- Results & Action Plan -->
            <section class="bg-white/80 dark:bg-slate-900/80 backdrop-blur-md rounded-2xl border border-slate-200/80 dark:border-slate-800/80 p-5 shadow-sm flex flex-col gap-4 h-[540px] md:h-full overflow-y-auto custom-scrollbar">
                <h2 class="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider" data-i18n="copilot_result_title">3. Evaluation Summary</h2>
                
                <div class="bg-slate-50/80 dark:bg-slate-950/80 p-4 rounded-xl border border-slate-200/80 dark:border-slate-800/80 flex flex-col gap-3">
                    <div class="flex justify-between items-center">
                        <span class="text-xs text-slate-500 dark:text-slate-400" data-i18n="copilot_status_label">Status:</span>
                        <span id="verdict-badge" data-i18n="copilot_awaiting_badge" class="px-2 py-0.5 rounded-md text-[11px] font-semibold bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300">AWAITING EVALUATION</span>
                    </div>
                    <h3 id="verdict-title" data-i18n="copilot_no_profile" class="text-xs font-bold text-slate-900 dark:text-white">No profile evaluated</h3>
                    <p id="verdict-details" data-i18n="copilot_calc_prompt" class="text-xs text-slate-600 dark:text-slate-400">Enter parameters above to view guidance.</p>
                    
                    <div class="pt-2 border-t border-slate-200 dark:border-slate-800">
                        <span class="text-[10px] uppercase font-semibold text-slate-500 dark:text-slate-400 tracking-wider" data-i18n="copilot_policy_label">Policy Reference:</span>
                        <p id="verdict-citation" class="text-xs text-slate-700 dark:text-slate-300 font-medium mt-0.5">—</p>
                    </div>

                    <div class="pt-2 border-t border-slate-200 dark:border-slate-800">
                        <span class="text-[10px] uppercase font-semibold text-slate-500 dark:text-slate-400 tracking-wider" data-i18n="copilot_checklist_label">Required Verification Documents:</span>
                        <ul id="document-checklist" class="text-xs text-slate-700 dark:text-slate-300 space-y-1 mt-1 pl-2">
                            <li data-i18n="copilot_checklist_awaiting">• Awaiting evaluation</li>
                        </ul>
                    </div>
                </div>

                <!-- Hardship Appeal -->
                <div class="bg-slate-50/80 dark:bg-slate-950/80 p-4 rounded-xl border border-slate-200/80 dark:border-slate-800/80 flex flex-col gap-2.5">
                    <span class="text-xs font-semibold text-slate-700 dark:text-slate-300 tracking-wider" data-i18n="copilot_appeal_title">Special Circumstances Appeal</span>
                    <p class="text-xs text-slate-500 dark:text-slate-400" data-i18n="copilot_appeal_desc">Submit an exception request for officer review.</p>
                    <select id="override-reason" class="w-full bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 text-xs rounded-xl p-2 border border-slate-300 dark:border-slate-800 outline-none">
                        <option value="" data-i18n="copilot_appeal_default">Select review reason...</option>
                        <option value="Medical Emergency" data-i18n="appeal_opt1">Family Medical Emergency</option>
                        <option value="Loss of Income" data-i18n="appeal_opt2">Sudden Loss of Income Provider</option>
                        <option value="Income Discrepancy" data-i18n="appeal_opt3">Seasonal Income Discrepancy</option>
                    </select>
                    <button onclick="executeOverride()" data-i18n="copilot_appeal_btn" class="py-2 bg-slate-900 dark:bg-slate-800 hover:bg-slate-800 dark:hover:bg-slate-700 text-white dark:text-slate-100 font-medium text-xs rounded-xl transition shadow-sm">
                        Submit Appeal Request
                    </button>
                    <div id="override-timestamp" class="text-[10px] text-slate-500 dark:text-slate-400 text-center hidden"></div>
                </div>
            </section>
        </div>

        <!-- VIEW 4: GRANT-TO-CAREER BRIDGE -->
        <div id="view-bridge" class="hidden flex-1 flex flex-col gap-4 overflow-y-auto custom-scrollbar">
            <div class="bg-white/80 dark:bg-slate-900/80 backdrop-blur-md rounded-2xl border border-slate-200/80 dark:border-slate-800/80 p-6 shadow-md flex flex-col gap-6 max-w-4xl mx-auto w-full relative overflow-hidden before:absolute before:top-0 before:left-0 before:right-0 before:h-1 before:bg-gradient-to-r before:from-indigo-500 before:via-purple-500 before:to-cyan-500">
                <div>
                    <h2 class="text-base font-bold text-slate-900 dark:text-white" data-i18n="bridge_title">Financial Assistance & Work-Study Bridge</h2>
                    <p class="text-xs text-slate-500 dark:text-slate-400 mt-0.5" data-i18n="bridge_subtitle">Evaluate funding gaps and available work-study programs.</p>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-3 gap-4 bg-slate-50/80 dark:bg-slate-950/80 p-4 rounded-xl border border-slate-200/80 dark:border-slate-800/80">
                    <div class="flex flex-col gap-1.5">
                        <div class="flex justify-between items-center text-xs text-slate-700 dark:text-slate-300">
                            <span data-i18n="bridge_income_label">Monthly Income:</span>
                            <input id="bridge-income-input-box" type="number" min="0" max="100000" step="100" value="10000" class="w-20 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 font-semibold text-xs rounded-lg px-2 py-1 border border-slate-300 dark:border-slate-800 text-right focus:outline-none" oninput="syncBridgeFromBox('income')">
                        </div>
                        <input id="bridge-income-slider" type="range" min="0" max="50000" step="500" value="10000" class="w-full accent-indigo-600 cursor-pointer" oninput="syncBridgeFromSlider('income')">
                    </div>

                    <div class="flex flex-col gap-1.5">
                        <div class="flex justify-between items-center text-xs text-slate-700 dark:text-slate-300">
                            <span data-i18n="bridge_tuition_label">Tuition Cost:</span>
                            <input id="tuition-input-box" type="number" min="0" max="200000" step="500" value="42100" class="w-20 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 font-semibold text-xs rounded-lg px-2 py-1 border border-slate-300 dark:border-slate-800 text-right focus:outline-none" oninput="syncBridgeFromBox('tuition')">
                        </div>
                        <input id="tuition-slider" type="range" min="10000" max="100000" step="1000" value="42100" class="w-full accent-indigo-600 cursor-pointer" oninput="syncBridgeFromSlider('tuition')">
                    </div>

                    <div class="flex flex-col gap-1.5">
                        <div class="flex justify-between items-center text-xs text-slate-700 dark:text-slate-300">
                            <span data-i18n="bridge_living_label">Living Expenses:</span>
                            <input id="living-input-box" type="number" min="0" max="200000" step="500" value="30000" class="w-20 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 font-semibold text-xs rounded-lg px-2 py-1 border border-slate-300 dark:border-slate-800 text-right focus:outline-none" oninput="syncBridgeFromBox('living')">
                        </div>
                        <input id="living-slider" type="range" min="0" max="80000" step="1000" value="30000" class="w-full accent-indigo-600 cursor-pointer" oninput="syncBridgeFromSlider('living')">
                    </div>
                </div>

                <div class="bg-slate-50/80 dark:bg-slate-950/80 p-4 rounded-xl border border-slate-200/80 dark:border-slate-800/80 flex flex-col gap-3">
                    <h3 class="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider" data-i18n="bridge_shortfall_title">Financial Gap Summary</h3>
                    <p class="text-xs text-slate-700 dark:text-slate-300"><span data-i18n="bridge_shortfall_text">Based on current inputs, calculated remaining shortfall:</span> <strong id="dynamic-shortfall" class="text-slate-900 dark:text-white">HKD $21,050</strong>.</p>
                    
                    <div class="p-3 rounded-xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 flex flex-col gap-1 text-xs">
                        <div class="flex justify-between items-center">
                            <span class="text-slate-700 dark:text-slate-300 font-medium" data-i18n="bridge_loan_status_label">Loan Scheme Options:</span>
                            <span id="loan-status-badge" data-i18n="bridge_loan_eligible_badge" class="px-2 py-0.5 rounded-md text-[10px] font-semibold bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800">NLSFT Eligible</span>
                        </div>
                        <p id="loan-details" class="text-slate-600 dark:text-slate-400 mt-1" data-i18n="bridge_loan_desc">You remain eligible to access government student loan schemes (NLSFT) to offset expenses.</p>
                    </div>
                </div>

                <div class="flex flex-col gap-3">
                    <h3 class="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider" data-i18n="bridge_matched_jobs_title">Campus & Work-Study Opportunities</h3>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div class="bg-slate-50/80 dark:bg-slate-950/80 p-4 rounded-xl border border-slate-200/80 dark:border-slate-800/80 flex flex-col justify-between gap-3">
                            <div>
                                <span class="px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-200 dark:bg-slate-800 text-slate-800 dark:text-slate-200" data-i18n="job_badge_flexible">Part-Time</span>
                                <h4 class="text-xs font-bold text-slate-900 dark:text-white mt-2" data-i18n="bridge_job1_title">AI Lab Student Assistant</h4>
                                <p class="text-xs text-slate-600 dark:text-slate-400 mt-1" data-i18n="bridge_job1_desc">Assist with basic Python data tasks and department script optimization.</p>
                            </div>
                            <div class="flex justify-between items-center pt-2 border-t border-slate-200 dark:border-slate-800">
                                <span class="text-xs font-semibold text-slate-900 dark:text-white">HKD $120 / hour</span>
                                <button onclick="alert('Application forwarded to Career Coach context.')" data-i18n="bridge_apply_btn" class="px-3 py-1 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white text-xs font-medium rounded-lg transition shadow-sm">Apply</button>
                            </div>
                        </div>

                        <div class="bg-slate-50/80 dark:bg-slate-950/80 p-4 rounded-xl border border-slate-200/80 dark:border-slate-800/80 flex flex-col justify-between gap-3">
                            <div>
                                <span class="px-2 py-0.5 rounded-md text-[10px] font-medium bg-slate-200 dark:bg-slate-800 text-slate-800 dark:text-slate-200" data-i18n="job_badge_grant">Work-Study</span>
                                <h4 class="text-xs font-bold text-slate-900 dark:text-white mt-2" data-i18n="bridge_job2_title">Financial Aid Ambassador</h4>
                                <p class="text-xs text-slate-600 dark:text-slate-400 mt-1" data-i18n="bridge_job2_desc">Help students navigate documentation requirements and submission checklists.</p>
                            </div>
                            <div class="flex justify-between items-center pt-2 border-t border-slate-200 dark:border-slate-800">
                                <span class="text-xs font-semibold text-slate-900 dark:text-white">HKD $4,500 / month</span>
                                <button onclick="alert('Application forwarded to Career Coach context.')" data-i18n="bridge_apply_btn" class="px-3 py-1 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white text-xs font-medium rounded-lg transition shadow-sm">Apply</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

    </main>

    <!-- Frontend Script Logic -->
    <script>
        // Global buffer map for streams running in the background
        window.activeStreams = window.activeStreams || {};

        const translations = {
            en: {
                brand_subtitle_career: "Career Navigation",
                btn_career: "Career Coach",
                btn_job: "Job Matcher",
                btn_copilot: "Financial Aid",
                btn_bridge: "Grant-to-Career",
                chat_history_title: "Conversations",
                new_chat_btn: "+ New",
                upload_resume_title: "Resume Context",
                upload_resume_label: "Attach PDF/TXT Resume",
                playbooks_title: "Action Templates",
                preset_roast: "Resume Audit",
                preset_gap: "Skill Gap Analysis",
                preset_behavioral: "Interview Prep",
                preset_roadmap: "90-Day Plan",
                chat_actions_title: "Session Options",
                export_btn: "Export Conversation",
                delete_btn: "Delete Current Session",
                chat_placeholder: "Ask a question or select an action template...",
                send_btn: "Send",
                tip_enter: "Press Enter to send, Shift + Enter for line break.",
                
                job_view_title: "Role Compatibility & Match Analysis",
                job_view_subtitle: "Evaluate target positions against your resume profile.",
                job_col1_title: "1. Resume & Target Positions",
                job_upload_label: "Upload CV Document:",
                job_upload_status: "Attach Resume (PDF/TXT)",
                job_paste_label: "Or Resume Text:",
                job_recommend_btn: "Suggest Target Roles from CV",
                job_target_label: "Target Positions:",
                job_add_role_btn: "+ Add Position",
                job_title_ph: "Job Title (e.g. Software Engineer)",
                job_desc_ph: "Job description (optional)...",
                job_submit_btn: "Run Match Evaluation",
                job_history_title: "2. Analysis Results",
                job_clear_btn: "Clear",
                job_history_empty: "Submit your resume and target job titles to generate fit metrics and keyword gaps.",

                copilot_col1_title: "1. Financial Assessment",
                scenario_full: "Full Grant Profile",
                scenario_partial: "Partial Grant Profile",
                scenario_high: "Standard Profile",
                scenario_incomplete: "Incomplete Profile",
                copilot_notes_ph: "Enter household financial details...",
                copilot_calc_btn: "Evaluate Eligibility",
                copilot_whatif_title: "Adjust Metrics",
                copilot_income_label: "Monthly Household Income (HKD):",
                copilot_members_label: "Household Members:",
                copilot_privacy_title: "2. Compliance & Privacy Audit",
                copilot_protected_label: "Redacted Items:",
                copilot_awaiting_input: "Awaiting input...",
                copilot_result_title: "3. Evaluation Summary",
                copilot_status_label: "Status:",
                copilot_awaiting_badge: "AWAITING EVALUATION",
                copilot_no_profile: "No profile evaluated",
                copilot_calc_prompt: "Enter parameters above to view guidance.",
                copilot_policy_label: "Policy Reference:",
                copilot_checklist_label: "Required Verification Documents:",
                copilot_checklist_awaiting: "• Awaiting evaluation",
                copilot_appeal_title: "Special Circumstances Appeal",
                copilot_appeal_desc: "Submit an exception request for officer review.",
                copilot_appeal_default: "Select review reason...",
                appeal_opt1: "Family Medical Emergency",
                appeal_opt2: "Sudden Loss of Income Provider",
                appeal_opt3: "Seasonal Income Discrepancy",
                copilot_appeal_btn: "Submit Appeal Request",

                bridge_title: "Financial Assistance & Work-Study Bridge",
                bridge_subtitle: "Evaluate funding gaps and available work-study programs.",
                bridge_income_label: "Monthly Income:",
                bridge_tuition_label: "Tuition Cost:",
                bridge_living_label: "Living Expenses:",
                bridge_shortfall_title: "Financial Gap Summary",
                bridge_shortfall_text: "Based on current inputs, calculated remaining shortfall:",
                bridge_loan_status_label: "Loan Scheme Options:",
                bridge_loan_eligible_badge: "NLSFT Eligible",
                bridge_loan_desc: "You remain eligible to access government student loan schemes (NLSFT) to offset expenses.",
                bridge_matched_jobs_title: "Campus & Work-Study Opportunities",
                job_badge_flexible: "Part-Time",
                job_badge_grant: "Work-Study",
                bridge_job1_title: "AI Lab Student Assistant",
                bridge_job1_desc: "Assist with basic Python data tasks and department script optimization.",
                bridge_job2_title: "Financial Aid Ambassador",
                bridge_job2_desc: "Help students navigate documentation requirements and submission checklists.",
                bridge_apply_btn: "Apply"
            },
            "zh-tw": {
                brand_subtitle_career: "職涯導航系統",
                btn_career: "職涯教練",
                btn_job: "職缺匹配",
                btn_copilot: "學生資助",
                btn_bridge: "資助與就業橋樑",
                chat_history_title: "對話歷史",
                new_chat_btn: "+ 新建",
                upload_resume_title: "履歷內容",
                upload_resume_label: "附加 PDF/TXT 履歷",
                playbooks_title: "快捷模組",
                preset_roast: "履歷檢核",
                preset_gap: "技能落差分析",
                preset_behavioral: "面試模擬",
                preset_roadmap: "90 天規劃",
                chat_actions_title: "會話選項",
                export_btn: "匯出對話紀錄",
                delete_btn: "刪除當前會話",
                chat_placeholder: "請輸入問題或選擇快捷模組...",
                send_btn: "發送",
                tip_enter: "按 Enter 發送，Shift + Enter 換行。",

                job_view_title: "職位匹配與適配度分析",
                job_view_subtitle: "根據您的履歷評估目標職位的匹配程度。",
                job_col1_title: "1. 履歷與目標職位",
                job_upload_label: "上傳履歷文件：",
                job_upload_status: "附加履歷 (PDF/TXT)",
                job_paste_label: "或貼上履歷內文：",
                job_recommend_btn: "根據履歷推薦目標職位",
                job_target_label: "目標職位：",
                job_add_role_btn: "+ 新增職位",
                job_title_ph: "職稱 (例如: 軟體工程師)",
                job_desc_ph: "職缺描述 (選填)...",
                job_submit_btn: "執行匹配評估",
                job_history_title: "2. 分析結果",
                job_clear_btn: "清除",
                job_history_empty: "請提交履歷與目標職稱以產生匹配度與關鍵字落差分析。",

                copilot_col1_title: "1. 財務狀況評估",
                scenario_full: "全額資助檔案",
                scenario_partial: "半額資助檔案",
                scenario_high: "標準檔案",
                scenario_incomplete: "不完整檔案",
                copilot_notes_ph: "請輸入家庭財務狀況...",
                copilot_calc_btn: "評估資助資格",
                copilot_whatif_title: "參數調整",
                copilot_income_label: "家庭每月總收入 (HKD)：",
                copilot_members_label: "同住家庭成員數：",
                copilot_privacy_title: "2. 合規與隱私審核",
                copilot_protected_label: "已脫敏項目：",
                copilot_awaiting_input: "等待輸入...",
                copilot_result_title: "3. 評估結果",
                copilot_status_label: "狀態：",
                copilot_awaiting_badge: "等待評估",
                copilot_no_profile: "尚未進行評估",
                copilot_calc_prompt: "請於左側輸入參數以檢視建議。",
                copilot_policy_label: "政策法規參考：",
                copilot_checklist_label: "所需證明文件：",
                copilot_checklist_awaiting: "• 等待評估",
                copilot_appeal_title: "特殊情況覆核",
                copilot_appeal_desc: "可提交特殊情況覆核申請以供專人審查。",
                copilot_appeal_default: "選擇覆核原因...",
                appeal_opt1: "突發家庭醫療緊急情況",
                appeal_opt2: "主要經濟支柱喪失",
                appeal_opt3: "季節性收入落差",
                copilot_appeal_btn: "提交覆核申請",

                bridge_title: "學生資助與校內工讀橋樑",
                bridge_subtitle: "評估資金缺口與相關校內兼職計畫。",
                bridge_income_label: "每月收入：",
                bridge_tuition_label: "學費支出：",
                bridge_living_label: "生活開支：",
                bridge_shortfall_title: "資金缺口摘要",
                bridge_shortfall_text: "根據當前參數計算之資金缺口為：",
                bridge_loan_status_label: "貸款方案：",
                bridge_loan_eligible_badge: "符合 NLSFT 資格",
                bridge_loan_desc: "您可透過政府非免入息審查貸款計畫 (NLSFT) 填補開支。",
                bridge_matched_jobs_title: "校內工讀與工作學習計畫",
                job_badge_flexible: "兼職",
                job_badge_grant: "工讀計畫",
                bridge_job1_title: "AI 實驗室學生助理",
                bridge_job1_desc: "協助 Python 資料處理與部門腳本優化。",
                bridge_job2_title: "學生資助大使",
                bridge_job2_desc: "協助學生完成資助文件申請與檢核流程。",
                bridge_apply_btn: "申請"
            },
            "zh-cn": {
                brand_subtitle_career: "职涯导航系统",
                btn_career: "职涯教练",
                btn_job: "职位匹配",
                btn_copilot: "学生资助",
                btn_bridge: "资助与就业桥梁",
                chat_history_title: "对话历史",
                new_chat_btn: "+ 新建",
                upload_resume_title: "简历内容",
                upload_resume_label: "附加 PDF/TXT 简历",
                playbooks_title: "快捷模块",
                preset_roast: "简历检核",
                preset_gap: "技能落差分析",
                preset_behavioral: "面试模拟",
                preset_roadmap: "90 天规划",
                chat_actions_title: "会话选项",
                export_btn: "导出对话记录",
                delete_btn: "删除当前会话",
                chat_placeholder: "请输入问题或选择快捷模块...",
                send_btn: "发送",
                tip_enter: "按 Enter 发送，Shift + Enter 换行。",

                job_view_title: "职位匹配与适配度分析",
                job_view_subtitle: "根据您的简历评估目标职位的匹配程度。",
                job_col1_title: "1. 简历与目标职位",
                job_upload_label: "上传简历文件：",
                job_upload_status: "附加简历 (PDF/TXT)",
                job_paste_label: "或粘贴简历正文：",
                job_recommend_btn: "根据简历推荐目标职位",
                job_target_label: "目标职位：",
                job_add_role_btn: "+ 新增职位",
                job_title_ph: "职称 (例如: 软件工程师)",
                job_desc_ph: "职位描述 (选填)...",
                job_submit_btn: "执行匹配评估",
                job_history_title: "2. 分析结果",
                job_clear_btn: "清除",
                job_history_empty: "请提交简历与目标职称以生成匹配度与关键词落差分析。",

                copilot_col1_title: "1. 财务状况评估",
                scenario_full: "全额资助档案",
                scenario_partial: "半额资助档案",
                scenario_high: "标准档案",
                scenario_incomplete: "不完整档案",
                copilot_notes_ph: "请输入家庭财务状况...",
                copilot_calc_btn: "评估资助资格",
                copilot_whatif_title: "参数调整",
                copilot_income_label: "家庭每月总收入 (HKD)：",
                copilot_members_label: "同住家庭成员数：",
                copilot_privacy_title: "2. 合规与隐私审核",
                copilot_protected_label: "已脱敏项目：",
                copilot_awaiting_input: "等待输入...",
                copilot_result_title: "3. 评估结果",
                copilot_status_label: "状态：",
                copilot_awaiting_badge: "等待评估",
                copilot_no_profile: "尚未进行评估",
                copilot_calc_prompt: "请于左侧输入参数以查看建议。",
                copilot_policy_label: "政策法规参考：",
                copilot_checklist_label: "所需证明文件：",
                copilot_checklist_awaiting: "• 等待评估",
                copilot_appeal_title: "特殊情况复核",
                copilot_appeal_desc: "可提交特殊情况复核申请以供专人审查。",
                copilot_appeal_default: "选择复核原因...",
                appeal_opt1: "突发家庭医疗紧急情况",
                appeal_opt2: "主要经济支柱丧失",
                appeal_opt3: "季节性收入落差",
                copilot_appeal_btn: "提交复核申请",

                bridge_title: "学生资助与校内工读桥梁",
                bridge_subtitle: "评估资金缺口与相关校内兼职计划。",
                bridge_income_label: "每月收入：",
                bridge_tuition_label: "学费支出：",
                bridge_living_label: "生活开支：",
                bridge_shortfall_title: "资金缺口摘要",
                bridge_shortfall_text: "根据当前参数计算之资金缺口为：",
                bridge_loan_status_label: "贷款方案：",
                bridge_loan_eligible_badge: "符合 NLSFT 资格",
                bridge_loan_desc: "您可通过政府非免入息审查贷款计划 (NLSFT) 填补开销。",
                bridge_matched_jobs_title: "校内工读与工作学习计划",
                job_badge_flexible: "兼职",
                job_badge_grant: "工读计划",
                bridge_job1_title: "AI 实验室学生助理",
                bridge_job1_desc: "协助 Python 数据处理与部门脚本优化。",
                bridge_job2_title: "学生资助大使",
                bridge_job2_desc: "协助学生完成资助文件申请与检核流程。",
                bridge_apply_btn: "申请"
            }
        };

        let currentLang = 'en';

        // Dark / Light Text Mode Switcher Logic
        function toggleTheme() {
            const html = document.documentElement;
            const label = document.getElementById('theme-label');
            if (html.classList.contains('dark')) {
                html.classList.remove('dark');
                html.classList.add('light');
                localStorage.setItem('theme', 'light');
                if (label) label.innerText = 'Dark';
            } else {
                html.classList.remove('light');
                html.classList.add('dark');
                localStorage.setItem('theme', 'dark');
                if (label) label.innerText = 'Light';
            }
        }

        function initTheme() {
            const savedTheme = localStorage.getItem('theme') || 'light';
            const html = document.documentElement;
            const label = document.getElementById('theme-label');
            if (savedTheme === 'dark') {
                html.classList.remove('light');
                html.classList.add('dark');
                if (label) label.innerText = 'Light';
            } else {
                html.classList.remove('dark');
                html.classList.add('light');
                if (label) label.innerText = 'Dark';
            }
        }

        function changeLanguage(lang) {
            currentLang = lang;
            localStorage.setItem('boussole_lang', lang);
            const t = translations[currentLang] || translations.en;

            document.querySelectorAll('[data-i18n]').forEach(el => {
                const key = el.getAttribute('data-i18n');
                if (t[key]) el.innerHTML = t[key];
            });

            document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
                const key = el.getAttribute('data-i18n-placeholder');
                if (t[key]) el.placeholder = t[key];
            });

            const userInput = document.getElementById('user-input');
            if (userInput && t.chat_placeholder) userInput.placeholder = t.chat_placeholder;

            const caseNotes = document.getElementById('case-notes');
            if (caseNotes && t.copilot_notes_ph) caseNotes.placeholder = t.copilot_notes_ph;
        }

        let currentMode = 'career';
        let activeChatId = null;
        let uploadedResumeText = "";

        async function initApp() {
            initTheme();
            const savedLang = localStorage.getItem('boussole_lang') || 'en';
            currentLang = savedLang;
            const langSelect = document.getElementById('lang-select');
            if (langSelect) langSelect.value = savedLang;
            
            changeLanguage(savedLang);
            await loadChats();
        }

        async function loadChats() {
            try {
                const res = await fetch('/api/chats');
                const data = await res.json();
                activeChatId = data.active_id;
                renderChatHistoryList(data.chats, data.active_id);
                renderMessages(data.messages);
            } catch (err) {
                console.error("Failed to load chats", err);
            }
        }

        function renderChatHistoryList(chats, activeId) {
            const listEl = document.getElementById('chat-history-list');
            if (!listEl) return;
            listEl.innerHTML = '';
            chats.forEach(chat => {
                const isActive = chat.id === activeId;
                const div = document.createElement('div');
                div.className = `p-2 rounded-xl text-xs cursor-pointer transition truncate ${isActive ? 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-900 dark:text-indigo-200 font-semibold border border-indigo-200/80 dark:border-indigo-800/80 shadow-sm' : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100/60 dark:hover:bg-slate-800/60'}`;
                div.innerHTML = `<span class="truncate block">${chat.title}</span>`;
                div.onclick = () => switchChat(chat.id);
                listEl.appendChild(div);
            });
        }

        async function createNewChat() {
            const res = await fetch('/api/chats/new', { method: 'POST' });
            await loadChats();
        }

        async function switchChat(chatId) {
            const res = await fetch('/api/chats/switch', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ chat_id: chatId })
            });
            const data = await res.json();
            if (data.status === 'switched') {
                activeChatId = data.active_id;
                if (data.chats) renderChatHistoryList(data.chats, data.active_id);
                renderMessages(data.messages);
            }
        }

        async function deleteActiveChat() {
            if (!confirm("Delete this session?")) return;
            const res = await fetch('/api/chats/active', { method: 'DELETE' });
            const data = await res.json();
            activeChatId = data.active_id;
            renderChatHistoryList(data.chats, data.active_id);
            renderMessages(data.messages);
        }

        function renderMessages(messages) {
            const chatStream = document.getElementById('chat-stream');
            chatStream.innerHTML = '';
            
            if (!messages || messages.length === 0) return;

            messages.forEach(msg => {
                if (msg.role === 'user') {
                    chatStream.innerHTML += `
                        <div class="flex items-start justify-end w-full">
                            <div class="bg-gradient-to-r from-slate-900 to-indigo-900 dark:from-slate-800 dark:to-indigo-950 border border-transparent dark:border-slate-700/60 rounded-2xl p-3.5 text-white font-medium max-w-[85%] text-xs leading-relaxed shadow-sm">${msg.content}</div>
                        </div>`;
                } else if (msg.role === 'assistant') {
                    chatStream.innerHTML += `
                        <div class="flex items-start gap-3 w-full">
                            <div class="w-6 h-6 rounded-lg bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 border border-indigo-200/60 dark:border-indigo-800/60 flex items-center justify-center font-bold text-[10px] flex-shrink-0 mt-0.5 shadow-sm">B</div>
                            <div class="bg-white/90 dark:bg-slate-950/90 border border-slate-200/80 dark:border-slate-800/80 rounded-2xl p-3.5 text-slate-800 dark:text-slate-200 max-w-[85%] text-xs leading-relaxed flex flex-col gap-2 shadow-sm">
                                <div class="ai-markdown-body">${marked.parse(msg.content)}</div>
                            </div>
                        </div>`;
                }
            });

            // Re-attach ongoing stream buffer if this chat is actively generating
            if (window.activeStreams[activeChatId]) {
                const streamData = window.activeStreams[activeChatId];
                chatStream.innerHTML += `
                    <div class="flex items-start gap-3 w-full">
                        <div class="w-6 h-6 rounded-lg bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 border border-indigo-200/60 dark:border-indigo-800/60 flex items-center justify-center font-bold text-[10px] flex-shrink-0 mt-0.5 shadow-sm">B</div>
                        <div class="bg-white/90 dark:bg-slate-950/90 border border-slate-200/80 dark:border-slate-800/80 rounded-2xl p-3.5 text-slate-800 dark:text-slate-200 max-w-[85%] text-xs leading-relaxed flex flex-col gap-2 shadow-sm">
                            <div id="${streamData.msgId}" class="ai-markdown-body">${streamData.isDone ? marked.parse(streamData.buffer) : streamData.buffer}</div>
                        </div>
                    </div>`;
            }

            chatStream.scrollTop = chatStream.scrollHeight;
        }

        function switchView(mode) {
            currentMode = mode;
            
            const mobileSelect = document.getElementById('mobile-view-select');
            if (mobileSelect) mobileSelect.value = mode;

            const careerView = document.getElementById('view-career');
            const jobView = document.getElementById('view-job');
            const copilotView = document.getElementById('view-copilot');
            const bridgeView = document.getElementById('view-bridge');

            const btnCareer = document.getElementById('btn-career');
            const btnJob = document.getElementById('btn-job');
            const btnCopilot = document.getElementById('btn-copilot');
            const btnBridge = document.getElementById('btn-bridge');

            [btnCareer, btnJob, btnCopilot, btnBridge].forEach(btn => {
                if (btn) btn.className = "text-xs font-medium px-3 py-1.5 rounded-lg text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition";
            });

            careerView.classList.add('hidden');
            jobView.classList.add('hidden');
            copilotView.classList.add('hidden');
            bridgeView.classList.add('hidden');

            if (mode === 'career') {
                careerView.classList.remove('hidden');
                if (btnCareer) btnCareer.className = "text-xs font-medium px-3 py-1.5 rounded-lg bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-sm transition";
            } else if (mode === 'job') {
                jobView.classList.remove('hidden');
                if (btnJob) btnJob.className = "text-xs font-medium px-3 py-1.5 rounded-lg bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-sm transition";
            } else if (mode === 'copilot') {
                copilotView.classList.remove('hidden');
                if (btnCopilot) btnCopilot.className = "text-xs font-medium px-3 py-1.5 rounded-lg bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-sm transition";
            } else if (mode === 'bridge') {
                bridgeView.classList.remove('hidden');
                if (btnBridge) btnBridge.className = "text-xs font-medium px-3 py-1.5 rounded-lg bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-sm transition";
            }
        }

        async function handleJobFileUpload(e) {
            const file = e.target.files[0];
            if (!file) return;
            document.getElementById('job-upload-status').innerText = file.name;
            const formData = new FormData();
            formData.append('file', file);
            const res = await fetch('/api/parse_resume', { method: 'POST', body: formData });
            const data = await res.json();
            if (data.text) {
                document.getElementById('job-cv-text').value = data.text;
            }
        }

        function addJobInputBox() {
            const list = document.getElementById('job-inputs-list');
            if (list.children.length >= 10) return alert("Maximum 10 roles.");
            const t = translations[currentLang] || translations.en;
            const div = document.createElement('div');
            div.className = "job-input-item flex flex-col gap-2 p-3 rounded-xl bg-slate-50/70 dark:bg-slate-950/70 border border-slate-200/80 dark:border-slate-800/80";
            div.innerHTML = `
                <div class="flex justify-between items-center gap-2">
                    <input type="text" placeholder="${t.job_title_ph}" class="job-title-input w-full bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 text-xs rounded-lg px-2.5 py-1.5 border border-slate-300 dark:border-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500">
                    <button onclick="this.parentElement.parentElement.remove()" class="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 text-xs px-1 font-bold">✕</button>
                </div>
                <textarea rows="2" placeholder="${t.job_desc_ph}" class="job-desc-input w-full bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 text-xs rounded-lg p-2.5 border border-slate-300 dark:border-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 custom-scrollbar resize-none"></textarea>
            `;
            list.appendChild(div);
        }

        async function recommendJobs() {
            const cvText = document.getElementById('job-cv-text').value.trim();
            if (!cvText) return alert("Provide CV text or upload a file first.");

            const btn = document.getElementById('recommend-jobs-btn');
            btn.disabled = true;
            btn.innerText = "Analyzing...";

            try {
                const res = await fetch('/api/recommend_jobs', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ cv_text: cvText })
                });
                const data = await res.json();

                if (data.recommended_jobs) {
                    const list = document.getElementById('job-inputs-list');
                    list.innerHTML = '';
                    data.recommended_jobs.forEach(job => {
                        const div = document.createElement('div');
                        div.className = "job-input-item flex flex-col gap-2 p-3 rounded-xl bg-slate-50/70 dark:bg-slate-950/70 border border-slate-200/80 dark:border-slate-800/80";
                        div.innerHTML = `
                            <div class="flex justify-between items-center gap-2">
                                <input type="text" value="${job.job_title}" placeholder="Job Title" class="job-title-input w-full bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 text-xs rounded-lg px-2.5 py-1.5 border border-slate-300 dark:border-slate-800 focus:outline-none">
                                <button onclick="this.parentElement.parentElement.remove()" class="text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 text-xs px-1 font-bold">✕</button>
                            </div>
                            <textarea rows="2" class="job-desc-input w-full bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 text-xs rounded-lg p-2.5 border border-slate-300 dark:border-slate-800 focus:outline-none custom-scrollbar resize-none">${job.job_description}</textarea>
                        `;
                        list.appendChild(div);
                    });
                }
            } catch (err) {
                alert("Error recommending jobs.");
            } finally {
                btn.disabled = false;
                const t = translations[currentLang] || translations.en;
                btn.innerText = t.job_recommend_btn;
            }
        }

        function clearJobHistory() {
            document.getElementById('job-history-container').innerHTML = '';
            document.getElementById('job-placeholder-state').classList.remove('hidden');
        }

        async function runJobMatch() {
            const cvText = document.getElementById('job-cv-text').value.trim();
            const items = document.querySelectorAll('.job-input-item');
            
            let jobEntries = [];
            items.forEach(item => {
                const title = item.querySelector('.job-title-input').value.trim();
                const desc = item.querySelector('.job-desc-input').value.trim();
                if (title) jobEntries.push({ title: title, desc: desc || "Standard role expectations." });
            });

            if (!cvText || jobEntries.length === 0) return alert("Provide CV text and at least one target title.");

            const btn = document.getElementById('job-submit-btn');
            btn.disabled = true;
            btn.innerText = "Evaluating...";

            try {
                const res = await fetch('/api/job_match', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ cv_text: cvText, jobs: jobEntries })
                });
                const data = await res.json();
                
                document.getElementById('job-placeholder-state').classList.add('hidden');
                const historyContainer = document.getElementById('job-history-container');

                if (data.results) {
                    data.results.forEach((result) => {
                        const card = document.createElement('div');
                        card.className = "bg-white dark:bg-slate-900 p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 text-xs flex flex-col gap-2 shadow-sm";
                        card.innerHTML = `
                            <div class="flex justify-between items-center border-b border-slate-100 dark:border-slate-800 pb-2">
                                <span class="font-bold text-slate-900 dark:text-white">${result.job_title}</span>
                                <span class="px-2 py-0.5 rounded font-semibold text-[10px] bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300 border border-indigo-200/50 dark:border-indigo-800/50">${result.score}% Match</span>
                            </div>
                            <p class="text-slate-600 dark:text-slate-400 text-xs">${result.match_summary}</p>
                            <div class="flex flex-col gap-1 pt-1">
                                <span class="text-[10px] font-semibold text-slate-500 dark:text-slate-400 uppercase">Key Recommendations:</span>
                                <ul class="list-disc pl-4 text-slate-700 dark:text-slate-300 space-y-0.5">
                                    ${(result.recommendations || []).map(r => `<li>${r}</li>`).join('')}
                                </ul>
                            </div>
                        `;
                        historyContainer.prepend(card);
                    });
                }
            } catch (err) {
                alert("Error analyzing roles.");
            } finally {
                btn.disabled = false;
                const t = translations[currentLang] || translations.en;
                btn.innerText = t.job_submit_btn;
            }
        }

        function exportMarkdown() {
            const chatStream = document.getElementById('chat-stream');
            const messages = [];
            chatStream.querySelectorAll('.flex').forEach(el => messages.push(el.innerText));
            if (messages.length === 0) return alert("No active conversation.");
            const blob = new Blob([messages.join("\n\n---\n\n")], { type: 'text/markdown' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = 'boussole-session.md';
            a.click();
        }

        const chatStream = document.getElementById('chat-stream');
        const chatForm = document.getElementById('chat-form');
        const userInput = document.getElementById('user-input');

        userInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                chatForm.requestSubmit();
            }
        });

        function applyPreset(type) {
            let promptText = "";
            if (type === 'roast') {
                promptText = uploadedResumeText ? `Audit my uploaded resume using Google X-Y-Z formula:\n\n${uploadedResumeText}` : "Provide a resume audit framework.";
            } else if (type === 'gap') {
                promptText = "Analyze my current skill set for software/tech roles and identify gaps.";
            } else if (type === 'behavioral') {
                promptText = "Conduct a practice interview. Ask me 3 questions sequentially.";
            } else if (type === 'roadmap') {
                promptText = "Generate a 90-day action plan for career advancement.";
            }
            userInput.value = promptText;
            userInput.focus();
        }

        async function handleFileUpload(e) {
            const file = e.target.files[0];
            if (!file) return;
            document.getElementById('upload-status-text').innerText = file.name;
            const formData = new FormData();
            formData.append('file', file);
            const res = await fetch('/api/parse_resume', { method: 'POST', body: formData });
            const data = await res.json();
            if (data.text) {
                uploadedResumeText = data.text;
                userInput.value = data.text;
                userInput.focus();
            }
        }

        // Direct Zero-Lag Real-Time Streaming Handler with Global Session Tracking
        chatForm.onsubmit = async (e) => {
            e.preventDefault();
            let text = userInput.value.trim();
            if (!text) return;

            userInput.value = '';
            const sendingChatId = activeChatId;
            const assistantMsgId = 'msg-' + Date.now();

            // Store active stream state in global window scope so switching chats doesn't lose text chunks
            window.activeStreams[sendingChatId] = {
                msgId: assistantMsgId,
                buffer: "",
                isDone: false
            };

            // If user is viewing the current chat, update the DOM immediately
            if (sendingChatId === activeChatId) {
                chatStream.innerHTML += `
                    <div class="flex items-start justify-end w-full">
                        <div class="bg-gradient-to-r from-slate-900 to-indigo-900 dark:from-slate-800 dark:to-indigo-950 border border-transparent dark:border-slate-700/60 rounded-2xl p-3.5 text-white font-medium max-w-[85%] text-xs leading-relaxed shadow-sm">${text}</div>
                    </div>`;
                
                chatStream.innerHTML += `
                    <div class="flex items-start gap-3 w-full">
                        <div class="w-6 h-6 rounded-lg bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 border border-indigo-200/60 dark:border-indigo-800/60 flex items-center justify-center font-bold text-[10px] flex-shrink-0 mt-0.5 shadow-sm">B</div>
                        <div class="bg-white/90 dark:bg-slate-950/90 border border-slate-200/80 dark:border-slate-800/80 rounded-2xl p-3.5 text-slate-800 dark:text-slate-200 max-w-[85%] text-xs leading-relaxed flex flex-col gap-2 shadow-sm">
                            <div id="${assistantMsgId}" class="ai-markdown-body"></div>
                        </div>
                    </div>`;
                
                chatStream.scrollTop = chatStream.scrollHeight;
            }

            try {
                const response = await fetch('/api/chat_stream', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ message: text, chat_id: sendingChatId })
                });

                // Instantly update sidebar history list
                fetch('/api/chats')
                    .then(res => res.json())
                    .then(data => renderChatHistoryList(data.chats, data.active_id))
                    .catch(err => console.error("Failed to refresh sidebar history:", err));

                if (!response.body) throw new Error("Stream unsupported");

                const reader = response.body.getReader();
                const decoder = new TextDecoder("utf-8");

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    const chunk = decoder.decode(value, { stream: true });
                    window.activeStreams[sendingChatId].buffer += chunk;

                    // If active chat is still visible, render directly to DOM element
                    if (sendingChatId === activeChatId) {
                        const targetContainer = document.getElementById(assistantMsgId);
                        if (targetContainer) {
                            targetContainer.innerText = window.activeStreams[sendingChatId].buffer;
                            chatStream.scrollTop = chatStream.scrollHeight;
                        }
                    }
                }

                window.activeStreams[sendingChatId].isDone = true;

                // Render markdown once complete
                if (sendingChatId === activeChatId) {
                    const targetContainer = document.getElementById(assistantMsgId);
                    if (targetContainer) {
                        targetContainer.innerHTML = marked.parse(window.activeStreams[sendingChatId].buffer);
                        chatStream.scrollTop = chatStream.scrollHeight;
                    }
                }

                delete window.activeStreams[sendingChatId];

            } catch (err) {
                if (sendingChatId === activeChatId) {
                    const targetContainer = document.getElementById(assistantMsgId);
                    if (targetContainer) targetContainer.innerText = "Error streaming message response.";
                }
                delete window.activeStreams[sendingChatId];
            }
        };

        const scenarios = {
            full_grant: "Student: Chan (HKID: A123456(7), Phone: 91234567).\nFamily size: 4 members.\nMonthly income: HKD $10,000.",
            partial_grant: "Student: Wong (HKID: B234567(8), Phone: 61234567).\nFamily size: 4 members.\nMonthly income: HKD $18,000.",
            ineligible: "Student: Lee (HKID: C345678(9), Phone: 51234567).\nFamily size: 3 members.\nMonthly income: HKD $24,000.",
            missing_income: "Student: Cheung (HKID: D456789(0), Phone: 98765432).\nEmergency aid request.\nMonthly income: Not provided."
        };

        function loadScenario(type, income, members) {
            document.getElementById('case-notes').value = scenarios[type];
            if (income !== null) setAllValues('income', income);
            if (members !== null) setAllValues('members', members);
        }

        function setAllValues(type, val) {
            if (type === 'income') {
                document.getElementById('income-slider').value = val;
                document.getElementById('bridge-income-slider').value = val;
                document.getElementById('income-input-box').value = val;
                document.getElementById('bridge-income-input-box').value = val;
            } else if (type === 'members') {
                document.getElementById('members-slider').value = val;
                document.getElementById('members-input-box').value = val;
            } else if (type === 'tuition') {
                document.getElementById('tuition-slider').value = val;
                document.getElementById('tuition-input-box').value = val;
            } else if (type === 'living') {
                document.getElementById('living-slider').value = val;
                document.getElementById('living-input-box').value = val;
            }
        }

        async function syncFromSlider(type) {
            let val = parseInt(document.getElementById(`${type}-slider`).value);
            setAllValues(type, val);
            triggerBackendRecalc();
        }

        async function syncFromBox(type) {
            let val = parseInt(document.getElementById(`${type}-input-box`).value) || 0;
            setAllValues(type, val);
            triggerBackendRecalc();
        }

        async function syncBridgeFromSlider(type) {
            let val = parseInt(document.getElementById(`bridge-${type}-slider` || `${type}-slider`).value);
            setAllValues(type, val);
            triggerBackendRecalc();
        }

        async function syncBridgeFromBox(type) {
            let val = parseInt(document.getElementById(`bridge-${type}-input-box` || `${type}-input-box`).value) || 0;
            setAllValues(type, val);
            triggerBackendRecalc();
        }

        async function triggerBackendRecalc() {
            const income = parseInt(document.getElementById('income-input-box').value) || 0;
            const members = parseInt(document.getElementById('members-input-box').value) || 1;

            const res = await fetch('/api/evaluate_case', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ notes: `Income: HKD $${income}, Members: ${members}` })
            });
            const data = await res.json();
            updateAuditUI(data.audit);
        }

        async function processCase() {
            const rawNotes = document.getElementById('case-notes').value.trim();
            if (!rawNotes) return alert("Enter financial details first.");

            try {
                const res = await fetch('/api/evaluate_case', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ notes: rawNotes })
                });
                const data = await res.json();
                
                document.getElementById('pii-status').classList.remove('hidden');
                document.getElementById('pii-count').innerText = data.pii_redacted_count;
                document.getElementById('sanitized-text').innerText = data.sanitized_notes;

                if (data.extracted_params.monthly_household_income_hkd !== null) {
                    setAllValues('income', data.extracted_params.monthly_household_income_hkd);
                }
                if (data.extracted_params.household_members_count) {
                    setAllValues('members', data.extracted_params.household_members_count);
                }

                updateAuditUI(data.audit);
            } catch (err) {
                alert("Error during evaluation.");
            }
        }

        function updateAuditUI(audit) {
            const badge = document.getElementById('verdict-badge');
            badge.innerText = audit.status;
            badge.className = "px-2 py-0.5 rounded-md text-[11px] font-semibold bg-slate-200 dark:bg-slate-800 text-slate-800 dark:text-slate-200";

            document.getElementById('verdict-title').innerText = audit.summary;
            document.getElementById('verdict-details').innerText = audit.details;
            document.getElementById('verdict-citation').innerText = audit.policy_citation;

            const tuition = parseInt(document.getElementById('tuition-input-box').value) || 42100;
            const living = parseInt(document.getElementById('living-input-box').value) || 30000;
            const grantCovered = tuition * audit.grant_percentage;
            const finalShortfall = Math.max(0, (tuition - grantCovered) + living);

            document.getElementById('dynamic-shortfall').innerText = `HKD $${Math.round(finalShortfall).toLocaleString()}`;

            const checklistEl = document.getElementById('document-checklist');
            checklistEl.innerHTML = '';
            if (audit.required_documents && audit.required_documents.length > 0) {
                audit.required_documents.forEach(doc => {
                    const li = document.createElement('li');
                    li.innerText = `• ${doc}`;
                    checklistEl.appendChild(li);
                });
            } else {
                checklistEl.innerHTML = '<li>• Standard processing.</li>';
            }
        }

        function executeOverride() {
            const reason = document.getElementById('override-reason').value;
            if (!reason) return alert("Select a review reason.");

            const badge = document.getElementById('verdict-badge');
            badge.innerText = "APPEAL_QUEUED";
            badge.className = "px-2 py-0.5 rounded-md text-[11px] font-semibold bg-slate-900 dark:bg-slate-800 text-white dark:text-slate-100 border border-transparent dark:border-slate-700";

            document.getElementById('verdict-title').innerText = "Appeal Submitted";
            document.getElementById('verdict-details').innerText = `Your request is queued for review. Reason: ${reason}`;
            
            const timestampEl = document.getElementById('override-timestamp');
            timestampEl.classList.remove('hidden');
            timestampEl.innerText = `Submitted: ${new Date().toLocaleTimeString()}`;
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# 3. ROUTING & API ENDPOINTS
# ==============================================================================

@app.before_request
def protect_routes():
    if request.endpoint in ('home', 'api_login', 'api_logout', 'static'):
        return
    if request.path.startswith('/api/') and not session.get('authenticated'):
        return jsonify({'error': 'Unauthorized'}), 401

@app.route('/')
def home():
    if not session.get('authenticated'):
        return render_template_string(LOGIN_HTML_TEMPLATE)
    return render_template_string(UNIFIED_HTML_TEMPLATE)

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.json or {}
    entered_password = data.get('password', '')
    if entered_password == APP_PASSWORD:
        session['authenticated'] = True
        return jsonify({'status': 'success'})
    return jsonify({'status': 'error', 'message': 'Incorrect password.'}), 401

@app.route('/api/logout', methods=['GET', 'POST'])
def api_logout():
    session.pop('authenticated', None)
    if request.method == 'POST':
        return '', 204
    return redirect(url_for('home'))

@app.route('/api/chats', methods=['GET'])
def list_chats():
    sessions, active_id = load_storage()
    if active_id not in sessions:
        active_id = list(sessions.keys())[0]
    
    chats_summary = [
        {"id": c["id"], "title": c["title"]}
        for c in sessions.values()
    ]
    active_messages = [m for m in sessions[active_id]["messages"] if m["role"] != "system"]
    return jsonify({
        "active_id": active_id,
        "chats": chats_summary,
        "messages": active_messages
    })

@app.route('/api/chats/new', methods=['POST'])
def new_chat():
    sessions, _ = load_storage()
    chat_id = datetime.now().strftime('%Y%m%d%H%M%S_%f')
    sessions[chat_id] = {
        "id": chat_id,
        "title": "New Conversation",
        "messages": [
            {"role": "system", "content": BOUSSOLE_SYSTEM_INSTRUCTION},
            {"role": "assistant", "content": WELCOME_GREETING}
        ]
    }
    save_storage(sessions, chat_id)

    chats_summary = [
        {"id": c["id"], "title": c["title"]}
        for c in sessions.values()
    ]
    return jsonify({
        "chat_id": chat_id, 
        "title": "New Conversation", 
        "messages": [{"role": "assistant", "content": WELCOME_GREETING}],
        "chats": chats_summary
    })

@app.route('/api/chats/switch', methods=['POST'])
def switch_chat():
    sessions, _ = load_storage()
    data = request.json
    chat_id = data.get('chat_id')
    if chat_id in sessions:
        save_storage(sessions, chat_id)
        chats_summary = [
            {"id": c["id"], "title": c["title"]}
            for c in sessions.values()
        ]
        messages = [m for m in sessions[chat_id]["messages"] if m["role"] != "system"]
        return jsonify({"status": "switched", "active_id": chat_id, "messages": messages, "chats": chats_summary})
    return jsonify({"error": "Chat not found"}), 404

@app.route('/api/chats/active', methods=['DELETE'])
def delete_active_chat():
    sessions, active_id = load_storage()
    if len(sessions) <= 1:
        sessions[active_id] = {
            "id": active_id,
            "title": "New Conversation",
            "messages": [
                {"role": "system", "content": BOUSSOLE_SYSTEM_INSTRUCTION},
                {"role": "assistant", "content": WELCOME_GREETING}
            ]
        }
    else:
        del sessions[active_id]
        active_id = list(sessions.keys())[0]
    
    save_storage(sessions, active_id)

    chats_summary = [
        {"id": c["id"], "title": c["title"]}
        for c in sessions.values()
    ]
    active_messages = [m for m in sessions[active_id]["messages"] if m["role"] != "system"]
    return jsonify({
        "status": "deleted",
        "active_id": active_id,
        "chats": chats_summary,
        "messages": active_messages
    })

@app.route('/api/chats/clear', methods=['DELETE'])
def clear_all_chats():
    default_id = "default"
    default_sessions = {
        default_id: {
            "id": default_id,
            "title": "New Conversation",
            "messages": [
                {"role": "system", "content": BOUSSOLE_SYSTEM_INSTRUCTION},
                {"role": "assistant", "content": WELCOME_GREETING}
            ]
        }
    }
    save_storage(default_sessions, default_id)
    chats_summary = [{"id": default_id, "title": "New Conversation"}]
    active_messages = [{"role": "assistant", "content": WELCOME_GREETING}]
    return jsonify({
        "status": "cleared",
        "active_id": default_id,
        "chats": chats_summary,
        "messages": active_messages
    })

@app.route('/api/evaluate_case', methods=['POST'])
def evaluate_case():
    raw_notes = request.json.get('notes', '').strip()
    sanitized_notes, pii_count = sanitize_pii(raw_notes)

    income_match = re.search(r'(?:HKD?|\$)\s*([0-9,]+)', sanitized_notes, re.IGNORECASE)
    members_match = re.search(r'(\d+)\s*members?', sanitized_notes, re.IGNORECASE)

    extracted_income = float(income_match.group(1).replace(',', '')) if income_match else None
    extracted_members = int(members_match.group(1)) if members_match else 1

    audit_result = evaluate_student_eligibility(extracted_income, extracted_members)

    return jsonify({
        'sanitized_notes': sanitized_notes,
        'pii_redacted_count': pii_count,
        'extracted_params': {
            "monthly_household_income_hkd": extracted_income,
            "household_members_count": extracted_members
        },
        'audit': audit_result
    })

@app.route('/api/recommend_jobs', methods=['POST'])
def recommend_jobs():
    data = request.json
    cv_text = data.get('cv_text', '').strip()

    if not cv_text:
        return jsonify({'error': 'CV text is required.'}), 400

    prompt = f"""
    You are an elite career strategist. Analyze the candidate's CV and recommend 5 top-tier, highly suitable career roles/job titles that match their skills, background, and experience level.
    
    Candidate CV:
    {cv_text}
    
    Provide your response in strict JSON format with a single key "recommended_jobs" containing an array of 5 objects, each having:
    - "job_title": string
    - "job_description": string
    """

    try:
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        result_json = response.choices[0].message.content
        parsed = json.loads(result_json)
        return jsonify(parsed)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/job_match', methods=['POST'])
def job_match():
    data = request.json
    cv_text = data.get('cv_text', '').strip()
    jobs = data.get('jobs', [])

    if not cv_text or not jobs:
        return jsonify({'error': 'CV text and at least one target job title are required.'}), 400

    prompt = f"""
    You are an expert recruiter and resume optimization engine.
    Analyze the candidate's CV against each of the target jobs provided below.
    
    Candidate CV Content:
    {cv_text}
    
    Target Jobs:
    {json.dumps(jobs)}
    
    Provide your response in strict JSON format with a single key "results" containing an array of objects. Each object must correspond to a job in order and have:
    - "job_title": string
    - "score": integer between 0 and 100
    - "match_summary": short summary
    - "matched_keywords": list of string keywords
    - "missing_keywords": list of key missing terms
    - "recommendations": list of 3-4 specific actionable points
    """

    try:
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        result_json = response.choices[0].message.content
        parsed = json.loads(result_json)
        return jsonify(parsed)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Direct Unbuffered Token Streaming Route
@app.route('/api/chat_stream', methods=['POST'])
def chat_stream():
    sessions, active_id = load_storage()
    data = request.json or {}
    user_msg = data.get('message', '').strip()
    chat_id = data.get('chat_id') or active_id

    if not user_msg:
        return jsonify({'error': 'Message required.'}), 400

    if chat_id not in sessions:
        chat_id = active_id
    if chat_id not in sessions:
        chat_id = list(sessions.keys())[0]

    chat_obj = sessions[chat_id]

    # Auto-generate title for new chats
    if chat_obj["title"] == "New Conversation":
        try:
            title_prompt = [
                {"role": "system", "content": "Generate a short title (max 5 words, no quotes) for this topic."},
                {"role": "user", "content": user_msg}
            ]
            title_res = client.chat.completions.create(
                model=deployment_name,
                messages=title_prompt
            )
            ai_title = title_res.choices[0].message.content.strip().strip('"\'')
            if ai_title:
                chat_obj["title"] = ai_title
        except Exception:
            chat_obj["title"] = (user_msg[:25] + '...') if len(user_msg) > 25 else user_msg

    # 1. Save user message immediately BEFORE streaming starts
    chat_obj["messages"].append({"role": "user", "content": user_msg})
    save_storage(sessions, chat_id)

    def generate_raw_chunks():
        full_reply = ""
        try:
            stream = client.chat.completions.create(
                model=deployment_name,
                messages=chat_obj["messages"],
                stream=True
            )
            for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        full_reply += delta
                        yield delta
        except Exception as e:
            full_reply += f"\n[Error: {str(e)}]"
            yield f"\n[Error: {str(e)}]"
        finally:
            # 2. Re-read disk state upon stream termination to prevent overwriting parallel changes
            latest_sessions, _ = load_storage()
            if chat_id in latest_sessions:
                latest_sessions[chat_id]["messages"].append({"role": "assistant", "content": full_reply})
                save_storage(latest_sessions, chat_id)

    resp = Response(stream_with_context(generate_raw_chunks()), mimetype='text/plain; charset=utf-8')
    resp.headers['X-Accel-Buffering'] = 'no'
    resp.headers['Cache-Control'] = 'no-cache, no-transform'
    return resp

@app.route('/api/parse_resume', methods=['POST'])
def parse_resume():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded.'}), 400
    file = request.files['file']
    filename = file.filename.lower()

    try:
        if filename.endswith('.pdf'):
            reader = PdfReader(io.BytesIO(file.read()))
            raw_text = "\n".join([page.extract_text() or "" for page in reader.pages])
        elif filename.endswith('.txt'):
            raw_text = file.read().decode('utf-8', errors='ignore')
        else:
            return jsonify({'error': 'Unsupported file format.'}), 400
        
        return jsonify({'text': raw_text.strip()})
    except Exception as e:
        return jsonify({'error': f'Failed to parse file: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)