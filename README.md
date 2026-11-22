BOUSSOLEAI
AI-POWERED CAREER & ACADEMIC NAVIGATION PLATFORM
================================================

ABOUT
-----
BoussoleAI is an AI-powered platform designed to help students and job seekers
navigate their academic and professional journeys. It brings career guidance,
resume analysis, job matching, financial aid assistance, skill development,
and an interactive game experience together in one application.

FEATURES
--------

1. CAREER COACH
   - AI-powered career guidance and chat.
   - Resume feedback and improvement suggestions.
   - Skill gap analysis.
   - Interview preparation.
   - 90-day career action planning.

2. JOB MATCHER
   - Provide or upload resume information.
   - Explore how skills relate to a target role.
   - Identify skills that may need further development.

3. FINANCIAL AID ASSISTANT
   - Estimate student financial aid eligibility using entered financial details.
   - Calculate monthly per-capita family income.
   - Display possible grant and loan guidance.
   - Show suggested supporting documents.

4. GRANT-TO-CAREER
   - Connect financial aid support with career opportunities.
   - Explore suggested work-study and career pathways.

5. SKILL CONSTELLATION
   - Generate a visual skill map using resume information and a target job.
   - Explore skill categories and development goals.
   - Track skill-related quests and progress.

6. BOUSSOLE GAME
   - Integrated Godot game experience.
   - Interactive career exploration.
   - Reload and fullscreen controls.

ADDITIONAL FEATURES
-------------------
- AI chat responses with streaming.
- PDF and TXT resume upload and text extraction.
- Conversation history management.
- Export and delete conversations.
- English, Traditional Chinese, and Simplified Chinese interface options.
- Light and dark themes.
- Password-protected access.

TECHNOLOGY
----------
- Python
- Flask
- Azure OpenAI
- OpenAI Python SDK
- PyPDF
- HTML, CSS, and JavaScript
- Tailwind CSS
- Godot
- JSON-based conversation storage

GETTING STARTED
---------------

REQUIREMENTS
- Python 3
- An Azure OpenAI resource and deployment
- Git

1. CLONE THE REPOSITORY

   git clone https://github.com/ImpulseDucky/BoussoleAI.git
   cd BoussoleAI

   Replace ImpulseDucky and the repository name with your GitHub details.

2. CREATE AND ACTIVATE A VIRTUAL ENVIRONMENT (macOS / Linux)

   python3 -m venv .venv
   source .venv/bin/activate

3. INSTALL THE PYTHON DEPENDENCIES

   pip install flask openai python-dotenv pypdf

4. CONFIGURE ENVIRONMENT VARIABLES

   Create a file named .env in the same directory as app.py.

   Add your own values:

   AZURE_OPENAI_ENDPOINT=your_azure_openai_endpoint
   AZURE_OPENAI_API_KEY=your_azure_openai_api_key
   AZURE_OPENAI_DEPLOYMENT_NAME=your_deployment_name
   APP_PASSWORD=your_secure_app_password
   FLASK_SECRET_KEY=your_random_secret_key

   Replace all placeholders with your own credentials. Generate a strong,
   random Flask secret key and keep all credentials private.

5. RUN THE APPLICATION

   python3 app.py

   Open this address in your browser:

   http://127.0.0.1:5001

   If app.py uses a different port, use the port configured in that file.

PROJECT STRUCTURE
-----------------
A simplified example of the project structure:

   BoussoleAI/
   |-- app.py
   |-- .env
   |-- .gitignore
   |-- README.txt
   |-- chat_storage.json
   |
   |-- boussole/
       |-- index.html
       |-- Godot game files and assets

Your actual folder structure may differ. Update this section to match the
files you include in your repository.

SECURITY
--------
- Keep API keys, passwords, and Flask secret keys in environment variables.
- Never commit your .env file to GitHub.
- Do not commit private conversation data or local runtime files.
- Use HTTPS and appropriate access controls when deploying the application.
- Review authentication and chat-data isolation before allowing unrestricted
  public or multi-user access.

IMPORTANT NOTES
---------------
- AI-generated career and resume suggestions may not always be accurate.
- Financial aid estimates are informational and should be checked against
  official government or university requirements.
- Career and job recommendations are guidance, not guarantees.
- Azure OpenAI credentials are required for AI-powered features.

PROJECT VISION
--------------
BoussoleAI aims to make career and academic planning more accessible by
combining AI guidance, practical tools, and interactive experiences.

Find your direction. Build your future.

LICENSE
-------
Keeping all rights reserved.
