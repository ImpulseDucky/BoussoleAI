import os
import io
import json
import re
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template_string, session, redirect, url_for
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
# SERVER-SIDE CHAT STORAGE
# ==============================================================================

BOUSSOLE_SYSTEM_INSTRUCTION = """
You are Boussole AI, an elite, executive-level career navigation strategist and hackathon career advisor.
Your mission is to help candidates navigate skill gaps, optimize resumes, master technical/behavioral interviews, and build structured career roadmaps.

Core Operating Principles:
1. Direct, Actionable Guidance: Cut generic fluff. Focus on clear execution steps.
2. The Google X-Y-Z Formula: When rewriting resume bullets, enforce "Accomplished [X], as measured by [Y], by doing [Z]".
3. Structure and Formatting: Utilize Markdown headers, bullet points, bold key terms, and code blocks where applicable.
4. Voice & Tone: Empathetic yet candid, strategic, professional, and encouraging.
5. Branding Identity: Always identify naturally as Boussole AI when introduced.
6. Add new blank lines between every single paragraph to guarantee readability. Use double line breaks (\n\n) for spacing.
7. Make paragraphs at least 3 lines per paragraph.
"""

WELCOME_GREETING = "Welcome to Boussole AI Career Strategist. How can I help you navigate your professional trajectory today?"

CHAT_SESSIONS = {
    "default": {
        "id": "default",
        "title": "New Conversation",
        "messages": [
            {"role": "system", "content": BOUSSOLE_SYSTEM_INSTRUCTION},
            {"role": "assistant", "content": WELCOME_GREETING}
        ]
    }
}
ACTIVE_SESSION_ID = "default"

# ==============================================================================
# 1. STUDENT FINANCIAL AID ENGINE (PDPO + DETERMINISTIC RULES + LOAN CALCULATOR)
# ==============================================================================

