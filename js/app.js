// Main Application Logic for NaviGo MVP (Backend Connected Wizard)

// --- Navigation & State ---
let currentWizardStep = 1;
const TOTAL_STEPS = 5;

function navigateTo(viewId) {
    // Hide all views
    document.querySelectorAll('.view').forEach(view => {
        view.classList.add('hidden');
        view.classList.remove('active');
    });
    
    // Show target view
    const target = document.getElementById(`view-${viewId}`);
    if (target) {
        target.classList.remove('hidden');
        target.classList.add('active');
    }
    
    // Specific logic per view
    if (viewId === 'tracker') {
        renderSavedJourneys();
    } else if (viewId === 'dashboard') {
        // Reset wizard state when returning to dashboard
        currentWizardStep = 1;
        document.getElementById('prompt-input').value = '';
    }
}

// --- Search / Intent Matching (Connects to FastAPI) ---
function handleEnter(e) {
    if (e.key === 'Enter') handleSearch();
}

async function handleSearch() {
    const input = document.getElementById('prompt-input').value.trim();
    if (!input) return;

    // Show loading state
    document.getElementById('dashboard-content').classList.add('hidden');
    document.getElementById('dashboard-loading').classList.remove('hidden');

    try {
        const currentLang = document.getElementById('language-switcher')?.value || 'en';
        // Send natural language query to the AI Backend
        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query: input, lang: currentLang })
        });
        
        if (!response.ok) throw new Error('Network response was not ok');
        
        const data = await response.json();
        
        // Hide loading
        document.getElementById('dashboard-loading').classList.add('hidden');
        document.getElementById('dashboard-content').classList.remove('hidden');
        
        // Start Wizard Flow
        renderWizardService(data);
    } catch (error) {
        console.error('Error fetching from backend:', error);
        alert("Failed to connect to the AI Backend. Ensure the server is running on localhost:8000.");
        
        // Revert UI
        document.getElementById('dashboard-loading').classList.add('hidden');
        document.getElementById('dashboard-content').classList.remove('hidden');
    }
}

let currentServiceId = null;
let currentServiceTitle = null;

function loadService(serviceId) {
    const quickQueries = {
        'fssai': 'I want to start a food business',
        'pmkisan': 'I want farming support',
        'nsp': 'I need a student scholarship',
        'udyam': 'I want to register my MSME business'
    };
    
    const query = quickQueries[serviceId];
    if (query) {
        document.getElementById('prompt-input').value = query;
        handleSearch();
    }
}

function startDocumentAnalysis() {
    currentServiceId = 'document-verification';
    currentServiceTitle = 'Document Verification';
    
    // Set step 1 name
    document.getElementById('wizard-service-title').textContent = 'Document Verification';
    
    // Reset Step 2 (Eligibility) and 3 (Documents) to be blank or generic
    document.getElementById('wizard-eligibility').innerHTML = '<li>Universal Eligibility Check</li>';
    document.getElementById('wizard-documents').innerHTML = '<p class="text-muted">Analyzing document...</p>';
    document.getElementById('wizard-timeline').innerHTML = '<div class="timeline-item"><div class="timeline-dot">1</div><div class="timeline-content">Upload your document.</div></div>';
    
    // Reset Step 5 (Document Analysis) UI
    document.getElementById('wizard-analysis-result').classList.add('hidden');
    document.getElementById('wizard-upload-zone').classList.remove('hidden');
    
    updateWizardUI(5);
    navigateTo('journey');
}

function renderWizardService(data) {
    currentServiceId = data.recommended_service.replace(/\s+/g, '-').toLowerCase();
    currentServiceTitle = data.recommended_service;

    // Step 1: Recommendation
    document.getElementById('wizard-service-title').textContent = data.recommended_service;
    const descEl = document.getElementById('wizard-service-desc');
    if (descEl) {
        descEl.textContent = data.description || 'Official government service registration.';
    }

    // Step 2: Eligibility
    const eligList = document.getElementById('wizard-eligibility');
    eligList.innerHTML = '';
    if (data.eligibility_criteria && Array.isArray(data.eligibility_criteria)) {
        data.eligibility_criteria.forEach(criterion => {
            const li = document.createElement('li');
            li.textContent = criterion;
            eligList.appendChild(li);
        });
    } else {
        const li = document.createElement('li');
        li.textContent = data.eligibility_status;
        eligList.appendChild(li);
    }

    // Step 3: Documents
    const docWrapper = document.getElementById('wizard-documents');
    docWrapper.innerHTML = '';
    data.required_documents.forEach((doc, idx) => {
        const docName = typeof doc === 'string' ? doc : doc.name;
        let displayName = docName;
        let displayDesc = "";
        if (docName.includes(":")) {
            const parts = docName.split(":");
            displayName = parts[0].trim();
            displayDesc = parts.slice(1).join(":").trim();
        }
        docWrapper.innerHTML += `
            <div class="checklist-item" style="align-items: flex-start; margin-bottom: 12px;">
                <input type="checkbox" id="wizard_doc_${idx}" style="margin-top: 4px;">
                <label for="wizard_doc_${idx}" style="margin-left: 8px; font-weight: normal; cursor: pointer;">
                    <strong>${displayName}</strong>
                    ${displayDesc ? `<br><span class="text-sm text-muted" style="display: block; margin-top: 4px; font-weight: 400; line-height: 1.4;">${displayDesc}</span>` : ''}
                </label>
            </div>
        `;
    });

    // Step 4: Action Plan
    const timeline = document.getElementById('wizard-timeline');
    timeline.innerHTML = '';
    data.action_plan.forEach((step, index) => {
        timeline.innerHTML += `
            <div class="timeline-item">
                <div class="timeline-dot">${index + 1}</div>
                <div class="timeline-content">${step}</div>
            </div>
        `;
    });

    // Reset document analysis step (Step 5)
    document.getElementById('wizard-analysis-result').classList.add('hidden');
    document.getElementById('wizard-upload-zone').classList.remove('hidden');

    // Reset and start wizard
    updateWizardUI(1);
    navigateTo('journey');
}

