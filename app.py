import os
import io
import json
import re
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template_string, session
from openai import OpenAI
from pypdf import PdfReader

# Load .env relative to script execution path
env_path = Path(__file__).resolve().parent / '.env'
load_dotenv(env_path)

endpoint = os.environ.get('AZURE_OPENAI_ENDPOINT')
api_key = os.environ.get('AZURE_OPENAI_API_KEY')
deployment_name = os.environ.get('AZURE_OPENAI_DEPLOYMENT_NAME', 'gpt-5-mini')

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
# 2. CAREER ADVISOR SYSTEM INSTRUCTION
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
6. Add new blank lines between every single paragraph to guarantee readability. Use double line breaks (\\n\\n) for spacing.
7. Make paragraphs at least 3 lines per paragraph.
"""

# ==============================================================================
# 3. UNIFIED FRONTEND
# ==============================================================================

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
        
        /* Absolute boundary containment rules to prevent out-of-bounds text/font overflow */
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
<body class="bg-slate-950 text-slate-100 h-[100dvh] flex flex-col justify-between selection:bg-cyan-500 selection:text-white overflow-hidden">

    <!-- Top Navigation Bar -->
    <header class="border-b border-slate-800 bg-slate-900 sticky top-0 z-50 flex-shrink-0">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-cyan-500/20 flex-shrink-0">
                    <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path></svg>
                </div>
                <div>
                    <h1 class="font-bold text-base sm:text-lg text-white tracking-tight leading-none">Boussole <span class="text-cyan-400 font-normal">AI</span></h1>
                    <div class="flex items-center gap-2 mt-0.5">
                        <p class="text-[10px] sm:text-[11px] text-slate-400 tracking-wide" id="brand-subtitle">Career Intelligence & Roadmapping</p>
                        <span class="text-[9px] px-1.5 py-0.5 rounded bg-slate-800 text-cyan-400 border border-slate-700 font-mono">⚡ gpt-5-mini</span>
                    </div>
                </div>
            </div>
            
            <div class="flex items-center gap-2 flex-wrap">
                <button onclick="switchView('career')" id="btn-career" class="text-xs font-semibold px-3 py-2 rounded-xl bg-cyan-600 text-white transition shadow-sm">
                    💼 Career Coach
                </button>
                <button onclick="switchView('ats')" id="btn-ats" class="text-xs font-semibold px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-indigo-300 border border-slate-700 transition shadow-sm">
                    🎯 ATS Matcher
                </button>
                <button onclick="switchView('copilot')" id="btn-copilot" class="text-xs font-semibold px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition shadow-sm">
                    🏛️️ Financial Aid
                </button>
                <button onclick="switchView('bridge')" id="btn-bridge" class="text-xs font-semibold px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-purple-300 border border-slate-700 transition shadow-sm">
                    🌉 Grant-to-Career
                </button>
            </div>
        </div>
    </header>

    <!-- MAIN APP VIEWS CONTAINER -->
    <main class="max-w-7xl mx-auto px-2 sm:px-6 lg:px-8 py-3 w-full flex-1 flex flex-col overflow-hidden">

        <!-- VIEW 1: CAREER COACH (DEFAULT) -->
        <div id="view-career" class="flex-1 flex flex-col md:flex-row gap-4 h-full overflow-hidden">
            <!-- Sidebar controls -->
            <aside class="w-full md:w-80 flex flex-col gap-3 flex-shrink-0 overflow-y-auto max-h-[160px] md:max-h-none custom-scrollbar">
                <div class="glass-panel rounded-2xl p-3 flex flex-col gap-2">
                    <h2 class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider px-1">Upload Resume (PDF/TXT)</h2>
                    <label for="pdf-file-input" class="cursor-pointer flex items-center justify-center p-3 border border-dashed border-slate-700 hover:border-cyan-500/50 rounded-xl bg-slate-900/40 transition text-center">
                        <span id="upload-status-text" class="text-xs text-slate-300 font-medium truncate">📎 Click to attach resume</span>
                    </label>
                    <input id="pdf-file-input" type="file" accept=".pdf,.txt" class="hidden" onchange="handleFileUpload(event)">
                </div>

                <div class="glass-panel rounded-2xl p-3 flex flex-col gap-2">
                    <h2 class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider px-1">Career Playbooks</h2>
                    <div class="grid grid-cols-2 md:grid-cols-1 gap-2">
                        <button onclick="applyPreset('roast')" class="text-left p-2 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-cyan-500/50 transition text-xs text-cyan-300 font-semibold truncate">🔥 Resume Roast</button>
                        <button onclick="applyPreset('gap')" class="text-left p-2 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-indigo-500/50 transition text-xs text-indigo-300 font-semibold truncate">🎯 Skill Gap Matrix</button>
                        <button onclick="applyPreset('behavioral')" class="text-left p-2 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-emerald-500/50 transition text-xs text-emerald-300 font-semibold truncate">🎙️ Interview Drill</button>
                        <button onclick="applyPreset('roadmap')" class="text-left p-2 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-purple-500/50 transition text-xs text-purple-300 font-semibold truncate">🗺️ 90-Day Roadmap</button>
                    </div>
                </div>

                <!-- Reset Chat & Export Chat Actions positioned at bottom of left sidebar -->
                <div id="sidebar-actions" class="glass-panel rounded-2xl p-3 flex flex-col gap-2">
                    <h2 class="text-[11px] font-semibold text-slate-400 uppercase tracking-wider px-1">Chat Actions</h2>
                    <div class="grid grid-cols-2 md:grid-cols-1 gap-2">
                        <button onclick="resetChat()" id="reset-btn" class="text-left p-2 rounded-xl bg-rose-950/60 hover:bg-rose-900/80 border border-rose-800/80 text-rose-300 text-xs font-semibold transition flex items-center gap-1.5 truncate" title="Clear chat history and restart">
                            🔄 Reset Chat
                        </button>
                        <button onclick="exportMarkdown()" id="export-btn" class="text-left p-2 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-slate-700 text-slate-300 text-xs font-semibold transition flex items-center gap-1.5 truncate" title="Export conversation history">
                            📥 Export Chat
                        </button>
                    </div>
                </div>
            </aside>

            <!-- Chat Panel -->
            <section class="flex-1 glass-panel rounded-2xl flex flex-col overflow-hidden h-full min-w-0">
                <div id="chat-stream" class="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar text-sm">
                    <div class="flex items-start gap-3 w-full">
                        <div class="w-8 h-8 rounded-lg bg-cyan-500/20 text-cyan-300 flex items-center justify-center font-bold flex-shrink-0">B</div>
                        <div class="bg-slate-900/90 border border-slate-800 rounded-2xl p-3.5 text-slate-200 max-w-[85%] flex flex-col gap-2 overflow-hidden">
                            <div class="ai-markdown-body">Welcome to Boussole AI Career Strategist. How can I help you navigate your professional trajectory today?</div>
                            <div class="flex items-center gap-3 pt-2 border-t border-slate-800/80 text-[11px]">
                                <button onclick="copyToClipboard(this, 'Welcome to Boussole AI Career Strategist. How can I help you navigate your professional trajectory today?')" class="text-slate-400 hover:text-slate-200 flex items-center gap-1 font-medium transition">📋 Copy</button>
                                <button data-speak-btn onclick="speakText(this, 'Welcome to Boussole AI Career Strategist. How can I help you navigate your professional trajectory today?')" class="text-slate-400 hover:text-slate-200 flex items-center gap-1 font-medium transition">🔊 Speak</button>
                            </div>
                        </div>
                    </div>
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
                        <button type="submit" id="send-button" class="px-5 py-3 bg-cyan-600 hover:bg-cyan-500 text-white font-semibold rounded-xl text-sm h-[48px] flex-shrink-0 transition">Send</button>
                    </form>
                    <div class="text-[11px] text-slate-400 px-1 flex items-center justify-between">
                        <span>💡 Tip: Press <kbd class="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-cyan-400 font-mono">Enter</kbd> to send, <kbd class="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-purple-400 font-mono">Shift + Enter</kbd> for a new line.</span>
                    </div>
                </div>
            </section>
        </div>

        <!-- VIEW 2: ATS RESUME MATCHING PAGE -->
        <div id="view-ats" class="hidden flex-1 flex flex-col gap-4 overflow-y-auto custom-scrollbar p-1">
            <div class="glass-panel rounded-2xl p-6 flex flex-col gap-5 max-w-5xl mx-auto w-full">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl bg-indigo-500/20 text-indigo-300 flex items-center justify-center font-bold text-lg">🎯</div>
                    <div>
                        <h2 class="text-base font-bold text-white">ATS Resume & Job Compatibility Engine</h2>
                        <p class="text-xs text-slate-400">Upload your CV and paste a target job description to calculate your ATS match score and discover missing keywords.</p>
                    </div>
                </div>

                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <!-- Column A: Inputs -->
                    <div class="flex flex-col gap-3 bg-slate-900 p-4 rounded-xl border border-slate-800">
                        <h3 class="text-xs font-bold text-indigo-400 uppercase tracking-wider">1. Provide CV & Job Details</h3>
                        
                        <div class="flex flex-col gap-1.5">
                            <label class="text-xs font-semibold text-slate-300">Upload CV (PDF or TXT):</label>
                            <label for="ats-file-input" class="cursor-pointer flex items-center justify-center p-3 border border-dashed border-slate-700 hover:border-indigo-500/50 rounded-xl bg-slate-950 transition text-center">
                                <span id="ats-upload-status" class="text-xs text-slate-300 font-medium truncate">📎 Click to upload CV file</span>
                            </label>
                            <input id="ats-file-input" type="file" accept=".pdf,.txt" class="hidden" onchange="handleAtsFileUpload(event)">
                        </div>

                        <div class="flex flex-col gap-1.5">
                            <label class="text-xs font-semibold text-slate-350">Or Paste CV Text Content:</label>
                            <textarea id="ats-cv-text" rows="5" class="w-full bg-slate-950 text-slate-200 text-xs rounded-xl p-3 border border-slate-800 focus:outline-none focus:border-indigo-500 custom-scrollbar resize-none" placeholder="Paste your resume text here..."></textarea>
                        </div>

                        <div class="flex flex-col gap-1.5">
                            <label class="text-xs font-semibold text-slate-350">Target Job Title & Description:</label>
                            <textarea id="ats-job-desc" rows="5" class="w-full bg-slate-950 text-slate-200 text-xs rounded-xl p-3 border border-slate-800 focus:outline-none focus:border-indigo-500 custom-scrollbar resize-none" placeholder="Paste the target job description or title here..."></textarea>
                        </div>

                        <button onclick="runAtsMatch()" id="ats-submit-btn" class="w-full py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs rounded-xl transition shadow-lg shadow-indigo-600/20">
                            Calculate ATS Compatibility Score ⚡
                        </button>
                    </div>

                    <!-- Column B: Results & Score Analysis -->
                    <div class="flex flex-col gap-3 bg-slate-900 p-4 rounded-xl border border-slate-800 overflow-y-auto custom-scrollbar">
                        <h3 class="text-xs font-bold text-cyan-400 uppercase tracking-wider">2. Compatibility Breakdown</h3>
                        
                        <div id="ats-placeholder-state" class="flex-1 flex flex-col items-center justify-center text-center p-6 text-slate-500 text-xs gap-2 min-h-[280px]">
                            <span class="text-3xl">📊</span>
                            <p>Awaiting CV and job description input.<br>Click calculate to run AI ATS analysis.</p>
                        </div>

                        <div id="ats-results-state" class="hidden flex flex-col gap-4">
                            <!-- Score Banner -->
                            <div class="p-4 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between">
                                <div>
                                    <span class="text-xs text-slate-400">Overall ATS Score:</span>
                                    <h4 id="ats-score-title" class="text-lg font-bold text-white">Analyzing...</h4>
                                </div>
                                <div id="ats-score-badge" class="w-16 h-16 rounded-2xl bg-indigo-600/20 text-indigo-400 border border-indigo-500/40 flex items-center justify-center font-bold text-xl">
                                    0%
                                </div>
                            </div>

                            <!-- Summary -->
                            <div class="flex flex-col gap-1">
                                <span class="text-[11px] font-bold text-slate-400 uppercase">Match Summary</span>
                                <p id="ats-summary-text" class="text-xs text-slate-300 leading-relaxed bg-slate-950 p-3 rounded-lg border border-slate-800">—</p>
                            </div>

                            <!-- Matched Keywords -->
                            <div class="flex flex-col gap-1.5">
                                <span class="text-[11px] font-bold text-emerald-400 uppercase">✓ Matched Keywords & Skills</span>
                                <div id="ats-matched-tags" class="flex flex-wrap gap-1.5 bg-slate-950 p-3 rounded-lg border border-slate-800 min-h-[44px]">
                                    <span class="text-xs text-slate-500 italic">None identified</span>
                                </div>
                            </div>

                            <!-- Missing Keywords -->
                            <div class="flex flex-col gap-1.5">
                                <span class="text-[11px] font-bold text-rose-400 uppercase">⚠️ Missing Keywords / Gaps</span>
                                <div id="ats-missing-tags" class="flex flex-wrap gap-1.5 bg-slate-950 p-3 rounded-lg border border-slate-800 min-h-[44px]">
                                    <span class="text-xs text-slate-500 italic">None identified</span>
                                </div>
                            </div>

                            <!-- Recommendations -->
                            <div class="flex flex-col gap-1.5">
                                <span class="text-[11px] font-bold text-cyan-400 uppercase">💡 Actionable Optimization Steps</span>
                                <ul id="ats-recommendations-list" class="text-xs text-slate-200 space-y-1.5 bg-slate-950 p-3 rounded-lg border border-slate-800 pl-4 list-disc">
                                    <li>Awaiting analysis...</li>
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- VIEW 3: STUDENT FINANCIAL AID PORTAL -->
        <div id="view-copilot" class="hidden flex-1 grid grid-cols-1 md:grid-cols-3 gap-4 h-full overflow-hidden">
            <!-- Left: Student Input & What-If Sliders with Custom Text Inputs -->
            <section class="glass-panel rounded-2xl p-4 flex flex-col gap-3 overflow-y-auto custom-scrollbar">
                <h2 class="text-xs font-bold text-slate-400 uppercase tracking-wider">1. Check Your Financial Aid</h2>
                <div class="grid grid-cols-2 gap-2">
                    <button onclick="loadScenario('full_grant', 10000, 4)" class="p-2 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs text-emerald-400 text-left truncate">🟢 Full Grant Profile</button>
                    <button onclick="loadScenario('partial_grant', 18000, 4)" class="p-2 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs text-cyan-300 text-left truncate">🔵 Partial Grant Profile</button>
                    <button onclick="loadScenario('ineligible', 24000, 3)" class="p-2 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs text-rose-400 text-left truncate">🔴 High Income Profile</button>
                    <button onclick="loadScenario('missing_income', null, 2)" class="p-2 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-xs text-amber-300 text-left truncate">⚠️ Incomplete Profile</button>
                </div>
                <textarea id="case-notes" rows="3" class="w-full bg-slate-900 text-slate-200 text-xs rounded-xl p-3 border border-slate-800 focus:outline-none focus:border-cyan-500 custom-scrollbar resize-none" placeholder="Paste your financial situation or notes..."></textarea>
                
                <button onclick="processCase()" id="process-btn" class="w-full py-2.5 bg-gradient-to-r from-cyan-500 to-indigo-600 text-white font-semibold text-xs rounded-xl hover:opacity-90 transition">Calculate My Eligibility</button>

                <!-- What-If Simulator Panel with Custom Input Boxes -->
                <div class="pt-2 border-t border-slate-800 flex flex-col gap-3 mt-1">
                    <span class="text-[11px] font-bold text-cyan-400 uppercase tracking-wider">🎛️ Explore "What-If" Scenarios</span>
                    
                    <div class="flex flex-col gap-1.5">
                        <div class="flex justify-between items-center text-[11px] text-slate-300">
                            <span>Family Monthly Income (HKD):</span>
                            <input id="income-input-box" type="number" min="0" max="100000" step="100" value="10000" class="w-24 bg-slate-900 text-cyan-300 font-bold text-xs rounded px-2 py-1 border border-slate-700 text-right focus:outline-none focus:border-cyan-500" oninput="syncFromBox('income')">
                        </div>
                        <input id="income-slider" type="range" min="0" max="50000" step="500" value="10000" class="w-full accent-cyan-500 cursor-pointer" oninput="syncFromSlider('income')">
                    </div>

                    <div class="flex flex-col gap-1.5">
                        <div class="flex justify-between items-center text-[11px] text-slate-300">
                            <span>Household Members:</span>
                            <input id="members-input-box" type="number" min="1" max="15" step="1" value="4" class="w-20 bg-slate-900 text-cyan-300 font-bold text-xs rounded px-2 py-1 border border-slate-700 text-right focus:outline-none focus:border-cyan-500" oninput="syncFromBox('members')">
                        </div>
                        <input id="members-slider" type="range" min="1" max="8" step="1" value="4" class="w-full accent-cyan-500 cursor-pointer" oninput="syncFromSlider('members')">
                    </div>
                </div>
            </section>

            <!-- Middle: PII Privacy Shield -->
            <section class="glass-panel rounded-2xl p-4 flex flex-col gap-3 overflow-hidden">
                <h2 class="text-xs font-bold text-slate-400 uppercase tracking-wider">2. Privacy Shield (PDPO Compliant)</h2>
                <div id="pii-status" class="hidden p-2.5 rounded-xl bg-slate-900 border border-slate-800 text-xs flex justify-between items-center">
                    <span class="text-slate-300">Protected Data:</span>
                    <span id="pii-count" class="font-bold text-cyan-400">0 Redacted</span>
                </div>
                <div id="sanitized-text" class="flex-1 bg-slate-950 p-3 rounded-xl border border-slate-900 text-xs text-slate-400 font-mono overflow-y-auto custom-scrollbar">Awaiting input...</div>
            </section>

            <!-- Right: Results, Checklist & Standalone Hardship Appeal Card -->
            <section class="glass-panel rounded-2xl p-4 flex flex-col gap-3 overflow-y-auto custom-scrollbar">
                <h2 class="text-xs font-bold text-slate-400 uppercase tracking-wider">3. Your Result & Action Plan</h2>
                
                <!-- Verdict Card (Box 3) -->
                <div class="bg-slate-900 p-4 rounded-xl border border-slate-800 flex flex-col gap-3">
                    <div class="flex justify-between items-center">
                        <span class="text-xs text-slate-400">Estimated Status:</span>
                        <span id="verdict-badge" class="px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-400">AWAITING</span>
                    </div>
                    <h3 id="verdict-title" class="text-sm font-bold text-white">No active profile checked</h3>
                    <p id="verdict-details" class="text-xs text-slate-400">Calculate your eligibility above to view details.</p>
                    
                    <div class="pt-2 border-t border-slate-800">
                        <span class="text-[10px] uppercase font-bold text-cyan-400 tracking-wider">Official Policy Reference:</span>
                        <p id="verdict-citation" class="text-xs text-slate-300 font-medium italic mt-1">—</p>
                    </div>

                    <div class="pt-2 border-t border-slate-800">
                        <span class="text-[10px] uppercase font-bold text-emerald-400 tracking-wider">📋 Your Document Checklist:</span>
                        <ul id="document-checklist" class="text-xs text-slate-200 space-y-1 mt-1 pl-2">
                            <li>• Awaiting evaluation...</li>
                        </ul>
                    </div>
                </div>

                <!-- Student Hardship Appeal Request (Standalone Card Outside Box 3) -->
                <div class="bg-slate-900 p-4 rounded-xl border border-slate-800 flex flex-col gap-2">
                    <span class="text-[10px] uppercase font-bold text-amber-400 tracking-wider">⚠️ Request Special Hardship Review</span>
                    <p class="text-[11px] text-slate-400 leading-tight">Facing unexpected financial hardship or medical issues? Submit an appeal for human officer review.</p>
                    <select id="override-reason" class="w-full bg-slate-950 text-slate-200 text-xs rounded-lg p-2 border border-slate-800 outline-none">
                        <option value="">Select your special circumstance...</option>
                        <option value="Sudden Family Medical Emergency / Hardship">Sudden Family Medical Emergency / Hardship</option>
                        <option value="Unexpected Loss of Family Breadwinner">Unexpected Loss of Family Breadwinner</option>
                        <option value="Fluctuating/Seasonal Income Discrepancy">Fluctuating/Seasonal Income Discrepancy</option>
                    </select>
                    <button onclick="executeOverride()" class="py-2 bg-amber-600 hover:bg-amber-500 text-white font-semibold text-xs rounded-lg transition">
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
                        <h2 class="text-base font-bold text-white">Grant-to-Career Livelihood & Work-Study Bridge</h2>
                        <p class="text-xs text-slate-400">Bridging financial aid shortfalls with verified campus employment and upskilling opportunities.</p>
                    </div>
                </div>

                <!-- Sliders & Custom Text Inputs for Family Income, Tuition, and Living Expenses -->
                <div class="grid grid-cols-1 md:grid-cols-3 gap-3 bg-slate-900 p-4 rounded-xl border border-slate-800">
                    <div class="flex flex-col gap-1.5">
                        <div class="flex justify-between items-center text-[11px] text-slate-300">
                            <span>Family Monthly Income:</span>
                            <input id="bridge-income-input-box" type="number" min="0" max="100000" step="100" value="10000" class="w-24 bg-slate-950 text-cyan-300 font-bold text-xs rounded px-2 py-1 border border-slate-700 text-right focus:outline-none focus:border-purple-500" oninput="syncBridgeFromBox('income')">
                        </div>
                        <input id="bridge-income-slider" type="range" min="0" max="50000" step="500" value="10000" class="w-full accent-purple-500 cursor-pointer" oninput="syncBridgeFromSlider('income')">
                    </div>

                    <div class="flex flex-col gap-1.5">
                        <div class="flex justify-between items-center text-[11px] text-slate-300">
                            <span>Tuition Fee:</span>
                            <input id="tuition-input-box" type="number" min="0" max="200000" step="500" value="42100" class="w-24 bg-slate-950 text-purple-300 font-bold text-xs rounded px-2 py-1 border border-slate-700 text-right focus:outline-none focus:border-purple-500" oninput="syncBridgeFromBox('tuition')">
                        </div>
                        <input id="tuition-slider" type="range" min="10000" max="100000" step="1000" value="42100" class="w-full accent-purple-500 cursor-pointer" oninput="syncBridgeFromSlider('tuition')">
                    </div>

                    <div class="flex flex-col gap-1.5">
                        <div class="flex justify-between items-center text-[11px] text-slate-300">
                            <span>Living Expenses:</span>
                            <input id="living-input-box" type="number" min="0" max="200000" step="500" value="30000" class="w-24 bg-slate-950 text-emerald-300 font-bold text-xs rounded px-2 py-1 border border-slate-700 text-right focus:outline-none focus:border-purple-500" oninput="syncBridgeFromBox('living')">
                        </div>
                        <input id="living-slider" type="range" min="0" max="80000" step="1000" value="30000" class="w-full accent-purple-500 cursor-pointer" oninput="syncBridgeFromSlider('living')">
                    </div>
                </div>

                <!-- Shortfall & Loan Eligibility Panel -->
                <div class="bg-slate-900 p-4 rounded-xl border border-slate-800 flex flex-col gap-3">
                    <h3 class="text-xs font-bold text-purple-400 uppercase tracking-wider">Your Dynamic Financial Shortfall & Loan Eligibility</h3>
                    <p class="text-xs text-slate-300">Based on your FASP tier and custom expense inputs, your total financial gap is: <strong id="dynamic-shortfall" class="text-cyan-400">HKD $21,050</strong>.</p>
                    
                    <div class="p-3 rounded-lg bg-slate-950 border border-slate-800 flex flex-col gap-1 text-xs">
                        <div class="flex justify-between items-center">
                            <span class="text-slate-300 font-semibold">Government Loan Status:</span>
                            <span id="loan-status-badge" class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-400 border border-emerald-800">ELIGIBLE FOR NLSFT LOAN</span>
                        </div>
                        <p id="loan-details" class="text-slate-400 mt-1">You are eligible to borrow up to <strong id="max-loan-amount" class="text-cyan-300">HKD $72,100</strong> via government schemes (NLSFT / Non-Means-Tested Loan Scheme) to cover your remaining tuition and living expenses.</p>
                    </div>

                    <div class="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-400">
                        💡 <strong>Recommended Action:</strong> Secure a flexible on-campus work-study role or tech internship to cover monthly living expenses and minimize student loan debt.
                    </div>
                </div>

                <div class="flex flex-col gap-3">
                    <h3 class="text-xs font-bold text-slate-400 uppercase tracking-wider">Matched Campus Jobs & Work-Study Programs</h3>
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                        <div class="bg-slate-900 p-4 rounded-xl border border-slate-800 flex flex-col justify-between gap-3">
                            <div>
                                <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-950 text-emerald-400 border border-emerald-800">Part-Time / Flexible</span>
                                <h4 class="text-sm font-bold text-white mt-2">AI Lab Student Assistant (HKUST)</h4>
                                <p class="text-xs text-slate-400 mt-1">Assist researchers with Python data processing and script optimization. Flexible hours around your class schedule.</p>
                            </div>
                            <div class="flex justify-between items-center pt-2 border-t border-slate-800">
                                <span class="text-xs font-bold text-cyan-400">HKD $120 / hour</span>
                                <button onclick="alert('Application draft sent to Career Coach!')" class="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold rounded-lg transition">Apply with AI Coach</button>
                            </div>
                        </div>

                        <div class="bg-slate-900 p-4 rounded-xl border border-slate-800 flex flex-col justify-between gap-3">
                            <div>
                                <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-indigo-950 text-indigo-400 border border-indigo-800">Work-Study Grant</span>
                                <h4 class="text-sm font-bold text-white mt-2">Student Financial Aid Student Ambassador</h4>
                                <p class="text-xs text-slate-400 mt-1">Help peers navigate campus digital forms and administrative document checklists.</p>
                            </div>
                            <div class="flex justify-between items-center pt-2 border-t border-slate-800">
                                <span class="text-xs font-bold text-cyan-400">HKD $4,500 / month</span>
                                <button onclick="alert('Application draft sent to Career Coach!')" class="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold rounded-lg transition">Apply with AI Coach</button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

    </main>

    <!-- Frontend Script Logic -->
    <script>
        let currentMode = 'career';
        let currentExtractedData = { income: 10000, members: 4, grantPercentage: 0.5, loanEligible: true, loanScheme: "NLSFT (Non-Means-Tested Loan Scheme)" };
        let fullConversationLog = [];
        let uploadedResumeText = "";

        function switchView(mode) {
            currentMode = mode;
            const careerView = document.getElementById('view-career');
            const atsView = document.getElementById('view-ats');
            const copilotView = document.getElementById('view-copilot');
            const bridgeView = document.getElementById('view-bridge');
            const brandSubtitle = document.getElementById('brand-subtitle');
            const sidebarActions = document.getElementById('sidebar-actions');

            const btnCareer = document.getElementById('btn-career');
            const btnAts = document.getElementById('btn-ats');
            const btnCopilot = document.getElementById('btn-copilot');
            const btnBridge = document.getElementById('btn-bridge');

            // Reset buttons
            btnCareer.className = "text-xs font-semibold px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition shadow-sm";
            btnAts.className = "text-xs font-semibold px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-indigo-300 border border-slate-700 transition shadow-sm";
            btnCopilot.className = "text-xs font-semibold px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition shadow-sm";
            btnBridge.className = "text-xs font-semibold px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-purple-300 border border-slate-700 transition shadow-sm";

            careerView.classList.add('hidden');
            atsView.classList.add('hidden');
            copilotView.classList.add('hidden');
            bridgeView.classList.add('hidden');

            if (mode === 'career') {
                careerView.classList.remove('hidden');
                brandSubtitle.innerText = 'Career Intelligence & Roadmapping';
                btnCareer.className = "text-xs font-semibold px-3 py-2 rounded-xl bg-cyan-600 text-white transition shadow-sm";
                if (sidebarActions) sidebarActions.classList.remove('hidden');
            } else if (mode === 'ats') {
                atsView.classList.remove('hidden');
                brandSubtitle.innerText = 'ATS Resume & Job Compatibility Engine';
                btnAts.className = "text-xs font-semibold px-3 py-2 rounded-xl bg-indigo-600 text-white transition shadow-sm";
                if (sidebarActions) sidebarActions.classList.add('hidden');
            } else if (mode === 'copilot') {
                copilotView.classList.remove('hidden');
                brandSubtitle.innerText = 'Student Financial Aid & Compliance';
                btnCopilot.className = "text-xs font-semibold px-3 py-2 rounded-xl bg-cyan-600 text-white transition shadow-sm";
                if (sidebarActions) sidebarActions.classList.add('hidden');
            } else if (mode === 'bridge') {
                bridgeView.classList.remove('hidden');
                brandSubtitle.innerText = 'Grant-to-Career Livelihood Bridge';
                btnBridge.className = "text-xs font-semibold px-3 py-2 rounded-xl bg-purple-600 text-white transition shadow-sm";
                if (sidebarActions) sidebarActions.classList.add('hidden');
            }
        }

        async function handleAtsFileUpload(e) {
            const file = e.target.files[0];
            if (!file) return;
            document.getElementById('ats-upload-status').innerText = `✅ ${file.name}`;
            const formData = new FormData();
            formData.append('file', file);
            const res = await fetch('/api/parse_resume', { method: 'POST', body: formData });
            const data = await res.json();
            if (data.text) {
                document.getElementById('ats-cv-text').value = data.text;
            }
        }

        async function runAtsMatch() {
            const cvText = document.getElementById('ats-cv-text').value.trim();
            const jobDesc = document.getElementById('ats-job-desc').value.trim();

            if (!cvText || !jobDesc) {
                return alert("Please provide both your CV text (or upload a file) and a target job title/description.");
            }

            const btn = document.getElementById('ats-submit-btn');
            btn.disabled = true;
            btn.innerText = "Analyzing Compatibility...";

            try {
                const res = await fetch('/api/ats_match', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ cv_text: cvText, job_desc: jobDesc })
                });
                const data = await res.json();
                
                document.getElementById('ats-placeholder-state').classList.add('hidden');
                document.getElementById('ats-results-state').classList.remove('hidden');

                const score = data.score || 0;
                document.getElementById('ats-score-badge').innerText = `${score}%`;
                document.getElementById('ats-score-title').innerText = score >= 75 ? "High ATS Compatibility" : score >= 50 ? "Moderate Compatibility" : "Low Match / Needs Optimization";
                document.getElementById('ats-summary-text').innerText = data.match_summary || "No summary provided.";

                // Render matched tags
                const matchedContainer = document.getElementById('ats-matched-tags');
                matchedContainer.innerHTML = '';
                if (data.matched_keywords && data.matched_keywords.length > 0) {
                    data.matched_keywords.forEach(kw => {
                        const span = document.createElement('span');
                        span.className = "px-2 py-1 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-800 text-[11px] font-mono";
                        span.innerText = kw;
                        matchedContainer.appendChild(span);
                    });
                } else {
                    matchedContainer.innerHTML = '<span class="text-xs text-slate-500 italic">No strong keyword matches found.</span>';
                }

                // Render missing tags
                const missingContainer = document.getElementById('ats-missing-tags');
                missingContainer.innerHTML = '';
                if (data.missing_keywords && data.missing_keywords.length > 0) {
                    data.missing_keywords.forEach(kw => {
                        const span = document.createElement('span');
                        span.className = "px-2 py-1 rounded bg-rose-950/80 text-rose-300 border border-rose-800 text-[11px] font-mono";
                        span.innerText = kw;
                        missingContainer.appendChild(span);
                    });
                } else {
                    missingContainer.innerHTML = '<span class="text-xs text-slate-500 italic">No critical missing keywords! Great job.</span>';
                }

                // Render recommendations
                const recList = document.getElementById('ats-recommendations-list');
                recList.innerHTML = '';
                if (data.recommendations && data.recommendations.length > 0) {
                    data.recommendations.forEach(rec => {
                        const li = document.createElement('li');
                        li.innerText = rec;
                        recList.appendChild(li);
                    });
                } else {
                    recList.innerHTML = '<li>No specific recommendations returned.</li>';
                }

            } catch (err) {
                alert("Error running ATS analysis. Please try again.");
                console.error(err);
            } finally {
                btn.disabled = false;
                btn.innerText = "Calculate ATS Compatibility Score ⚡";
            }
        }

        function exportMarkdown() {
            if (fullConversationLog.length === 0) {
                return alert("No conversation history to export yet.");
            }
            const blob = new Blob([fullConversationLog.join("\n\n---\n\n")], { type: 'text/markdown' });
            const a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = 'boussole-career-roadmap.md';
            a.click();
        }

        async function resetChat() {
            if (!confirm("Are you sure you want to reset the conversation?")) return;
            window.speechSynthesis.cancel();
            await fetch('/api/clear', { method: 'POST' });
            fullConversationLog = [];
            document.getElementById('chat-stream').innerHTML = `
                <div class="flex items-start gap-3 w-full">
                    <div class="w-8 h-8 rounded-lg bg-cyan-500/20 text-cyan-300 flex items-center justify-center font-bold flex-shrink-0">B</div>
                    <div class="bg-slate-900/90 border border-slate-800 rounded-2xl p-3.5 text-slate-200 max-w-[85%] flex flex-col gap-2 overflow-hidden">
                        <div class="ai-markdown-body">Chat reset successfully. How can I help you navigate your professional trajectory today?</div>
                        <div class="flex items-center gap-3 pt-2 border-t border-slate-800/80 text-[11px]">
                            <button onclick="copyToClipboard(this, 'Chat reset successfully. How can I help you navigate your professional trajectory today?')" class="text-slate-400 hover:text-slate-200 flex items-center gap-1 font-medium transition">📋 Copy</button>
                            <button data-speak-btn onclick="speakText(this, 'Chat reset successfully. How can I help you navigate your professional trajectory today?')" class="text-slate-400 hover:text-slate-200 flex items-center gap-1 font-medium transition">🔊 Speak</button>
                        </div>
                    </div>
                </div>`;
        }

        // Copy AI Response to Clipboard
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

        // Text-to-Speech Voice Output Utilities
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
                buttonElement.innerHTML = '⏹️ Stop';
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

        // Career Coach Chat & Smart Playbooks Logic
        const chatStream = document.getElementById('chat-stream');
        const chatForm = document.getElementById('chat-form');
        const userInput = document.getElementById('user-input');
        const typingIndicator = document.getElementById('typing-indicator');

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
                userInput.value = `Successfully parsed resume (${file.name}). Click '🔥 Resume Roast' or ask me anything about your career path!`;
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

            chatStream.innerHTML += `
                <div class="flex items-start justify-end gap-3 w-full">
                    <div class="bg-cyan-600/90 rounded-2xl p-3.5 text-white max-w-[85%] break-words overflow-hidden">${text}</div>
                </div>`;
            chatStream.scrollTop = chatStream.scrollHeight;
            typingIndicator.classList.remove('hidden');

            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ message: text })
                });
                const data = await response.json();
                typingIndicator.classList.add('hidden');

                if (data.reply) {
                    fullConversationLog.push(`**User:** ${text}\n\n**Boussole AI:** ${data.reply}`);
                    const rawReplyForCopy = data.reply.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"').replace(/\n/g, '\\n');
                    const cleanReplyForSpeech = stripMarkdownForSpeech(data.reply).replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"').replace(/\n/g, '\\n');
                    chatStream.innerHTML += `
                        <div class="flex items-start gap-3 w-full">
                            <div class="w-8 h-8 rounded-lg bg-cyan-500/20 text-cyan-300 flex items-center justify-center font-bold flex-shrink-0">B</div>
                            <div class="bg-slate-900/90 border border-slate-800 rounded-2xl p-3.5 text-slate-200 max-w-[85%] flex flex-col gap-2 overflow-hidden">
                                <div class="ai-markdown-body">${marked.parse(data.reply)}</div>
                                <div class="flex items-center gap-3 pt-2 border-t border-slate-800/80 text-[11px]">
                                    <button onclick="copyToClipboard(this, '${rawReplyForCopy}')" class="text-slate-400 hover:text-slate-200 flex items-center gap-1 font-medium transition">📋 Copy</button>
                                    <button data-speak-btn onclick="speakText(this, '${cleanReplyForSpeech}')" class="text-slate-400 hover:text-slate-200 flex items-center gap-1 font-medium transition">🔊 Speak</button>
                                </div>
                            </div>
                        </div>`;
                }
            } catch (err) {
                typingIndicator.classList.add('hidden');
                alert("Network error connecting to AI backend.");
            }
            chatStream.scrollTop = chatStream.scrollHeight;
        };

        // Copilot Scenarios Logic
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
# 4. ROUTING & API ENDPOINTS
# ==============================================================================

@app.route('/')
def home():
    if 'messages' not in session:
        session['messages'] = [{"role": "system", "content": BOUSSOLE_SYSTEM_INSTRUCTION}]
    return render_template_string(UNIFIED_HTML_TEMPLATE)

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

@app.route('/api/ats_match', methods=['POST'])
def ats_match():
    data = request.json
    cv_text = data.get('cv_text', '').strip()
    job_desc = data.get('job_desc', '').strip()

    if not cv_text or not job_desc:
        return jsonify({'error': 'Both CV text and job description are required.'}), 400

    prompt = f"""
    You are an expert ATS (Applicant Tracking System) recruiter and resume optimization engine.
    Analyze the candidate's CV against the target Job Description/Title.
    
    Target Job Description / Title:
    {job_desc}
    
    Candidate CV Content:
    {cv_text}
    
    Provide your response in strict JSON format with the following keys:
    - "score": integer between 0 and 100 representing the ATS match percentage.
    - "match_summary": short executive summary of why it matches or doesn't match the target role.
    - "matched_keywords": list of string keywords/skills found in both the CV and job description.
    - "missing_keywords": list of key technical or domain terms requested in the job description but missing from the CV.
    - "recommendations": list of 3-4 specific, actionable bullet points to improve the resume score.
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
    user_msg = request.json.get('message', '').strip()
    if not user_msg:
        return jsonify({'error': 'Message required.'}), 400

    if 'messages' not in session:
        session['messages'] = [{"role": "system", "content": BOUSSOLE_SYSTEM_INSTRUCTION}]

    messages = session['messages']
    messages.append({"role": "user", "content": user_msg})

    try:
        response = client.chat.completions.create(model=deployment_name, messages=messages)
        reply = response.choices[0].message.content
        messages.append({"role": "assistant", "content": reply})
        session['messages'] = messages
        return jsonify({'reply': reply})
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
            text = "\n".join([page.extract_text() or "" for page in reader.pages])
        elif filename.endswith('.txt'):
            text = file.read().decode('utf-8')
        else:
            return jsonify({'error': 'Unsupported file format.'}), 400
        return jsonify({'text': text.strip()})
    except Exception as e:
        return jsonify({'error': f'Failed to parse file: {str(e)}'}), 500

@app.route('/api/clear', methods=['POST'])
def clear_chat():
    session['messages'] = [{"role": "system", "content": BOUSSOLE_SYSTEM_INSTRUCTION}]
    return jsonify({'status': 'cleared'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)