def sanitize_pii(text: str) -> tuple[str, int]:
    """
    Scrubs HKIDs and Hong Kong phone numbers client-side/server-side before AI processing.
    Complying with Hong Kong Personal Data (Privacy) Ordinance (PDPO Cap. 486).
    """
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
            "badge_color": "cyan",
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
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Boussole AI — Protected Access</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>body { font-family: 'Plus Jakarta Sans', sans-serif; }</style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex items-center justify-center p-4 selection:bg-cyan-500 selection:text-white">
    <div class="glass-panel bg-slate-900 border border-slate-800 p-8 rounded-2xl shadow-2xl max-w-md w-full flex flex-col gap-6">
        <div class="flex items-center gap-3">
            <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
                <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path></svg>
            </div>
            <div>
                <h1 class="font-bold text-lg text-white">Boussole <span class="text-cyan-400">AI</span></h1>
                <p class="text-xs text-slate-400">Restricted Access Portal</p>
            </div>
        </div>
        <form id="login-form" onsubmit="handleLogin(event)" class="flex flex-col gap-4">
            <div class="flex flex-col gap-1.5">
                <label class="text-xs font-semibold text-slate-300">Enter Access Password:</label>
                <input type="password" id="password-input" class="w-full bg-slate-950 text-slate-100 text-sm rounded-xl px-4 py-3 border border-slate-800 focus:outline-none focus:border-cyan-500" placeholder="Password..." required>
            </div>
            <div id="error-msg" class="text-xs text-rose-400 hidden"></div>
            <button type="submit" class="w-full py-3 bg-cyan-600 hover:bg-cyan-500 text-white font-semibold text-xs rounded-xl transition shadow-lg shadow-cyan-600/20">Unlock Portal</button>
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
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Boussole AI — Career Navigation & Student Copilot</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Plus Jakarta Sans', sans-serif; }
        .glass-panel { background: rgba(15, 23, 42, 0.85); border: 1px solid rgba(255, 255, 255, 0.08); }
        .custom-scrollbar::-webkit-scrollbar { width: 5px; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.15); border-radius: 9999px; }
        .typing-dot { animation: typingWave 1.4s infinite ease-in-out both; }
        .typing-dot:nth-child(1) { animation-delay: 0s; }
        .typing-dot:nth-child(2) { animation-delay: 0.2s; }
        .typing-dot:nth-child(3) { animation-delay: 0.4s; }
        @keyframes typingWave { 0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; } 40% { transform: scale(1); opacity: 1; } }
        
        * {
            box-sizing: border-box;
            min-width: 0;
        }
        body, html {
            overflow-x: hidden;
            width: 100%;
            height: 100%;
        }
        #chat-stream {
            overflow-x: hidden !important;
            word-break: break-word;
            overflow-wrap: anywhere;
        }
        .ai-markdown-body, .ai-markdown-body p, .ai-markdown-body li, .ai-markdown-body span, .ai-markdown-body div {
            overflow-wrap: anywhere;
            word-break: break-word;
            max-width: 100%;
        }
        .ai-markdown-body pre, .ai-markdown-body code {
            white-space: pre-wrap !important;
            word-break: break-all !important;
            max-width: 100% !important;
        }
        .ai-markdown-body p {
            margin-bottom: 1rem !important;
        }
        .ai-markdown-body ul, .ai-markdown-body ol {
            margin-bottom: 1rem !important;
            padding-left: 1.25rem;
        }
        input[type=number]::-webkit-inner-spin-button, input[type=number]::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
    </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-[100dvh] flex flex-col justify-between selection:bg-cyan-500 selection:text-white overflow-y-auto md:overflow-hidden" onload="initApp()">

    <!-- Top Navigation Bar -->
    <header class="border-b border-slate-800 bg-slate-900 sticky top-0 z-50 flex-shrink-0">
        <div class="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-2">
            <div class="flex items-center gap-2 min-w-0">
                <div class="w-8 h-8 sm:w-9 sm:h-9 rounded-xl bg-gradient-to-tr from-cyan-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-cyan-500/20 flex-shrink-0">
                    <svg class="w-4 h-4 sm:w-5 sm:h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path></svg>
                </div>
                <div class="min-w-0">
                    <h1 class="font-bold text-sm sm:text-lg text-white tracking-tight leading-none truncate">Boussole <span class="text-cyan-400 font-normal">AI</span></h1>
                    <div class="flex items-center gap-1.5 mt-0.5">
                        <p class="text-[9px] sm:text-[11px] text-slate-400 tracking-wide truncate" id="brand-subtitle" data-i18n="brand_subtitle_career">Career Intelligence & Roadmapping</p>
                        <span class="hidden sm:inline text-[9px] px-1.5 py-0.5 rounded bg-slate-800 text-cyan-400 border border-slate-700 font-mono">⚡ gpt-5-mini</span>
                    </div>
                </div>
            </div>
            
            <div class="flex items-center gap-1.5 sm:gap-2 flex-shrink-0">
                <!-- Mobile View Switcher Dropdown (Visible only on small screens < md) -->
                <select id="mobile-view-select" onchange="switchView(this.value)" class="md:hidden text-xs font-semibold px-2 py-2 rounded-xl bg-slate-800 text-cyan-300 border border-slate-700 outline-none cursor-pointer">
                    <option value="career" data-i18n="btn_career">💼 Career Coach</option>
                    <option value="job" data-i18n="btn_job">🎯 Job Matcher</option>
                    <option value="copilot" data-i18n="btn_copilot">🏛 Financial Aid</option>
                    <option value="bridge" data-i18n="btn_bridge">🌉 Grant-to-Career</option>
                </select>

                <!-- Desktop View Switcher Buttons (Visible only on medium screens and up >= md) -->
                <div class="hidden md:flex items-center gap-2">
                    <button onclick="switchView('career')" id="btn-career" data-i18n="btn_career" class="text-xs font-semibold px-3 py-2 rounded-xl bg-cyan-600 text-white transition shadow-sm">
                        💼 Career Coach
                    </button>
                    <button onclick="switchView('job')" id="btn-job" data-i18n="btn_job" class="text-xs font-semibold px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-indigo-300 border border-slate-700 transition shadow-sm">
                        🎯 Job Matcher
                    </button>
                    <button onclick="switchView('copilot')" id="btn-copilot" data-i18n="btn_copilot" class="text-xs font-semibold px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition shadow-sm">
                        🏛 Financial Aid
                    </button>
                    <button onclick="switchView('bridge')" id="btn-bridge" data-i18n="btn_bridge" class="text-xs font-semibold px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-purple-300 border border-slate-700 transition shadow-sm">
                        🌉 Grant-to-Career
                    </button>
                </div>

                <!-- Language Dropdown Selector -->
                <select id="lang-select" onchange="changeLanguage(this.value)" class="text-xs font-semibold px-2 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition shadow-sm outline-none cursor-pointer">
                    <option value="en">🇬🇧 EN</option>
                    <option value="zh-tw">🇭🇰 繁體</option>
                    <option value="zh-cn">🇨🇳 简体</option>
                </select>

                <!-- Logout Button -->
                <a href="/api/logout" class="text-xs font-semibold px-2.5 py-2 rounded-xl bg-slate-800 hover:bg-rose-950 text-rose-300 border border-slate-700 transition shadow-sm" title="Lock session">🔒 Lock</a>
            </div>
        </div>
    </header>

    <!-- MAIN APP VIEWS CONTAINER -->
    <main class="max-w-7xl mx-auto px-2 sm:px-6 lg:px-8 py-3 w-full flex-1 flex flex-col overflow-y-auto md:overflow-hidden">

        <!-- VIEW 1: CAREER COACH (DEFAULT) -->
        <div id="view-career" class="flex-1 flex flex-col md:flex-row gap-4 h-full overflow-y-auto md:overflow-hidden">
            <!-- Sidebar controls -->
            <aside class="w-full md:w-80 flex flex-col gap-3 flex-shrink-0 overflow-y-auto max-h-[220px] md:max-h-none custom-scrollbar">
                
                <!-- New Chat & Chat History Panel -->
                <div class="glass-panel rounded-2xl p-3 flex flex-col gap-2">
                    <div class="flex items-center justify-between px-1">
                        <h2 class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider" data-i18n="chat_history_title">Chat History</h2>
                        <button onclick="createNewChat()" data-i18n="new_chat_btn" class="text-[11px] bg-cyan-600/30 hover:bg-cyan-600/50 text-cyan-300 px-2 py-0.5 rounded border border-cyan-500/30 font-semibold transition">+ New Chat</button>
                    </div>
                    <div id="chat-history-list" class="flex flex-col gap-1.5 max-h-[140px] overflow-y-auto custom-scrollbar pr-1">
                        <!-- Dynamic chat history items inserted here -->
                    </div>
                </div>

                <div class="glass-panel rounded-2xl p-3 flex flex-col gap-2">
                    <h2 class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider px-1" data-i18n="upload_resume_title">Upload Resume (PDF/TXT)</h2>
                    <label for="pdf-file-input" class="cursor-pointer flex items-center justify-center p-3 border border-dashed border-slate-700 hover:border-cyan-500/50 rounded-xl bg-slate-900/40 transition text-center">
                        <span id="upload-status-text" data-i18n="upload_resume_label" class="text-xs text-slate-300 font-medium truncate">📎 Click to attach resume</span>
                    </label>
                    <input id="pdf-file-input" type="file" accept=".pdf,.txt" class="hidden" onchange="handleFileUpload(event)">
                </div>

                <div class="glass-panel rounded-2xl p-3 flex flex-col gap-2">
                    <h2 class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider px-1" data-i18n="playbooks_title">Career Playbooks</h2>
                    <div class="grid grid-cols-2 md:grid-cols-1 gap-2">
                        <button onclick="applyPreset('roast')" data-i18n="preset_roast" class="text-left p-2 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-cyan-500/50 transition text-xs text-cyan-300 font-semibold truncate">🔥 Resume Roast</button>
                        <button onclick="applyPreset('gap')" data-i18n="preset_gap" class="text-left p-2 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-indigo-500/50 transition text-xs text-indigo-300 font-semibold truncate">🎯 Skill Gap Matrix</button>
                        <button onclick="applyPreset('behavioral')" data-i18n="preset_behavioral" class="text-left p-2 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-emerald-500/50 transition text-xs text-emerald-300 font-semibold truncate">🎙️ Interview Drill</button>
                        <button onclick="applyPreset('roadmap')" data-i18n="preset_roadmap" class="text-left p-2 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-purple-500/50 transition text-xs text-purple-300 font-semibold truncate">🗺️ 90-Day Roadmap</button>
                    </div>
                </div>

                <!-- Chat Actions (Export & Delete Active Chat) -->
                <div id="sidebar-actions" class="glass-panel rounded-2xl p-3 flex flex-col gap-2">
                    <h2 class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider px-1" data-i18n="chat_actions_title">Chat Actions</h2>
                    <div class="grid grid-cols-1 gap-2">
                        <button onclick="exportMarkdown()" id="export-btn" data-i18n="export_btn" class="text-left p-2 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 text-slate-300 text-xs font-semibold transition flex items-center justify-center gap-1.5 truncate" title="Export conversation history">
                            📥 Export Active Chat
                        </button>
                        <button onclick="deleteActiveChat()" data-i18n="delete_btn" class="text-left p-2 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-rose-500/50 text-rose-300 text-xs font-semibold transition flex items-center justify-center gap-1.5 truncate" title="Delete active chat">
                            🗑️ Delete Active Chat
                        </button>
                    </div>
                </div>
            </aside>

            <!-- Chat Panel -->
            <section class="flex-1 glass-panel rounded-2xl flex flex-col overflow-hidden h-full min-h-[480px] md:min-h-0 min-w-0">
                <div id="chat-stream" class="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar text-sm">
                    <!-- Dynamic chat messages loaded here -->
                </div>

                <div id="typing-indicator" class="hidden px-4 py-1.5 flex items-center gap-2 text-xs text-slate-400">
                    <span class="w-1.5 h-1.5 bg-cyan-400 rounded-full typing-dot"></span>
                    <span class="w-1.5 h-1.5 bg-cyan-400 rounded-full typing-dot"></span>
                    <span class="w-1.5 h-1.5 bg-cyan-400 rounded-full typing-dot"></span>
                </div>

                <!-- Input Bar -->
                <div class="p-3 border-t border-slate-800/80 bg-slate-950/60 flex-shrink-0 flex flex-col gap-1.5">
                    <form id="chat-form" class="flex gap-2 items-center">
                        <textarea id="user-input" rows="1" class="flex-1 bg-slate-900 text-slate-100 text-base sm:text-sm rounded-xl px-4 py-3 border border-slate-800 focus:outline-none focus:border-cyan-500 custom-scrollbar resize-none min-h-[48px]" placeholder="Ask Boussole AI or select a playbook above..." required></textarea>
                        <button type="submit" id="send-button" data-i18n="send_btn" class="px-5 py-3 bg-cyan-600 hover:bg-cyan-500 text-white font-semibold rounded-xl text-sm h-[48px] flex-shrink-0 transition">Send</button>
                    </form>
                    <div class="text-[11px] text-slate-400 px-1 flex items-center justify-between">
                        <span data-i18n="tip_enter">💡 Tip: Press <kbd class="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-cyan-400 font-mono">Enter</kbd> to send, <kbd class="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-purple-400 font-mono">Shift + Enter</kbd> for a new line.</span>
                    </div>
                </div>
            </section>
        </div>

        <!-- VIEW 2: MULTI-JOB COMPARISON & HISTORY PAGE -->
        <div id="view-job" class="hidden flex-1 flex flex-col gap-4 overflow-y-auto custom-scrollbar p-1">
            <div class="glass-panel rounded-2xl p-6 flex flex-col gap-5 max-w-5xl mx-auto w-full">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl bg-indigo-500/20 text-indigo-300 flex items-center justify-center font-bold text-lg">🎯</div>
                    <div>
                        <h2 class="text-base font-bold text-white" data-i18n="job_view_title">Multi-Role Job Compatibility & History Dashboard</h2>
                        <p class="text-xs text-slate-400" data-i18n="job_view_subtitle">Compare up to 10 roles simultaneously (descriptions optional). Use AI job recommendations based on your CV!</p>
                    </div>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <!-- Column A: Inputs -->
                    <div class="flex flex-col gap-3 bg-slate-900 p-4 rounded-xl border border-slate-800">
                        <h3 class="text-xs font-bold text-indigo-400 uppercase tracking-wider" data-i18n="job_col1_title">1. CV & Target Roles</h3>
                        
                        <div class="flex flex-col gap-1.5">
                            <label class="text-xs font-semibold text-slate-300" data-i18n="job_upload_label">Upload CV (PDF or TXT):</label>
                            <label for="job-file-input" class="cursor-pointer flex items-center justify-center p-3 border border-dashed border-slate-700 hover:border-indigo-500/50 rounded-xl bg-slate-950 transition text-center">
                                <span id="job-upload-status" data-i18n="job_upload_status" class="text-xs text-slate-300 font-medium truncate">📎 Click to upload CV file</span>
                            </label>
                            <input id="job-file-input" type="file" accept=".pdf,.txt" class="hidden" onchange="handleJobFileUpload(event)">
                        </div>

                        <div class="flex flex-col gap-1.5">
                            <label class="text-xs font-semibold text-slate-300" data-i18n="job_paste_label">Or Paste CV Text Content:</label>
                            <textarea id="job-cv-text" rows="4" class="w-full bg-slate-950 text-slate-200 text-xs rounded-xl p-3 border border-slate-800 focus:outline-none focus:border-indigo-500 custom-scrollbar resize-none" placeholder="Paste your resume text here..."></textarea>
                        </div>

                        <!-- AI Job Recommendation Button -->
                        <button onclick="recommendJobs()" id="recommend-jobs-btn" data-i18n="job_recommend_btn" class="w-full py-2.5 bg-slate-800 hover:bg-slate-700 text-indigo-300 border border-indigo-700/50 font-semibold text-xs rounded-xl transition flex items-center justify-center gap-1.5 shadow-sm">
                            ✨ AI: Recommend Top Roles for My CV
                        </button>

                        <!-- Multiple Job Inputs List -->
                        <div class="flex flex-col gap-2">
                            <div class="flex justify-between items-center">
                                <label class="text-xs font-semibold text-slate-300" data-i18n="job_target_label">Target Jobs (Up to 10 roles):</label>
                                <button onclick="addJobInputBox()" data-i18n="job_add_role_btn" class="text-[11px] text-indigo-400 hover:text-indigo-300 font-semibold">+ Add Role</button>
                            </div>
                            <div id="job-inputs-list" class="flex flex-col gap-2">
                                <div class="job-input-item flex flex-col gap-1.5 p-2.5 rounded-lg bg-slate-950 border border-slate-800">
                                    <input type="text" placeholder="Job Title (e.g. AI Software Engineer)" data-i18n-placeholder="job_title_ph" class="job-title-input w-full bg-slate-900 text-slate-100 text-xs rounded px-2.5 py-1.5 border border-slate-800 focus:outline-none focus:border-indigo-500">
                                    <textarea rows="2" placeholder="Paste job description here (optional)..." data-i18n-placeholder="job_desc_ph" class="job-desc-input w-full bg-slate-900 text-slate-200 text-xs rounded p-2.5 border border-slate-800 focus:outline-none focus:border-indigo-500 custom-scrollbar resize-none"></textarea>
                                </div>
                            </div>
                        </div>

                        <button onclick="runJobMatch()" id="job-submit-btn" data-i18n="job_submit_btn" class="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs rounded-xl transition shadow-lg shadow-indigo-600/20">
                            Calculate Multi-Job Compatibility ⚡
                        </button>
                    </div>

                    <!-- Column B: History & Results Feed -->
                    <div class="flex flex-col gap-3 bg-slate-900 p-4 rounded-xl border border-slate-800 overflow-y-auto custom-scrollbar max-h-[600px] md:max-h-none">
                        <div class="flex justify-between items-center">
                            <h3 class="text-xs font-bold text-cyan-400 uppercase tracking-wider" data-i18n="job_history_title">2. Compatibility History Feed</h3>
                            <button onclick="clearJobHistory()" data-i18n="job_clear_btn" class="text-[10px] text-slate-400 hover:text-rose-400 transition">Clear History</button>
                        </div>
                        
                        <div id="job-placeholder-state" class="flex-1 flex flex-col items-center justify-center text-center p-6 text-slate-500 text-xs gap-2 min-h-[280px]">
                            <span class="text-3xl">📊</span>
                            <p data-i18n="job_history_empty">Awaiting CV and job input.<br>Past runs accumulate here so you can track improvements.</p>
                        </div>

                        <div id="job-history-container" class="flex flex-col gap-4">
                            <!-- Dynamic comparison batches injected here -->
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- VIEW 3: STUDENT FINANCIAL AID PORTAL (SPACIOUS & INDEPENDENTLY SCROLLABLE) -->
        <div id="view-copilot" class="hidden flex-1 grid grid-cols-1 md:grid-cols-3 gap-4 h-auto md:h-full overflow-y-auto md:overflow-hidden custom-scrollbar p-1">
            <!-- Left: Student Input & What-If Sliders with Custom Text Inputs -->
            <section class="glass-panel rounded-2xl p-5 flex flex-col gap-4 h-[460px] md:h-full overflow-y-auto custom-scrollbar flex-shrink-0">
                <h2 class="text-xs font-bold text-slate-400 uppercase tracking-wider" data-i18n="copilot_col1_title">1. Check Your Financial Aid</h2>
                <div class="grid grid-cols-2 gap-2">
                    <button onclick="loadScenario('full_grant', 10000, 4)" data-i18n="scenario_full" class="p-2.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs text-emerald-400 text-left truncate">🟢 Full Grant Profile</button>
                    <button onclick="loadScenario('partial_grant', 18000, 4)" data-i18n="scenario_partial" class="p-2.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs text-cyan-300 text-left truncate">🔵 Partial Grant Profile</button>
                    <button onclick="loadScenario('ineligible', 24000, 3)" data-i18n="scenario_high" class="p-2.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs text-rose-400 text-left truncate">🔴 High Income Profile</button>
                    <button onclick="loadScenario('missing_income', null, 2)" data-i18n="scenario_incomplete" class="p-2.5 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs text-amber-300 text-left truncate">⚠️ Incomplete Profile</button>
                </div>
                <textarea id="case-notes" rows="4" class="w-full bg-slate-900 text-slate-200 text-xs rounded-xl p-3 border border-slate-800 focus:outline-none focus:border-cyan-500 custom-scrollbar resize-none" placeholder="Paste your financial situation or notes..." data-i18n-placeholder="copilot_notes_ph"></textarea>
                
                <button onclick="processCase()" id="process-btn" data-i18n="copilot_calc_btn" class="w-full py-3 bg-gradient-to-r from-cyan-500 to-indigo-600 text-white font-semibold text-xs rounded-xl hover:opacity-90 transition">Calculate My Eligibility</button>

                <!-- What-If Simulator Panel with Custom Input Boxes -->
                <div class="pt-3 border-t border-slate-800 flex flex-col gap-3 mt-1">
                    <span class="text-[11px] font-bold text-cyan-400 uppercase tracking-wider" data-i18n="copilot_whatif_title">🎛️ Explore "What-If" Scenarios</span>
                    
                    <div class="flex flex-col gap-1.5">
                        <div class="flex justify-between items-center text-[11px] text-slate-300">
                            <span data-i18n="copilot_income_label">Family Monthly Income (HKD):</span>
                            <input id="income-input-box" type="number" min="0" max="100000" step="100" value="10000" class="w-24 bg-slate-900 text-cyan-300 font-bold text-xs rounded px-2 py-1.5 border border-slate-700 text-right focus:outline-none focus:border-cyan-500" oninput="syncFromBox('income')">
                        </div>
                        <input id="income-slider" type="range" min="0" max="50000" step="500" value="10000" class="w-full accent-cyan-500 cursor-pointer py-1" oninput="syncFromSlider('income')">
                    </div>

                    <div class="flex flex-col gap-1.5">
                        <div class="flex justify-between items-center text-[11px] text-slate-300">
                            <span data-i18n="copilot_members_label">Household Members:</span>
                            <input id="members-input-box" type="number" min="1" max="15" step="1" value="4" class="w-20 bg-slate-900 text-cyan-300 font-bold text-xs rounded px-2 py-1.5 border border-slate-700 text-right focus:outline-none focus:border-cyan-500" oninput="syncFromBox('members')">
                        </div>
                        <input id="members-slider" type="range" min="1" max="8" step="1" value="4" class="w-full accent-cyan-500 cursor-pointer py-1" oninput="syncFromSlider('members')">
                    </div>
                </div>
            </section>

            <!-- Middle: PII Privacy Shield -->
            <section class="glass-panel rounded-2xl p-5 flex flex-col gap-3 h-[420px] md:h-full overflow-y-auto custom-scrollbar flex-shrink-0">
                <h2 class="text-xs font-bold text-slate-400 uppercase tracking-wider" data-i18n="copilot_privacy_title">2. Privacy Shield (PDPO Compliant)</h2>
                <div id="pii-status" class="hidden p-3 rounded-xl bg-slate-900 border border-slate-800 text-xs flex justify-between items-center">
                    <span class="text-slate-300" data-i18n="copilot_protected_label">Protected Data:</span>
                    <span id="pii-count" class="font-bold text-cyan-400">0 Redacted</span>
                </div>
                <div id="sanitized-text" data-i18n="copilot_awaiting_input" class="flex-1 bg-slate-950 p-4 rounded-xl border border-slate-900 text-xs text-slate-400 font-mono overflow-y-auto custom-scrollbar min-h-[220px]">Awaiting input...</div>
            </section>

            <!-- Right: Results, Checklist & Standalone Hardship Appeal Card -->
            <section class="glass-panel rounded-2xl p-5 flex flex-col gap-4 h-[540px] md:h-full overflow-y-auto custom-scrollbar flex-shrink-0">
                <h2 class="text-xs font-bold text-slate-400 uppercase tracking-wider" data-i18n="copilot_result_title">3. Your Result & Action Plan</h2>
                
                <!-- Verdict Card (Box 3) -->
                <div class="bg-slate-900 p-4 rounded-xl border border-slate-800 flex flex-col gap-3">
                    <div class="flex justify-between items-center">
                        <span class="text-xs text-slate-400" data-i18n="copilot_status_label">Estimated Status:</span>
                        <span id="verdict-badge" data-i18n="copilot_awaiting_badge" class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-400">AWAITING</span>
                    </div>
                    <h3 id="verdict-title" data-i18n="copilot_no_profile" class="text-sm font-bold text-white">No active profile checked</h3>
                    <p id="verdict-details" data-i18n="copilot_calc_prompt" class="text-xs text-slate-400">Calculate your eligibility above to view details.</p>
                    
                    <div class="pt-2 border-t border-slate-800">
                        <span class="text-[10px] uppercase font-bold text-cyan-400 tracking-wider" data-i18n="copilot_policy_label">Official Policy Reference:</span>
                        <p id="verdict-citation" class="text-xs text-slate-300 font-medium italic mt-1">—</p>
                    </div>

                    <div class="pt-2 border-t border-slate-800">
                        <span class="text-[10px] uppercase font-bold text-emerald-400 tracking-wider" data-i18n="copilot_checklist_label">📋 Your Document Checklist:</span>
                        <ul id="document-checklist" class="text-xs text-slate-200 space-y-1 mt-1 pl-2">
                            <li data-i18n="copilot_checklist_awaiting">• Awaiting evaluation...</li>
                        </ul>
                    </div>
                </div>

                <!-- Student Hardship Appeal Request -->
                <div class="bg-slate-900 p-4 rounded-xl border border-slate-800 flex flex-col gap-2.5">
                    <span class="text-[10px] uppercase font-bold text-amber-400 tracking-wider" data-i18n="copilot_appeal_title">⚠️️ Request Special Hardship Review</span>
                    <p class="text-[11px] text-slate-400 leading-tight" data-i18n="copilot_appeal_desc">Facing unexpected financial hardship or medical issues? Submit an appeal for human officer review.</p>
                    <select id="override-reason" class="w-full bg-slate-950 text-slate-200 text-xs rounded-lg p-2.5 border border-slate-800 outline-none">
                        <option value="" data-i18n="copilot_appeal_default">Select your special circumstance...</option>
                        <option value="Sudden Family Medical Emergency / Hardship" data-i18n="appeal_opt1">Sudden Family Medical Emergency / Hardship</option>
                        <option value="Unexpected Loss of Family Breadwinner" data-i18n="appeal_opt2">Unexpected Loss of Family Breadwinner</option>
                        <option value="Fluctuating/Seasonal Income Discrepancy" data-i18n="appeal_opt3">Fluctuating/Seasonal Income Discrepancy</option>
                    </select>
                    <button onclick="executeOverride()" data-i18n="copilot_appeal_btn" class="py-2.5 bg-amber-600 hover:bg-amber-500 text-white font-semibold text-xs rounded-lg transition">
                        Submit Appeal for Officer Review
                    </button>
                    <div id="override-timestamp" class="text-[10px] text-slate-400 italic text-center hidden"></div>
                </div>
            </section>
        </div>

        <!-- VIEW 4: GRANT-TO-CAREER BRIDGE -->
        <div id="view-bridge" class="hidden flex-1 flex flex-col gap-4 overflow-y-auto custom-scrollbar p-1">
            <div class="glass-panel rounded-2xl p-6 flex flex-col gap-4 max-w-4xl mx-auto w-full">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl bg-purple-500/20 text-purple-300 flex items-center justify-center font-bold text-lg">🌉</div>
                    <div>
                        <h2 class="text-base font-bold text-white" data-i18n="bridge_title">Grant-to-Career Livelihood & Work-Study Bridge</h2>
                        <p class="text-xs text-slate-400" data-i18n="bridge_subtitle">Bridging financial aid shortfalls with verified campus employment and upskilling opportunities.</p>
                    </div>
                </div>

                <!-- Sliders & Custom Text Inputs for Family Income, Tuition, and Living Expenses -->
                <div class="grid grid-cols-1 md:grid-cols-3 gap-3 bg-slate-900 p-4 rounded-xl border border-slate-800">
                    <div class="flex flex-col gap-1.5">
                        <div class="flex justify-between items-center text-[11px] text-slate-300">
                            <span data-i18n="bridge_income_label">Family Monthly Income:</span>
                            <input id="bridge-income-input-box" type="number" min="0" max="100000" step="100" value="10000" class="w-24 bg-slate-950 text-cyan-300 font-bold text-xs rounded px-2 py-1 border border-slate-700 text-right focus:outline-none focus:border-purple-500" oninput="syncBridgeFromBox('income')">
                        </div>
                        <input id="bridge-income-slider" type="range" min="0" max="50000" step="500" value="10000" class="w-full accent-purple-500 cursor-pointer" oninput="syncBridgeFromSlider('income')">
                    </div>

                    <div class="flex flex-col gap-1.5">
                        <div class="flex justify-between items-center text-[11px] text-slate-300">
                            <span data-i18n="bridge_tuition_label">Tuition Fee:</span>
                            <input id="tuition-input-box" type="number" min="0" max="200000" step="500" value="42100" class="w-24 bg-slate-950 text-purple-300 font-bold text-xs rounded px-2 py-1 border border-slate-700 text-right focus:outline-none focus:border-purple-500" oninput="syncBridgeFromBox('tuition')">
                        </div>
                        <input id="tuition-slider" type="range" min="10000" max="100000" step="1000" value="42100" class="w-full accent-purple-500 cursor-pointer" oninput="syncBridgeFromSlider('tuition')">
                    </div>

                    <div class="flex flex-col gap-1.5">
                        <div class="flex justify-between items-center text-[11px] text-slate-300">
                            <span data-i18n="bridge_living_label">Living Expenses:</span>
                            <input id="living-input-box" type="number" min="0" max="200000" step="500" value="30000" class="w-24 bg-slate-950 text-emerald-300 font-bold text-xs rounded px-2 py-1 border border-slate-700 text-right focus:outline-none focus:border-purple-500" oninput="syncBridgeFromBox('living')">
                        </div>
                        <input id="living-slider" type="range" min="0" max="80000" step="1000" value="30000" class="w-full accent-purple-500 cursor-pointer" oninput="syncBridgeFromSlider('living')">
                    </div>
                </div>

                <!-- Shortfall & Loan Eligibility Panel -->
                <div class="bg-slate-900 p-4 rounded-xl border border-slate-800 flex flex-col gap-3">
                    <h3 class="text-xs font-bold text-purple-400 uppercase tracking-wider" data-i18n="bridge_shortfall_title">Your Dynamic Financial Shortfall & Loan Eligibility</h3>
                    <p class="text-xs text-slate-300"><span data-i18n="bridge_shortfall_text">Based on your FASP tier and custom expense inputs, your total financial gap is:</span> <strong id="dynamic-shortfall" class="text-cyan-400">HKD $21,050</strong>.</p>
                    
                    <div class="p-3 rounded-lg bg-slate-950 border border-slate-800 flex flex-col gap-1 text-xs">
                        <div class="flex justify-between items-center">
                            <span class="text-slate-300 font-semibold" data-i18n="bridge_loan_status_label">Government Loan Status:</span>
                            <span id="loan-status-badge" data-i18n="bridge_loan_eligible_badge" class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-400 border border-emerald-800">ELIGIBLE FOR NLSFT LOAN</span>
                        </div>
                        <p id="loan-details" class="text-slate-400 mt-1" data-i18n="bridge_loan_desc">You are eligible to borrow up to <strong class="text-cyan-300">HKD $72,100</strong> via government schemes (NLSFT / Non-Means-Tested Loan Scheme) to cover your remaining tuition and living expenses.</p>
                    </div>

                    <div class="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-400" data-i18n="bridge_tip">
                        💡 <strong>Recommended Action:</strong> Secure a flexible on-campus work-study role or tech internship to cover monthly living expenses and minimize student loan debt.
                    </div>
                </div>

                <div class="flex flex-col gap-3">
                    <h3 class="text-xs font-bold text-slate-400 uppercase tracking-wider" data-i18n="bridge_matched_jobs_title">Matched Campus Jobs & Work-Study Programs</h3>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div class="bg-slate-900 p-4 rounded-xl border border-slate-800 flex flex-col justify-between gap-3">
                            <div>
                                <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-400 border border-emerald-800" data-i18n="job_badge_flexible">Part-Time / Flexible</span>
                                <h4 class="text-sm font-bold text-white mt-2" data-i18n="bridge_job1_title">AI Lab Student Assistant (HKUST)</h4>
                                <p class="text-xs text-slate-400 mt-1" data-i18n="bridge_job1_desc">Assist researchers with Python data processing and script optimization. Flexible hours around your class schedule.</p>
                            </div>
                            <div class="flex justify-between items-center pt-2 border-t border-slate-800">
                                <span class="text-xs font-bold text-cyan-400">HKD $120 / hour</span>
                                <button onclick="alert('Application draft sent to Career Coach!')" data-i18n="bridge_apply_btn" class="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold rounded-lg transition">Apply with AI Coach</button>
                            </div>
                        </div>

                        <div class="bg-slate-900 p-4 rounded-xl border border-slate-800 flex flex-col justify-between gap-3">
                            <div>
                                <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-950 text-indigo-400 border border-indigo-800" data-i18n="job_badge_grant">Work-Study Grant</span>
                                <h4 class="text-sm font-bold text-white mt-2" data-i18n="bridge_job2_title">Student Financial Aid Student Ambassador</h4>
                                <p class="text-xs text-slate-400 mt-1" data-i18n="bridge_job2_desc">Help peers navigate campus digital forms and administrative document checklists.</p>
                            </div>
                            <div class="flex justify-between items-center pt-2 border-t border-slate-800">
                                <span class="text-xs font-bold text-cyan-400">HKD $4,500 / month</span>
                                <button onclick="alert('Application draft sent to Career Coach!')" data-i18n="bridge_apply_btn" class="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold rounded-lg transition">Apply with AI Coach</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

    </main>

    <!-- Frontend Script Logic -->
    <script>
        const translations = {
            en: {
                brand_subtitle_career: "Career Intelligence & Roadmapping",
                btn_career: "💼 Career Coach",
                btn_job: "🎯 Job Matcher",
                btn_copilot: "🏛 Financial Aid",
                btn_bridge: "🌉 Grant-to-Career",
                chat_history_title: "Chat History",
                new_chat_btn: "+ New Chat",
                upload_resume_title: "Upload Resume (PDF/TXT)",
                upload_resume_label: "📎 Click to attach resume",
                playbooks_title: "Career Playbooks",
                preset_roast: "🔥 Resume Roast",
                preset_gap: "🎯 Skill Gap Matrix",
                preset_behavioral: "🎙️ Interview Drill",
                preset_roadmap: "🗺️ 90-Day Roadmap",
                chat_actions_title: "Chat Actions",
                export_btn: "📥 Export Active Chat",
                delete_btn: "🗑️ Delete Active Chat",
                chat_placeholder: "Ask Boussole AI or select a playbook above...",
                send_btn: "Send",
                tip_enter: "💡 Tip: Press Enter to send, Shift + Enter for a new line.",
                
                // Job Matcher View
                job_view_title: "Multi-Role Job Compatibility & History Dashboard",
                job_view_subtitle: "Compare up to 10 roles simultaneously (descriptions optional). Use AI job recommendations based on your CV!",
                job_col1_title: "1. CV & Target Roles",
                job_upload_label: "Upload CV (PDF or TXT):",
                job_upload_status: "📎 Click to upload CV file",
                job_paste_label: "Or Paste CV Text Content:",
                job_recommend_btn: "✨ AI: Recommend Top Roles for My CV",
                job_target_label: "Target Jobs (Up to 10 roles):",
                job_add_role_btn: "+ Add Role",
                job_title_ph: "Job Title (e.g. AI Software Engineer)",
                job_desc_ph: "Paste job description here (optional)...",
                job_submit_btn: "Calculate Multi-Job Compatibility ⚡",
                job_history_title: "2. Compatibility History Feed",
                job_clear_btn: "Clear History",
                job_history_empty: "Awaiting CV and job input.<br>Past runs accumulate here so you can track improvements.",

                // Financial Aid Copilot View
                copilot_col1_title: "1. Check Your Financial Aid",
                scenario_full: "🟢 Full Grant Profile",
                scenario_partial: "🔵 Partial Grant Profile",
                scenario_high: "🔴 High Income Profile",
                scenario_incomplete: "⚠️ Incomplete Profile",
                copilot_notes_ph: "Paste your financial situation or notes...",
                copilot_calc_btn: "Calculate My Eligibility",
                copilot_whatif_title: "🎛️ Explore \"What-If\" Scenarios",
                copilot_income_label: "Family Monthly Income (HKD):",
                copilot_members_label: "Household Members:",
                copilot_privacy_title: "2. Privacy Shield (PDPO Compliant)",
                copilot_protected_label: "Protected Data:",
                copilot_awaiting_input: "Awaiting input...",
                copilot_result_title: "3. Your Result & Action Plan",
                copilot_status_label: "Estimated Status:",
                copilot_awaiting_badge: "AWAITING",
                copilot_no_profile: "No active profile checked",
                copilot_calc_prompt: "Calculate your eligibility above to view details.",
                copilot_policy_label: "Official Policy Reference:",
                copilot_checklist_label: "📋 Your Document Checklist:",
                copilot_checklist_awaiting: "• Awaiting evaluation...",
                copilot_appeal_title: "⚠️ Request Special Hardship Review",
                copilot_appeal_desc: "Facing unexpected financial hardship or medical issues? Submit an appeal for human officer review.",
                copilot_appeal_default: "Select your special circumstance...",
                appeal_opt1: "Sudden Family Medical Emergency / Hardship",
                appeal_opt2: "Unexpected Loss of Family Breadwinner",
                appeal_opt3: "Fluctuating/Seasonal Income Discrepancy",
                copilot_appeal_btn: "Submit Appeal for Officer Review",

                // Grant-to-Career Bridge View
                bridge_title: "Grant-to-Career Livelihood & Work-Study Bridge",
                bridge_subtitle: "Bridging financial aid shortfalls with verified campus employment and upskilling opportunities.",
                bridge_income_label: "Family Monthly Income:",
                bridge_tuition_label: "Tuition Fee:",
                bridge_living_label: "Living Expenses:",
                bridge_shortfall_title: "Your Dynamic Financial Shortfall & Loan Eligibility",
                bridge_shortfall_text: "Based on your FASP tier and custom expense inputs, your total financial gap is:",
                bridge_loan_status_label: "Government Loan Status:",
                bridge_loan_eligible_badge: "ELIGIBLE FOR NLSFT LOAN",
                bridge_loan_desc: "You are eligible to borrow up to via government schemes (NLSFT / Non-Means-Tested Loan Scheme) to cover your remaining tuition and living expenses.",
                bridge_tip: "💡 Recommended Action: Secure a flexible on-campus work-study role or tech internship to cover monthly living expenses and minimize student loan debt.",
                bridge_matched_jobs_title: "Matched Campus Jobs & Work-Study Programs",
                job_badge_flexible: "Part-Time / Flexible",
                job_badge_grant: "Work-Study Grant",
                bridge_job1_title: "AI Lab Student Assistant (HKUST)",
                bridge_job1_desc: "Assist researchers with Python data processing and script optimization. Flexible hours around your class schedule.",
                bridge_job2_title: "Student Financial Aid Student Ambassador",
                bridge_job2_desc: "Help peers navigate campus digital forms and administrative document checklists.",
                bridge_apply_btn: "Apply with AI Coach"
            },
            "zh-tw": {
                brand_subtitle_career: "職涯智能與路徑規劃",
                btn_career: "💼 職涯教練",
                btn_job: "🎯 職缺匹配",
                btn_copilot: "🏛 學生資助",
                btn_bridge: "🌉 資助與就業橋樑",
                chat_history_title: "對話紀錄",
                new_chat_btn: "+ 新對話",
                upload_resume_title: "上傳履歷 (PDF/TXT)",
                upload_resume_label: "📎 點擊附加履歷",
                playbooks_title: "職涯錦囊",
                preset_roast: "🔥 履歷健檢",
                preset_gap: "🎯 技能落差矩陣",
                preset_behavioral: "🎙️ 面試模擬",
                preset_roadmap: "🗺️ 90天職涯藍圖",
                chat_actions_title: "對話操作",
                export_btn: "📥 匯出當前對話",
                delete_btn: "🗑 刪除當前對話",
                chat_placeholder: "向 Boussole AI 提問或選擇上方錦囊...",
                send_btn: "發送",
                tip_enter: "💡 提示：按 Enter 發送，Shift + Enter 換行。",

                // Job Matcher View
                job_view_title: "多角色職缺匹配與歷史儀表板",
                job_view_subtitle: "同時比較最多 10 個職位（職缺描述選填）。利用基於您履歷的 AI 職缺推薦！",
                job_col1_title: "1. 履歷與目標職位",
                job_upload_label: "上傳履歷 (PDF 或 TXT)：",
                job_upload_status: "📎 點擊上傳履歷檔案",
                job_paste_label: "或貼上履歷文字內容：",
                job_recommend_btn: "✨ AI：推薦最適合我的職位",
                job_target_label: "目標職位 (最多 10 個)：",
                job_add_role_btn: "+ 新增職位",
                job_title_ph: "職稱 (例如：AI 軟體工程師)",
                job_desc_ph: "在此貼上職缺描述 (選填)...",
                job_submit_btn: "計算多職位匹配度 ⚡",
                job_history_title: "2. 匹配歷史與紀錄",
                job_clear_btn: "清除歷史",
                job_history_empty: "等待上傳履歷與輸入職位。<br>過去的分析記錄會累積在此以追蹤進步。",

                // Financial Aid Copilot View
                copilot_col1_title: "1. 查詢學生資助資格",
                scenario_full: "🟢 全額資助檔案",
                scenario_partial: "🔵 半額資助檔案",
                scenario_high: "🔴 高收入檔案",
                scenario_incomplete: "⚠️ 資料不全檔案",
                copilot_notes_ph: "貼上您的財務狀況或筆記...",
                copilot_calc_btn: "計算我的資助資格",
                copilot_whatif_title: "🎛️ 探索「假設情境」",
                copilot_income_label: "家庭每月總收入 (港幣)：",
                copilot_members_label: "同住家庭成員人數：",
                copilot_privacy_title: "2. 隱私防護罩 (符合個人資料私隱條例)",
                copilot_protected_label: "已保護資料：",
                copilot_awaiting_input: "等待輸入...",
                copilot_result_title: "3. 審查結果與行動方案",
                copilot_status_label: "預估狀態：",
                copilot_awaiting_badge: "等待中",
                copilot_no_profile: "尚未檢測有效檔案",
                copilot_calc_prompt: "請於上方計算您的資格以查看詳細資訊。",
                copilot_policy_label: "官方政策參照：",
                copilot_checklist_label: "📋 所需文件清單：",
                copilot_checklist_awaiting: "• 等待評估...",
                copilot_appeal_title: "⚠️ 申請特殊經濟困難覆核",
                copilot_appeal_desc: "面臨突發經濟困難或醫療問題？可提交申請由專人人工審查。",
                copilot_appeal_default: "選擇您的特殊情況...",
                appeal_opt1: "突發家庭醫療緊急情況 / 經濟困難",
                appeal_opt2: "家庭經濟支柱突然喪失",
                appeal_opt3: "收入波動 / 季節性收入落差",
                copilot_appeal_btn: "提交專人覆核申請",

                // Grant-to-Career Bridge View
                bridge_title: "資助與就業橋樑 (工作學習計畫)",
                bridge_subtitle: "以校內工讀與職能培訓彌補學生資助缺口。",
                bridge_income_label: "家庭每月收入：",
                bridge_tuition_label: "學費金額：",
                bridge_living_label: "生活費預算：",
                bridge_shortfall_title: "您的動態財務缺口與貸款資格",
                bridge_shortfall_text: "根據您的資助級距與自訂開支，您的總財務缺口為：",
                bridge_loan_status_label: "政府貸款狀態：",
                bridge_loan_eligible_badge: "符合免入息審查貸款資格",
                bridge_loan_desc: "您符合透過政府非免入息審查貸款計畫 (NLSFT) 借款的資格，以涵蓋剩餘學費與生活開支。",
                bridge_tip: "💡 建議行動：爭取校內彈性工讀或科技實習，以支應每月生活開支並減少學生貸款負債。",
                bridge_matched_jobs_title: "配對之校內工讀與工作學習計畫",
                job_badge_flexible: "兼職 / 彈性工時",
                job_badge_grant: "工讀資助計畫",
                bridge_job1_title: "AI 實驗室學生助理 (港科大)",
                bridge_job1_desc: "協助研究人員進行 Python 資料處理與腳本優化。可配合您的課表彈性排班。",
                bridge_job2_title: "學生資助處學生大使",
                bridge_job2_desc: "協助同儕熟悉校內數位表格與行政文件檢核表。",
                bridge_apply_btn: "透過 AI 教練應徵"
            },
            "zh-cn": {
                brand_subtitle_career: "职涯智能与路径规划",
                btn_career: "💼 职涯教练",
                btn_job: "🎯 职位匹配",
                btn_copilot: "🏛 学生资助",
                btn_bridge: "🌉 资助与就业桥梁",
                chat_history_title: "对话记录",
                new_chat_btn: "+ 新对话",
                upload_resume_title: "上传简历 (PDF/TXT)",
                upload_resume_label: "📎 点击附加简历",
                playbooks_title: "职涯锦囊",
                preset_roast: "🔥 简历健检",
                preset_gap: "🎯 技能落差矩阵",
                preset_behavioral: "🎙️ 面试模拟",
                preset_roadmap: "🗺 90天职涯蓝图",
                chat_actions_title: "对话操作",
                export_btn: "📥 导出当前对话",
                delete_btn: "🗑️ 删除当前对话",
                chat_placeholder: "向 Boussole AI 提问或选择上方锦囊...",
                send_btn: "发送",
                tip_enter: "💡 提示：按 Enter 发送，Shift + Enter 换行。",

                // Job Matcher View
                job_view_title: "多角色职位匹配与历史仪表板",
                job_view_subtitle: "同时比较最多 10 个职位（职位描述选填）。利用基于您简历的 AI 职位推荐！",
                job_col1_title: "1. 简历与目标职位",
                job_upload_label: "上传简历 (PDF 或 TXT)：",
                job_upload_status: "📎 点击上传简历文件",
                job_paste_label: "或粘贴简历文字内容：",
                job_recommend_btn: "✨ AI：推荐最适合我的职位",
                job_target_label: "目标职位 (最多 10 个)：",
                job_add_role_btn: "+ 新增职位",
                job_title_ph: "职称 (例如：AI 软件工程师)",
                job_desc_ph: "在此粘贴职位描述 (选填)...",
                job_submit_btn: "计算多职位匹配度 ⚡",
                job_history_title: "2. 匹配历史与记录",
                job_clear_btn: "清除历史",
                job_history_empty: "等待上传简历与输入职位。<br>过去的分析记录会累积在此以追踪进步。",

                // Financial Aid Copilot View
                copilot_col1_title: "1. 查询学生资助资格",
                scenario_full: "🟢 全额资助档案",
                scenario_partial: "🔵 半额资助档案",
                scenario_high: "🔴 高收入档案",
                scenario_incomplete: "⚠️ 资料不全档案",
                copilot_notes_ph: "粘贴您的财务状况或笔记...",
                copilot_calc_btn: "计算我的资助资格",
                copilot_whatif_title: "🎛️ 探索“假设情境”",
                copilot_income_label: "家庭每月总收入 (港币)：",
                copilot_members_label: "同住家庭成员人数：",
                copilot_privacy_title: "2. 隐私防护罩 (符合个人资料隐私条例)",
                copilot_protected_label: "已保护数据：",
                copilot_awaiting_input: "等待输入...",
                copilot_result_title: "3. 审查结果与行动方案",
                copilot_status_label: "预估状态：",
                copilot_awaiting_badge: "等待中",
                copilot_no_profile: "尚未检测有效档案",
                copilot_calc_prompt: "请于上方计算您的资格以查看详细信息。",
                copilot_policy_label: "官方政策参照：",
                copilot_checklist_label: "📋 所需文件清单：",
                copilot_checklist_awaiting: "• 等待评估...",
                copilot_appeal_title: "⚠️ 申请特殊经济困难复核",
                copilot_appeal_desc: "面临突发经济困难或医疗问题？可提交申请由专人人工审查。",
                copilot_appeal_default: "选择您的特殊情况...",
                appeal_opt1: "Sudden Family Medical Emergency / Hardship",
                appeal_opt2: "Unexpected Loss of Family Breadwinner",
                appeal_opt3: "Fluctuating/Seasonal Income Discrepancy",
                copilot_appeal_btn: "提交专人复核申请",

                // Grant-to-Career Bridge View
                bridge_title: "资助与就业桥梁 (工作学习计划)",
                bridge_subtitle: "以校内工读与职能培训弥补学生资助缺口。",
                bridge_income_label: "家庭每月收入：",
                bridge_tuition_label: "学费金额：",
                bridge_living_label: "生活费预算：",
                bridge_shortfall_title: "您的动态财务缺口与贷款资格",
                bridge_shortfall_text: "根据您的资助级距与自订开支，您的总财务缺口为：",
                bridge_loan_status_label: "政府贷款状态：",
                bridge_loan_eligible_badge: "符合免入息审查贷款资格",
                bridge_loan_desc: "您符合通过政府非免入息审查贷款计划 (NLSFT) 借款的资格，以涵盖剩余学费与生活开支。",
                bridge_tip: "💡 建议行动：争取校内弹性工读或科技实习，以支应每月生活开支并减少学生贷款负债。",
                bridge_matched_jobs_title: "配对之校内工读与工作学习计划",
                job_badge_flexible: "兼职 / 弹性工时",
                job_badge_grant: "工读资助计划",
                bridge_job1_title: "AI 实验室学生助理 (港科大)",
                bridge_job1_desc: "协助研究人员进行 Python 数据处理与脚本优化。可配合您的课表弹性排班。",
                bridge_job2_title: "学生资助处学生大使",
                bridge_job2_desc: "协助同侪熟悉校内数字表格与行政文件检核表。",
                bridge_apply_btn: "透過 AI 教練應聘"
            }
        };

        let currentLang = 'en';

        function changeLanguage(lang) {
            currentLang = lang;
            localStorage.setItem('boussole_lang', lang);
            const t = translations[currentLang] || translations.en;

            document.querySelectorAll('[data-i18n]').forEach(el => {
                const key = el.getAttribute('data-i18n');
                if (t[key]) {
                    el.innerHTML = t[key];
                }
            });

            document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
                const key = el.getAttribute('data-i18n-placeholder');
                if (t[key]) {
                    el.placeholder = t[key];
                }
            });

            const userInput = document.getElementById('user-input');
            if (userInput && t.chat_placeholder) {
                userInput.placeholder = t.chat_placeholder;
            }

            const caseNotes = document.getElementById('case-notes');
            if (caseNotes && t.copilot_notes_ph) {
                caseNotes.placeholder = t.copilot_notes_ph;
            }

            const jobCvText = document.getElementById('job-cv-text');
            if (jobCvText) {
                const cvPlaceholderMap = {
                    en: "Paste your resume text here...",
                    "zh-tw": "在此貼上您的履歷文字...",
                    "zh-cn": "在此粘贴您的简历文字..."
                };
                jobCvText.placeholder = cvPlaceholderMap[currentLang] || cvPlaceholderMap.en;
            }
        }

        let currentMode = 'career';
        let currentExtractedData = { income: 10000, members: 4, grantPercentage: 0.5, loanEligible: true, loanScheme: "NLSFT (Non-Means-Tested Loan Scheme)" };
        let activeChatId = null;
        let uploadedResumeText = "";
        let pendingChatIds = new Set(); // Tracks active AI generation per chat ID

        async function initApp() {
            // Instantly lock on page reload / refresh (F5) on the very first reload
            const navEntries = performance.getEntriesByType("navigation");
            if (navEntries.length > 0 && navEntries[0].type === 'reload') {
                window.location.replace('/api/logout');
                return;
            }

            const savedLang = localStorage.getItem('boussole_lang') || 'en';
            currentLang = savedLang;
            const langSelect = document.getElementById('lang-select');
            if (langSelect) langSelect.value = savedLang;
            
            changeLanguage(savedLang);
            await loadChats();
        }

        function updateTypingIndicator() {
            const typingIndicator = document.getElementById('typing-indicator');
            if (pendingChatIds.has(activeChatId)) {
                typingIndicator.classList.remove('hidden');
            } else {
                typingIndicator.classList.add('hidden');
            }
        }

        async function loadChats() {
            try {
                const res = await fetch('/api/chats');
                const data = await res.json();
                activeChatId = data.active_id;
                renderChatHistoryList(data.chats, data.active_id);
                renderMessages(data.messages);
                updateTypingIndicator();
            } catch (err) {
                console.error("Failed to load chats", err);
            }
        }

        function renderChatHistoryList(chats, activeId) {
            const listEl = document.getElementById('chat-history-list');
            listEl.innerHTML = '';
            chats.forEach(chat => {
                const isActive = chat.id === activeId;
                const div = document.createElement('div');
                div.className = `p-2 rounded-xl text-xs cursor-pointer transition truncate flex-shrink-0 ${isActive ? 'bg-cyan-600/25 border border-cyan-500/40 text-white font-semibold' : 'bg-slate-900/60 border border-slate-800 text-slate-300 hover:bg-slate-800/80'}`;
                div.innerHTML = `<span class="truncate block pointer-events-none">${chat.title}</span>`;
                div.onclick = () => switchChat(chat.id);
                listEl.appendChild(div);
            });
        }

        async function createNewChat() {
            window.speechSynthesis.cancel();
            const res = await fetch('/api/chats/new', { method: 'POST' });
            await loadChats();
        }

        async function switchChat(chatId) {
            window.speechSynthesis.cancel();
            const res = await fetch('/api/chats/switch', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ chat_id: chatId })
            });
            const data = await res.json();
            if (data.status === 'switched') {
                activeChatId = data.active_id;
                await loadChats();
            }
        }

        async function deleteActiveChat() {
            if (!confirm("Are you sure you want to delete this active chat conversation?")) return;
            window.speechSynthesis.cancel();
            const res = await fetch('/api/chats/active', { method: 'DELETE' });
            const data = await res.json();
            activeChatId = data.active_id;
            renderChatHistoryList(data.chats, data.active_id);
            renderMessages(data.messages);
            updateTypingIndicator();
        }

        function renderMessages(messages) {
            const chatStream = document.getElementById('chat-stream');
            chatStream.innerHTML = '';
            
            if (!messages || messages.length === 0) {
                return;
            }

            messages.forEach(msg => {
                if (msg.role === 'user') {
                    chatStream.innerHTML += `
                        <div class="flex items-start justify-end gap-3 w-full">
                            <div class="bg-cyan-600/90 rounded-2xl p-3.5 text-white max-w-[85%] break-words overflow-hidden">${msg.content}</div>
                        </div>`;
                } else if (msg.role === 'assistant') {
                    const rawReplyForCopy = msg.content.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"').replace(/\n/g, '\\n');
                    const cleanReplyForSpeech = stripMarkdownForSpeech(msg.content).replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"').replace(/\n/g, '\\n');
                    chatStream.innerHTML += `
                        <div class="flex items-start gap-3 w-full">
                            <div class="w-8 h-8 rounded-lg bg-cyan-500/20 text-cyan-300 flex items-center justify-center font-bold flex-shrink-0">B</div>
                            <div class="bg-slate-900/90 border border-slate-800 rounded-2xl p-3.5 text-slate-200 max-w-[85%] flex flex-col gap-2 overflow-hidden">
                                <div class="ai-markdown-body">${marked.parse(msg.content)}</div>
                                <div class="flex items-center gap-3 pt-2 border-t border-slate-800/80 text-[11px]">
                                    <button onclick="copyToClipboard(this, '${rawReplyForCopy}')" class="text-slate-400 hover:text-slate-200 flex items-center gap-1 font-medium transition">📋 Copy</button>
                                    <button data-speak-btn onclick="speakText(this, '${cleanReplyForSpeech}')" class="text-slate-400 hover:text-slate-200 flex items-center gap-1 font-medium transition">🔊 Speak</button>
                                </div>
                            </div>
                        </div>`;
                }
            });
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
            const sidebarActions = document.getElementById('sidebar-actions');

            const btnCareer = document.getElementById('btn-career');
            const btnJob = document.getElementById('btn-job');
            const btnCopilot = document.getElementById('btn-copilot');
            const btnBridge = document.getElementById('btn-bridge');

            if (btnCareer) btnCareer.className = "text-xs font-semibold px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition shadow-sm";
            if (btnJob) btnJob.className = "text-xs font-semibold px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-indigo-300 border border-slate-700 transition shadow-sm";
            if (btnCopilot) btnCopilot.className = "text-xs font-semibold px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition shadow-sm";
            if (btnBridge) btnBridge.className = "text-xs font-semibold px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-purple-300 border border-slate-700 transition shadow-sm";

            careerView.classList.add('hidden');
            jobView.classList.add('hidden');
            copilotView.classList.add('hidden');
            bridgeView.classList.add('hidden');

            if (mode === 'career') {
                careerView.classList.remove('hidden');
                if (btnCareer) btnCareer.className = "text-xs font-semibold px-3 py-2 rounded-xl bg-cyan-600 text-white transition shadow-sm";
                if (sidebarActions) sidebarActions.classList.remove('hidden');
            } else if (mode === 'job') {
                jobView.classList.remove('hidden');
                if (btnJob) btnJob.className = "text-xs font-semibold px-3 py-2 rounded-xl bg-indigo-600 text-white transition shadow-sm";
                if (sidebarActions) sidebarActions.classList.add('hidden');
            } else if (mode === 'copilot') {
                copilotView.classList.remove('hidden');
                if (btnCopilot) btnCopilot.className = "text-xs font-semibold px-3 py-2 rounded-xl bg-cyan-600 text-white transition shadow-sm";
                if (sidebarActions) sidebarActions.classList.add('hidden');
            } else if (mode === 'bridge') {
                bridgeView.classList.remove('hidden');
                if (btnBridge) btnBridge.className = "text-xs font-semibold px-3 py-2 rounded-xl bg-purple-600 text-white transition shadow-sm";
                if (sidebarActions) sidebarActions.classList.add('hidden');
            }
        }

        async function handleJobFileUpload(e) {
            const file = e.target.files[0];
            if (!file) return;
            document.getElementById('job-upload-status').innerText = `✅ ${file.name}`;
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
            if (list.children.length >= 10) {
                return alert("You can compare up to 10 roles simultaneously.");
            }
            const t = translations[currentLang] || translations.en;
            const div = document.createElement('div');
            div.className = "job-input-item flex flex-col gap-1.5 p-2.5 rounded-lg bg-slate-950 border border-slate-800";
            div.innerHTML = `
                <div class="flex justify-between items-center">
                    <input type="text" placeholder="${t.job_title_ph}" class="job-title-input w-full bg-slate-900 text-slate-100 text-xs rounded px-2.5 py-1.5 border border-slate-800 focus:outline-none focus:border-indigo-500">
                    <button onclick="this.parentElement.parentElement.remove()" class="text-rose-400 hover:text-rose-300 text-xs px-2 font-bold" title="Remove role">✕</button>
                </div>
                <textarea rows="2" placeholder="${t.job_desc_ph}" class="job-desc-input w-full bg-slate-900 text-slate-200 text-xs rounded p-2.5 border border-slate-800 focus:outline-none focus:border-indigo-500 custom-scrollbar resize-none"></textarea>
            `;
            list.appendChild(div);
        }

        async function recommendJobs() {
            const cvText = document.getElementById('job-cv-text').value.trim();
            if (!cvText) {
                return alert("Please upload or paste your CV text first so Boussole AI can analyze your background.");
            }

            const btn = document.getElementById('recommend-jobs-btn');
            btn.disabled = true;
            btn.innerText = "✨ Analyzing CV & Recommending Roles...";

            try {
                const res = await fetch('/api/recommend_jobs', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ cv_text: cvText })
                });
                const data = await res.json();

                if (data.recommended_jobs && data.recommended_jobs.length > 0) {
                    const list = document.getElementById('job-inputs-list');
                    list.innerHTML = '';
                    data.recommended_jobs.forEach(job => {
                        const div = document.createElement('div');
                        div.className = "job-input-item flex flex-col gap-1.5 p-2.5 rounded-lg bg-slate-950 border border-slate-800";
                        div.innerHTML = `
                            <div class="flex justify-between items-center">
                                <input type="text" value="${job.job_title}" placeholder="Job Title" class="job-title-input w-full bg-slate-900 text-slate-100 text-xs rounded px-2.5 py-1.5 border border-slate-800 focus:outline-none focus:border-indigo-500">
                                <button onclick="this.parentElement.parentElement.remove()" class="text-rose-400 hover:text-rose-300 text-xs px-2 font-bold" title="Remove role">✕</button>
                            </div>
                            <textarea rows="2" class="job-desc-input w-full bg-slate-900 text-slate-200 text-xs rounded p-2.5 border border-slate-800 focus:outline-none focus:border-indigo-500 custom-scrollbar resize-none">${job.job_description}</textarea>
                        `;
                        list.appendChild(div);
                    });
                    runJobMatch();
                }
            } catch (err) {
                alert("Error recommending jobs. Please try again.");
                console.error(err);
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

        function toggleDropdown(headerEl) {
            const content = headerEl.nextElementSibling;
            const arrow = headerEl.querySelector('.dropdown-arrow');
            if (content.classList.contains('hidden')) {
                content.classList.remove('hidden');
                if (arrow) arrow.style.transform = 'rotate(180deg)';
            } else {
                content.classList.add('hidden');
                if (arrow) arrow.style.transform = 'rotate(0deg)';
            }
        }

        async function runJobMatch() {
            const cvText = document.getElementById('job-cv-text').value.trim();
            const items = document.querySelectorAll('.job-input-item');
            
            let jobEntries = [];
            items.forEach(item => {
                const title = item.querySelector('.job-title-input').value.trim();
                const desc = item.querySelector('.job-desc-input').value.trim();
                if (title) {
                    jobEntries.push({ 
                        title: title, 
                        desc: desc || "No specific job description provided. Evaluate based on standard industry expectations for this job title." 
                    });
                }
            });

            if (!cvText || jobEntries.length === 0) {
                return alert("Please provide your CV text (or upload a file) and at least one job title.");
            }

            const btn = document.getElementById('job-submit-btn');
            btn.disabled = true;
            btn.innerText = "Analyzing Multiple Roles...";

            try {
                const res = await fetch('/api/job_match', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ cv_text: cvText, jobs: jobEntries })
                });
                const data = await res.json();
                
                document.getElementById('job-placeholder-state').classList.add('hidden');
                const historyContainer = document.getElementById('job-history-container');

                const batchDiv = document.createElement('div');
                batchDiv.className = "flex flex-col gap-3 p-3.5 rounded-xl bg-slate-950 border border-slate-800 shadow-sm";
                
                const timestamp = new Date().toLocaleTimeString();
                let htmlContent = `<div class="flex justify-between items-center text-[11px] text-slate-400 border-b border-slate-800 pb-2">
                    <span>⚡ Analysis Batch (${jobEntries.length} roles compared)</span>
                    <span class="font-mono">${timestamp}</span>
                </div><div class="flex flex-col gap-2.5">`;

                if (data.results && Array.isArray(data.results)) {
                    data.results.forEach((result, idx) => {
                        const score = result.score || 0;
                        const badgeColor = score >= 75 ? "emerald" : score >= 50 ? "cyan" : "rose";
                        const roleTitle = result.job_title || jobEntries[idx]?.title || `Role ${idx+1}`;
                        
                        let matchedHtml = result.matched_keywords?.length ? result.matched_keywords.map(kw => `<span class="px-2 py-0.5 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-800 text-[10px] font-mono">${kw}</span>`).join('') : '<span class="text-xs text-slate-500 italic">None</span>';
                        
                        let missingHtml = result.missing_keywords?.length ? result.missing_keywords.map(kw => `<span class="px-2 py-0.5 rounded bg-rose-950/80 text-rose-300 border border-rose-800 text-[10px] font-mono">${kw}</span>`).join('') : '<span class="text-xs text-slate-500 italic">None</span>';

                        let recsHtml = result.recommendations?.length ? result.recommendations.map(r => `<li>${r}</li>`).join('') : '<li>No recommendations.</li>';

                        htmlContent += `
                            <div class="rounded-lg bg-slate-900 border border-slate-800 overflow-hidden">
                                <div onclick="toggleDropdown(this)" class="cursor-pointer p-3 flex items-center justify-between hover:bg-slate-850 transition">
                                    <div class="flex items-center gap-3">
                                        <div class="w-10 h-10 rounded-xl bg-${badgeColor}-600/20 text-${badgeColor}-400 border border-${badgeColor}-500/40 flex items-center justify-center font-bold text-sm flex-shrink-0">
                                            ${score}%
                                        </div>
                                        <div>
                                            <h4 class="text-xs font-bold text-white">${roleTitle}</h4>
                                            <p class="text-[11px] text-slate-400 truncate max-w-[220px] sm:max-w-md">${result.match_summary || 'Click to view in-depth analysis'}</p>
                                        </div>
                                    </div>
                                    <div class="flex items-center gap-2">
                                        <span class="text-[10px] px-2 py-1 rounded bg-slate-800 text-slate-300 font-semibold flex items-center gap-1">
                                            Details <span class="dropdown-arrow transition-transform inline-block">▼</span>
                                        </span>
                                    </div>
                                </div>
                                <div class="hidden p-3 pt-0 border-t border-slate-800/80 flex flex-col gap-2.5 text-xs bg-slate-950/60 mt-2">
                                    <div class="pt-2">
                                        <span class="text-[10px] font-bold text-slate-400 uppercase">Match Summary</span>
                                        <p class="text-slate-300 mt-0.5">${result.match_summary}</p>
                                    </div>
                                    <div>
                                        <span class="text-[10px] font-bold text-emerald-400 uppercase">✓ Matched Keywords</span>
                                        <div class="flex flex-wrap gap-1 mt-1">${matchedHtml}</div>
                                    </div>
                                    <div>
                                        <span class="text-[10px] font-bold text-rose-400 uppercase">⚠️ Missing Keywords / Gaps</span>
                                        <div class="flex flex-wrap gap-1 mt-1">${missingHtml}</div>
                                    </div>
                                    <div>
                                        <span class="text-[10px] font-bold text-cyan-400 uppercase">💡 Actionable Optimization Steps</span>
                                        <ul class="list-disc pl-4 space-y-1 text-slate-200 mt-1">${recsHtml}</ul>
                                    </div>
                                </div>
                            </div>
                        `;
                    });
                }

                htmlContent += `</div>`;
                batchDiv.innerHTML = htmlContent;
                historyContainer.prepend(batchDiv);

            } catch (err) {
                alert("Error running multi-job analysis.");
                console.error(err);
            } finally {
                btn.disabled = false;
                const t = translations[currentLang] || translations.en;
                btn.innerText = t.job_submit_btn;
            }
        }

        function exportMarkdown() {
            const chatStream = document.getElementById('chat-stream');
            const messages = [];
            chatStream.querySelectorAll('.flex').forEach(el => {
                messages.push(el.innerText);
            });
            if (messages.length === 0) {
                return alert("No active conversation to export yet.");
            }
            const blob = new Blob([messages.join("\n\n---\n\n")], { type: 'text/markdown' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = 'boussole-career-roadmap.md';
            a.click();
        }

        function copyToClipboard(buttonElement, textToCopy) {
            navigator.clipboard.writeText(textToCopy).then(() => {
                const originalText = buttonElement.innerHTML;
                buttonElement.innerHTML = '✅ Copied!';
                setTimeout(() => {
                    buttonElement.innerHTML = originalText;
                }, 2000);
            }).catch(err => {
                console.error('Failed to copy text: ', err);
            });
        }

        function stripMarkdownForSpeech(text) {
            return text
                .replace(/```[\s\S]*?```/g, 'code block omitted')
                .replace(/`([^`]+)`/g, '$1')
                .replace(/#{1,6}\s+/g, '')
                .replace(/\*\*([^*]+)\*\*/g, '$1')
                .replace(/\*([^*]+)\*/g, '$1')
                .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1')
                .replace(/>\s+/g, '');
        }

        function speakText(buttonElement, textToSpeak) {
            if (!('speechSynthesis' in window)) {
                alert("Text-to-speech is not supported in your browser.");
                return;
            }

            window.speechSynthesis.cancel();

            if (buttonElement.dataset.speaking === 'true') {
                buttonElement.dataset.speaking = 'false';
                buttonElement.innerHTML = '🔊 Speak';
                return;
            }

            document.querySelectorAll('[data-speak-btn]').forEach(btn => {
                btn.dataset.speaking = 'false';
                btn.innerHTML = '🔊 Speak';
            });

            const utterance = new SpeechSynthesisUtterance(textToSpeak);
            utterance.rate = 1.0;
            utterance.pitch = 1.0;

            utterance.onstart = () => {
                buttonElement.dataset.speaking = 'true';
                buttonElement.innerHTML = '⏹ Stop';
            };

            utterance.onend = () => {
                buttonElement.dataset.speaking = 'false';
                buttonElement.innerHTML = '🔊 Speak';
            };

            utterance.onerror = () => {
                buttonElement.dataset.speaking = 'false';
                buttonElement.innerHTML = '🔊 Speak';
            };

            window.speechSynthesis.speak(utterance);
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
                if (uploadedResumeText) {
                    promptText = `Please perform a rigorous Resume Roast on my uploaded resume using the Google X-Y-Z formula ("Accomplished [X], as measured by [Y], by doing [Z]"): \n\n${uploadedResumeText}`;
                } else {
                    promptText = "Please perform a Resume Roast. (Tip: You can also upload your PDF resume using the sidebar attachment button!). Here are my general experience bullets to review:";
                }
            } else if (type === 'gap') {
                promptText = "Analyze my current skill set (Python, AI/ML, Flask, math) and identify skill gaps and high-priority learning milestones for an AI Software Engineering internship.";
            } else if (type === 'behavioral') {
                promptText = "Conduct a mock behavioral interview with me. Ask me 3 challenging technical/behavioral interview questions one by one, starting with the first question.";
            } else if (type === 'roadmap') {
                promptText = "Generate a structured 90-day execution roadmap for an undergraduate AI student aiming to land a tech internship.";
            }
            
            userInput.value = promptText;
            userInput.focus();
        }

        async function handleFileUpload(e) {
            const file = e.target.files[0];
            if (!file) return;
            document.getElementById('upload-status-text').innerText = `✅ ${file.name}`;
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

        chatForm.onsubmit = async (e) => {
            e.preventDefault();
            let text = userInput.value.trim();
            if (!text) return;

            if (uploadedResumeText && !text.includes(uploadedResumeText)) {
                text = `Here is my resume context:\n${uploadedResumeText}\n\nUser Request: ${text}`;
            }

            userInput.value = '';
            const sendingChatId = activeChatId;

            pendingChatIds.add(sendingChatId);

            if (activeChatId === sendingChatId) {
                chatStream.innerHTML += `
                    <div class="flex items-start justify-end gap-3 w-full">
                        <div class="bg-cyan-600/90 rounded-2xl p-3.5 text-white max-w-[85%] break-words overflow-hidden">${text}</div>
                    </div>`;
                chatStream.scrollTop = chatStream.scrollHeight;
                updateTypingIndicator();
            }

            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ message: text, chat_id: sendingChatId })
                });
                const data = await response.json();

                pendingChatIds.delete(sendingChatId);

                if (activeChatId === sendingChatId) {
                    updateTypingIndicator();
                    if (data.reply) {
                        await loadChats();
                    }
                } else {
                    const resChats = await fetch('/api/chats');
                    const chatListData = await resChats.json();
                    renderChatHistoryList(chatListData.chats, activeChatId);
                }
            } catch (err) {
                pendingChatIds.delete(sendingChatId);
                if (activeChatId === sendingChatId) {
                    updateTypingIndicator();
                }
                console.error("Network error connecting to AI backend.", err);
            }
        };

        const scenarios = {
            full_grant: "Student: Chan Tai Man (HKID: A123456(7), Phone: 91234567).\nApplied for FASP.\nFamily size: 4 members.\nFamily monthly income: HKD $10,000.",
            partial_grant: "Student: Wong Ka Ho (HKID: B234567(8), Phone: 61234567).\nApplied for FASP.\nFamily size: 4 members.\nFamily monthly income: HKD $18,000.",
            ineligible: "Student: Lee Ming (HKID: C345678(9), Phone: 51234567).\nApplied for FASP.\nFamily size: 3 members.\nFamily monthly income: HKD $24,000.",
            missing_income: "Student: Cheung Wai (HKID: D456789(0), Phone: 98765432).\nRequesting urgent emergency support due to sudden family hardship.\nFamily monthly income: Not provided yet."
        };

        function loadScenario(type, income, members) {
            document.getElementById('case-notes').value = scenarios[type];
            if (income !== null) {
                setAllValues('income', income);
                currentExtractedData.income = income;
            }
            if (members !== null) {
                setAllValues('members', members);
                currentExtractedData.members = members;
            }
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
            let val = 0;
            if (type === 'income') {
                val = parseInt(document.getElementById('income-slider').value);
                setAllValues('income', val);
                currentExtractedData.income = val;
            } else if (type === 'members') {
                val = parseInt(document.getElementById('members-slider').value);
                setAllValues('members', val);
                currentExtractedData.members = val;
            }
            triggerBackendRecalc();
        }

        async function syncFromBox(type) {
            let val = 0;
            if (type === 'income') {
                val = parseInt(document.getElementById('income-input-box').value) || 0;
                setAllValues('income', val);
                currentExtractedData.income = val;
            } else if (type === 'members') {
                val = parseInt(document.getElementById('members-input-box').value) || 1;
                setAllValues('members', val);
                currentExtractedData.members = val;
            }
            triggerBackendRecalc();
        }

        async function syncBridgeFromSlider(type) {
            let val = 0;
            if (type === 'income') {
                val = parseInt(document.getElementById('bridge-income-slider').value);
                setAllValues('income', val);
                currentExtractedData.income = val;
            } else if (type === 'tuition') {
                val = parseInt(document.getElementById('tuition-slider').value);
                setAllValues('tuition', val);
            } else if (type === 'living') {
                val = parseInt(document.getElementById('living-slider').value);
                setAllValues('living', val);
            }
            triggerBackendRecalc();
        }

        async function syncBridgeFromBox(type) {
            let val = 0;
            if (type === 'income') {
                val = parseInt(document.getElementById('bridge-income-input-box').value) || 0;
                setAllValues('income', val);
                currentExtractedData.income = val;
            } else if (type === 'tuition') {
                val = parseInt(document.getElementById('tuition-input-box').value) || 0;
                setAllValues('tuition', val);
            } else if (type === 'living') {
                val = parseInt(document.getElementById('living-input-box').value) || 0;
                setAllValues('living', val);
            }
            triggerBackendRecalc();
        }

        async function triggerBackendRecalc() {
            const income = currentExtractedData.income;
            const members = currentExtractedData.members;

            const res = await fetch('/api/evaluate_case', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ notes: `Simulated Family Income: HKD $${income}, Members: ${members}` })
            });
            const data = await res.json();
            currentExtractedData.grantPercentage = data.audit.grant_percentage;
            currentExtractedData.loanEligible = data.audit.loan_eligible;
            currentExtractedData.loanScheme = data.audit.loan_scheme;
            updateAuditUI(data.audit);
        }

        async function processCase() {
            const rawNotes = document.getElementById('case-notes').value.trim();
            if (!rawNotes) return alert("Please enter your financial details first.");

            try {
                const res = await fetch('/api/evaluate_case', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ notes: rawNotes })
                });
                const data = await res.json();
                
                document.getElementById('pii-status').classList.remove('hidden');
                document.getElementById('pii-count').innerText = `${data.pii_redacted_count} Protected`;
                document.getElementById('sanitized-text').innerText = data.sanitized_notes;

                if (data.extracted_params.monthly_household_income_hkd !== null) {
                    const inc = data.extracted_params.monthly_household_income_hkd;
                    setAllValues('income', inc);
                    currentExtractedData.income = inc;
                }
                if (data.extracted_params.household_members_count) {
                    const mem = data.extracted_params.household_members_count;
                    setAllValues('members', mem);
                    currentExtractedData.members = mem;
                }

                currentExtractedData.grantPercentage = data.audit.grant_percentage;
                currentExtractedData.loanEligible = data.audit.loan_eligible;
                currentExtractedData.loanScheme = data.audit.loan_scheme;
                updateAuditUI(data.audit);
            } catch (err) {
                alert("Error calculating eligibility.");
            }
        }

        function updateAuditUI(audit) {
            const badge = document.getElementById('verdict-badge');
            badge.innerText = audit.status;
            badge.className = `px-2 py-0.5 rounded text-[10px] font-bold bg-${audit.badge_color}-950 text-${audit.badge_color}-400 border border-${audit.badge_color}-800`;

            document.getElementById('verdict-title').innerText = audit.summary;
            document.getElementById('verdict-details').innerText = audit.details;
            document.getElementById('verdict-citation').innerText = audit.policy_citation;

            const tuition = parseInt(document.getElementById('tuition-input-box').value) || 42100;
            const living = parseInt(document.getElementById('living-input-box').value) || 30000;
            const grantCovered = tuition * audit.grant_percentage;
            const finalShortfall = Math.max(0, (tuition - grantCovered) + living);

            document.getElementById('dynamic-shortfall').innerText = `HKD $${Math.round(finalShortfall).toLocaleString()}`;

            const maxLoan = tuition + living;
            const schemeName = audit.loanScheme || currentExtractedData.loanScheme || "NLSFT (Non-Means-Tested Loan Scheme)";
            document.getElementById('loan-details').innerHTML = `You are eligible to borrow up to <strong class="text-cyan-300">HKD $${Math.round(maxLoan).toLocaleString()}</strong> via government schemes (${schemeName}) to cover your remaining tuition and living expenses.`;

            const checklistEl = document.getElementById('document-checklist');
            checklistEl.innerHTML = '';
            if (audit.required_documents && audit.required_documents.length > 0) {
                audit.required_documents.forEach(doc => {
                    const li = document.createElement('li');
                    li.innerText = `• ${doc}`;
                    checklistEl.appendChild(li);
                });
            } else {
                checklistEl.innerHTML = '<li>• No additional documents needed.</li>';
            }
        }

        function executeOverride() {
            const reason = document.getElementById('override-reason').value;
            if (!reason) return alert("Please select your special circumstance before submitting an appeal.");

            const badge = document.getElementById('verdict-badge');
            badge.innerText = "APPEAL_QUEUED";
            badge.className = "px-2 py-0.5 rounded text-[10px] font-bold bg-amber-950 text-amber-400 border border-amber-800";

            document.getElementById('verdict-title').innerText = "Hardship Appeal Successfully Submitted";
            document.getElementById('verdict-details').innerText = `Your request has been queued for human officer review. Reason flagged: ${reason}`;
            
            const timestampEl = document.getElementById('override-timestamp');
            timestampEl.classList.remove('hidden');
            timestampEl.innerText = `Appeal Ticket Generated on ${new Date().toLocaleString()} [Queue ID: SFO-APP-2026-99X]`;
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
    return jsonify({'status': 'error', 'message': 'Incorrect password. Please try again.'}), 401

@app.route('/api/logout', methods=['GET', 'POST'])
def api_logout():
    session.pop('authenticated', None)
    if request.method == 'POST':
        return '', 204
    return redirect(url_for('home'))

@app.route('/api/chats', methods=['GET'])
def list_chats():
    global ACTIVE_SESSION_ID
    if ACTIVE_SESSION_ID not in CHAT_SESSIONS:
        ACTIVE_SESSION_ID = list(CHAT_SESSIONS.keys())[0]
    chats_summary = [
        {"id": c["id"], "title": c["title"]}
        for c in CHAT_SESSIONS.values()
    ]
    active_messages = [m for m in CHAT_SESSIONS[ACTIVE_SESSION_ID]["messages"] if m["role"] != "system"]
    return jsonify({
        "active_id": ACTIVE_SESSION_ID,
        "chats": chats_summary,
        "messages": active_messages
    })

@app.route('/api/chats/new', methods=['POST'])
def new_chat():
    global ACTIVE_SESSION_ID
    chat_id = datetime.now().strftime('%Y%m%d%H%M%S_%f')
    CHAT_SESSIONS[chat_id] = {
        "id": chat_id,
        "title": "New Conversation",
        "messages": [
            {"role": "system", "content": BOUSSOLE_SYSTEM_INSTRUCTION},
            {"role": "assistant", "content": WELCOME_GREETING}
        ]
    }
    ACTIVE_SESSION_ID = chat_id
    return jsonify({
        "chat_id": chat_id, 
        "title": "New Conversation", 
        "messages": [{"role": "assistant", "content": WELCOME_GREETING}]
    })

@app.route('/api/chats/switch', methods=['POST'])
def switch_chat():
    global ACTIVE_SESSION_ID
    data = request.json
    chat_id = data.get('chat_id')
    if chat_id in CHAT_SESSIONS:
        ACTIVE_SESSION_ID = chat_id
        messages = [m for m in CHAT_SESSIONS[chat_id]["messages"] if m["role"] != "system"]
        return jsonify({"status": "switched", "active_id": chat_id, "messages": messages})
    return jsonify({"error": "Chat not found"}), 404

@app.route('/api/chats/active', methods=['DELETE'])
def delete_active_chat():
    global ACTIVE_SESSION_ID
    if len(CHAT_SESSIONS) <= 1:
        CHAT_SESSIONS[ACTIVE_SESSION_ID] = {
            "id": ACTIVE_SESSION_ID,
            "title": "New Conversation",
            "messages": [
                {"role": "system", "content": BOUSSOLE_SYSTEM_INSTRUCTION},
                {"role": "assistant", "content": WELCOME_GREETING}
            ]
        }
    else:
        del CHAT_SESSIONS[ACTIVE_SESSION_ID]
        ACTIVE_SESSION_ID = list(CHAT_SESSIONS.keys())[0]
    
    chats_summary = [
        {"id": c["id"], "title": c["title"]}
        for c in CHAT_SESSIONS.values()
    ]
    active_messages = [m for m in CHAT_SESSIONS[ACTIVE_SESSION_ID]["messages"] if m["role"] != "system"]
    return jsonify({
        "status": "deleted",
        "active_id": ACTIVE_SESSION_ID,
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
    - "job_description": string (a concise summary of core job expectations or description for this role)
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
    Analyze the candidate's CV against each of the target jobs provided below. Note that for some jobs, a formal description might be missing or minimal; in those cases, evaluate based on standard industry expectations and core skill requirements for the specified job title.
    
    Candidate CV Content:
    {cv_text}
    
    Target Jobs:
    {json.dumps(jobs)}
    
    Provide your response in strict JSON format with a single key "results" containing an array of objects. Each object must correspond to a job in order and have:
    - "job_title": string (the title provided or inferred)
    - "score": integer between 0 and 100 representing the match percentage.
    - "match_summary": short executive summary of why it matches or doesn't match the role.
    - "matched_keywords": list of string keywords/skills found in both the CV and job expectations.
    - "missing_keywords": list of key technical or domain terms expected for this role but missing from the CV.
    - "recommendations": list of 3-4 specific, actionable bullet points to improve the resume score for this role.
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

@app.route('/api/chat', methods=['POST'])
def chat():
    global ACTIVE_SESSION_ID
    data = request.json
    user_msg = data.get('message', '').strip()
    chat_id = data.get('chat_id') or ACTIVE_SESSION_ID

    if not user_msg:
        return jsonify({'error': 'Message required.'}), 400

    if chat_id not in CHAT_SESSIONS:
        chat_id = ACTIVE_SESSION_ID
    if chat_id not in CHAT_SESSIONS:
        chat_id = list(CHAT_SESSIONS.keys())[0]

    chat_obj = CHAT_SESSIONS[chat_id]
    messages = chat_obj["messages"]

    # AI-Generated Chat Title on First Message
    if chat_obj["title"] == "New Conversation":
        try:
            title_prompt = [
                {"role": "system", "content": "Generate a short, concise title (max 5 words, no quotes, no periods) that summarizes this chat topic."},
                {"role": "user", "content": user_msg}
            ]
            title_res = client.chat.completions.create(
                model=deployment_name,
                messages=title_prompt
            )
            ai_title = title_res.choices[0].message.content.strip().strip('"\'')
            if ai_title:
                chat_obj["title"] = ai_title
        except Exception as e:
            print(f"Title generation failed: {e}")
            chat_obj["title"] = (user_msg[:25] + '...') if len(user_msg) > 25 else user_msg

    messages.append({"role": "user", "content": user_msg})

    try:
        response = client.chat.completions.create(model=deployment_name, messages=messages)
        reply = response.choices[0].message.content
        messages.append({"role": "assistant", "content": reply})
        return jsonify({'reply': reply, 'title': chat_obj["title"], 'chat_id': chat_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
        
        # Normalize line endings
        raw_text = raw_text.replace('\r\n', '\n').replace('\r', '\n')
        raw_lines = raw_text.split('\n')
        
        non_empty_lines = [l.strip() for l in raw_lines if l.strip()]
        
        single_word_lines = sum(1 for l in non_empty_lines if ' ' not in l and len(l.split()) == 1)
        is_word_per_line = (len(non_empty_lines) > 0) and (single_word_lines / len(non_empty_lines) > 0.4)
        
        if is_word_per_line:
            reconstructed = []
            current_line = []
            for line in non_empty_lines:
                is_bullet = line.startswith(('•', '-', '*', '◦', '▪'))
                is_header = line.isupper() and len(line) < 25 and len(line.split()) <= 3
                
                if is_bullet or is_header:
                    if current_line:
                        reconstructed.append(" ".join(current_line))
                        current_line = []
                    reconstructed.append(line)
                else:
                    current_line.append(line)
                    if line.endswith(('.', ';', ':')) and len(current_line) >= 8:
                        reconstructed.append(" ".join(current_line))
                        current_line = []
            if current_line:
                reconstructed.append(" ".join(current_line))
            text = "\n".join(reconstructed)
        else:
            blocks = re.split(r'\n\s*\n', raw_text)
            cleaned_blocks = []
            for block in blocks:
                flat_block = re.sub(r'[ \t]+\n[ \t]*', ' ', block)
                flat_block = re.sub(r'[ \t]+', ' ', flat_block).strip()
                if flat_block:
                    cleaned_blocks.append(flat_block)
            text = '\n\n'.join(cleaned_blocks)

        return jsonify({'text': text.strip()})
    except Exception as e:
        return jsonify({'error': f'Failed to parse file: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)