// --- Wizard Stepper Logic ---
function nextStep(targetStep) {
    if (targetStep <= TOTAL_STEPS) {
        updateWizardUI(targetStep);
    }
}

function prevStep(targetStep) {
    if (targetStep >= 1) {
        updateWizardUI(targetStep);
    }
}

function updateWizardUI(step) {
    currentWizardStep = step;

    // Update Steps display
    for (let i = 1; i <= TOTAL_STEPS; i++) {
        const stepContent = document.getElementById(`wizard-step-${i}`);
        const stepNav = document.getElementById(`step-nav-${i}`);
        
        if (i === step) {
            stepContent.classList.remove('hidden-step');
            stepContent.classList.add('active-step');
            stepNav.classList.add('active');
            stepNav.classList.remove('completed');
        } else {
            stepContent.classList.add('hidden-step');
            stepContent.classList.remove('active-step');
            stepNav.classList.remove('active');
            
            if (i < step) {
                stepNav.classList.add('completed');
            } else {
                stepNav.classList.remove('completed');
            }
        }
    }

    // Update Step Lines
    const lines = document.querySelectorAll('.step-line');
    lines.forEach((line, index) => {
        if (index < step - 1) {
            line.classList.add('completed');
        } else {
            line.classList.remove('completed');
        }
    });
}

// --- Document Analysis (Wizard Step 5) ---
async function handleWizardFileUpload(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Show loading inline
    document.getElementById('wizard-upload-zone').classList.add('hidden');
    document.getElementById('wizard-analysis-loading').classList.remove('hidden');

    const formData = new FormData();
    formData.append("file", file);

    try {
        const currentLang = document.getElementById('language-switcher')?.value || 'en';
        const response = await fetch(`/api/analyze_document?lang=${currentLang}`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error("Network response error");
        
        const data = await response.json();
        
        document.getElementById('wizard-analysis-loading').classList.add('hidden');
        document.getElementById('wizard-analysis-result').classList.remove('hidden');
        
        // Render backend issues and recommendations
        document.getElementById('wizard-analysis-issue').textContent = data.detected_issues[0] || "Issue detected in document.";
        
        const stepsList = document.getElementById('wizard-analysis-steps');
        stepsList.innerHTML = '';
        data.recommendations.forEach(rec => {
            const li = document.createElement('li');
            li.textContent = rec;
            stepsList.appendChild(li);
        });

    } catch (error) {
        console.error("Analysis Error:", error);
        alert("Failed to connect to the AI Backend Document Analyzer.");
        document.getElementById('wizard-analysis-loading').classList.add('hidden');
        document.getElementById('wizard-upload-zone').classList.remove('hidden');
    }
}

// --- Save Journey ---
// savedJourneys is already declared in mockData.js

function completeJourney() {
    if (!currentServiceId) return;
    
    // Check if already saved
    if (!savedJourneys.some(j => j.id === currentServiceId)) {
        savedJourneys.push({
            id: currentServiceId,
            title: currentServiceTitle,
            date: new Date().toLocaleDateString()
        });
    }

    alert("Journey Completed and Saved!");
    navigateTo('tracker');
}

function renderSavedJourneys() {
    const list = document.getElementById('journeys-list');
    const emptyState = document.getElementById('no-journeys');
    
    list.innerHTML = '';
    
    if (savedJourneys.length === 0) {
        list.classList.add('hidden');
        emptyState.classList.remove('hidden');
        return;
    }
    
    list.classList.remove('hidden');
    emptyState.classList.add('hidden');

    savedJourneys.forEach(journey => {
        list.innerHTML += `
            <div class="journey-item">
                <div>
                    <h4>${journey.title}</h4>
                    <p class="text-sm text-muted">Completed on: ${journey.date}</p>
                </div>
                <button class="btn-outline" onclick="navigateTo('dashboard')">New Search <i class="fa-solid fa-arrow-right"></i></button>
            </div>
        `;
    });
}

// --- i18n Language Switching ---
function changeLanguage(lang) {
    if (typeof translations !== 'undefined') {
        const texts = translations[lang] || translations['en'];
        
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            if (texts[key]) {
                if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                    el.placeholder = texts[key];
                } else {
                    el.textContent = texts[key];
                }
            }
        });

        // Translate elements with data-i18n-placeholder specifically if any
        document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            const key = el.getAttribute('data-i18n-placeholder');
            if (texts[key]) {
                el.placeholder = texts[key];
            }
        });
    }
}

window.onload = () => {
    // Default initialization
    const currentLang = document.getElementById('language-switcher')?.value || 'en';
    changeLanguage(currentLang);
};
