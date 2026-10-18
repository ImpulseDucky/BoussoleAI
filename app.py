import os
import io
import json
import re
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for, Response, stream_with_context, send_from_directory
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

# SINGLE app initialization here:
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'boussole-ai-super-secret-key-2026')

# Define an absolute path to your game folder next to app.py
GAME_FOLDER = Path(__file__).resolve().parent / 'boussole'

@app.route('/boussole')
@app.route('/boussole/')
def serve_godot_game():
    response = send_from_directory(GAME_FOLDER, 'index.html')
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
    response.headers['Cross-Origin-Embedder-Policy'] = 'require-corp'
    return response

@app.route('/boussole/<path:filename>')
def serve_godot_assets(filename):
    response = send_from_directory(GAME_FOLDER, filename)
    if filename.endswith('.wasm'):
        response.headers['Content-Type'] = 'application/wasm'
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
    response.headers['Cross-Origin-Embedder-Policy'] = 'require-corp'
    return response

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
    
    default_id = f"chat_{int(datetime.now().timestamp())}"
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

# Helper function to fix vertical string line breaks in extracted text
def normalize_resume_text(raw_text: str) -> str:
    if not raw_text:
        return ""
    text = raw_text.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'[ \t]+', ' ', text)
    paragraphs = text.split('\n\n')
    cleaned_paragraphs = []
    for p in paragraphs:
        lines = [line.strip() for line in p.split('\n') if line.strip()]
        cleaned_paragraphs.append(' '.join(lines))
    return '\n\n'.join(cleaned_paragraphs)

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
        html, body { height: 100vh; overflow: hidden; }
        body { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; display: flex; flex-direction: column; }
        .custom-scrollbar::-webkit-scrollbar { width: 6px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
        .dark .custom-scrollbar::-webkit-scrollbar-thumb { background: #334155; }
        * { box-sizing: border-box; min-width: 0; }
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
        canvas { touch-action: none; }
    </style>
</head>
<body class="bg-slate-50 dark:bg-slate-950 text-slate-900 dark:text-slate-100 transition-colors relative bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-indigo-100/50 via-slate-50 to-slate-100 dark:from-indigo-950/30 dark:via-slate-950 dark:to-slate-950" onload="initApp()">

    <!-- Header Navigation Bar -->
    <header class="border-b border-slate-200/80 dark:border-slate-800/80 bg-white/70 dark:bg-slate-900/70 backdrop-blur-md sticky top-0 z-50 flex-shrink-0 transition-colors shadow-sm h-14">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-full flex items-center justify-between gap-4">
            
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
                    <option value="constellation" data-i18n="btn_constellation">Skill Constellation</option>
                    <option value="godotgame" data-i18n="btn_godotgame">Godot Game</option>
                </select>

                <!-- Desktop Navigation Pills (6 Views) -->
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
                    <button onclick="switchView('constellation')" id="btn-constellation" data-i18n="btn_constellation" class="text-xs font-medium px-3 py-1.5 rounded-lg text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition">
                        Skill Constellation
                    </button>
                    <button onclick="switchView('godotgame')" id="btn-godotgame" data-i18n="btn_godotgame" class="text-xs font-medium px-3 py-1.5 rounded-lg text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition">
                        Godot Game
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
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 w-full flex-1 flex flex-col bg-grid-pattern overflow-hidden">

        <!-- VIEW 1: CAREER COACH -->
        <div id="view-career" class="flex-1 flex flex-col md:flex-row gap-4 h-[calc(100vh-6.5rem)] min-h-0">
            <aside class="w-full md:w-72 flex flex-col gap-3 flex-shrink-0 h-full overflow-hidden">
                
                <!-- Chat History Panel -->
                <div class="bg-white/80 dark:bg-slate-900/80 backdrop-blur-md rounded-2xl border border-slate-200/80 dark:border-slate-800/80 p-3.5 shadow-sm flex flex-col flex-1 min-h-[160px] max-h-[240px] flex-shrink-0">
                    <div class="flex items-center justify-between pb-2 flex-shrink-0">
                        <h2 class="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider" data-i18n="chat_history_title">Conversations</h2>
                        <button onclick="createNewChat()" data-i18n="new_chat_btn" class="text-xs text-indigo-600 dark:text-indigo-400 hover:underline font-semibold transition">+ New</button>
                    </div>
                    <div id="chat-history-list" class="flex flex-col gap-1.5 overflow-y-auto custom-scrollbar flex-1 pr-1">
                        <!-- Dynamic items -->
                    </div>
                </div>

                <!-- Resume Upload -->
                <div class="bg-white/80 dark:bg-slate-900/80 backdrop-blur-md rounded-2xl border border-slate-200/80 dark:border-slate-800/80 p-3.5 shadow-sm flex flex-col gap-2 flex-shrink-0">
                    <h2 class="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider" data-i18n="upload_resume_title">Resume Context</h2>
                    <label for="pdf-file-input" class="cursor-pointer flex items-center justify-center p-2.5 border border-dashed border-slate-300 dark:border-slate-700 hover:border-indigo-500 dark:hover:border-indigo-400 rounded-xl bg-slate-50/50 dark:bg-slate-950/50 transition text-center">
                        <span id="upload-status-text" data-i18n="upload_resume_label" class="text-xs text-slate-600 dark:text-slate-400 font-medium truncate">Attach PDF/TXT Resume</span>
                    </label>
                    <input id="pdf-file-input" type="file" accept=".pdf,.txt" class="hidden" onchange="handleFileUpload(event)">
                </div>

                <!-- Playbooks -->
                <div class="bg-white/80 dark:bg-slate-900/80 backdrop-blur-md rounded-2xl border border-slate-200/80 dark:border-slate-800/80 p-3.5 shadow-sm flex flex-col gap-2 flex-1 min-h-0 overflow-y-auto custom-scrollbar">
                    <h2 class="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider" data-i18n="playbooks_title">Action Templates</h2>
                    <div class="grid grid-cols-1 gap-1.5">
                        <button onclick="applyPreset('roast')" data-i18n="preset_roast" class="text-left p-2 rounded-xl bg-slate-50/80 dark:bg-slate-950/80 border border-slate-200/60 dark:border-slate-800/60 hover:border-indigo-500/40 hover:bg-slate-100 dark:hover:bg-slate-800 transition text-xs text-slate-700 dark:text-slate-300 font-medium truncate">Resume Audit</button>
                        <button onclick="applyPreset('gap')" data-i18n="preset_gap" class="text-left p-2 rounded-xl bg-slate-50/80 dark:bg-slate-950/80 border border-slate-200/60 dark:border-slate-800/60 hover:border-indigo-500/40 hover:bg-slate-100 dark:hover:bg-slate-800 transition text-xs text-slate-700 dark:text-slate-300 font-medium truncate">Skill Gap Analysis</button>
                        <button onclick="applyPreset('behavioral')" data-i18n="preset_behavioral" class="text-left p-2 rounded-xl bg-slate-50/80 dark:bg-slate-950/80 border border-slate-200/60 dark:border-slate-800/60 hover:border-indigo-500/40 hover:bg-slate-100 dark:hover:bg-slate-800 transition text-xs text-slate-700 dark:text-slate-300 font-medium truncate">Interview Prep</button>
                        <button onclick="applyPreset('roadmap')" data-i18n="preset_roadmap" class="text-left p-2 rounded-xl bg-slate-50/80 dark:bg-slate-950/80 border border-slate-200/60 dark:border-slate-800/60 hover:border-indigo-500/40 hover:bg-slate-100 dark:hover:bg-slate-800 transition text-xs text-slate-700 dark:text-slate-300 font-medium truncate">90-Day Plan</button>
                    </div>
                </div>

                <!-- Actions -->
                <div id="sidebar-actions" class="bg-white/80 dark:bg-slate-900/80 backdrop-blur-md rounded-2xl border border-slate-200/80 dark:border-slate-800/80 p-3.5 shadow-sm flex flex-col gap-2 flex-shrink-0">
                    <h2 class="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider" data-i18n="chat_actions_title">Session Options</h2>
                    <div class="flex flex-col gap-1.5">
                        <button onclick="exportMarkdown()" id="export-btn" data-i18n="export_btn" class="text-left p-2 rounded-xl bg-slate-50/80 dark:bg-slate-950/80 border border-slate-200/60 dark:border-slate-800/60 hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300 text-xs font-medium transition truncate">
                            Export Conversation
                        </button>
                        <button onclick="deleteActiveChat()" data-i18n="delete_btn" class="text-left p-2 rounded-xl bg-slate-50/80 dark:bg-slate-950/80 border border-slate-200/60 dark:border-slate-800/60 hover:bg-rose-50 dark:hover:bg-rose-950/40 hover:text-rose-600 text-slate-700 dark:text-slate-300 text-xs font-medium transition truncate">
                            Delete Current Session
                        </button>
                        <button onclick="deleteAllChats()" data-i18n="delete_all_btn" class="text-left p-2 rounded-xl bg-slate-50/80 dark:bg-slate-950/80 border border-slate-200/60 dark:border-slate-800/60 hover:bg-rose-50 dark:hover:bg-rose-950/40 hover:text-rose-600 text-slate-700 dark:text-slate-300 text-xs font-medium transition truncate">
                            Delete All Sessions
                        </button>
                    </div>
                </div>
            </aside>

            <!-- Chat Main Panel with Top Gradient Line -->
            <section class="flex-1 bg-white/80 dark:bg-slate-900/80 backdrop-blur-md rounded-2xl border border-slate-200/80 dark:border-slate-800/80 shadow-md flex flex-col overflow-hidden h-full min-w-0 relative before:absolute before:top-0 before:left-0 before:right-0 before:h-1 before:bg-gradient-to-r before:from-indigo-500 before:via-purple-500 before:to-cyan-500">
                <div id="chat-stream" class="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar text-sm pt-5">
                    <!-- Messages -->
                </div>

                <!-- Input Bar -->
                <div class="p-3 border-t border-slate-200/80 dark:border-slate-800/80 bg-slate-50/50 dark:bg-slate-950/50 flex-shrink-0 flex flex-col gap-2">
                    <form id="chat-form" onsubmit="submitChat(event)" class="flex gap-2 items-center">
                        <textarea id="user-input" rows="1" class="flex-1 bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 text-sm rounded-xl px-3.5 py-2.5 border border-slate-300 dark:border-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 custom-scrollbar resize-none min-h-[42px] shadow-inner" placeholder="Ask a question or select an action template..." required></textarea>
                        <button type="submit" id="send-button" data-i18n="send_btn" class="px-4 py-2.5 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-medium rounded-xl text-xs transition shadow-md">Send</button>
                    </form>
                    <div class="text-[11px] text-slate-500 dark:text-slate-400 px-1">
                        <span data-i18n="tip_enter">Press Enter to send, Shift + Enter for line break.</span>
                    </div>
                </div>
            </section>
        </div>

        <!-- VIEW 2: JOB COMPARISON & HISTORY LOG PAGE -->
        <div id="view-job" class="hidden flex-1 flex flex-col gap-4 pb-12 overflow-y-auto custom-scrollbar">
            <div class="bg-white/80 dark:bg-slate-900/80 backdrop-blur-md rounded-2xl border border-slate-200/80 dark:border-slate-800/80 p-6 shadow-md flex flex-col gap-6 max-w-5xl mx-auto w-full relative overflow-hidden before:absolute before:top-0 before:left-0 before:right-0 before:h-1 before:bg-gradient-to-r before:from-indigo-500 before:via-purple-500 before:to-cyan-500">
                <div>
                    <h2 class="text-base font-bold text-slate-900 dark:text-white" data-i18n="job_view_title">Role Compatibility & Match Analysis</h2>
                    <p class="text-xs text-slate-500 dark:text-slate-400 mt-0.5" data-i18n="job_view_subtitle">Evaluate target positions against your resume profile.</p>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-6 items-start">
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
                            <textarea id="job-cv-text" rows="4" onblur="cleanResumeText(this)" class="w-full bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-100 text-xs rounded-xl p-3 border border-slate-300 dark:border-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 custom-scrollbar resize-none shadow-inner" placeholder="Paste resume text..."></textarea>
                        </div>

                        <button onclick="recommendJobs()" id="recommend-jobs-btn" data-i18n="job_recommend_btn" class="w-full py-2 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 font-medium text-xs rounded-xl border border-slate-200 dark:border-slate-700 transition">
                            Suggest Target Roles from CV
                        </button>

                        <div class="flex flex-col gap-2">
                            <div class="flex justify-between items-center">
                                <label class="text-xs font-medium text-slate-700 dark:text-slate-300" data-i18n="job_target_label">Target Positions:</label>
                                <button onclick="addJobInputBox()" data-i18n="job_add_role_btn" class="text-xs text-indigo-600 dark:text-indigo-400 font-semibold hover:underline">+ Add Position</button>
                            </div>
                            <div id="job-inputs-list" class="flex flex-col gap-2 max-h-[380px] overflow-y-auto custom-scrollbar p-1">
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

                    <!-- Column B: History Log Container -->
                    <div class="flex flex-col gap-3 bg-slate-50/70 dark:bg-slate-950/70 p-4 rounded-xl border border-slate-200/80 dark:border-slate-800/80 max-h-[680px] overflow-y-auto custom-scrollbar">
                        <div class="flex justify-between items-center">
                            <h3 class="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider" data-i18n="job_history_title">2. Role Evaluation History Log</h3>
                            <button onclick="clearJobHistory()" data-i18n="job_clear_btn" class="text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 transition">Clear History</button>
                        </div>
                        
                        <div id="job-placeholder-state" class="flex-1 flex flex-col items-center justify-center text-center p-6 text-slate-500 dark:text-slate-400 text-xs gap-1 min-h-[220px]">
                            <p data-i18n="job_history_empty">Submit your resume and target job titles to generate fit metrics and keyword gaps.</p>
                        </div>

                        <!-- Dynamic Grouped History Logs -->
                        <div id="job-history-container" class="flex flex-col gap-4">
                            <!-- Grouped Run Cards appended here -->
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- VIEW 3: STUDENT FINANCIAL AID PORTAL -->
        <div id="view-copilot" class="hidden flex-1 grid grid-cols-1 md:grid-cols-3 gap-4 pb-12 overflow-y-auto custom-scrollbar">
            <!-- Left Inputs -->
            <section class="bg-white/80 dark:bg-slate-900/80 backdrop-blur-md rounded-2xl border border-slate-200/80 dark:border-slate-800/80 p-5 shadow-sm flex flex-col gap-4 overflow-y-auto custom-scrollbar">
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
            <section class="bg-white/80 dark:bg-slate-900/80 backdrop-blur-md rounded-2xl border border-slate-200/80 dark:border-slate-800/80 p-5 shadow-sm flex flex-col gap-3 overflow-y-auto custom-scrollbar">
                <h2 class="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider" data-i18n="copilot_privacy_title">2. Compliance & Privacy Audit</h2>
                <div id="pii-status" class="hidden p-2.5 rounded-xl bg-slate-50/80 dark:bg-slate-950/80 border border-slate-200 dark:border-slate-800 text-xs flex justify-between items-center">
                    <span class="text-slate-600 dark:text-slate-400" data-i18n="copilot_protected_label">Redacted Items:</span>
                    <span id="pii-count" class="font-semibold text-indigo-600 dark:text-indigo-400">0</span>
                </div>
                <div id="sanitized-text" data-i18n="copilot_awaiting_input" class="flex-1 bg-slate-50/70 dark:bg-slate-950/70 p-3 rounded-xl border border-slate-200/80 dark:border-slate-800/80 text-xs text-slate-600 dark:text-slate-400 font-mono overflow-y-auto custom-scrollbar min-h-[220px]">Awaiting input...</div>
            </section>

            <!-- Results & Action Plan -->
            <section class="bg-white/80 dark:bg-slate-900/80 backdrop-blur-md rounded-2xl border border-slate-200/80 dark:border-slate-800/80 p-5 shadow-sm flex flex-col gap-4 overflow-y-auto custom-scrollbar">
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
        <div id="view-bridge" class="hidden flex-1 flex flex-col gap-4 pb-12 overflow-y-auto custom-scrollbar">
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

        <!-- VIEW 5: SKILL CONSTELLATION MAP -->
        <div id="view-constellation" class="hidden flex-1 relative bg-slate-900/60 dark:bg-slate-950/80 rounded-2xl border border-slate-200/80 dark:border-slate-800/80 shadow-md overflow-hidden flex flex-col justify-between h-[calc(100vh-6.5rem)] min-h-0">
            
            <!-- Main Split Body: Left Generator/History Panel & Right Canvas -->
            <div class="flex-1 relative flex flex-col md:flex-row min-h-0 overflow-hidden">
                
                <!-- Left Sidebar: Constellation Generator & History Log -->
                <div class="w-full md:w-80 flex-shrink-0 bg-white/90 dark:bg-slate-900/95 backdrop-blur-md border-r border-slate-200/80 dark:border-slate-800/80 p-3 flex flex-col gap-3 overflow-y-auto custom-scrollbar z-10">
                    
                    <!-- Generator Box -->
                    <div class="flex flex-col gap-2.5 bg-slate-50/80 dark:bg-slate-950/80 p-3 rounded-xl border border-slate-200/80 dark:border-slate-800 flex-shrink-0">
                        <div class="flex justify-between items-center">
                            <h3 class="text-[10px] font-bold uppercase tracking-wider text-indigo-600 dark:text-indigo-400">OpenAI Galaxy Generator</h3>
                            <label for="constellation-cv-file" class="text-[10px] text-indigo-500 hover:underline cursor-pointer">Upload CV PDF</label>
                            <input type="file" id="constellation-cv-file" accept=".pdf,.txt" class="hidden" onchange="uploadConstellationCV(event)">
                        </div>

                        <textarea id="constellation-cv" rows="3" onblur="cleanResumeText(this)" class="w-full bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 text-[11px] rounded-lg p-2 border border-slate-300 dark:border-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500 custom-scrollbar resize-none" placeholder="Paste CV details..."></textarea>
                        <input type="text" id="constellation-job" class="w-full bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 text-[11px] rounded-lg px-2.5 py-1.5 border border-slate-300 dark:border-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500" placeholder="Target Job Title (e.g., AI Research Engineer)">

                        <button onclick="generateNewConstellation()" id="gen-constellation-btn" class="w-full py-2 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-medium text-xs rounded-lg transition shadow-sm">
                            Generate Detailed Skill Map
                        </button>
                    </div>

                    <!-- Constellation History Log -->
                    <div class="flex flex-col bg-slate-50/80 dark:bg-slate-950/80 p-3 rounded-xl border border-slate-200/80 dark:border-slate-800 h-[220px] flex-shrink-0">
                        <div class="flex justify-between items-center pb-2 flex-shrink-0">
                            <h3 class="text-[10px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Galaxy History Log</h3>
                            <button onclick="clearConstellationHistory()" class="text-[10px] text-slate-500 hover:text-rose-500 transition">Clear</button>
                        </div>
                        <div id="constellation-history-list" class="flex flex-col gap-1.5 overflow-y-auto custom-scrollbar flex-1 pr-1">
                            <div class="text-[11px] text-slate-400 dark:text-slate-500 text-center py-4">No recent map generations.</div>
                        </div>
                    </div>

                </div>

                <!-- Right Canvas Viewport -->
                <div class="flex-1 relative overflow-hidden bg-slate-950">
                    <canvas id="constellationCanvas" class="w-full h-full absolute inset-0 cursor-grab active:cursor-grabbing"></canvas>

                    <!-- Top Right Floating Controls for Constellation Map -->
                    <div class="absolute top-3 right-3 z-20 flex items-center gap-1.5 bg-white/90 dark:bg-slate-900/90 backdrop-blur-md p-1.5 rounded-xl border border-slate-200/80 dark:border-slate-800 shadow-md">
                        <button onclick="resetCamera()" class="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-[11px] font-medium text-slate-700 dark:text-slate-300 transition">Recenter</button>
                        <button onclick="toggleConnections()" class="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-[11px] font-medium text-slate-700 dark:text-slate-300 transition">Toggle Beams</button>
                    </div>

                    <!-- Node Quest Slide-Out Modal -->
                    <div id="nodeModal" class="absolute bottom-4 right-4 z-20 w-72 bg-white/95 dark:bg-slate-900/95 backdrop-blur-xl border border-slate-200/80 dark:border-slate-800 p-4 rounded-2xl shadow-xl transition-all transform translate-y-6 opacity-0 pointer-events-none flex flex-col gap-2.5">
                        <div class="flex justify-between items-start">
                            <div>
                                <span id="nodeCategory" class="text-[10px] font-extrabold uppercase tracking-widest text-indigo-600 dark:text-indigo-400">Cluster Name</span>
                                <h3 id="nodeTitle" class="text-xs font-bold text-slate-900 dark:text-white mt-0.5">Node Title</h3>
                            </div>
                            <span id="nodeStatusBadge" class="px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider">Status</span>
                        </div>

                        <p id="nodeDesc" class="text-[11px] text-slate-600 dark:text-slate-300 leading-relaxed">—</p>

                        <div class="p-2.5 rounded-xl bg-slate-50 dark:bg-slate-950/80 border border-slate-200/80 dark:border-slate-800 flex flex-col gap-1">
                            <span class="text-[9px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Mission Quest:</span>
                            <p id="nodeQuest" class="text-[11px] text-indigo-700 dark:text-indigo-300 font-medium leading-tight">—</p>
                        </div>

                        <div class="flex justify-end items-center pt-1.5 border-t border-slate-200/80 dark:border-slate-800">
                            <button id="nodeActionBtn" onclick="toggleQuestStatus()" class="px-3 py-1 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-medium text-xs rounded-lg shadow-sm transition">
                                Complete Quest
                            </button>
                        </div>
                    </div>
                </div>

            </div>
        </div>

        <!-- VIEW 6: GODOT GAME SANDBOX -->
        <div id="view-godotgame" class="hidden flex-1 relative bg-slate-900/60 dark:bg-slate-950/80 rounded-2xl border border-slate-200/80 dark:border-slate-800/80 shadow-md overflow-hidden flex flex-col h-[calc(100vh-6.5rem)] min-h-0">
            <div class="p-4 bg-white/90 dark:bg-slate-900/95 backdrop-blur-md border-b border-slate-200/80 dark:border-slate-800 flex items-center justify-between flex-shrink-0">
                <div>
                    <h2 class="text-sm font-bold text-slate-900 dark:text-white" data-i18n="godot_view_title">Boussole Game</h2>
                    <p class="text-xs text-slate-500 dark:text-slate-400" data-i18n="godot_view_subtitle">Boussole Game</p>
                </div>
                <div class="flex items-center gap-2">
                    <button onclick="reloadGodotGame()" class="px-3 py-1.5 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-xs font-medium text-slate-700 dark:text-slate-300 rounded-lg transition shadow-sm" data-i18n="godot_reload_btn">Reload Game</button>
                    <button onclick="toggleGodotFullscreen()" class="px-3 py-1.5 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-xs font-medium text-white rounded-lg transition shadow-sm" data-i18n="godot_fs_btn">Fullscreen</button>
                </div>
            </div>
            
            <div id="godot-container" class="flex-1 relative bg-black flex items-center justify-center overflow-hidden p-4">
                <div class="relative w-full max-w-[1280px] aspect-[16/9] max-h-full shadow-2xl rounded-xl overflow-hidden bg-black">
                    <iframe id="godot-iframe" src="/boussole/" class="w-full h-full border-0 absolute inset-0" allow="autoplay; fullscreen; pointer-lock" sandbox="allow-scripts allow-same-origin allow-pointer-lock allow-downloads"></iframe>
                </div>
            </div>
        </div>
    </main>

    <!-- Frontend Script Logic -->
    <script>
        window.activeStreams = window.activeStreams || {};

        function cleanResumeText(el) {
            if (!el || !el.value) return;
            const raw = el.value;
            const cleaned = raw.replace(/\r\n/g, '\n')
                               .replace(/[ \t]+/g, ' ')
                               .split(/\n\s*\n/)
                               .map(para => para.split('\n').map(line => line.trim()).filter(Boolean).join(' '))
                               .join('\n\n');
            el.value = cleaned;
        }

        const translations = {
            en: {
                btn_career: "Career Coach",
                btn_job: "Job Matcher",
                btn_copilot: "Financial Aid",
                btn_bridge: "Grant-to-Career",
                btn_constellation: "Skill Constellation",
                btn_godotgame: "Boussole Game",
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
                delete_all_btn: "Delete All Sessions",
                chat_placeholder: "Ask a question or select an action template...",
                send_btn: "Send",
                tip_enter: "Press Enter to send, Shift + Enter for line break.",
                godot_view_title: "Boussole Game",
                godot_view_subtitle: "Play, try different careers and navigate through life!",
                godot_reload_btn: "Reload Game",
                godot_fs_btn: "Fullscreen"
            },
            "zh-tw": {
                btn_career: "職涯教練",
                btn_job: "職缺匹配",
                btn_copilot: "學生資助",
                btn_bridge: "資助與就業橋樑",
                btn_constellation: "技能星座圖",
                btn_godotgame: "Boussole 遊戲",
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
                delete_all_btn: "刪除所有會話",
                chat_placeholder: "請輸入問題或選擇快捷模組...",
                send_btn: "發送",
                tip_enter: "按 Enter 發送，Shift + Enter 換行。",
                godot_view_title: "Boussole 遊戲",
                godot_view_subtitle: "遊玩、嘗試不同的職涯並導航人生！",
                godot_reload_btn: "重新載入遊戲",
                godot_fs_btn: "全螢幕"
            },
            "zh-cn": {
                btn_career: "职涯教练",
                btn_job: "职位匹配",
                btn_copilot: "学生资助",
                btn_bridge: "资助与就业桥梁",
                btn_constellation: "技能星座图",
                btn_godotgame: "Boussole 游戏",
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
                delete_all_btn: "删除所有会话",
                chat_placeholder: "请输入问题或选择快捷模块...",
                send_btn: "发送",
                tip_enter: "按 Enter 发送，Shift + Enter 换行。",
                godot_view_title: "Boussole 游戏",
                godot_view_subtitle: "游玩、尝试不同的职业并导航人生！",
                godot_reload_btn: "重新加载游戏",
                godot_fs_btn: "全屏幕"
            }
        };
        let currentLang = 'en';

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
            if (currentMode === 'constellation') drawConstellation();
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
        let constellationHistory = [];

        async function initApp() {
            initTheme();
            const savedLang = localStorage.getItem('boussole_lang') || 'en';
            currentLang = savedLang;
            const langSelect = document.getElementById('lang-select');
            if (langSelect) langSelect.value = savedLang;
            
            changeLanguage(savedLang);
            loadConstellationHistoryFromStorage();
            await loadChats();
            initConstellationEngine();

            const inputEl = document.getElementById('user-input');
            if (inputEl) {
                inputEl.addEventListener('keydown', (e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                        e.preventDefault();
                        submitChat(e);
                    }
                });
            }
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
            const sortedChats = [...chats].reverse();
            sortedChats.forEach(chat => {
                const isActive = chat.id === activeId;
                const div = document.createElement('div');
                div.className = `p-2 rounded-xl text-xs cursor-pointer transition truncate flex justify-between items-center flex-shrink-0 ${isActive ? 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-900 dark:text-indigo-200 font-semibold border border-indigo-200/80 dark:border-indigo-800/80 shadow-sm' : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100/60 dark:hover:bg-slate-800/60'}`;
                div.innerHTML = `<span class="truncate block flex-1" onclick="switchChat('${chat.id}')">${chat.title}</span>`;
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
            if (!confirm("Are you sure you want to delete this session?")) return;
            const res = await fetch('/api/chats/active', { method: 'DELETE' });
            const data = await res.json();
            activeChatId = data.active_id;
            renderChatHistoryList(data.chats, data.active_id);
            renderMessages(data.messages);
        }

        async function deleteAllChats() {
            if (!confirm("Are you sure you want to delete ALL chat sessions?")) return;
            const res = await fetch('/api/chats/all', { method: 'DELETE' });
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
                    const escapedContent = (msg.content || '').replace(/["'`]/g, '&quot;');
                    chatStream.innerHTML += `
                        <div class="flex items-start gap-3 w-full">
                            <div class="w-6 h-6 rounded-lg bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 border border-indigo-200/60 dark:border-indigo-800/60 flex items-center justify-center font-bold text-[10px] flex-shrink-0 mt-0.5 shadow-sm">B</div>
                            <div class="bg-white/90 dark:bg-slate-950/90 border border-slate-200/80 dark:border-slate-800/80 rounded-2xl p-3.5 text-slate-800 dark:text-slate-200 max-w-[85%] text-xs leading-relaxed flex flex-col gap-2 shadow-sm">
                                <div class="ai-markdown-body">${marked.parse(msg.content)}</div>
                                <div class="flex items-center gap-2 pt-1 border-t border-slate-100 dark:border-slate-800/80 text-[10px]">
                                    <button onclick="copyMessageText(this)" data-text="${escapedContent}" class="text-slate-500 hover:text-indigo-600 dark:hover:text-indigo-400 font-medium transition flex items-center gap-1">📋 Copy</button>
                                    <button onclick="speakMessageText(this)" data-text="${escapedContent}" class="text-slate-500 hover:text-indigo-600 dark:hover:text-indigo-400 font-medium transition flex items-center gap-1">🔊 Speak</button>
                                </div>
                            </div>
                        </div>`;
                }
            });

            if (window.activeStreams[activeChatId]) {
                const streamData = window.activeStreams[activeChatId];
                const escapedBuffer = (streamData.buffer || '').replace(/["'`]/g, '&quot;');
                chatStream.innerHTML += `
                    <div class="flex items-start gap-3 w-full">
                        <div class="w-6 h-6 rounded-lg bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 border border-indigo-200/60 dark:border-indigo-800/60 flex items-center justify-center font-bold text-[10px] flex-shrink-0 mt-0.5 shadow-sm">B</div>
                        <div class="bg-white/90 dark:bg-slate-950/90 border border-slate-200/80 dark:border-slate-800/80 rounded-2xl p-3.5 text-slate-800 dark:text-slate-200 max-w-[85%] text-xs leading-relaxed flex flex-col gap-2 shadow-sm">
                            <div id="${streamData.msgId}" class="ai-markdown-body">${streamData.isDone ? marked.parse(streamData.buffer) : streamData.buffer}</div>
                            ${streamData.isDone ? `
                            <div class="flex items-center gap-2 pt-1 border-t border-slate-100 dark:border-slate-800/80 text-[10px]">
                                <button onclick="copyMessageText(this)" data-text="${escapedBuffer}" class="text-slate-500 hover:text-indigo-600 dark:hover:text-indigo-400 font-medium transition flex items-center gap-1">📋 Copy</button>
                                <button onclick="speakMessageText(this)" data-text="${escapedBuffer}" class="text-slate-500 hover:text-indigo-600 dark:hover:text-indigo-400 font-medium transition flex items-center gap-1">🔊 Speak</button>
                            </div>` : ''}
                        </div>
                    </div>`;
            }

            chatStream.scrollTop = chatStream.scrollHeight;
        }

        function copyMessageText(btn) {
            const text = btn.getAttribute('data-text');
            navigator.clipboard.writeText(text).then(() => {
                const orig = btn.innerText;
                btn.innerText = '✓ Copied!';
                setTimeout(() => { btn.innerText = orig; }, 1500);
            });
        }

        function speakMessageText(btn) {
            let text = btn.getAttribute('data-text');
            if (!('speechSynthesis' in window)) {
                return alert("Text-to-speech is not supported in this browser.");
            }
            
            text = text
                .replace(/###|\*\*|\*|__|_|`|#|>|\[.*?\]\(.*?\)/g, '')
                .replace(/[-•]\s+/g, '. ')
                .replace(/\n+/g, '. ');

            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(text);
            const voices = window.speechSynthesis.getVoices();
            const targetLang = currentLang === 'zh-tw' || currentLang === 'zh-cn' ? 'zh' : 'en';
            const preferredVoice = voices.find(v => v.lang.toLowerCase().startsWith(targetLang) && (v.name.includes('Natural') || v.name.includes('Neural') || v.name.includes('Enhanced'))) || voices.find(v => v.lang.toLowerCase().startsWith(targetLang));
            
            if (preferredVoice) utterance.voice = preferredVoice;
            utterance.rate = 1.0; 
            utterance.pitch = 1.0; 
            window.speechSynthesis.speak(utterance);
        }

        function switchView(mode) {
            currentMode = mode;
            
            const mobileSelect = document.getElementById('mobile-view-select');
            if (mobileSelect) mobileSelect.value = mode;

            const careerView = document.getElementById('view-career');
            const jobView = document.getElementById('view-job');
            const copilotView = document.getElementById('view-copilot');
            const bridgeView = document.getElementById('view-bridge');
            const constellationView = document.getElementById('view-constellation');
            const godotView = document.getElementById('view-godotgame');

            const btnCareer = document.getElementById('btn-career');
            const btnJob = document.getElementById('btn-job');
            const btnCopilot = document.getElementById('btn-copilot');
            const btnBridge = document.getElementById('btn-bridge');
            const btnConstellation = document.getElementById('btn-constellation');
            const btnGodot = document.getElementById('btn-godotgame');

            [btnCareer, btnJob, btnCopilot, btnBridge, btnConstellation, btnGodot].forEach(btn => {
                if (btn) btn.className = "text-xs font-medium px-3 py-1.5 rounded-lg text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition";
            });

            careerView.classList.add('hidden');
            jobView.classList.add('hidden');
            copilotView.classList.add('hidden');
            bridgeView.classList.add('hidden');
            constellationView.classList.add('hidden');
            godotView.classList.add('hidden');

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
            } else if (mode === 'constellation') {
                constellationView.classList.remove('hidden');
                if (btnConstellation) btnConstellation.className = "text-xs font-medium px-3 py-1.5 rounded-lg bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-sm transition";
                setTimeout(() => { resizeConstellationCanvas(); }, 50);
            } else if (mode === 'godotgame') {
                godotView.classList.remove('hidden');
                if (btnGodot) btnGodot.className = "text-xs font-medium px-3 py-1.5 rounded-lg bg-white dark:bg-slate-900 text-slate-900 dark:text-white shadow-sm transition";
            }
        }

        function reloadGodotGame() {
            const iframe = document.getElementById('godot-iframe');
            if (iframe) iframe.src = iframe.src;
        }

        function toggleGodotFullscreen() {
            const iframe = document.getElementById('godot-iframe');
            if (!document.fullscreenElement) {
                if (iframe.requestFullscreen) {
                    iframe.requestFullscreen();
                } else if (iframe.webkitRequestFullscreen) {
                    iframe.webkitRequestFullscreen();
                }
            } else {
                if (document.exitFullscreen) {
                    document.exitFullscreen();
                } else if (document.webkitExitFullscreen) {
                    document.webkitExitFullscreen();
                }
            }
        }

        function launchConstellationFromJob(jobTitle) {
            const cvText = document.getElementById('job-cv-text').value.trim() || uploadedResumeText;
            if (!cvText) {
                return alert("Please upload or enter a CV before mapping the constellation.");
            }
            document.getElementById('constellation-cv').value = cvText;
            document.getElementById('constellation-job').value = jobTitle;
            switchView('constellation');
            generateNewConstellation();
        }

        function toggleAccordion(id) {
            const el = document.getElementById(id);
            if (el) el.classList.toggle('hidden');
        }

        // ==============================================================================
        // DYNAMIC CONSTELLATION ENGINE LOGIC
        // ==============================================================================
        let cCanvas, cCtx;
        let cWidth, cHeight;
        let cameraOffset = { x: 0, y: 0 };
        let isDragging = false;
        let dragStart = { x: 0, y: 0 };
        let showBeams = true;
        let selectedNode = null;

        let constellationNodes = [];
        let nodeConnections = [];

        function loadConstellationHistoryFromStorage() {
            try {
                const saved = localStorage.getItem('boussole_constellation_history');
                if (saved) {
                    const parsed = JSON.parse(saved);
                    if (Array.isArray(parsed)) constellationHistory = parsed;
                }
            } catch (e) {
                console.error("Error loading constellation history:", e);
            }
            renderConstellationHistory();
        }

        function saveConstellationHistoryToStorage() {
            try {
                localStorage.setItem('boussole_constellation_history', JSON.stringify(constellationHistory));
            } catch (e) {
                console.error("Error saving constellation history:", e);
            }
        }

        function initConstellationEngine() {
            cCanvas = document.getElementById('constellationCanvas');
            if (!cCanvas) return;
            cCtx = cCanvas.getContext('2d');

            cCanvas.addEventListener('mousedown', e => {
                isDragging = true;
                dragStart = { x: e.clientX - cameraOffset.x, y: e.clientY - cameraOffset.y };
            });

            cCanvas.addEventListener('mousemove', e => {
                if (isDragging) {
                    cameraOffset.x = e.clientX - dragStart.x;
                    cameraOffset.y = e.clientY - dragStart.y;
                    drawConstellation();
                }
            });

            cCanvas.addEventListener('mouseup', () => { isDragging = false; });

            cCanvas.addEventListener('click', e => {
                const rect = cCanvas.getBoundingClientRect();
                const clickX = e.clientX - rect.left - (cWidth / 2 + cameraOffset.x);
                const clickY = e.clientY - rect.top - (cHeight / 2 + cameraOffset.y);

                let hit = false;
                constellationNodes.forEach(node => {
                    const dist = Math.hypot(clickX - node.x, clickY - node.y);
                    if (dist <= node.r + 8) {
                        selectedNode = node;
                        showNodeModal(node);
                        hit = true;
                    }
                });

                if (!hit && selectedNode) {
                    selectedNode = null;
                    hideNodeModal();
                }
                drawConstellation();
            });

            window.addEventListener('resize', () => {
                if (currentMode === 'constellation') resizeConstellationCanvas();
            });
        }

        async function uploadConstellationCV(e) {
            const file = e.target.files[0];
            if (!file) return;
            const formData = new FormData();
            formData.append('file', file);
            try {
                const res = await fetch('/api/parse_resume', { method: 'POST', body: formData });
                const data = await res.json();
                if (data.text) {
                    const el = document.getElementById('constellation-cv');
                    el.value = data.text;
                    cleanResumeText(el);
                }
            } catch (err) {
                console.error("Parse error", err);
            }
        }

        async function generateNewConstellation() {
            const cvText = document.getElementById('constellation-cv').value.trim();
            const jobTitle = document.getElementById('constellation-job').value.trim();
            const btn = document.getElementById('gen-constellation-btn');

            if (!cvText || !jobTitle) {
                return alert("Please enter your CV text/upload document and target job title.");
            }

            btn.disabled = true;
            btn.innerText = "OpenAI Mapping Detailed Tree (15+ Nodes)...";

            try {
                const res = await fetch('/api/generate_constellation', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ cv_text: cvText, job_title: jobTitle })
                });

                const data = await res.json();
                if (data.status === 'success' && data.constellation) {
                    constellationNodes = data.constellation.nodes || [];
                    nodeConnections = data.constellation.connections || [];
                    cameraOffset = { x: 0, y: 0 };
                    selectedNode = null;
                    hideNodeModal();
                    drawConstellation();

                    constellationHistory.unshift({
                        id: Date.now(),
                        title: jobTitle,
                        time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                        nodes: constellationNodes,
                        connections: nodeConnections
                    });
                    saveConstellationHistoryToStorage();
                    renderConstellationHistory();
                } else {
                    alert("Error: " + (data.message || "Failed to generate constellation"));
                }
            } catch (err) {
                console.error(err);
                alert("An error occurred while communicating with OpenAI.");
            } finally {
                btn.disabled = false;
                btn.innerText = "Generate Detailed Skill Map";
            }
        }

        function renderConstellationHistory() {
            const listEl = document.getElementById('constellation-history-list');
            if (!listEl) return;
            if (constellationHistory.length === 0) {
                listEl.innerHTML = `<div class="text-[11px] text-slate-400 dark:text-slate-500 text-center py-4">No recent map generations.</div>`;
                return;
            }
            listEl.innerHTML = '';
            constellationHistory.forEach((item) => {
                const div = document.createElement('div');
                div.className = "p-2 rounded-xl text-xs bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 flex justify-between items-center gap-2 group transition hover:border-indigo-500 cursor-pointer flex-shrink-0";
                div.innerHTML = `
                    <div class="truncate flex-1" onclick="loadConstellationFromHistory(${item.id})">
                        <span class="font-semibold text-slate-900 dark:text-white truncate block">${item.title}</span>
                        <span class="text-[9px] text-slate-400 font-mono">${item.time} • ${item.nodes.length} Nodes</span>
                    </div>
                    <button onclick="deleteConstellationHistoryItem(event, ${item.id})" class="text-slate-400 hover:text-rose-500 p-1 text-[11px]">✕</button>
                `;
                listEl.appendChild(div);
            });
        }

        function loadConstellationFromHistory(id) {
            const found = constellationHistory.find(i => i.id === id);
            if (found) {
                constellationNodes = found.nodes;
                nodeConnections = found.connections;
                cameraOffset = { x: 0, y: 0 };
                selectedNode = null;
                hideNodeModal();
                drawConstellation();
            }
        }

        function deleteConstellationHistoryItem(e, id) {
            e.stopPropagation();
            if (!confirm("Are you sure you want to delete this constellation from history?")) return;
            constellationHistory = constellationHistory.filter(i => i.id !== id);
            saveConstellationHistoryToStorage();
            renderConstellationHistory();
        }

        function clearConstellationHistory() {
            if (!confirm("Are you sure you want to clear all galaxy history logs?")) return;
            constellationHistory = [];
            saveConstellationHistoryToStorage();
            renderConstellationHistory();
        }

        function resizeConstellationCanvas() {
            if (!cCanvas || !cCanvas.parentElement) return;
            cWidth = cCanvas.parentElement.clientWidth;
            cHeight = cCanvas.parentElement.clientHeight;
            cCanvas.width = cWidth * window.devicePixelRatio;
            cCanvas.height = cHeight * window.devicePixelRatio;
            cCtx.scale(window.devicePixelRatio, window.devicePixelRatio);
            drawConstellation();
        }

        function wrapCanvasText(ctx, text, maxWidth) {
            const words = text.split(' ');
            const lines = [];
            let currentLine = words[0] || '';

            for (let i = 1; i < words.length; i++) {
                const word = words[i];
                const width = ctx.measureText(currentLine + " " + word).width;
                if (width < maxWidth) {
                    currentLine += " " + word;
                } else {
                    lines.push(currentLine);
                    currentLine = word;
                }
            }
            if (currentLine) lines.push(currentLine);
            return lines;
        }

        function drawConstellation() {
            if (!cCtx) return;
            cCtx.clearRect(0, 0, cWidth, cHeight);
            const centerX = cWidth / 2 + cameraOffset.x;
            const centerY = cHeight / 2 + cameraOffset.y;
            const isDark = document.documentElement.classList.contains('dark');

            if (showBeams) {
                nodeConnections.forEach(([sourceId, targetId]) => {
                    const source = constellationNodes.find(n => n.id === sourceId);
                    const target = constellationNodes.find(n => n.id === targetId);
                    if (!source || !target) return;

                    cCtx.beginPath();
                    cCtx.moveTo(centerX + source.x, centerY + source.y);
                    cCtx.lineTo(centerX + target.x, centerY + target.y);
                    cCtx.strokeStyle = (source.status === 'unlocked' && target.status === 'unlocked')
                        ? (isDark ? 'rgba(129, 140, 248, 0.4)' : 'rgba(99, 102, 241, 0.3)')
                        : (isDark ? 'rgba(51, 65, 85, 0.3)' : 'rgba(203, 213, 225, 0.6)');
                    cCtx.lineWidth = 1.5;
                    cCtx.setLineDash([4, 4]);
                    cCtx.stroke();
                    cCtx.setLineDash([]);
                });
            }

            if (constellationNodes.length === 0) {
                cCtx.font = '12px Inter, sans-serif';
                cCtx.fillStyle = isDark ? '#64748b' : '#94a3b8';
                cCtx.textAlign = 'center';
                cCtx.fillText("Awaiting generation. Fill out CV & Target Job on the left to map galaxy.", centerX, centerY);
                return;
            }

            constellationNodes.forEach((node) => {
                const nx = centerX + node.x;
                const ny = centerY + node.y;

                if (selectedNode && selectedNode.id === node.id) {
                    cCtx.beginPath();
                    cCtx.arc(nx, ny, node.r + 7, 0, Math.PI * 2);
                    cCtx.strokeStyle = '#38bdf8';
                    cCtx.lineWidth = 2;
                    cCtx.stroke();
                }

                const gradient = cCtx.createRadialGradient(nx, ny, 1, nx, ny, node.r * 2.2);
                gradient.addColorStop(0, node.color || '#6366f1');
                gradient.addColorStop(1, 'transparent');

                cCtx.beginPath();
                cCtx.arc(nx, ny, node.r * 2.2, 0, Math.PI * 2);
                cCtx.fillStyle = gradient;
                cCtx.globalAlpha = node.status === 'locked' ? 0.2 : 0.6;
                cCtx.fill();
                cCtx.globalAlpha = 1.0;

                cCtx.beginPath();
                cCtx.arc(nx, ny, node.r, 0, Math.PI * 2);
                cCtx.fillStyle = node.status === 'locked' ? (isDark ? '#334155' : '#94a3b8') : (node.color || '#6366f1');
                cCtx.fill();

                cCtx.font = '10px Inter, sans-serif';
                const lines = wrapCanvasText(cCtx, node.title, 110);
                const lineHeight = 12;
                const labelOffsetY = node.y < 0 ? -(node.r + 8 + (lines.length * lineHeight)) : (node.r + 14);

                lines.forEach((line, index) => {
                    const textWidth = cCtx.measureText(line).width;
                    const lineY = ny + labelOffsetY + (index * lineHeight);

                    cCtx.fillStyle = isDark ? 'rgba(15, 23, 42, 0.75)' : 'rgba(255, 255, 255, 0.85)';
                    cCtx.beginPath();
                    cCtx.roundRect(nx - (textWidth / 2) - 3, lineY - 9, textWidth + 6, 12, 3);
                    cCtx.fill();

                    cCtx.fillStyle = node.status === 'locked' ? (isDark ? '#94a3b8' : '#64748b') : (isDark ? '#f8fafc' : '#0f172a');
                    cCtx.textAlign = 'center';
                    cCtx.fillText(line, nx, lineY);
                });
            });
        }

        function showNodeModal(node) {
            const modal = document.getElementById('nodeModal');
            document.getElementById('nodeCategory').innerText = node.category || "Skill Node";
            document.getElementById('nodeTitle').innerText = node.title;
            document.getElementById('nodeDesc').innerText = node.desc || "Skill milestone in trajectory.";
            document.getElementById('nodeQuest').innerText = node.quest || "Complete standard practical task.";

            const badge = document.getElementById('nodeStatusBadge');
            const btn = document.getElementById('nodeActionBtn');

            if (node.status === 'unlocked') {
                badge.innerText = "UNLOCKED";
                badge.className = "px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-emerald-100 dark:bg-emerald-950 text-emerald-800 dark:text-emerald-400 border border-emerald-300 dark:border-emerald-800";
                btn.innerText = "Undo Quest";
                btn.className = "px-3 py-1 bg-slate-200 dark:bg-slate-800 hover:bg-slate-300 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 font-medium text-xs rounded-lg transition shadow-sm";
            } else {
                badge.innerText = "LOCKED";
                badge.className = "px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-300 dark:border-slate-700";
                btn.innerText = "Complete Quest";
                btn.className = "px-3 py-1 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-medium text-xs rounded-lg shadow-sm transition";
            }

            modal.classList.remove('opacity-0', 'translate-y-6', 'pointer-events-none');
            modal.classList.add('opacity-100', 'translate-y-0');
        }

        function hideNodeModal() {
            const modal = document.getElementById('nodeModal');
            modal.classList.remove('opacity-100', 'translate-y-0');
            modal.classList.add('opacity-0', 'translate-y-6', 'pointer-events-none');
        }

        function toggleQuestStatus() {
            if (!selectedNode) return;
            selectedNode.status = (selectedNode.status === 'unlocked') ? 'locked' : 'unlocked';
            showNodeModal(selectedNode);
            drawConstellation();
        }

        function resetCamera() {
            cameraOffset = { x: 0, y: 0 };
            drawConstellation();
        }

        function toggleConnections() {
            showBeams = !showBeams;
            drawConstellation();
        }

        // ==============================================================================
        // Job History & Fast Batch Input Handlers
        // ==============================================================================

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
                alert("Resume context uploaded successfully.");
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
                const el = document.getElementById('job-cv-text');
                el.value = data.text;
                cleanResumeText(el);
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
                    <button onclick="this.parentElement.parentElement.remove()" class="text-xs text-rose-500 font-bold hover:underline px-1">✕</button>
                </div>
                <textarea rows="2" placeholder="${t.job_desc_ph}" class="job-desc-input w-full bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 text-xs rounded-lg p-2.5 border border-slate-300 dark:border-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 custom-scrollbar resize-none"></textarea>
            `;
            list.appendChild(div);
        }

        async function recommendJobs() {
            const cvText = document.getElementById('job-cv-text').value;
            if (!cvText) return alert("Please provide or upload a resume first.");
            
            const btn = document.getElementById('recommend-jobs-btn');
            btn.disabled = true;
            btn.innerText = "Analyzing CV...";

            try {
                const res = await fetch('/api/suggest_jobs', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ cv_text: cvText })
                });
                const data = await res.json();
                if (data.jobs && data.jobs.length > 0) {
                    const list = document.getElementById('job-inputs-list');
                    list.innerHTML = '';
                    data.jobs.forEach(j => {
                        const div = document.createElement('div');
                        div.className = "job-input-item flex flex-col gap-2 p-3 rounded-xl bg-slate-50/70 dark:bg-slate-950/70 border border-slate-200/80 dark:border-slate-800/80";
                        div.innerHTML = `
                            <div class="flex justify-between items-center gap-2">
                                <input type="text" value="${j.title || ''}" class="job-title-input w-full bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 text-xs rounded-lg px-2.5 py-1.5 border border-slate-300 dark:border-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500">
                                <button onclick="this.parentElement.parentElement.remove()" class="text-xs text-rose-500 font-bold hover:underline px-1">✕</button>
                            </div>
                            <textarea rows="2" class="job-desc-input w-full bg-white dark:bg-slate-900 text-slate-900 dark:text-slate-100 text-xs rounded-lg p-2.5 border border-slate-300 dark:border-slate-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 custom-scrollbar resize-none">${j.description || ''}</textarea>
                        `;
                        list.appendChild(div);
                    });
                }
            } catch (e) {
                console.error(e);
            } finally {
                btn.disabled = false;
                btn.innerText = (translations[currentLang] || translations.en).job_recommend_btn;
            }
        }

        async function runJobMatch() {
            const cvText = document.getElementById('job-cv-text').value;
            const items = document.querySelectorAll('.job-input-item');
            const targetJobs = [];

            items.forEach(item => {
                const title = item.querySelector('.job-title-input').value;
                const desc = item.querySelector('.job-desc-input').value;
                if (title.trim()) targetJobs.push({ title, description: desc });
            });

            if (!cvText || targetJobs.length === 0) return alert("Provide CV text and at least one target job position.");

            const btn = document.getElementById('job-submit-btn');
            btn.disabled = true;
            btn.innerHTML = `<span class="inline-block animate-pulse">⚡ Batch Evaluating (${targetJobs.length} roles)...</span>`;

            try {
                const res = await fetch('/api/match_jobs', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ cv_text: cvText, target_jobs: targetJobs })
                });
                const data = await res.json();
                
                const historyContainer = document.getElementById('job-history-container');
                const placeholder = document.getElementById('job-placeholder-state');
                if (placeholder) placeholder.classList.add('hidden');

                const runTimestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
                const runId = 'run-' + Date.now();

                const groupCard = document.createElement('div');
                groupCard.className = "bg-white dark:bg-slate-900 rounded-xl border border-slate-200/80 dark:border-slate-800 p-3.5 shadow-sm flex flex-col gap-3";
                
                let jobsHTML = '';
                (data.results || []).forEach((resItem, idx) => {
                    const escapedTitle = (resItem.title || 'Role').replace(/'/g, "\\'");
                    const accId = `acc-${runId}-${idx}`;
                    const score = resItem.score || 0;
                    let badgeColorClass = 'bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300';
                    if (score >= 70) badgeColorClass = 'bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300';
                    else if (score <= 30) badgeColorClass = 'bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300';

                    const goodSkillsList = (resItem.good_skills || []).map(s => 
                        `<li class="text-[11px] text-emerald-800 dark:text-emerald-300">• <strong class="font-semibold text-emerald-900 dark:text-emerald-200">${s.skill || 'Matched Skill'}:</strong> ${s.reason || 'Proven alignment.'}</li>`
                    ).join('');

                    const missingSkillsList = (resItem.missing_skills || []).map(s => 
                        `<li class="text-[11px] text-rose-800 dark:text-rose-300">• <strong class="font-semibold text-rose-900 dark:text-rose-200">${s.skill || 'Gap'}:</strong> ${s.action || 'Recommended focus.'}</li>`
                    ).join('');

                    jobsHTML += `
                        <div class="p-3 rounded-lg bg-slate-50/80 dark:bg-slate-950/80 border border-slate-200/60 dark:border-slate-800 flex flex-col gap-2">
                            <div class="flex justify-between items-center">
                                <h5 class="text-xs font-bold text-slate-900 dark:text-white">${resItem.title}</h5>
                                <span class="px-2 py-0.5 rounded-md text-[10px] font-bold ${badgeColorClass}">${score}% Match</span>
                            </div>
                            <button onclick="toggleAccordion('${accId}')" class="text-[11px] font-semibold text-indigo-600 dark:text-indigo-400 hover:underline flex items-center justify-between w-full pt-1 border-t border-slate-200/60 dark:border-slate-800/80">
                                <span>🔍 Details & Skill Gaps</span>
                                <span>▼</span>
                            </button>
                            <div id="${accId}" class="hidden flex flex-col gap-2.5 pt-2 border-t border-slate-200/40 dark:border-slate-800/60">
                                <div class="p-2 rounded-md bg-white dark:bg-slate-900 border border-slate-200/60 dark:border-slate-800 flex flex-col gap-1">
                                    <span class="text-[9px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Candidate Judgement Review</span>
                                    <p class="text-[11px] text-slate-700 dark:text-slate-300 leading-relaxed">${resItem.summary || 'Strong fit based on skill profile.'}</p>
                                </div>
                                <div class="p-2 rounded-md bg-emerald-50/70 dark:bg-emerald-950/40 border border-emerald-200/70 dark:border-emerald-900/50 flex flex-col gap-1">
                                    <span class="text-[9px] font-bold uppercase tracking-wider text-emerald-700 dark:text-emerald-400">✅ Matched Strengths</span>
                                    <ul class="space-y-1">${goodSkillsList}</ul>
                                </div>
                                <div class="p-2 rounded-md bg-rose-50/70 dark:bg-rose-950/40 border border-rose-200/70 dark:border-rose-900/50 flex flex-col gap-1">
                                    <span class="text-[9px] font-bold uppercase tracking-wider text-rose-700 dark:text-rose-400">⚠️ Missing Skills</span>
                                    <ul class="space-y-1">${missingSkillsList}</ul>
                                </div>
                                <div class="pt-1 flex justify-end">
                                    <button onclick="launchConstellationFromJob('${escapedTitle}')" class="px-2.5 py-1 bg-indigo-50 dark:bg-indigo-950/80 hover:bg-indigo-100 dark:hover:bg-indigo-900 text-indigo-700 dark:text-indigo-300 text-[10px] font-semibold rounded-md border border-indigo-200 dark:border-indigo-800 transition flex items-center gap-1 shadow-sm">
                                        <span>🌐 Map Skill Constellation</span>
                                    </button>
                                </div>
                            </div>
                        </div>
                    `;
                });

                groupCard.innerHTML = `
                    <div class="flex justify-between items-center border-b border-slate-100 dark:border-slate-800 pb-2">
                        <span class="text-[10px] font-bold uppercase tracking-wider text-indigo-600 dark:text-indigo-400">Batch Evaluation @ ${runTimestamp}</span>
                        <span class="text-[10px] text-slate-400 font-mono">${(data.results || []).length} Roles Analyzed</span>
                    </div>
                    <div class="flex flex-col gap-2.5">${jobsHTML}</div>
                `;

                historyContainer.prepend(groupCard);

            } catch (e) {
                console.error(e);
            } finally {
                btn.disabled = false;
                btn.innerText = (translations[currentLang] || translations.en).job_submit_btn;
            }
        }

        function clearJobHistory() {
            if (!confirm("Are you sure you want to clear all job evaluation history logs?")) return;
            document.getElementById('job-history-container').innerHTML = '';
            const placeholder = document.getElementById('job-placeholder-state');
            if (placeholder) placeholder.classList.remove('hidden');
        }

        async function submitChat(e) {
            if (e) e.preventDefault();
            const inputEl = document.getElementById('user-input');
            const prompt = inputEl.value.trim();
            if (!prompt) return;

            inputEl.value = '';
            const chatStream = document.getElementById('chat-stream');

            chatStream.innerHTML += `
                <div class="flex items-start justify-end w-full">
                    <div class="bg-gradient-to-r from-slate-900 to-indigo-900 dark:from-slate-800 dark:to-indigo-950 border border-transparent dark:border-slate-700/60 rounded-2xl p-3.5 text-white font-medium max-w-[85%] text-xs leading-relaxed shadow-sm">${prompt}</div>
                </div>`;

            const msgId = 'stream-' + Date.now();
            chatStream.innerHTML += `
                <div class="flex items-start gap-3 w-full">
                    <div class="w-6 h-6 rounded-lg bg-indigo-50 dark:bg-indigo-950 text-indigo-600 dark:text-indigo-400 border border-indigo-200/60 dark:border-indigo-800/60 flex items-center justify-center font-bold text-[10px] flex-shrink-0 mt-0.5 shadow-sm">B</div>
                    <div class="bg-white/90 dark:bg-slate-950/90 border border-slate-200/80 dark:border-slate-800/80 rounded-2xl p-3.5 text-slate-800 dark:text-slate-200 max-w-[85%] text-xs leading-relaxed flex flex-col gap-2 shadow-sm">
                        <div id="${msgId}" class="ai-markdown-body">Thinking...</div>
                    </div>
                </div>`;

            chatStream.scrollTop = chatStream.scrollHeight;
            window.activeStreams[activeChatId] = { msgId, buffer: '', isDone: false };

            try {
                const response = await fetch('/api/chat/stream', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ prompt, resume_context: uploadedResumeText })
                });

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let fullResponse = '';

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    const chunk = decoder.decode(value, { stream: true });
                    fullResponse += chunk;
                    window.activeStreams[activeChatId].buffer = fullResponse;
                    const streamEl = document.getElementById(msgId);
                    if (streamEl) streamEl.innerHTML = marked.parse(fullResponse);
                    chatStream.scrollTop = chatStream.scrollHeight;
                }

                window.activeStreams[activeChatId].isDone = true;
                delete window.activeStreams[activeChatId];
                await loadChats();
            } catch (err) {
                console.error("Stream error", err);
            }
        }

        function applyPreset(presetKey) {
            const input = document.getElementById('user-input');
            const presets = {
                roast: "Conduct a direct resume audit. Point out key areas for improvement.",
                gap: "Analyze potential skill gaps between my current background and senior industry standards.",
                behavioral: "Simulate a behavioral interview question and provide feedback on my response using STAR method.",
                roadmap: "Build a structured 90-day action roadmap to transition into my target role."
            };
            if (presets[presetKey]) {
                input.value = presets[presetKey];
                submitChat();
            }
        }

        function exportMarkdown() {
            window.location.href = '/api/chats/export';
        }

        function loadScenario(type, income, members) {
            const notes = document.getElementById('case-notes');
            if (income !== null) {
                notes.value = `Household income is HKD $${income} per month with ${members} family members residing together.`;
                document.getElementById('income-input-box').value = income;
                document.getElementById('income-slider').value = Math.min(income, 50000);
            } else {
                notes.value = `Household has ${members} family members. Monthly income pending confirmation.`;
            }
            document.getElementById('members-input-box').value = members;
            document.getElementById('members-slider').value = members;
            processCase();
        }

        function syncFromBox(type) {
            if (type === 'income') {
                const val = document.getElementById('income-input-box').value;
                document.getElementById('income-slider').value = Math.min(val, 50000);
            } else {
                const val = document.getElementById('members-input-box').value;
                document.getElementById('members-slider').value = Math.min(val, 8);
            }
            processCase();
        }

        function syncFromSlider(type) {
            if (type === 'income') {
                const val = document.getElementById('income-slider').value;
                document.getElementById('income-input-box').value = val;
            } else {
                const val = document.getElementById('members-slider').value;
                document.getElementById('members-input-box').value = val;
            }
            processCase();
        }

        async function processCase() {
            const text = document.getElementById('case-notes').value;
            const income = parseFloat(document.getElementById('income-input-box').value) || null;
            const members = parseInt(document.getElementById('members-input-box').value) || 1;

            const res = await fetch('/api/copilot/evaluate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ notes: text, income, members })
            });

            const data = await res.json();
            document.getElementById('pii-status').classList.remove('hidden');
            document.getElementById('pii-count').innerText = data.sanitized_count;
            document.getElementById('sanitized-text').innerText = data.sanitized_text;

            const evalData = data.evaluation;
            const badge = document.getElementById('verdict-badge');
            badge.innerText = evalData.status;
            badge.className = `px-2 py-0.5 rounded-md text-[11px] font-semibold bg-${evalData.badge_color}-100 dark:bg-${evalData.badge_color}-950 text-${evalData.badge_color}-800 dark:text-${evalData.badge_color}-300`;

            document.getElementById('verdict-title').innerText = evalData.summary;
            document.getElementById('verdict-details').innerText = evalData.details;
            document.getElementById('verdict-citation').innerText = evalData.policy_citation;

            const checklist = document.getElementById('document-checklist');
            checklist.innerHTML = '';
            evalData.required_documents.forEach(doc => {
                checklist.innerHTML += `<li>${doc}</li>`;
            });
        }

        function executeOverride() {
            const reason = document.getElementById('override-reason').value;
            if (!reason) return alert("Select appeal reason.");
            const ts = document.getElementById('override-timestamp');
            ts.classList.remove('hidden');
            ts.innerText = `Appeal logged on ${new Date().toLocaleString()} (${reason})`;
        }

        function syncBridgeFromBox(type) {
            if (type === 'income') {
                const val = document.getElementById('bridge-income-input-box').value;
                document.getElementById('bridge-income-slider').value = Math.min(val, 50000);
            } else if (type === 'tuition') {
                const val = document.getElementById('tuition-input-box').value;
                document.getElementById('tuition-slider').value = Math.min(val, 100000);
            } else if (type === 'living') {
                const val = document.getElementById('living-input-box').value;
                document.getElementById('living-slider').value = Math.min(val, 80000);
            }
            recalcBridge();
        }

        function syncBridgeFromSlider(type) {
            if (type === 'income') {
                const val = document.getElementById('bridge-income-slider').value;
                document.getElementById('bridge-income-input-box').value = val;
            } else if (type === 'tuition') {
                const val = document.getElementById('tuition-slider').value;
                document.getElementById('tuition-input-box').value = val;
            } else if (type === 'living') {
                const val = document.getElementById('living-slider').value;
                document.getElementById('living-input-box').value = val;
            }
            recalcBridge();
        }

        function recalcBridge() {
            const inc = parseFloat(document.getElementById('bridge-income-input-box').value) || 0;
            const tui = parseFloat(document.getElementById('tuition-input-box').value) || 0;
            const liv = parseFloat(document.getElementById('living-input-box').value) || 0;
            const shortfall = Math.max(0, (tui + liv) - (inc * 5));
            document.getElementById('dynamic-shortfall').innerText = `HKD $${shortfall.toLocaleString()}`;
        }
    </script>
</body>
</html>
"""

# ==============================================================================
# 3. API ENDPOINTS & FLASK ROUTES
# ==============================================================================

@app.route('/login')
def login_page():
    if session.get('authenticated'):
        return redirect(url_for('index'))
    return render_template_string(LOGIN_HTML_TEMPLATE)

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json() or {}
    password = data.get('password', '')
    if password == APP_PASSWORD:
        session['authenticated'] = True
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Invalid password"}), 401

@app.route('/api/logout')
def api_logout():
    session.clear()
    return redirect(url_for('login_page'))

@app.before_request
def require_login():
    allowed_routes = ['login_page', 'api_login', 'static']
    if request.endpoint and request.endpoint not in allowed_routes:
        if not session.get('authenticated'):
            if request.path.startswith('/api/'):
                return jsonify({"status": "error", "message": "Unauthorized"}), 401
            return redirect(url_for('login_page'))

@app.route('/')
def index():
    return render_template_string(UNIFIED_HTML_TEMPLATE)

@app.route('/api/generate_constellation', methods=['POST'])
def generate_constellation():
    data = request.get_json() or {}
    cv_text = data.get('cv_text', '')
    job_title = data.get('job_title', '')

    if not cv_text or not job_title:
        return jsonify({"status": "error", "message": "Both CV text and target job title are required."}), 400

    prompt = f"""
    You are an expert technical career architect. Analyze the candidate CV against the target job '{job_title}'.
    Build a comprehensive, multi-tiered Skill Constellation graph with 15 to 20 detailed nodes in a single response.

    Requirements:
    1. Node 1: Central Hub (x:0, y:0, title: "Target Trajectory: {job_title}", status: "unlocked", color: "#6366f1", r: 16).
    2. Inner Orbit (4-6 nodes, radius ~120-160px): Strong, mastered core skills found in the candidate CV. Set status="unlocked", color="#10b981".
    3. Middle Orbit (5-7 nodes, radius ~200-260px): Intermediate foundational and supporting skills required for the role. Set status="unlocked" or "locked" appropriately, color="#06b6d4" or "#a855f7".
    4. Outer Orbit (5-7 nodes, radius ~300-380px): Missing skill gaps & advanced domain requirements for '{job_title}'. Set status="locked", color="#f59e0b" or "#ef4444".
    5. Coordinates: Distribute nodes evenly across 360 degrees so nodes do NOT overlap. Keep spacing clean.
    6. Provide a rich array of connections [source_id, target_id] linking central, inner, middle, and outer nodes.

    Return ONLY raw JSON in this exact structure:
    {{
      "nodes": [
        {{
          "id": 1,
          "title": "Skill Name",
          "category": "Core / Systems / Gap",
          "status": "unlocked",
          "x": 0,
          "y": 0,
          "r": 12,
          "color": "#6366f1",
          "desc": "Detailed technical explanation.",
          "quest": "Actionable mission task to complete."
        }}
      ],
      "connections": [
        [1, 2], [2, 5], [1, 3]
      ]
    }}

    Target Role: {job_title}
    Candidate CV Content:
    {cv_text[:3000]}
    """

    try:
        response = client.chat.completions.create(
            model=deployment_name,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        graph_data = json.loads(response.choices[0].message.content)
        return jsonify({"status": "success", "constellation": graph_data})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/chats', methods=['GET'])
def get_chats():
    sessions, active_id = load_storage()
    chats_list = [{"id": k, "title": v["title"]} for k, v in sessions.items()]
    active_messages = sessions.get(active_id, {}).get("messages", [])
    filtered_messages = [m for m in active_messages if m["role"] != "system"]
    return jsonify({
        "chats": chats_list,
        "active_id": active_id,
        "messages": filtered_messages
    })

@app.route('/api/chats/new', methods=['POST'])
def create_chat():
    sessions, _ = load_storage()
    new_id = f"chat_{int(datetime.now().timestamp())}"
    sessions[new_id] = {
        "id": new_id,
        "title": "New Conversation",
        "messages": [
            {"role": "system", "content": BOUSSOLE_SYSTEM_INSTRUCTION},
            {"role": "assistant", "content": WELCOME_GREETING}
        ]
    }
    save_storage(sessions, new_id)
    return jsonify({"status": "created", "active_id": new_id})

@app.route('/api/chats/switch', methods=['POST'])
def switch_chat():
    data = request.get_json() or {}
    chat_id = data.get('chat_id')
    sessions, _ = load_storage()
    if chat_id in sessions:
        save_storage(sessions, chat_id)
        filtered = [m for m in sessions[chat_id]["messages"] if m["role"] != "system"]
        chats_list = [{"id": k, "title": v["title"]} for k, v in sessions.items()]
        return jsonify({"status": "switched", "active_id": chat_id, "messages": filtered, "chats": chats_list})
    return jsonify({"status": "error", "message": "Session not found"}), 404

@app.route('/api/chats/active', methods=['DELETE'])
def delete_active_chat():
    sessions, active_id = load_storage()
    keys = list(sessions.keys())
    
    if len(keys) <= 1:
        sessions[active_id]["messages"] = [
            {"role": "system", "content": BOUSSOLE_SYSTEM_INSTRUCTION},
            {"role": "assistant", "content": WELCOME_GREETING}
        ]
        sessions[active_id]["title"] = "New Conversation"
        save_storage(sessions, active_id)
    else:
        idx = keys.index(active_id) if active_id in keys else 0
        del sessions[active_id]
        remaining_keys = list(sessions.keys())
        
        if idx > 0 and (idx - 1) < len(remaining_keys):
            active_id = remaining_keys[idx - 1]
        elif remaining_keys:
            active_id = remaining_keys[0]
        else:
            active_id = f"chat_{int(datetime.now().timestamp())}"
            sessions[active_id] = {
                "id": active_id,
                "title": "New Conversation",
                "messages": [
                    {"role": "system", "content": BOUSSOLE_SYSTEM_INSTRUCTION},
                    {"role": "assistant", "content": WELCOME_GREETING}
                ]
            }
        save_storage(sessions, active_id)
    
    chats_list = [{"id": k, "title": v["title"]} for k, v in sessions.items()]
    filtered = [m for m in sessions[active_id]["messages"] if m["role"] != "system"]
    return jsonify({"status": "deleted", "active_id": active_id, "chats": chats_list, "messages": filtered})

@app.route('/api/chats/all', methods=['DELETE'])
def delete_all_chats():
    default_id = f"chat_{int(datetime.now().timestamp())}"
    new_sessions = {
        default_id: {
            "id": default_id,
            "title": "New Conversation",
            "messages": [
                {"role": "system", "content": BOUSSOLE_SYSTEM_INSTRUCTION},
                {"role": "assistant", "content": WELCOME_GREETING}
            ]
        }
    }
    save_storage(new_sessions, default_id)
    chats_list = [{"id": default_id, "title": "New Conversation"}]
    return jsonify({"status": "deleted_all", "active_id": default_id, "chats": chats_list, "messages": []})

@app.route('/api/chat/stream', methods=['POST'])
def stream_chat():
    data = request.get_json() or {}
    prompt = data.get('prompt', '')
    resume_context = data.get('resume_context', '')
    
    sessions, active_id = load_storage()
    active_session = sessions.get(active_id)
    
    if not active_session:
        return jsonify({"error": "No active session"}), 400

    if len(active_session["messages"]) <= 2:
        active_session["title"] = prompt[:24] + ("..." if len(prompt) > 24 else "")

    user_content = prompt
    if resume_context:
        user_content += f"\n\n[Candidate Resume Context Attachment]:\n{resume_context}"

    active_session["messages"].append({"role": "user", "content": user_content})
    save_storage(sessions, active_id)

    def generate():
        response_text = ""
        try:
            stream = client.chat.completions.create(
                model=deployment_name,
                messages=active_session["messages"],
                stream=True
            )
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    response_text += token
                    yield token
        except Exception as e:
            response_text = f"Error calling OpenAI backend: {e}"
            yield response_text

        sessions, active_id_latest = load_storage()
        if active_id_latest in sessions:
            sessions[active_id_latest]["messages"].append({"role": "assistant", "content": response_text})
            save_storage(sessions, active_id_latest)

    return Response(stream_with_context(generate()), mimetype='text/plain')

@app.route('/api/parse_resume', methods=['POST'])
def parse_resume():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files['file']
    raw_text = ""
    if file.filename.endswith('.pdf'):
        reader = PdfReader(io.BytesIO(file.read()))
        for page in reader.pages:
            raw_text += (page.extract_text() or "") + "\n"
    else:
        raw_text = file.read().decode('utf-8', errors='ignore')
    
    clean_text = normalize_resume_text(raw_text)
    return jsonify({"text": clean_text})

@app.route('/api/suggest_jobs', methods=['POST'])
def suggest_jobs():
    data = request.get_json() or {}
    cv_text = data.get('cv_text', '')
    
    prompt = f"""
    Analyze this resume thoroughly. Suggest 5 highly specific and tailored target job roles.
    For each role, provide the specific title and a detailed 2-3 sentence description. 
    Return raw JSON format like: [{{"title": "...", "description": "..."}}]

    Resume:
    {cv_text[:2500]}
    """
    try:
        res = client.chat.completions.create(
            model=deployment_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        content = res.choices[0].message.content
        json_match = re.search(r'\[.*\]', content, re.DOTALL)
        if json_match:
            jobs = json.loads(json_match.group(0))
            return jsonify({"jobs": jobs})
    except Exception as e:
        print(f"Error suggesting jobs: {e}")
    
    return jsonify({"jobs": [
        {"title": "Senior Full-Stack Python & React Engineer", "description": "Design and scale cloud-native microservices using FastAPI and React. Own backend architecture, CI/CD deployment pipelines, and database optimization."},
        {"title": "AI Model Alignment & LLM Integration Specialist", "description": "Implement Retrieval-Augmented Generation (RAG) pipelines, fine-tune open-source LLMs, and optimize enterprise API integrations using Azure and OpenAI endpoints."},
        {"title": "Quantitative Data Analyst & BI Developer", "description": "Build high-performance SQL data pipelines and interactive executive dashboards to track retention metrics and financial performance indicators."},
        {"title": "Cloud Infrastructure & DevOps Automation Engineer", "description": "Manage containerized Kubernetes clusters, automated Terraform infrastructure, and secure cloud CI/CD workflows across multi-region environments."},
        {"title": "Technical Product Manager (AI & Data Platforms)", "description": "Drive product roadmaps for enterprise data systems, bridging engineering teams and stakeholders to optimize feature deployment and alignment metrics."}
    ]})

@app.route('/api/match_jobs', methods=['POST'])
def match_jobs():
    data = request.get_json() or {}
    cv_text = data.get('cv_text', '')
    target_jobs = data.get('target_jobs', [])

    if not target_jobs:
        return jsonify({"results": []})

    prompt = f"""
    Compare the Candidate CV against the following target roles:
    {json.dumps(target_jobs, indent=2)}

    Analyze ALL roles in a SINGLE batch run and return JSON with a top-level "results" array:
    {{
      "results": [
        {{
          "title": "Exact Role Title",
          "score": 85,
          "summary": "Fit review summary.",
          "job_purpose": "Primary responsibilities in industry.",
          "good_skills": [{{"skill": "Name", "reason": "Why candidate matches"}}],
          "missing_skills": [{{"skill": "Name", "action": "How to bridge gap"}}]
        }}
      ]
    }}

    Candidate CV:
    {cv_text[:2500]}
    """

    try:
        res = client.chat.completions.create(
            model=deployment_name,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        parsed = json.loads(res.choices[0].message.content)
        return jsonify({"results": parsed.get("results", [])})
    except Exception as e:
        print(f"Batch match error: {e}")
        fallback_results = [
            {
                "title": job.get('title', 'Target Role'),
                "score": 75,
                "summary": "Role alignment processed via baseline engine.",
                "job_purpose": "Core domain responsibilities.",
                "good_skills": [{"skill": "Core Foundations", "reason": "Technical alignment in CV."}],
                "missing_skills": [{"skill": "Specialized Tooling", "action": "Review targeted job specs."}]
            }
            for job in target_jobs
        ]
        return jsonify({"results": fallback_results})

@app.route('/api/copilot/evaluate', methods=['POST'])
def copilot_evaluate():
    data = request.get_json() or {}
    notes = data.get('notes', '')
    income = data.get('income')
    members = data.get('members', 1)

    sanitized_text, count = sanitize_pii(notes)
    eval_res = evaluate_student_eligibility(income, members)

    return jsonify({
        "sanitized_text": sanitized_text,
        "sanitized_count": count,
        "evaluation": eval_res
    })

@app.route('/api/chats/export', methods=['GET'])
def export_chat():
    sessions, active_id = load_storage()
    messages = sessions.get(active_id, {}).get("messages", [])
    
    md_content = "# Boussole AI Chat Session Export\n\n"
    for msg in messages:
        if msg["role"] == "system": continue
        role_name = "User" if msg["role"] == "user" else "Boussole AI"
        md_content += f"### {role_name}\n{msg['content']}\n\n---\n\n"

    return Response(
        md_content,
        mimetype="text/markdown",
        headers={"Content-Disposition": f"attachment;filename=boussole_session_{active_id}.md"}
    )

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)