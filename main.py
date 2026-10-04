import os
import io
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template_string, session
from openai import OpenAI
from pypdf import PdfReader

# Load .env relative to script execution path
env_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=env_path)

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

# System Instruction for Boussole AI Persona
BOUSSOLE_SYSTEM_INSTRUCTION = """
You are Boussole AI, an elite, executive-level career navigation strategist and hackathon career advisor.
Your mission is to help candidates navigate skill gaps, optimize resumes, master technical/behavioral interviews, and build structured career roadmaps.

Core Operating Principles:
1. Direct, Actionable Guidance: Cut generic fluff. Focus on clear execution steps.
2. The Google X-Y-Z Formula: When rewriting resume bullets, enforce "Accomplished [X], as measured by [Y], by doing [Z]".
3. Structure and Formatting: Utilize Markdown headers, bullet points, bold key terms, and code blocks where applicable.
4. Voice & Tone: Empathetic yet candid, strategic, professional, and encouraging.
5. Branding Identity: Always identify naturally as Boussole AI when introduced.
6. Add new blank lines each paragraph for readability.
"""

HTML_CONTENT = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Boussole AI — Strategic Career Navigation</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Plus Jakarta Sans', sans-serif; }
        .glass-panel {
            background: rgba(17, 24, 39, 0.85);
            border: 1px solid rgba(255, 255, 255, 0.08);
        }
        .custom-scrollbar::-webkit-scrollbar { width: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(255, 255, 255, 0.15); border-radius: 9999px; }
        .custom-scrollbar::-webkit-scrollbar-thumb:hover { background: rgba(255, 255, 255, 0.3); }
        .typing-dot { animation: typingWave 1.4s infinite ease-in-out both; }
        .typing-dot:nth-child(1) { animation-delay: 0s; }
        .typing-dot:nth-child(2) { animation-delay: 0.2s; }
        .typing-dot:nth-child(3) { animation-delay: 0.4s; }
        @keyframes typingWave {
            0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
            40% { transform: scale(1); opacity: 1; }
        }
    </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex flex-col justify-between selection:bg-cyan-500 selection:text-white">

    <!-- Top Navigation Bar -->
    <header class="border-b border-slate-800 bg-slate-900 sticky top-0 z-50">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
            <div class="flex items-center gap-3">
                <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-cyan-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
                    <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path>
                    </svg>
                </div>
                <div>
                    <h1 class="font-bold text-lg text-white tracking-tight leading-none">Boussole <span class="text-cyan-400 font-normal">AI</span></h1>
                    <p class="text-[11px] text-slate-400 tracking-wide mt-0.5">Career Intelligence & Roadmapping</p>
                </div>
            </div>
            
            <div class="flex items-center gap-3">
                <button onclick="exportMarkdown()" class="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"></path></svg>
                    Export Roadmap
                </button>
                <button onclick="clearHistory()" class="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800/80 hover:bg-rose-950/50 hover:text-rose-300 hover:border-rose-800/50 text-slate-400 border border-slate-700/60 transition">
                    Reset Chat
                </button>
                <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-cyan-950/80 text-cyan-400 border border-cyan-800/50">
                    <span class="w-1.5 h-1.5 rounded-full bg-cyan-400 mr-1.5 animate-pulse"></span>
                    Azure GPT-5 Mini
                </span>
            </div>
        </div>
    </header>

    <!-- Main Content Area -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6 w-full flex-1 flex flex-col md:flex-row gap-6">
        
        <!-- Left Sidebar: Career Playbooks & PDF Uploader -->
        <aside class="w-full md:w-80 flex flex-col gap-4">
            
            <!-- PDF Upload Card -->
            <div class="glass-panel rounded-2xl p-4 flex flex-col gap-2">
                <h2 class="text-xs font-semibold text-slate-400 uppercase tracking-wider px-1">Upload Resume (PDF/TXT)</h2>
                <label for="pdf-file-input" class="cursor-pointer flex flex-col items-center justify-center p-4 border-2 border-dashed border-slate-800 hover:border-cyan-500/50 rounded-xl bg-slate-900/40 hover:bg-slate-900/80 transition text-center group">
                    <svg class="w-6 h-6 text-slate-500 group-hover:text-cyan-400 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 0115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path></svg>
                    <span id="upload-status-text" class="text-xs text-slate-300 font-medium">Click to attach resume</span>
                    <span class="text-[10px] text-slate-500 mt-0.5">Extracts text directly into context</span>
                </label>
                <input id="pdf-file-input" type="file" accept=".pdf,.txt" class="hidden" onchange="handleFileUpload(event)">
            </div>

            <!-- Career Playbooks -->
            <div class="glass-panel rounded-2xl p-4 flex flex-col gap-3">
                <h2 class="text-xs font-semibold text-slate-400 uppercase tracking-wider px-1">Career Playbooks</h2>
                
                <button onclick="applyPreset('roast')" class="text-left p-3 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-cyan-500/50 hover:bg-slate-800/60 transition group">
                    <div class="text-sm font-semibold text-cyan-300 group-hover:text-cyan-200">🔥 Resume Roast & Optimize</div>
                    <div class="text-xs text-slate-400 mt-1">Get candid feedback and rewrite bullets in Google X-Y-Z format.</div>
                </button>

                <button onclick="applyPreset('gap')" class="text-left p-3 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-indigo-500/50 hover:bg-slate-800/60 transition group">
                    <div class="text-sm font-semibold text-indigo-300 group-hover:text-indigo-200">🎯 Skill Gap Matrix</div>
                    <div class="text-xs text-slate-400 mt-1">Compare your current resume directly against a target job description.</div>
                </button>

                <button onclick="applyPreset('behavioral')" class="text-left p-3 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-emerald-500/50 hover:bg-slate-800/60 transition group">
                    <div class="text-sm font-semibold text-emerald-300 group-hover:text-emerald-200">🎙️ Interview Drill</div>
                    <div class="text-xs text-slate-400 mt-1">Simulate high-stakes behavioral and technical scenario questions.</div>
                </button>

                <button onclick="applyPreset('roadmap')" class="text-left p-3 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-purple-500/50 hover:bg-slate-800/60 transition group">
                    <div class="text-sm font-semibold text-purple-300 group-hover:text-purple-200">🗺️ 90-Day Career Roadmap</div>
                    <div class="text-xs text-slate-400 mt-1">Generate a structured milestone plan for a career transition.</div>
                </button>
            </div>
        </aside>

        <!-- Right Console: Chat Stream -->
        <section class="flex-1 glass-panel rounded-2xl flex flex-col h-[75vh] md:h-[82vh] overflow-hidden">
            
            <!-- Message Display Area -->
            <div id="chat-stream" class="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4 custom-scrollbar">
                <div class="flex items-start gap-3 max-w-3xl">
                    <div class="w-8 h-8 rounded-lg bg-cyan-500/20 border border-cyan-500/40 text-cyan-300 flex items-center justify-center flex-shrink-0 text-sm font-bold">
                        B
                    </div>
                    <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 text-slate-200 text-sm leading-relaxed shadow-sm">
                        <p class="font-semibold text-cyan-300 mb-1">Welcome to Boussole AI</p>
                        <p>I am your career intelligence strategist powered by Azure AI Foundry. Choose a playbook from the left sidebar, attach your resume PDF, or ask any question to start mapping your path.</p>
                    </div>
                </div>
            </div>

            <!-- Typing Indicator -->
            <div id="typing-indicator" class="hidden px-6 py-2 flex items-center gap-2 text-xs text-slate-400">
                <div class="w-6 h-6 rounded-md bg-cyan-500/20 text-cyan-300 flex items-center justify-center text-xs font-bold">B</div>
                <div class="flex gap-1 items-center bg-slate-900/80 px-3 py-2 rounded-xl border border-slate-800">
                    <span class="w-1.5 h-1.5 bg-cyan-400 rounded-full typing-dot"></span>
                    <span class="w-1.5 h-1.5 bg-cyan-400 rounded-full typing-dot"></span>
                    <span class="w-1.5 h-1.5 bg-cyan-400 rounded-full typing-dot"></span>
                </div>
            </div>

            <!-- Input Box Section -->
            <div class="p-3 sm:p-4 border-t border-slate-800/80 bg-slate-950/40">
                <form id="chat-form" class="flex flex-col gap-2">
                    <div class="relative flex items-center">
                        <textarea 
                            id="user-input" 
                            rows="2" 
                            class="w-full bg-slate-900/90 text-slate-100 placeholder-slate-500 text-sm rounded-xl px-4 py-3 border border-slate-800 focus:outline-none focus:border-cyan-500/80 focus:ring-1 focus:ring-cyan-500/80 transition resize-none custom-scrollbar pr-12"
                            placeholder="Ask Boussole AI or paste your resume/job specs..." 
                            required></textarea>
                        
                        <button 
                            type="submit" 
                            id="send-button"
                            class="absolute right-2 p-2 bg-gradient-to-tr from-cyan-500 to-indigo-600 text-white rounded-lg hover:opacity-90 transition disabled:opacity-40 disabled:cursor-not-allowed">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14 5l7 7m0 0l-7 7m7-7H3"></path>
                            </svg>
                        </button>
                    </div>
                </form>
            </div>

        </section>
    </main>

    <script>
        const chatStream = document.getElementById('chat-stream');
        const chatForm = document.getElementById('chat-form');
        const userInput = document.getElementById('user-input');
        const sendButton = document.getElementById('send-button');
        const typingIndicator = document.getElementById('typing-indicator');
        let fullConversationLog = [];
        let messageCounter = 0;

        const presets = {
            roast: "Review my resume bullet points below. Critique them for vagueness and rewrite them into strong Google X-Y-Z formula bullets:\n\n[PASTE YOUR BULLETS HERE]",
            gap: "Compare my current resume against this target job description. List key skill gaps, missing ATS keywords, and match score (0-100%):\n\nRESUME:\n[PASTE RESUME]\n\nJOB DESCRIPTION:\n[PASTE JOB DESCRIPTION]",
            behavioral: "I am preparing for an interview for a software engineering role. Ask me 3 challenging behavioral scenario questions one by one and grade my answers.",
            roadmap: "Generate a structured 90-day execution roadmap for transitioning into my target role. Break down month by month with actionable milestones."
        };

        function applyPreset(type) {
            userInput.value = presets[type];
            userInput.focus();
            userInput.style.height = 'auto';
            userInput.style.height = (userInput.scrollHeight) + 'px';
        }

        async function handleFileUpload(e) {
            const file = e.target.files[0];
            if (!file) return;

            const statusText = document.getElementById('upload-status-text');
            statusText.innerText = "Extracting text...";

            const formData = new FormData();
            formData.append('file', file);

            try {
                const res = await fetch('/api/parse_resume', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();
                if (data.text) {
                    statusText.innerText = `Loaded: ${file.name}`;
                    userInput.value = `Here is my uploaded resume:\n\n${data.text}\n\nPlease analyze this resume for strengths and high-priority improvements.`;
                    userInput.style.height = '140px';
                } else {
                    statusText.innerText = "Upload failed";
                    alert(data.error || "Failed to extract text");
                }
            } catch (err) {
                statusText.innerText = "Upload error";
                alert("Error parsing file.");
            }
        }

        async function clearHistory() {
            await fetch('/api/clear', { method: 'POST' });
            chatStream.innerHTML = `
                <div class="flex items-start gap-3 max-w-3xl">
                    <div class="w-8 h-8 rounded-lg bg-cyan-500/20 border border-cyan-500/40 text-cyan-300 flex items-center justify-center flex-shrink-0 text-sm font-bold">B</div>
                    <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 text-slate-200 text-sm leading-relaxed shadow-sm">
                        Conversation context reset. Ready for a new strategy session!
                    </div>
                </div>`;
            fullConversationLog = [];
            messageCounter = 0;
        }

        function exportMarkdown() {
            if (fullConversationLog.length === 0) {
                alert("No roadmap or conversation to export yet!");
                return;
            }
            const blob = new Blob([fullConversationLog.join("\n\n---\n\n")], { type: 'text/markdown' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'boussole-career-plan.md';
            a.click();
        }

        async function copyMessageText(msgId, buttonEl) {
            const container = document.getElementById(msgId);
            if (!container) return;
            const textToCopy = container.innerText.trim();

            try {
                await navigator.clipboard.writeText(textToCopy);
                const originalHTML = buttonEl.innerHTML;
                buttonEl.innerHTML = `
                    <svg class="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                    <span class="text-emerald-400 font-semibold">Copied!</span>
                `;
                setTimeout(() => {
                    buttonEl.innerHTML = originalHTML;
                }, 2000);
            } catch (err) {
                alert("Failed to copy text.");
            }
        }

        userInput.addEventListener('input', () => {
            userInput.style.height = 'auto';
            userInput.style.height = Math.min(userInput.scrollHeight, 180) + 'px';
        });

        userInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                chatForm.dispatchEvent(new Event('submit'));
            }
        });

        chatForm.onsubmit = async (e) => {
            e.preventDefault();
            const text = userInput.value.trim();
            if (!text) return;

            userInput.value = '';
            userInput.style.height = 'auto';

            fullConversationLog.push(`**User:**\n${text}`);

            chatStream.innerHTML += `
                <div class="flex items-start gap-3 justify-end">
                    <div class="bg-cyan-600/90 text-white rounded-2xl p-4 text-sm leading-relaxed max-w-2xl shadow-md">
                        ${escapeHtml(text).replace(/\n/g, '<br>')}
                    </div>
                </div>
            `;
            chatStream.scrollTop = chatStream.scrollHeight;

            sendButton.disabled = true;
            typingIndicator.classList.remove('hidden');

            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ message: text })
                });

                const data = await response.json();
                
                if (data.reply) {
                    messageCounter++;
                    const msgId = `msg-content-${messageCounter}`;
                    fullConversationLog.push(`**Boussole AI:**\n${data.reply}`);
                    const parsedMarkdown = marked.parse(data.reply);
                    chatStream.innerHTML += `
                        <div class="flex items-start gap-3 max-w-3xl group">
                            <div class="w-8 h-8 rounded-lg bg-cyan-500/20 border border-cyan-500/40 text-cyan-300 flex items-center justify-center flex-shrink-0 text-sm font-bold">B</div>
                            <div class="relative bg-slate-900/90 border border-slate-800 rounded-2xl p-4 text-slate-200 text-sm leading-relaxed shadow-sm prose prose-invert max-w-none prose-p:my-1.5 prose-headings:text-cyan-300 prose-strong:text-white prose-code:bg-slate-800 prose-code:px-1 prose-code:rounded">
                                <div id="${msgId}">${parsedMarkdown}</div>
                                <div class="mt-3 pt-2 border-t border-slate-800/60 flex items-center justify-end">
                                    <button onclick="copyMessageText('${msgId}', this)" class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium text-slate-400 hover:text-cyan-300 hover:bg-slate-800 transition">
                                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"></path></svg>
                                        <span>Copy</span>
                                    </button>
                                </div>
                            </div>
                        </div>
                    `;
                } else {
                    chatStream.innerHTML += `
                        <div class="flex items-start gap-3 max-w-3xl">
                            <div class="w-8 h-8 rounded-lg bg-rose-500/20 border border-rose-500/40 text-rose-400 flex items-center justify-center flex-shrink-0 text-sm font-bold">!</div>
                            <div class="bg-rose-950/40 border border-rose-900/60 rounded-2xl p-4 text-rose-200 text-sm">
                                <strong>Error:</strong> ${data.error || 'Failed to process request.'}
                            </div>
                        </div>
                    `;
                }
            } catch (err) {
                chatStream.innerHTML += `
                    <div class="flex items-start gap-3 max-w-3xl">
                        <div class="w-8 h-8 rounded-lg bg-rose-500/20 border border-rose-500/40 text-rose-400 flex items-center justify-center flex-shrink-0 text-sm font-bold">!</div>
                        <div class="bg-rose-950/40 border border-rose-900/60 rounded-2xl p-4 text-rose-200 text-sm">
                            Network connection error. Please verify backend service status.
                        </div>
                    </div>
                `;
            } finally {
                sendButton.disabled = false;
                typingIndicator.classList.add('hidden');
                chatStream.scrollTop = chatStream.scrollHeight;
            }
        };

        function escapeHtml(str) {
            return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    if 'messages' not in session:
        session['messages'] = [{"role": "system", "content": BOUSSOLE_SYSTEM_INSTRUCTION}]
    return render_template_string(HTML_CONTENT)

@app.route('/api/chat', methods=['POST'])
def chat():
    user_msg = request.json.get('message', '').strip()
    
    if not user_msg:
        return jsonify({'error': 'Message string cannot be empty.'}), 400

    # Ensure session history exists
    if 'messages' not in session:
        session['messages'] = [{"role": "system", "content": BOUSSOLE_SYSTEM_INSTRUCTION}]

    messages = session['messages']
    messages.append({"role": "user", "content": user_msg})

    try:
        response = client.chat.completions.create(
            model=deployment_name,
            messages=messages
        )
        reply = response.choices[0].message.content
        messages.append({"role": "assistant", "content": reply})
        session['messages'] = messages  # Save back to session

        return jsonify({
            'reply': reply,
            'model_used': deployment_name
        })
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
            return jsonify({'error': 'Unsupported file format. Please upload PDF or TXT.'}), 400

        return jsonify({'text': text.strip()})
    except Exception as e:
        return jsonify({'error': f'Failed to parse file: {str(e)}'}), 500

@app.route('/api/clear', methods=['POST'])
def clear_chat():
    session['messages'] = [{"role": "system", "content": BOUSSOLE_SYSTEM_INSTRUCTION}]
    return jsonify({'status': 'cleared'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)