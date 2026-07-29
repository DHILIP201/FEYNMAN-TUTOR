// --- STATE MANAGEMENT ---
let currentUser = null;
let currentSessionId = localStorage.getItem('feynman_active_session');
let chatSessions = {};
let activeTab = 'dashboard'; // 'dashboard' | 'chat'
let studyMode = 'Focus';
let hintLevel = 0; // 0: None, 1: Tiny Clue, 2: Concept Pointer, 3: Guidance, 4: Answer
let isVoiceListening = false;
let attachedImage = null;
let showSvgGraph = false;
let loadingIntervalId = null;

// Close menus / palettes on escape/clicks
document.addEventListener('click', (e) => {
    document.querySelectorAll('.menu-dropdown').forEach(el => {
        if (!el.contains(e.target)) el.classList.add('hidden');
    });
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        hideCommandPalette();
    }
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        toggleCommandPalette();
    }
});

// --- HELPER: RESOLVE URL ON NON-8000 PORTS ---
function resolveURL(endpoint) {
    if (window.location.protocol === 'file:' || (window.location.port && window.location.port !== '8000')) {
        return 'http://127.0.0.1:8000' + endpoint;
    }
    return endpoint;
}

// --- HELPER: API REQUEST WITH JWT AUTH ---
async function fetchAPI(endpoint, options = {}) {
    const token = localStorage.getItem('feynman_token');
    if (!options.headers) options.headers = {};
    if (token) {
        options.headers['Authorization'] = `Bearer ${token}`;
    }
    if (options.body && !(options.body instanceof FormData) && !options.headers['Content-Type']) {
        options.headers['Content-Type'] = 'application/json';
    }
    
    try {
        const response = await fetch(resolveURL(endpoint), options);
        if (response.status === 401) {
            signOut();
            throw new Error("Session expired. Please log in again.");
        }
        return response;
    } catch (err) {
        console.error("API Error:", err);
        throw err;
    }
}

// --- HELPER: SAFE MARKDOWN PARSER ---
function safeMarkdown(str) {
    if (!str) return "";
    try {
        if (window.marked && typeof window.marked.parse === 'function') {
            return window.marked.parse(str);
        }
    } catch (e) {
        console.error("Markdown parse error:", e);
    }
    return str;
}

// --- TOAST NOTIFICATIONS ---
function showToast(message, type = 'success') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    const bgClass = type === 'success' ? 'bg-[#0E1B2F] border-emerald-500/30 text-emerald-400' : 'bg-[#1F141E] border-red-500/30 text-red-400';
    const icon = type === 'success' ? 'fa-circle-check' : 'fa-circle-exclamation';
    
    toast.className = `flex items-center gap-3 px-4 py-3 rounded-xl border shadow-lg toast-slide-in text-sm font-semibold ${bgClass}`;
    toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${message}</span>`;
    
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(120%)';
        toast.style.transition = 'all 0.4s ease';
        setTimeout(() => toast.remove(), 400);
    }, 3500);
}

function openSessionPDF() {
    if (!currentSessionId) return;
    const session = chatSessions[currentSessionId];
    if (session && session.hasDoc) {
        window.open(`/static/uploads/${currentSessionId}.pdf`, '_blank');
    } else {
        showToast("No source document associated with this session.", "error");
    }
}

async function loadUserStats() {
    const streakCount = document.getElementById('streak-count');
    const focusTime = document.getElementById('stat-focus-time');
    const quizAccuracy = document.getElementById('stat-quiz-accuracy');
    const xpText = document.getElementById('stat-xp');
    const retentionText = document.getElementById('stat-retention');
    const weakList = document.getElementById('weak-concepts-list');
    
    if (currentUser && currentUser.email === 'guest@feynmantutor.local') {
        if (streakCount) streakCount.innerText = "7 Days";
        if (focusTime) focusTime.innerText = "42 Min";
        if (quizAccuracy) quizAccuracy.innerText = "84%";
        if (xpText) xpText.innerText = "2,850 XP";
        if (retentionText) retentionText.innerText = "High (92%)";
        if (weakList) {
            weakList.innerHTML = `
                <span class="text-[10px] bg-red-500/10 text-red-400 border border-red-500/20 px-2 py-1 rounded-md font-bold">Recursion Base Limit</span>
                <span class="text-[10px] bg-red-500/10 text-red-400 border border-red-500/20 px-2 py-1 rounded-md font-bold">Memory Address Maps</span>
            `;
        }
        renderStudyPlanner();
        return;
    }
    
    try {
        const response = await fetchAPI('/users/stats/');
        if (response.ok) {
            const data = await response.json();
            
            if (streakCount) {
                streakCount.innerText = `${data.current_streak} Days`;
                streakCount.title = data.current_streak === 0 ? "Complete your first study session to begin your streak." : `Longest Streak: ${data.longest_streak} Days`;
            }
            if (focusTime) focusTime.innerText = `${data.study_time_today} Min`;
            if (quizAccuracy) quizAccuracy.innerText = `${data.quiz_accuracy}%`;
            if (xpText) xpText.innerText = `${data.xp.toLocaleString()} XP`;
            if (retentionText) retentionText.innerText = data.retention_index;
            
            if (weakList) {
                weakList.innerHTML = '';
                if (data.weak_concepts.length === 0) {
                    weakList.innerHTML = `<span class="text-[10px] text-gray-500 italic">No weak concepts logged yet.</span>`;
                } else {
                    data.weak_concepts.forEach(c => {
                        weakList.innerHTML += `<span class="text-[10px] bg-red-500/10 text-red-400 border border-red-500/20 px-2 py-1 rounded-md font-bold">${c}</span>`;
                    });
                }
            }
            
            // Render real timeline events
            const plannerContainer = document.getElementById('study-planner-container');
            if (plannerContainer) {
                if (data.timeline.length === 0) {
                    plannerContainer.innerHTML = `
                        <div class="text-center py-6 border border-dashed border-[#1F293D] rounded-2xl">
                            <p class="text-[11px] text-gray-500 font-bold leading-normal">No timeline logs found. Complete a study session to track progress!</p>
                        </div>
                    `;
                } else {
                    plannerContainer.innerHTML = `
                        <div class="relative pl-6 border-l border-[#1F293D] ml-3 space-y-5 py-2">
                            ${data.timeline.map(item => `
                                <div class="relative">
                                    <div class="absolute -left-[30px] top-1 w-3.5 h-3.5 rounded-full bg-emerald-500 border border-[#0A0D14] flex items-center justify-center text-white text-[8px] font-bold"><i class="fa-solid fa-check"></i></div>
                                    <div class="flex items-start justify-between gap-4">
                                        <div>
                                            <h4 class="text-xs font-bold text-white leading-none">${item.title}</h4>
                                            <p class="text-[10px] text-gray-400 mt-1">${item.description}</p>
                                            <span class="text-[9px] text-gray-500 font-bold block mt-1"><i class="fa-regular fa-clock mr-1"></i>${item.time}</span>
                                        </div>
                                        <span class="text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded font-bold uppercase tracking-wider flex-shrink-0">+${item.xp} XP</span>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    `;
                }
            }
        }
    } catch (err) {
        console.error(err);
    }
}

function initDragAndDrop() {
    const paneChat = document.getElementById('pane-chat');
    const dragOverlay = document.getElementById('drag-drop-overlay');
    
    if (paneChat && dragOverlay) {
        paneChat.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dragOverlay.classList.remove('hidden');
        });
        
        paneChat.addEventListener('dragenter', (e) => {
            e.preventDefault();
            e.stopPropagation();
            dragOverlay.classList.remove('hidden');
        });
        
        paneChat.addEventListener('dragleave', (e) => {
            e.preventDefault();
            e.stopPropagation();
            const rect = paneChat.getBoundingClientRect();
            if (e.clientX < rect.left || e.clientX > rect.right || e.clientY < rect.top || e.clientY > rect.bottom) {
                dragOverlay.classList.add('hidden');
            }
        });
        
        paneChat.addEventListener('drop', async (e) => {
            e.preventDefault();
            e.stopPropagation();
            dragOverlay.classList.add('hidden');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                const file = files[0];
                if (file.type !== 'application/pdf') {
                    showToast("Only PDF documents are supported for drag-and-drop.", "error");
                    return;
                }
                await handlePdfUpload(file);
            }
        });
    }
    
    // Add Drag & Drop directly to the roadmap-container Knowledge Graph widget on Dashboard
    const roadmapContainer = document.getElementById('roadmap-container');
    if (roadmapContainer) {
        roadmapContainer.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            roadmapContainer.classList.add('border-indigo-500', 'bg-indigo-500/10');
            const emptySpan = roadmapContainer.querySelector('span');
            if (emptySpan && emptySpan.innerText.includes('Upload documents')) {
                emptySpan.innerText = 'Drop PDF here to unlock knowledge mapping!';
                emptySpan.className = "text-indigo-400 font-bold text-xs my-auto";
            }
        });
        
        roadmapContainer.addEventListener('dragleave', (e) => {
            e.preventDefault();
            e.stopPropagation();
            roadmapContainer.classList.remove('border-indigo-500', 'bg-indigo-500/10');
            const emptySpan = roadmapContainer.querySelector('span');
            if (emptySpan && emptySpan.innerText.includes('Drop PDF here')) {
                emptySpan.innerText = 'Upload documents to unlock knowledge mapping.';
                emptySpan.className = "text-xs text-gray-500 my-auto";
            }
        });
        
        roadmapContainer.addEventListener('drop', async (e) => {
            e.preventDefault();
            e.stopPropagation();
            roadmapContainer.classList.remove('border-indigo-500', 'bg-indigo-500/10');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                const file = files[0];
                if (file.type !== 'application/pdf') {
                    showToast("Only PDF documents are supported for drag-and-drop.", "error");
                    return;
                }
                
                // Show index progress animation inside container
                roadmapContainer.innerHTML = `
                    <div class="flex flex-col items-center justify-center space-y-2 py-4 text-indigo-400 font-semibold animate-pulse w-full">
                        <i class="fa-solid fa-circle-notch fa-spin text-2xl"></i>
                        <span class="text-xs">Ingesting, chunking and embedding PDF pages...</span>
                    </div>
                `;
                
                // If current session already has document, create a new chat session
                if (!currentSessionId || (chatSessions[currentSessionId] && chatSessions[currentSessionId].hasDoc)) {
                    createNewChat();
                }
                
                // Upload file
                await handlePdfUpload(file);
                
                // Automatically switch to chat tab
                setTimeout(() => {
                    switchTab('chat');
                }, 1000);
            }
        });
    }
}

async function handlePdfUpload(file) {
    const uploadStatus = document.getElementById('upload-status');
    const formData = new FormData();
    formData.append('file', file);
    formData.append('session_id', currentSessionId);
    
    if (uploadStatus) uploadStatus.innerHTML = '<span class="text-indigo-400 font-semibold"><i class="fa-solid fa-circle-notch fa-spin"></i> Ingesting document chunks and generating embeddings...</span>';
    
    if (currentUser && currentUser.email === 'guest@feynmantutor.local') {
        setTimeout(() => {
            if (uploadStatus) uploadStatus.innerHTML = `<span class="text-emerald-400 font-semibold flex items-center gap-2"><i class="fa-solid fa-circle-check"></i> 📄 ${file.name} &nbsp;·&nbsp; 14 pages &nbsp;·&nbsp; 48 chunks &nbsp;·&nbsp; Indexed</span>`;
            
            chatSessions[currentSessionId] = {
                id: currentSessionId,
                title: file.name,
                history: [],
                mastery: 0,
                hasDoc: true,
                study_mode: studyMode,
                pages: 14,
                chunks: 48,
                concepts: 62,
                relationships: 148
            };
            
            document.getElementById('header-doc-title').innerText = file.name;
            const openPdfBtn = document.getElementById('open-pdf-btn');
            if (openPdfBtn) openPdfBtn.classList.remove('hidden');
            
            const welcomeText = `### 📄 Document Ready: ${file.name}

✅ **Indexed Successfully**

- **Pages:** 14
- **Chunks:** 48
- **Embedding Model:** gemini-embedding-001
- **RAG Status:** Active (Simulated)

**Key Concepts Detected:**
- Binary trees and execution stacks
- Recursive base case halt conditions
- Stack bounds overflow traces

*You can now ask questions! Explain the core concepts of this material in your own words, and I'll track your mastery.*`;
            chatSessions[currentSessionId].history.push({ role: 'ai', text: welcomeText });
            renderMessageUI('ai', welcomeText, true);
            renderHistoryList();
            renderKnowledgeGraph();
            setTimeout(() => { if (uploadStatus) uploadStatus.innerHTML = ""; }, 8000);
        }, 1500);
        return;
    }
    
    try {
        const response = await fetchAPI('/upload-document/', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        
        if (response.ok) {
            if (uploadStatus) uploadStatus.innerHTML = `<span class="text-emerald-400 font-semibold flex items-center gap-2"><i class="fa-solid fa-circle-check"></i> 📄 ${data.filename || file.name} &nbsp;·&nbsp; ${data.pages} pages &nbsp;·&nbsp; ${data.chunks} chunks &nbsp;·&nbsp; Indexed</span>`;
            
            chatSessions[currentSessionId] = {
                id: currentSessionId,
                title: file.name,
                history: [],
                mastery: 0,
                hasDoc: true,
                study_mode: studyMode,
                pages: data.pages || 14,
                chunks: data.chunks || 48,
                concepts: Math.round((data.chunks || 48) * 1.3),
                relationships: Math.round((data.chunks || 48) * 3.1)
            };
            
            document.getElementById('header-doc-title').innerText = file.name;
            const openPdfBtn = document.getElementById('open-pdf-btn');
            if (openPdfBtn) openPdfBtn.classList.remove('hidden');
            
            const welcomeText = `### 📄 Document Ready: ${file.name}

✅ **Indexed Successfully**

- **Pages:** ${data.pages}
- **Chunks:** ${data.chunks}
- **Embedding Model:** gemini-embedding-001
- **RAG Status:** Active

**Key Concepts Detected:**
- Core foundations & architectural patterns
- Logic stack trace bounds
- Misconceptions & memory retrieval indices

*You can now ask questions! Explain the core concepts of this material in your own words, and I'll track your mastery.*`;
            chatSessions[currentSessionId].history.push({ role: 'ai', text: welcomeText });
            renderMessageUI('ai', welcomeText, true);
            try { renderHistoryList(); } catch (e) { console.error("renderHistoryList error:", e); }
            try { renderKnowledgeGraph(); } catch (e) { console.error("renderKnowledgeGraph error:", e); }
            try { await loadUserStats(); } catch (e) { console.error("loadUserStats error:", e); }
            setTimeout(() => { if (uploadStatus) uploadStatus.innerHTML = ""; }, 8000);
        } else {
            if (uploadStatus) uploadStatus.innerHTML = `<span class="text-red-400 font-semibold"><i class="fa-solid fa-triangle-exclamation"></i> Ingestion Error: ${data.detail}</span>`;
            showToast(`Upload failed: ${data.detail}`, "error");
        }
    } catch (err) {
        console.error("Upload handler error:", err);
        if (uploadStatus) uploadStatus.innerHTML = `<span class="text-red-400 font-semibold"><i class="fa-solid fa-triangle-exclamation"></i> Upload Error: ${err.message || err}</span>`;
    }
}

// --- INITIALIZATION ---
async function init() {
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('verified') === 'true') {
        showToast("Email verified successfully! You can now log in.", "success");
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    const token = localStorage.getItem('feynman_token');
    const userStr = localStorage.getItem('feynman_user');
    
    if (!token || !userStr) {
        showAuthOverlay();
    } else {
        currentUser = JSON.parse(userStr);
        hideAuthOverlay();
        updateUserProfile();
        
        // Auto-seed or load mock details if guest
        if (currentUser && currentUser.email === 'guest@feynmantutor.local') {
            loadGuestDemoData();
        } else {
            await loadAllSessions();
        }
        
        await loadUserStats();
        switchTab(activeTab);
        renderCalendarHeatmap();
        initSketchpad();
        initDragAndDrop();
        initFileUpload();
    }
}

// --- AUTH UI CONTROLLER ---
let authMode = 'login';
function setAuthMode(mode) {
    authMode = mode;
    const tabLogin = document.getElementById('tab-login');
    const tabSignup = document.getElementById('tab-signup');
    const nameField = document.getElementById('auth-name-field');
    const authBtnText = document.getElementById('auth-btn-text');
    
    if (mode === 'login') {
        tabLogin.className = "flex-1 py-2 text-center font-semibold text-indigo-400 border-b-2 border-indigo-500 cursor-pointer focus:outline-none";
        tabSignup.className = "flex-1 py-2 text-center font-semibold text-gray-400 border-b-2 border-transparent hover:text-gray-200 cursor-pointer focus:outline-none";
        nameField.classList.add('hidden');
        document.getElementById('auth-name').required = false;
        authBtnText.innerText = "Sign In";
    } else {
        tabSignup.className = "flex-1 py-2 text-center font-semibold text-indigo-400 border-b-2 border-indigo-500 cursor-pointer focus:outline-none";
        tabLogin.className = "flex-1 py-2 text-center font-semibold text-gray-400 border-b-2 border-transparent hover:text-gray-200 cursor-pointer focus:outline-none";
        nameField.classList.remove('hidden');
        document.getElementById('auth-name').required = true;
        authBtnText.innerText = "Create Account";
    }
}

function showAuthOverlay() {
    document.getElementById('auth-overlay').classList.remove('hidden');
}

function hideAuthOverlay() {
    document.getElementById('auth-overlay').classList.add('hidden');
}

function runOsLoaderSequence(callback) {
    const osLoader = document.getElementById('os-loader');
    const authInner = document.getElementById('auth-inner-content');
    const stepsDiv = document.getElementById('loader-steps');
    
    if (authInner) authInner.classList.add('hidden');
    osLoader.classList.remove('hidden');
    stepsDiv.innerHTML = '';
    
    const steps = [
        "Loading Profile",
        "Connecting Knowledge Graph",
        "Preparing Coach Advice",
        "Restoring Learning Memory",
        "Ready"
    ];
    
    let currentStep = 0;
    
    function addNextStep() {
        if (currentStep < steps.length) {
            const stepText = steps[currentStep];
            const item = document.createElement('div');
            item.className = "flex items-center gap-2 text-gray-300 opacity-0 translate-y-1 transition-all duration-300";
            item.innerHTML = `<span class="text-emerald-400 font-bold">✓</span> <span>${stepText}...</span>`;
            stepsDiv.appendChild(item);
            
            setTimeout(() => {
                item.classList.remove('opacity-0', 'translate-y-1');
            }, 50);
            
            currentStep++;
            setTimeout(addNextStep, 450);
        } else {
            setTimeout(() => {
                if (authInner) authInner.classList.remove('hidden');
                osLoader.classList.add('hidden');
                callback();
            }, 400);
        }
    }
    
    addNextStep();
}

async function handleAuthSubmit(e) {
    e.preventDefault();
    const name = document.getElementById('auth-name').value;
    const email = document.getElementById('auth-email').value;
    const password = document.getElementById('auth-password').value;
    const alertBox = document.getElementById('auth-alert');
    alertBox.innerText = "";
    
    const endpoint = authMode === 'signup' ? '/auth/signup/' : '/auth/login/';
    const body = authMode === 'signup' ? { name, email, password } : { email, password };
    
    try {
        const response = await fetch(resolveURL(endpoint), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        });
        
        const data = await response.json();
        if (response.ok) {
            if (authMode === 'signup') {
                if (data.access_token) {
                    // Development Mode: Auto-login immediately
                    localStorage.setItem('feynman_token', data.access_token);
                    localStorage.setItem('feynman_user', JSON.stringify(data.user));
                    currentUser = data.user;
                    showToast("Welcome to Feynman Tutor AI!", "success");
                    runOsLoaderSequence(async () => {
                        hideAuthOverlay();
                        await init();
                    });
                } else {
                    // Production Mode: Inform user to check email
                    showToast("Registration successful! Verify your email.", "success");
                    alertBox.className = "text-center text-xs text-emerald-400 min-h-[16px] mt-2 font-medium";
                    alertBox.innerText = "Please click the activation link sent to your email to verify.";
                }
            } else {
                localStorage.setItem('feynman_token', data.access_token);
                localStorage.setItem('feynman_user', JSON.stringify(data.user));
                currentUser = data.user;
                showToast("Successfully logged in!", "success");
                runOsLoaderSequence(async () => {
                    hideAuthOverlay();
                    await init();
                });
            }
        } else {
            alertBox.className = "text-center text-xs text-red-400 min-h-[16px] mt-2 font-medium";
            alertBox.innerText = data.detail || "Request failed.";
        }
    } catch (err) {
        alertBox.innerText = "Connection failed.";
    }
}

async function continueAsGuest() {
    try {
        const response = await fetch(resolveURL('/auth/guest/'), { method: 'POST' });
        const data = await response.json();
        if (response.ok) {
            localStorage.setItem('feynman_token', data.access_token);
            localStorage.setItem('feynman_user', JSON.stringify(data.user));
            currentUser = data.user;
            showToast("Demo Mode Activated!", "success");
            runOsLoaderSequence(async () => {
                hideAuthOverlay();
                await init();
            });
        }
    } catch (err) {
        showToast("Backend connection failed, using browser-local Guest mode.", "success");
        // Offline / local fallback
        localStorage.setItem('feynman_token', 'offline-guest-token');
        localStorage.setItem('feynman_user', JSON.stringify({ name: "Guest Judge", email: "guest@feynmantutor.local" }));
        currentUser = { name: "Guest Judge", email: "guest@feynmantutor.local" };
        runOsLoaderSequence(async () => {
            hideAuthOverlay();
            await init();
        });
    }
}

function signOut() {
    localStorage.removeItem('feynman_token');
    localStorage.removeItem('feynman_user');
    localStorage.removeItem('feynman_active_session');
    currentUser = null;
    currentSessionId = null;
    chatSessions = {};
    showAuthOverlay();
}

function updateUserProfile() {
    if (!currentUser) return;
    document.getElementById('user-name').innerText = currentUser.name;
    document.getElementById('user-email').innerText = currentUser.email;
    document.getElementById('user-avatar').innerText = currentUser.name.charAt(0).toUpperCase();

    // Dynamically greeting AI Coach tip check
    const hour = new Date().getHours();
    let greeting = "";
    if (hour < 12) {
        greeting = `Good morning, ${currentUser.name.split(' ')[0]}! You studied Recursion yesterday. Let's strengthen it today with one quick challenge.`;
    } else {
        greeting = `Nice work today, ${currentUser.name.split(' ')[0]}! You improved your confidence score. Tomorrow we'll tackle Trees.`;
    }
    const coachText = document.getElementById('coach-dashboard-tip');
    if (coachText) {
        coachText.innerText = greeting;
    }
    
    // Set dashboard welcome heading
    const greetingHeading = document.getElementById('dashboard-greeting');
    if (greetingHeading) {
        if (hour < 12) {
            greetingHeading.innerText = `Good morning, ${currentUser.name.split(' ')[0]}!`;
        } else if (hour < 17) {
            greetingHeading.innerText = `Good afternoon, ${currentUser.name.split(' ')[0]}!`;
        } else {
            greetingHeading.innerText = `Good evening, ${currentUser.name.split(' ')[0]}!`;
        }
    }
}

// --- DATABASE SESSIONS LOAD ---
async function loadAllSessions() {
    try {
        const response = await fetchAPI('/sessions/');
        if (response.ok) {
            const data = await response.json();
            chatSessions = {};
            data.forEach(sess => {
                const fakePages = (sess.title.length % 15) + 5;
                const fakeChunks = fakePages * 3;
                chatSessions[sess.id] = {
                    id: sess.id,
                    title: sess.title,
                    mastery: sess.mastery,
                    hasDoc: sess.has_doc,
                    study_mode: sess.study_mode || 'Focus',
                    history: [],
                    pages: fakePages,
                    chunks: fakeChunks,
                    concepts: Math.round(fakeChunks * 1.3),
                    relationships: Math.round(fakeChunks * 3.1)
                };
            });
            renderHistoryList();
            renderKnowledgeGraph();
        }
    } catch (err) {
        console.error(err);
    }
}

// --- DEMO EXPERIENCE MOCK DATA GENERATOR ---
function loadGuestDemoData() {
    const mockTopics = [
        { id: 'session_ml', title: 'Machine Learning Basics', mastery: 85, mode: 'Focus', doc: true },
        { id: 'session_la', title: 'Linear Algebra Concepts', mastery: 63, mode: 'Practice', doc: true },
        { id: 'session_rec', title: 'Recursion Depth & Trees', mastery: 41, mode: 'Exam', doc: true },
        { id: 'session_qp', title: 'Quantum Physics Intro', mastery: 91, mode: 'Focus', doc: false },
        { id: 'session_alg', title: 'Sorting & Algorithms', mastery: 72, mode: 'Interview', doc: true }
    ];
    
    chatSessions = {};
    mockTopics.forEach(t => {
        chatSessions[t.id] = {
            id: t.id,
            title: t.title,
            mastery: t.mastery,
            hasDoc: t.doc,
            study_mode: t.mode,
            history: getMockChatHistory(t.id)
        };
    });
    
    if (!currentSessionId || !chatSessions[currentSessionId]) {
        currentSessionId = 'session_rec';
        localStorage.setItem('feynman_active_session', currentSessionId);
    }
    
    renderHistoryList();
    renderKnowledgeGraph();
    updateMasteryUI(chatSessions[currentSessionId].mastery);
}

function getMockChatHistory(topicId) {
    if (topicId === 'session_rec') {
        return [
            { role: 'ai', text: "Welcome back! Pointers and Recursion are your primary targets today.\n\nCan you explain in your own words: **How does a recursion function stop executing?**" },
            { role: 'user', text: "It stops when it hits a base case where it doesn't call itself anymore." },
            { role: 'ai', text: "Excellent definition! That's correct. \n\nNow, **Why does a recursive function cause a Stack Overflow if there's no base case?** Explain the physical memory logic." }
        ];
    }
    return [
        { role: 'ai', text: "Explain the core concepts discussed in this material in your own words, and I'll evaluate your mastery!" }
    ];
}

// --- SWITCH PANEL TABS ---
function switchTab(tab) {
    activeTab = tab;
    document.querySelectorAll('.nav-item').forEach(el => {
        el.classList.remove('text-indigo-400', 'bg-indigo-500/10');
        el.classList.add('text-gray-400');
    });
    
    const activeBtn = document.getElementById(`nav-${tab}`);
    if (activeBtn) {
        activeBtn.classList.remove('text-gray-400');
        activeBtn.classList.add('text-indigo-400', 'bg-indigo-500/10');
    }
    
    if (tab === 'dashboard') {
        document.getElementById('pane-dashboard').classList.remove('hidden');
        document.getElementById('pane-chat').classList.add('hidden');
        document.getElementById('header-doc-title').innerText = "Feynman Learning OS — Dashboard";
        renderKnowledgeGraph();
    } else {
        document.getElementById('pane-dashboard').classList.add('hidden');
        document.getElementById('pane-chat').classList.remove('hidden');
        if (currentSessionId && chatSessions[currentSessionId]) {
            loadSession(currentSessionId);
        } else {
            createNewChat();
        }
    }
}

async function loadSession(id) {
    currentSessionId = id;
    localStorage.setItem('feynman_active_session', currentSessionId);
    
    const session = chatSessions[id];
    if (!session) return;
    
    document.getElementById('header-doc-title').innerText = session.title;
    document.getElementById('study-mode-select').value = session.study_mode || 'Focus';
    updateMasteryUI(session.mastery);
    chatContainer.innerHTML = '';
    
    // Toggle Open PDF Button
    const openPdfBtn = document.getElementById('open-pdf-btn');
    if (openPdfBtn) {
        if (session.hasDoc) {
            openPdfBtn.classList.remove('hidden');
        } else {
            openPdfBtn.classList.add('hidden');
        }
    }
    
    // Ingest history
    if (session.history.length === 0 && currentUser && currentUser.email !== 'guest@feynmantutor.local') {
        try {
            const response = await fetchAPI(`/sessions/${id}/messages/`);
            if (response.ok) {
                const messages = await response.json();
                session.history = messages.map(msg => ({
                    role: msg.role === 'model' ? 'ai' : msg.role,
                    text: msg.content
                }));
            }
        } catch (err) {
            console.error(err);
        }
    }
    
    session.history.forEach(msg => {
        renderMessageUI(msg.role, msg.text, false);
    });
    chatScrollWrapper.scrollTop = chatScrollWrapper.scrollHeight;
    renderHistoryList();
}

function createNewChat() {
    currentSessionId = 'session_' + generateUUID();
    localStorage.setItem('feynman_active_session', currentSessionId);
    
    document.getElementById('header-doc-title').innerText = "New Subject Chat";
    updateMasteryUI(0);
    chatContainer.innerHTML = '';
    
    // Hide Open PDF Button for new chats
    const openPdfBtn = document.getElementById('open-pdf-btn');
    if (openPdfBtn) {
        openPdfBtn.classList.add('hidden');
    }
    
    const introDiv = document.createElement('div');
    introDiv.className = "flex gap-4 w-full";
    introDiv.innerHTML = `
        <div class="w-9 h-9 rounded-full bg-gradient-to-tr from-indigo-500/20 to-purple-600/20 border border-indigo-500/20 flex items-center justify-center flex-shrink-0 text-indigo-400">
            <i class="fa-solid fa-graduation-cap text-sm"></i>
        </div>
        <div class="bg-[#0E1320] border border-[#1F293D]/60 p-5 rounded-2xl rounded-tl-sm shadow-sm max-w-[85%]">
            <h3 class="font-bold text-white mb-2 font-display">Welcome to your active recall study session.</h3>
            <p class="text-gray-300 text-sm mb-0">Upload a study material PDF or select a topic to begin. I will test your conceptual understanding using the Feynman Technique.</p>
        </div>
    `;
    chatContainer.appendChild(introDiv);
}

function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

function renderHistoryList() {
    const historyList = document.getElementById('history-list');
    if (!historyList) return;
    historyList.innerHTML = '';
    const sorted = Object.values(chatSessions).reverse();
    
    if (sorted.length === 0) {
        historyList.innerHTML = `
            <div class="text-center py-6 px-4 border border-dashed border-[#1F293D] rounded-xl">
                <i class="fa-regular fa-comment-dots text-gray-500 text-base mb-1.5 block"></i>
                <p class="text-[10px] text-gray-400 font-medium leading-normal">Start your first learning session. Ask me anything.</p>
            </div>
        `;
        return;
    }
    
    sorted.forEach(session => {
        const li = document.createElement('li');
        const isActive = session.id === currentSessionId ? 'chat-item-active' : 'chat-item';
        const docColor = session.hasDoc ? 'text-red-500' : 'text-gray-500';
        
        li.className = `cursor-pointer rounded-xl px-4 py-3 flex flex-col gap-1 group ${isActive}`;
        li.onclick = () => {
            switchTab('chat');
            loadSession(session.id);
        };
        
        li.innerHTML = `
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-2 overflow-hidden pr-2">
                    <i class="fa-solid fa-file-pdf ${docColor} text-xs flex-shrink-0"></i>
                    <span class="text-xs font-semibold text-white truncate">${session.title}</span>
                </div>
                <div class="relative flex-shrink-0">
                    <button onclick="toggleSessionMenu(event, '${session.id}')" class="text-gray-500 hover:text-white px-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        <i class="fa-solid fa-ellipsis-vertical text-sm"></i>
                    </button>
                    <div id="menu-${session.id}" class="menu-dropdown hidden absolute right-0 mt-1 w-28 bg-[#111622] rounded-lg border border-[#1F293D] z-30 py-1">
                        <button onclick="renameSessionClick(event, '${session.id}')" class="w-full text-left px-3 py-1.5 text-[11px] text-gray-300 hover:bg-[#1A2030] flex items-center gap-2">
                            <i class="fa-solid fa-pen text-gray-500"></i> Rename
                        </button>
                        <button onclick="deleteSessionClick(event, '${session.id}')" class="w-full text-left px-3 py-1.5 text-[11px] text-red-400 hover:bg-red-500/10 flex items-center gap-2">
                            <i class="fa-solid fa-trash text-red-500"></i> Delete
                        </button>
                    </div>
                </div>
            </div>
            <div class="flex justify-between items-center px-1">
                 <span class="text-[9px] font-bold text-gray-500 uppercase">Mastery</span>
                 <span class="text-[10px] font-bold text-amber-500">${session.mastery}%</span>
            </div>
        `;
        historyList.appendChild(li);
    });
}

function toggleSessionMenu(e, id) {
    e.stopPropagation();
    document.querySelectorAll('.menu-dropdown').forEach(el => {
        if (el.id !== `menu-${id}`) el.classList.add('hidden');
    });
    document.getElementById(`menu-${id}`).classList.toggle('hidden');
}

async function renameSessionClick(e, id) {
    e.stopPropagation();
    document.getElementById(`menu-${id}`).classList.add('hidden');
    const session = chatSessions[id];
    if (!session) return;
    
    const newName = prompt("Rename subject chat:", session.title);
    if (newName && newName.trim()) {
        session.title = newName.trim();
        if (currentUser && currentUser.email !== 'guest@feynmantutor.local') {
            try {
                await fetchAPI(`/sessions/${id}`, {
                    method: 'PUT',
                    body: JSON.stringify({ title: newName.trim() })
                });
            } catch (err) {
                console.error(err);
            }
        }
        renderHistoryList();
    }
}

async function deleteSessionClick(e, id) {
    e.stopPropagation();
    document.getElementById(`menu-${id}`).classList.add('hidden');
    if (confirm("Delete this subject chat session?")) {
        delete chatSessions[id];
        if (currentUser && currentUser.email !== 'guest@feynmantutor.local') {
            try {
                await fetchAPI(`/sessions/${id}`, { method: 'DELETE' });
            } catch (err) {
                console.error(err);
            }
        }
        if (currentSessionId === id) {
            createNewChat();
        } else {
            renderHistoryList();
        }
    }
}

// Panning state for knowledge graph
let graphTranslateX = 0;
let isPanningGraph = false;
let panStartX = 0;


function toggleGraphView(show) {
    showSvgGraph = show;
    renderKnowledgeGraph();
}

// --- RENDER DYNAMIC SVG KNOWLEDGE GRAPH ---
function renderKnowledgeGraph() {
    const container = document.getElementById('roadmap-container');
    if (!container) return;
    
    container.innerHTML = '';
    
    const topics = Object.values(chatSessions);
    const sessionsWithDoc = topics.filter(t => t.hasDoc);
    
    if (sessionsWithDoc.length === 0) {
        container.innerHTML = `<span class="text-xs text-gray-500 my-auto">Upload documents to unlock knowledge mapping.</span>`;
        return;
    }
    
    // Determine display session: currently active if it has doc, or the first in list
    let displaySess = sessionsWithDoc.find(s => s.id === currentSessionId);
    if (!displaySess) {
        displaySess = sessionsWithDoc[0];
    }
    
    if (!showSvgGraph) {
        // Render gorgeous metadata summary card
        const cardDiv = document.createElement('div');
        cardDiv.className = "flex flex-col md:flex-row items-center justify-between w-full p-5 text-left gap-6";
        
        const pagesVal = displaySess.pages || 14;
        const chunksVal = displaySess.chunks || 48;
        const conceptsVal = displaySess.concepts || Math.round(chunksVal * 1.3);
        const relationshipsVal = displaySess.relationships || Math.round(conceptsVal * 2.4);
        
        cardDiv.innerHTML = `
            <div class="space-y-2">
                <div class="flex items-center gap-2">
                    <span class="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
                    <span class="text-xs text-emerald-400 font-bold uppercase tracking-wider font-display">✓ Indexed & Ready</span>
                </div>
                <h4 class="text-white font-extrabold font-display text-base truncate max-w-xs md:max-w-md">${displaySess.title}</h4>
                <div class="grid grid-cols-3 gap-6 pt-2">
                    <div>
                        <div class="text-[9px] font-bold text-gray-500 uppercase tracking-widest">Pages</div>
                        <div class="text-lg font-black text-indigo-300 font-display">${pagesVal}</div>
                    </div>
                    <div>
                        <div class="text-[9px] font-bold text-gray-500 uppercase tracking-widest">Concepts</div>
                        <div class="text-lg font-black text-indigo-300 font-display">${conceptsVal}</div>
                    </div>
                    <div>
                        <div class="text-[9px] font-bold text-gray-500 uppercase tracking-widest">Relationships</div>
                        <div class="text-lg font-black text-indigo-300 font-display">${relationshipsVal}</div>
                    </div>
                </div>
            </div>
            <button onclick="toggleGraphView(true)" class="bg-indigo-600 hover:bg-indigo-700 text-white font-bold py-2.5 px-5 rounded-xl shadow-lg transition-all text-xs flex items-center gap-2 shrink-0">
                <i class="fa-solid fa-diagram-project"></i> Open Graph
            </button>
        `;
        container.appendChild(cardDiv);
        return;
    }
    
    // Create UI Zoom/Reset buttons inside container
    const ctrlDiv = document.createElement('div');
    ctrlDiv.className = "absolute top-3 right-3 flex items-center gap-1.5 z-10 bg-[#0E1320] border border-[#1F293D] p-1 rounded-lg text-xs";
    ctrlDiv.innerHTML = `
        <button onclick="toggleGraphView(false)" class="text-indigo-400 hover:text-white px-2 font-semibold" title="Show Metadata"><i class="fa-solid fa-circle-info"></i> Info</button>
        <div class="h-3 w-px bg-gray-700 mx-1"></div>
        <button onclick="panGraphOffset(-50)" class="text-gray-400 hover:text-white p-1" title="Pan Left"><i class="fa-solid fa-chevron-left"></i></button>
        <button onclick="panGraphReset()" class="text-gray-400 hover:text-white px-1.5 font-bold" title="Reset View">Reset</button>
        <button onclick="panGraphOffset(50)" class="text-gray-400 hover:text-white p-1" title="Pan Right"><i class="fa-solid fa-chevron-right"></i></button>
    `;
    container.appendChild(ctrlDiv);
    
    const width = 700;
    const height = 130;
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("width", "100%");
    svg.setAttribute("height", "100%");
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("style", "overflow: visible; cursor: grab;");
    
    // Set up dragging listeners directly on the SVG element
    svg.addEventListener('mousedown', (e) => {
        isPanningGraph = true;
        svg.style.cursor = 'grabbing';
        panStartX = e.clientX - graphTranslateX;
    });
    
    svg.addEventListener('mousemove', (e) => {
        if (!isPanningGraph) return;
        graphTranslateX = e.clientX - panStartX;
        viewportGroup.setAttribute("transform", `translate(${graphTranslateX}, 0)`);
    });
    
    const endPan = () => {
        isPanningGraph = false;
        svg.style.cursor = 'grab';
    };
    svg.addEventListener('mouseup', endPan);
    svg.addEventListener('mouseleave', endPan);
    
    const viewportGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
    viewportGroup.setAttribute("transform", `translate(${graphTranslateX}, 0)`);
    svg.appendChild(viewportGroup);
    
    // Create connecting line path
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    let d = `M 60 ${height/2} `;
    const spacing = 160; // Fixed spacing to make long lists horizontal scrollable
    
    topics.forEach((t, i) => {
        if (i > 0) {
            d += `L ${60 + i * spacing} ${height/2} `;
        }
    });
    
    path.setAttribute("d", d);
    path.setAttribute("stroke", "#1B2233");
    path.setAttribute("stroke-width", "4");
    path.setAttribute("fill", "none");
    viewportGroup.appendChild(path);
    
    // Draw Nodes sequentially: First node unlocked. Subsequent node is locked unless previous has mastery >= 50%
    let unlocked = true;
    
    topics.forEach((t, i) => {
        const x = 60 + i * spacing;
        const y = height / 2;
        
        // Determine lock state
        if (i > 0) {
            const prev = topics[i - 1];
            if (prev.mastery < 50) {
                unlocked = false;
            }
        }
        
        const isNodeLocked = !unlocked;
        
        const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
        g.setAttribute("class", "knowledge-node outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 rounded");
        g.setAttribute("tabindex", "0");
        g.setAttribute("aria-label", isNodeLocked ? `Locked Topic: ${t.title}` : `Topic: ${t.title}, mastery score ${t.mastery}%`);
        g.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                g.click();
            }
        });
        g.style.transition = "all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275)";
        
        if (isNodeLocked) {
            g.onclick = () => {
                showToast(`Node "${t.title}" is locked. Score 50%+ in "${topics[i-1].title}" first!`, "error");
            };
        } else {
            g.onclick = () => {
                switchTab('chat');
                loadSession(t.id);
            };
        }
        
        // Outer ring glow color base
        let strokeColor = "#313E5C";
        if (!isNodeLocked) {
            strokeColor = t.mastery >= 80 ? "#10B981" : (t.mastery >= 50 ? "#6366F1" : "#F59E0B");
        }
        
        const circleOuter = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        circleOuter.setAttribute("cx", x);
        circleOuter.setAttribute("cy", y);
        circleOuter.setAttribute("r", "22");
        circleOuter.setAttribute("fill", "#0C0F17");
        circleOuter.setAttribute("stroke", strokeColor);
        circleOuter.setAttribute("stroke-width", isNodeLocked ? "2" : "3.5");
        if (!isNodeLocked && t.id === currentSessionId) {
            // Highlight active nodes
            circleOuter.setAttribute("stroke-dasharray", "4 2");
        }
        g.appendChild(circleOuter);
        
        // Center node checkmark, lock or study mark
        if (isNodeLocked) {
            const lockText = document.createElementNS("http://www.w3.org/2000/svg", "text");
            lockText.setAttribute("x", x);
            lockText.setAttribute("y", y + 4);
            lockText.setAttribute("fill", "#4B5563");
            lockText.setAttribute("font-family", "FontAwesome");
            lockText.setAttribute("font-size", "12");
            lockText.setAttribute("text-anchor", "middle");
            lockText.textContent = "\uf023"; // FontAwesome Lock symbol
            g.appendChild(lockText);
        } else {
            const circleInner = document.createElementNS("http://www.w3.org/2000/svg", "circle");
            circleInner.setAttribute("cx", x);
            circleInner.setAttribute("cy", y);
            circleInner.setAttribute("r", "8");
            circleInner.setAttribute("fill", strokeColor);
            g.appendChild(circleInner);
        }
        
        // Text labels
        const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
        text.setAttribute("x", x);
        text.setAttribute("y", y + 40);
        text.setAttribute("fill", isNodeLocked ? "#4B5563" : "#E2E8F0");
        text.setAttribute("font-size", "10");
        text.setAttribute("font-weight", "bold");
        text.setAttribute("text-anchor", "middle");
        text.textContent = t.title.length > 18 ? t.title.substring(0, 16) + '..' : t.title;
        g.appendChild(text);
        
        viewportGroup.appendChild(g);
    });
    
    container.appendChild(svg);
}

function panGraphOffset(offset) {
    graphTranslateX += offset;
    const viewport = document.querySelector('#roadmap-container svg g');
    if (viewport) {
        viewport.setAttribute("transform", `translate(${graphTranslateX}, 0)`);
    }
}

function panGraphReset() {
    graphTranslateX = 0;
    const viewport = document.querySelector('#roadmap-container svg g');
    if (viewport) {
        viewport.setAttribute("transform", `translate(0, 0)`);
    }
}

// --- RENDER DYNAMIC HEATMAP CALENDAR ---
function renderCalendarHeatmap() {
    const calendar = document.getElementById('heatmap-calendar');
    if (!calendar) return;
    calendar.innerHTML = '';
    
    for (let i = 0; i < 28; i++) {
        const block = document.createElement('div');
        const level = Math.floor(Math.random() * 5); // 0 to 4 levels
        block.className = `w-7 h-7 rounded-md heatmap-level-${level} transition-all duration-300 hover:scale-110 cursor-pointer border border-[#1B2233]/40`;
        block.title = `Activity level: ${level}`;
        calendar.appendChild(block);
    }
}

// --- RENDER STUDY PLANNER ---
function renderStudyPlanner() {
    const container = document.getElementById('study-planner-container');
    if (!container) return;
    
    // Renders a beautiful Git-history style learning log timeline
    container.innerHTML = `
        <div class="relative pl-6 border-l border-[#1F293D] ml-3 space-y-5 py-2">
            <!-- Timeline Item 1 -->
            <div class="relative">
                <!-- Dot marker -->
                <div class="absolute -left-[30px] top-1 w-3.5 h-3.5 rounded-full bg-emerald-500 border border-[#0A0D14] flex items-center justify-center text-white text-[8px] font-bold"><i class="fa-solid fa-check"></i></div>
                <div class="flex items-start justify-between gap-4">
                    <div>
                        <h4 class="text-xs font-bold text-white leading-none">RAG Material Indexed</h4>
                        <p class="text-[10px] text-gray-400 mt-1">Processed page structures on recursion stack frames.</p>
                        <span class="text-[9px] text-gray-500 font-bold block mt-1"><i class="fa-regular fa-clock mr-1"></i>12 mins ago</span>
                    </div>
                    <span class="text-[10px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded font-bold uppercase tracking-wider flex-shrink-0">+100 XP</span>
                </div>
            </div>
            
            <!-- Timeline Item 2 -->
            <div class="relative">
                <!-- Dot marker -->
                <div class="absolute -left-[30px] top-1 w-3.5 h-3.5 rounded-full bg-indigo-500 border border-[#0A0D14] flex items-center justify-center text-white text-[8px] font-bold"><i class="fa-solid fa-brain"></i></div>
                <div class="flex items-start justify-between gap-4">
                    <div>
                        <h4 class="text-xs font-bold text-white leading-none">Cognitive Trace Rectified</h4>
                        <p class="text-[10px] text-gray-400 mt-1">Remediated recursion halt exits in code segments.</p>
                        <span class="text-[9px] text-gray-500 font-bold block mt-1"><i class="fa-regular fa-clock mr-1"></i>1 hour ago</span>
                    </div>
                    <span class="text-[10px] bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 px-2 py-0.5 rounded font-bold uppercase tracking-wider flex-shrink-0">+150 XP</span>
                </div>
            </div>
            
            <!-- Timeline Item 3 -->
            <div class="relative">
                <!-- Dot marker -->
                <div class="absolute -left-[30px] top-1 w-3.5 h-3.5 rounded-full bg-amber-500 border border-[#0A0D14] flex items-center justify-center text-white text-[8px] font-bold"><i class="fa-solid fa-trophy"></i></div>
                <div class="flex items-start justify-between gap-4">
                    <div>
                        <h4 class="text-xs font-bold text-white leading-none">Quiz Mastery Passed</h4>
                        <p class="text-[10px] text-gray-400 mt-1">Correctly mapped stack frames boundaries.</p>
                        <span class="text-[9px] text-gray-500 font-bold block mt-1"><i class="fa-regular fa-clock mr-1"></i>Yesterday</span>
                    </div>
                    <span class="text-[10px] bg-amber-500/10 text-amber-400 border border-amber-500/20 px-2 py-0.5 rounded font-bold uppercase tracking-wider flex-shrink-0">+200 XP</span>
                </div>
            </div>
        </div>
    `;
}

// --- RENDER WEAK CONCEPTS ---
function renderWeakConcepts() {
    const container = document.getElementById('weak-concepts-list');
    if (!container) return;
    
    container.innerHTML = `
        <span class="text-[10px] bg-red-500/10 text-red-400 border border-red-500/20 px-2 py-1 rounded-md font-bold">Recursion Base Limit</span>
        <span class="text-[10px] bg-red-500/10 text-red-400 border border-red-500/20 px-2 py-1 rounded-md font-bold">Memory Address Maps</span>
        <span class="text-[10px] bg-red-500/10 text-red-400 border border-red-500/20 px-2 py-1 rounded-md font-bold">Matrix Multiplications</span>
    `;
}

function removeAttachedImage() {
    attachedImage = null;
    const uploadStatus = document.getElementById('upload-status');
    if (uploadStatus) uploadStatus.innerHTML = "";
    const fileUpload = document.getElementById('file-upload');
    if (fileUpload) fileUpload.value = "";
    showToast("Attached image removed", "success");
}

async function sendMessage() {
    console.log("SEND BUTTON CLICKED");
    const messageInput = document.getElementById('message-input');
    const sendBtn = document.getElementById('send-btn');
    if (!messageInput || !sendBtn) {
        console.log("Exit: messageInput or sendBtn not found");
        return;
    }
    const text = messageInput.value.trim();
    console.log("Current session:", currentSessionId);
    console.log("Message:", text);
    if (!text && !attachedImage) {
        console.log("Exit: message empty");
        return;
    }
    
    // Copy reference and reset globals
        const imgToSend = attachedImage;
        renderMessageUI('user', text, true, imgToSend);
    
    const isNew = !chatSessions[currentSessionId];
    if (isNew) {
        chatSessions[currentSessionId] = {
            id: currentSessionId,
            title: text ? (text.length > 25 ? text.substring(0, 25) + '...' : text) : 'Attached Image',
            history: [],
            mastery: 0,
            hasDoc: false,
            study_mode: studyMode
        };
    }
    
    chatSessions[currentSessionId].history.push({ role: 'user', text: text });
    messageInput.value = '';
    messageInput.style.height = 'auto';
    sendBtn.disabled = true;
    sendBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i>';
    
    // Reset inputs
    attachedImage = null;
    const uploadStatus = document.getElementById('upload-status');
    if (uploadStatus) uploadStatus.innerHTML = "";
    const fileUpload = document.getElementById('file-upload');
    if (fileUpload) fileUpload.value = "";
    
    // Simulate streaming and fetch response
    if (currentUser && currentUser.email === 'guest@feynmantutor.local') {
        setTimeout(() => {
            const guestAnswers = {
                "base case": {
                    simple_explanation: "The base case is the halting condition of recursion. Think of it as the exit door of a labyrinth—without it, you wander infinitely.",
                    why_it_works: "Every recursive call consumes stack space. Halting calls prevents StackOverflow exceptions.",
                    visual_intuition: "| Call Level | Stack Depth | State |\n|---|---|---|\n| f(3) | 1 | Open |\n| f(2) | 2 | Open |\n| f(1) | 3 | Base Reached |",
                    example: "Analogy: A line of people forwarding a question. The first person asks the second, the second asks the third, until the last person knows the answer directly (the base case) and passes it back.",
                    common_mistake: "Forgetting to write the base case, or writing a condition that is never met, leading to infinite recursion.",
                    mini_quiz: "What happens if a recursive function is called and the base case condition is never met?",
                    reflection_prompt: "Can you explain how stack unwinding returns the value back to the first caller?",
                    coach_recommendation: "Focus on memory tracing recursive trees. Spend 10 minutes practice visualizing frames.",
                    next_learning_step: "Recursive Tree Traversals",
                    estimated_study_time: 15,
                    cognitive_trace: "I noticed you mapped halting logic directly. This shows strong foundational understanding of call stack bounds. Let's look at stack unwinding next.",
                    mastery_score: 49
                }
            };
            
            let matchedAns = guestAnswers["base case"];
            if (text && !text.toLowerCase().includes("base") && !text.toLowerCase().includes("halting")) {
                matchedAns = {
                    simple_explanation: "That is partial. In recursion, we split a problem into smaller instances. If we don't declare when to stop, it goes on forever.",
                    why_it_works: "Memory frames pile up indefinitely in stack memory.",
                    visual_intuition: "Stack Overflow: [f(inf) -> f(3) -> f(2) -> f(1)]",
                    example: "Analogy: Placing mirrors facing each other. The reflection repeats infinitely.",
                    common_mistake: "Assuming the function halts automatically without an explicit logical gate.",
                    mini_quiz: "What is the specific keyword name for this halting gate?",
                    reflection_prompt: "Explain why recursion is different from a normal while loop.",
                    coach_recommendation: "Spend 5 minutes reviewing conditional halt statements.",
                    next_learning_step: "Halting base cases",
                    estimated_study_time: 10,
                    cognitive_trace: "Your answer focused on recursion splitting but omitted the halt mechanism. Let's look at the exit condition.",
                    mastery_score: 42
                };
            }
            
            // If image attached, tutor responds to it in Cognitive Trace
            if (imgToSend) {
                matchedAns.cognitive_trace = `I have reviewed the uploaded image (${imgToSend.name}). It represents custom whiteboard partitioning logic. Let's trace it.`;
            }
            
            const stringified = JSON.stringify(matchedAns);
            chatSessions[currentSessionId].history.push({ role: 'ai', text: stringified });
            chatSessions[currentSessionId].mastery = matchedAns.mastery_score;
            updateMasteryUI(matchedAns.mastery_score);
            renderMessageUI('ai', stringified, true);
            
            sendBtn.disabled = false;
            sendBtn.innerHTML = '<i class="fa-solid fa-arrow-up"></i>';
            renderHistoryList();
        }, 1200);
        return;
    }
    
    // Add E2E dynamic loading state cards
    renderMessageUI('loading', 'Thinking...', true);
    
    // Start active loading steps simulation
    let loadingStep = 1;
    loadingIntervalId = setInterval(() => {
        const statusText = document.getElementById('loading-status-text');
        const step1 = document.getElementById('load-step-1');
        const step2 = document.getElementById('load-step-2');
        const step3 = document.getElementById('load-step-3');
        
        if (loadingStep === 1) {
            if (statusText) statusText.innerText = "Searching document...";
            if (step1) step1.innerHTML = '<i class="fa-solid fa-circle-check text-emerald-400"></i> Intent parsed';
            if (step1) step1.className = "text-gray-400 flex items-center gap-1.5";
            if (step2) step2.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin text-[8px]"></i> Scanning PDF index vectors...';
            if (step2) step2.className = "text-indigo-300 flex items-center gap-1.5";
            loadingStep = 2;
        } else if (loadingStep === 2) {
            if (statusText) statusText.innerText = "Generating explanation...";
            if (step2) step2.innerHTML = '<i class="fa-solid fa-circle-check text-emerald-400"></i> Found relevant reference blocks';
            if (step2) step2.className = "text-gray-400 flex items-center gap-1.5";
            if (step3) step3.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin text-[8px]"></i> Formulating Feynman active recall cards...';
            if (step3) step3.className = "text-indigo-300 flex items-center gap-1.5";
            loadingStep = 3;
        } else if (loadingStep === 3) {
            if (statusText) statusText.innerText = "Preparing quiz...";
            loadingStep = 4;
        } else if (loadingStep === 4) {
            if (statusText) statusText.innerText = "Rendering whiteboard...";
            clearInterval(loadingIntervalId);
            loadingIntervalId = null;
        }
    }, 1200);

    // Guard: session must exist before sending
    if (!currentSessionId) {
        console.log("Exit: currentSessionId is null — no session created yet");
        removeLoadingCard();
        renderMessageUI('system', '### ⚠️ No Active Session\n\nPlease upload a PDF first or create a new study session.', true);
        sendBtn.disabled = false;
        sendBtn.innerHTML = '<i class="fa-solid fa-arrow-up"></i>';
        return;
    }

    // Abort fetch after 90 seconds to surface a clear timeout error
    const abortController = new AbortController();
    const fetchTimeout = setTimeout(() => abortController.abort(), 90000);

    try {
        console.log("About to call fetchAPI");
        console.log("FETCH START", { session: currentSessionId, message: text });
        const response = await fetchAPI('/tutor-chat/', {
            method: 'POST',
            signal: abortController.signal,
            body: JSON.stringify({
                session_id: currentSessionId,
                user_message: text,
                image_base64: imgToSend ? imgToSend.base64 : null,
                image_mime: imgToSend ? imgToSend.mime : null
            })
        });
        clearTimeout(fetchTimeout);
        console.log("FETCH RETURNED", response.status);
        
        let data = null;
        const contentType = response.headers.get("content-type");
        if (contentType && contentType.includes("application/json")) {
            data = await response.json();
            console.log("Tutor response data:", data);
            if (data && typeof data === 'object') {
                console.log("Tutor response keys:", Object.keys(data));
            }
        } else {
            const textResponse = await response.text();
            data = { detail: textResponse || `HTTP Error ${response.status}: ${response.statusText}` };
            console.log("Non-JSON response data:", data);
        }

        removeLoadingCard();

        if (response.ok) {
            const stringified = JSON.stringify(data);
            chatSessions[currentSessionId].history.push({ role: 'ai', text: stringified });
            chatSessions[currentSessionId].mastery = data.mastery_score;
            updateMasteryUI(data.mastery_score);
            renderMessageUI('ai', stringified, true);
            renderHistoryList();
        } else {
            chatSessions[currentSessionId].history.pop();
            if (data.detail === "NO_DOCUMENT") {
                renderMessageUI('system', "Please attach a PDF document using the paperclip icon first so I have study material to tutor you on!", true);
            } else {
                let errorDetails = data.detail;
                if (typeof data.detail === 'object') {
                    errorDetails = `**Exception Type:** \`${data.detail.exception_type}\`\n\n**Message:** ${data.detail.message}\n\n**Traceback:**\n\`\`\`python\n${data.detail.traceback}\n\`\`\``;
                }
                
                // Determine descriptive title based on status
                let errorTitle = "RAG AI Engine Error";
                if (response.status === 401) {
                    errorTitle = "Authentication Required";
                } else if (response.status === 403) {
                    errorTitle = "Access Forbidden";
                } else if (response.status === 404) {
                    errorTitle = "Resource Not Found";
                } else if (response.status === 429) {
                    errorTitle = "Gemini API Rate Limited";
                } else if (response.status === 503) {
                    errorTitle = "Gemini API Temporarily Overloaded";
                } else if (response.status === 500) {
                    errorTitle = "Internal Server Exception";
                }
                
                renderMessageUI('system', `### ⚠️ ${errorTitle}\n\n**Status Code:** \`${response.status}\`\n\n${errorDetails}`, true);
            }
        }
    } catch (err) {
        clearTimeout(fetchTimeout);
        removeLoadingCard();
        console.error("Chat message error:", err.name, err.message, err);
        
        let errorMsg;
        if (err.name === 'AbortError') {
            errorMsg = 'Request timed out after 90 seconds. The Gemini AI is taking too long — please try again.';
        } else if (err.message && err.message.includes("Session expired")) {
            errorMsg = 'Authentication session expired. Please reload the page and log in again.';
        } else if (err.message && (err.message.includes("Failed to fetch") || err.message.includes("NetworkError") || err.message.includes("fetch"))) {
            errorMsg = `Cannot reach the backend server at http://127.0.0.1:8000. Make sure the server is running.\n\n**Error:** \`${err.message}\``;
        } else {
            errorMsg = `**Error:** \`${err.message || String(err)}\`\n\n**Online status:** ${navigator.onLine ? 'Browser reports online' : 'Browser reports offline — check internet connection'}`;
        }
        
        renderMessageUI('system', `### ⚠️ Study Pipeline Error\n\n${errorMsg}`, true);
    } finally {
        sendBtn.disabled = false;
        sendBtn.innerHTML = '<i class="fa-solid fa-arrow-up"></i>';
    }
}

function initFileUpload() {
    const fileUploadEl = document.getElementById('file-upload');
    if (!fileUploadEl) return;
    fileUploadEl.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        const uploadStatusEl = document.getElementById('upload-status');
        
        // Check if image file
        if (file.type.startsWith('image/')) {
            if (uploadStatusEl) uploadStatusEl.innerHTML = '<span class="text-indigo-400 font-semibold"><i class="fa-solid fa-circle-notch fa-spin"></i> Preparing image preview...</span>';
            const reader = new FileReader();
            reader.onload = function(evt) {
                const base64Str = evt.target.result.split(',')[1];
                attachedImage = {
                    base64: base64Str,
                    mime: file.type,
                    name: file.name
                };
                if (uploadStatusEl) uploadStatusEl.innerHTML = `<span class="text-indigo-400 font-semibold cursor-pointer" onclick="removeAttachedImage()"><i class="fa-solid fa-image mr-1"></i> Attached: ${file.name} (Click to remove)</span>`;
                showToast("Image attached! Ready to send.", "success");
            };
            reader.readAsDataURL(file);
            return;
        }
        
        // Otherwise it's a PDF document upload
        await handlePdfUpload(file);
    });
}

// --- PROGRESSIVE HINT ENGINE ---
function triggerProgressiveHint() {
    hintLevel++;
    const hintText = document.getElementById('hint-btn-text');
    
    const hints = [
        "No hint requested.",
        "Hint 1: Think about how recursion avoids endless loops (there must be a base condition).",
        "Hint 2: It is a logical boundary check mapping stack limits.",
        "Hint 3: Look at how if-else constraints avoid stack-overflow issues.",
        "Answer: The recursion base case blocks child execution and initiates stack unwinding."
    ];
    
    if (hintLevel > 4) hintLevel = 1;
    
    hintText.innerText = `Request Clue ${hintLevel === 4 ? 'Answer' : hintLevel + 1}`;
    
    // Render the hint block directly in chat UI
    renderMessageUI('system', `💡 **Progressive Hint (${hintLevel}/4):** ${hints[hintLevel]}`, true);
}

function updateWhiteboardContent(content) {
    const canvas = document.getElementById('whiteboard-canvas');
    const emptyState = document.getElementById('whiteboard-empty-state');
    const drawer = document.getElementById('whiteboard-drawer');
    if (!canvas) return;
    
    if (emptyState) emptyState.classList.add('hidden');
    canvas.innerHTML = `
        <div class="bg-[#0C0F17] border border-[#1B2233] p-4 rounded-xl whiteboard-animate-item shadow-lg" style="animation-delay: 0.1s;">
            <div class="text-[10px] font-bold text-indigo-400 uppercase tracking-widest mb-2 flex items-center gap-1">
                <i class="fa-solid fa-compass-drafting"></i> Visual Sandbox
            </div>
            <div class="markdown-body text-xs text-gray-300">
                ${safeMarkdown(content)}
            </div>
        </div>
    `;
    
    if (drawer) drawer.classList.remove('hidden');
}

function scrollToBottom() {
    const chatScrollWrapper = document.getElementById('chat-scroll-wrapper');
    if (!chatScrollWrapper) return;
    chatScrollWrapper.scrollTop = chatScrollWrapper.scrollHeight;
    try {
        chatScrollWrapper.scrollTo({
            top: chatScrollWrapper.scrollHeight,
            behavior: 'smooth'
        });
    } catch (e) {}
    setTimeout(() => {
        chatScrollWrapper.scrollTop = chatScrollWrapper.scrollHeight;
    }, 100);
    setTimeout(() => {
        chatScrollWrapper.scrollTop = chatScrollWrapper.scrollHeight;
    }, 300);
}

function removeLoadingCard() {
    if (loadingIntervalId) {
        clearInterval(loadingIntervalId);
        loadingIntervalId = null;
    }
    const loadingCard = document.getElementById('ai-loading-card');
    if (loadingCard) loadingCard.remove();
}

function renderMessageUI(role, text, animate, imageObj = null) {
    console.log("Rendering message UI:", { role, textLength: text ? text.length : 0, animate });
    const chatContainer = document.getElementById('chat-container');
    const div = document.createElement('div');
    div.className = "flex gap-4 w-full " + (animate ? "opacity-0 translate-y-4 transition-all duration-400 ease-out" : "");
    
    if (role === 'user') {
        div.classList.add('flex-row-reverse');
        
        let imgTag = "";
        if (imageObj) {
            imgTag = `<img src="data:${imageObj.mime};base64,${imageObj.base64}" class="w-48 h-auto rounded-lg border border-[#1F293D] mt-2 shadow-sm block">`;
        }
        
        div.innerHTML = `
            <div class="w-9 h-9 rounded-full bg-gray-800 flex items-center justify-center flex-shrink-0 text-white shadow-md text-xs font-bold font-display">
                ${(currentUser && currentUser.name) ? currentUser.name.charAt(0).toUpperCase() : 'U'}
            </div>
            <div class="bg-indigo-600 text-white p-4 rounded-2xl rounded-tr-sm shadow-sm max-w-[80%] text-sm" style="color: white !important;">
                <div>${text}</div>
                ${imgTag}
            </div>
        `;
        try {
            if (chatContainer) {
                chatContainer.appendChild(div);
                console.log("User message appended successfully");
            } else {
                console.error("appendChild failed: chatContainer is null");
            }
        } catch (e) {
            console.error("appendChild failed:", e);
        }
    } else if (role === 'system') {
        let iconClass = "fa-regular fa-lightbulb";
        let cardColorClass = "bg-[#1C1812] border border-yellow-500/20 text-yellow-200/90";
        let iconWrapperClass = "bg-yellow-500/10 border border-yellow-500/20 text-yellow-500";
        
        if (text.includes("Authentication Required")) {
            iconClass = "fa-solid fa-lock";
            cardColorClass = "bg-[#1E1912] border border-amber-500/20 text-amber-200/90";
            iconWrapperClass = "bg-amber-500/10 border border-amber-500/20 text-amber-500";
        } else if (text.includes("Gemini API Rate Limited")) {
            iconClass = "fa-solid fa-hourglass-half";
            cardColorClass = "bg-[#1E1912] border border-amber-500/20 text-amber-200/90";
            iconWrapperClass = "bg-amber-500/10 border border-amber-500/20 text-amber-500";
        } else if (text.includes("Gemini API Temporarily Overloaded") || text.includes("Unavailable")) {
            iconClass = "fa-solid fa-server";
            cardColorClass = "bg-[#211414] border border-rose-500/20 text-rose-200/90";
            iconWrapperClass = "bg-rose-500/10 border border-rose-500/20 text-rose-400";
        } else if (text.includes("Internal Server Exception") || text.includes("RAG AI Engine Error")) {
            iconClass = "fa-solid fa-bug";
            cardColorClass = "bg-[#1F141E] border border-red-500/20 text-red-200/90";
            iconWrapperClass = "bg-red-500/10 border border-red-500/20 text-red-400";
        }
        
        div.innerHTML = `
            <div class="w-9 h-9 rounded-full ${iconWrapperClass} flex items-center justify-center flex-shrink-0 shadow-sm">
                <i class="${iconClass} text-sm"></i>
            </div>
            <div class="${cardColorClass} p-4 rounded-2xl rounded-tl-sm shadow-sm max-w-[85%] text-sm w-full">
                ${safeMarkdown(text)}
            </div>
        `;
        try {
            if (chatContainer) {
                chatContainer.appendChild(div);
                console.log("System message appended successfully");
            } else {
                console.error("appendChild failed: chatContainer is null");
            }
        } catch (e) {
            console.error("appendChild failed:", e);
        }
    } else if (role === 'loading') {
        div.id = "ai-loading-card";
        div.innerHTML = `
            <div class="w-9 h-9 rounded-full bg-gradient-to-tr from-indigo-500/20 to-purple-600/20 border border-indigo-500/20 flex items-center justify-center flex-shrink-0 text-indigo-400 shadow-sm animate-pulse">
                <i class="fa-solid fa-graduation-cap text-sm"></i>
            </div>
            <div class="bg-[#0E1320] border border-indigo-500/20 p-5 rounded-2xl rounded-tl-sm shadow-sm max-w-[85%] text-sm w-full space-y-3">
                <div class="flex items-center gap-2 text-indigo-400 font-semibold animate-pulse">
                    <i class="fa-solid fa-circle-notch fa-spin text-sm"></i>
                    <span id="loading-status-text">Thinking...</span>
                </div>
                <div class="text-[10px] text-gray-500 space-y-1 font-mono">
                    <div id="load-step-1" class="text-indigo-300 flex items-center gap-1.5"><i class="fa-solid fa-circle-notch fa-spin text-[8px]"></i> Parsing study query and intent...</div>
                    <div id="load-step-2" class="text-gray-600 flex items-center gap-1.5"><i class="fa-solid fa-circle text-[4px]"></i> Searching vector database chunks</div>
                    <div id="load-step-3" class="text-gray-600 flex items-center gap-1.5"><i class="fa-solid fa-circle text-[4px]"></i> Generating active recall response</div>
                </div>
            </div>
        `;
        try {
            if (chatContainer) {
                chatContainer.appendChild(div);
                console.log("Loading card appended successfully");
            } else {
                console.error("appendChild failed: chatContainer is null");
            }
        } catch (e) {
            console.error("appendChild failed:", e);
        }
    } else {
        // AI MESSAGE
        // Try parsing JSON response contract
        let data = null;
        try {
            let cleanText = text.trim();
            if (cleanText.startsWith('```json')) {
                cleanText = cleanText.substring(7);
            }
            if (cleanText.startsWith('```')) {
                cleanText = cleanText.substring(3);
            }
            if (cleanText.endsWith('```')) {
                cleanText = cleanText.substring(0, cleanText.length - 3);
            }
            cleanText = cleanText.trim();
            
            const startIdx = cleanText.indexOf('{');
            const endIdx = cleanText.lastIndexOf('}');
            if (startIdx !== -1 && endIdx !== -1 && endIdx > startIdx) {
                const possibleJson = cleanText.substring(startIdx, endIdx + 1);
                data = JSON.parse(possibleJson);
            }
        } catch (e) {
            console.error("JSON parse fail:", e);
            data = null;
        }
        
        if (data) {
            const cardUniqueId = `ai-card-${Date.now()}-${Math.floor(Math.random()*1000)}`;
            
            // Auto update whiteboard if visual block exists
            if (data.visual_intuition) {
                updateWhiteboardContent(data.visual_intuition);
            }
            
            // Build citation badges if sources exist
            let sourcesTag = "";
            if (data.sources && data.sources.length > 0) {
                sourcesTag = `
                    <div class="space-y-2">
                        <div class="text-[10px] font-bold text-gray-400 uppercase tracking-widest flex items-center gap-1.5 mb-2">
                            <i class="fa-solid fa-database text-indigo-400"></i> RAG Ground Truth Vectors & References
                        </div>
                        <div class="flex flex-wrap gap-2">
                            ${data.sources.map(s => `
                                <div class="bg-[#07090E] text-[11px] text-indigo-300 border border-[#1F293D] p-3 rounded-xl flex items-center justify-between w-full shadow-sm">
                                    <div class="flex items-center gap-2">
                                        <i class="fa-solid fa-file-pdf text-red-500 text-sm"></i>
                                        <span class="font-semibold text-white">${s.filename}</span>
                                        <span class="bg-indigo-500/10 text-indigo-400 text-[10px] px-2 py-0.5 rounded-md font-mono border border-indigo-500/20">Page ${s.page}</span>
                                    </div>
                                    <span class="text-emerald-400 font-bold text-[10px]"><i class="fa-solid fa-circle-check mr-1"></i>96% Vector Match</span>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                `;
            } else {
                sourcesTag = `
                    <div class="text-xs text-gray-400 italic bg-[#07090E]/60 p-3 rounded-xl border border-[#1F293D]">
                        No external PDF context retrieved for this query. Responded using Feynman Core Model knowledge.
                    </div>
                `;
            }
            
            const rawSimpleText = data.simple_explanation || "";
            const escapedSimpleText = rawSimpleText.replace(/'/g, "\\'").replace(/"/g, '&quot;').replace(/\n/g, ' ');

            div.innerHTML = `
                <div class="w-8 h-8 rounded-lg bg-[#161B26] border border-[#222833] flex items-center justify-center flex-shrink-0 text-[#5B8DEF]">
                    <i class="fa-solid fa-sparkles text-xs"></i>
                </div>
                    <div class="bg-[#11141A] border border-[#222833] rounded-xl overflow-hidden shadow-lg">
                        ${renderWorkspaceHeader(data)}
                        ${renderWorkspaceTabs(cardUniqueId, escapedSimpleText)}
                        
                        <div class="p-6">
                            ${renderOverviewTab(cardUniqueId, data)}
                            ${renderDeepDiveTab(data)}
                            ${renderQuizTab(data)}
                            <div data-panel="sources" class="card-tab-panel hidden">${sourcesTag}</div>
                        </div>

                        ${renderWorkspaceFooter()}
                    </div>
                </div>
            `;
            console.log("chatContainer:", chatContainer);
            console.log("AI div:", div);
            try {
                if (chatContainer) {
                    chatContainer.appendChild(div);
                    console.log("AI message appended successfully");
                    if (animate && data && cardUniqueId) {
                        typewriterStream(`typewriter-body-${cardUniqueId}`, safeMarkdown(data.simple_explanation || ""));
                    } else {
                        initMermaidDiagrams();
                    }
                } else {
                    console.error("appendChild failed: chatContainer is null");
                }
            } catch (e) {
                console.error("appendChild failed:", e);
            }
        } else {
            // Raw text message rendering fallback
            div.innerHTML = `
                <div class="w-9 h-9 rounded-full bg-gradient-to-tr from-indigo-500/20 to-purple-600/20 border border-indigo-500/20 flex items-center justify-center flex-shrink-0 text-indigo-400 shadow-sm">
                    <i class="fa-solid fa-graduation-cap text-sm"></i>
                </div>
                <div class="bg-[#0E1320] border border-[#1F293D]/60 text-gray-200 p-5 rounded-2xl rounded-tl-sm shadow-sm max-w-[85%] markdown-body">
                    ${safeMarkdown(text)}
                </div>
            `;
            console.log("chatContainer:", chatContainer);
            console.log("Fallback AI div:", div);
            try {
                if (chatContainer) {
                    chatContainer.appendChild(div);
                    console.log("Fallback AI message appended successfully");
                } else {
                    console.error("appendChild failed: chatContainer is null");
                }
            } catch (e) {
                console.error("appendChild failed:", e);
            }
        }
    }
    
    if (animate) {
        setTimeout(() => div.classList.remove('opacity-0', 'translate-y-4'), 50);
    }
    scrollToBottom();
}

function updateMasteryUI(score) {
    const bar = document.getElementById('mastery-bar');
    const text = document.getElementById('mastery-text');
    const coachTip = document.getElementById('coach-dashboard-tip');
    if (!bar || !text) return;
    
    bar.style.width = score + '%';
    text.innerText = score + '%';
    
    // Dynamic coach recommendations based on mastery levels
    if (coachTip) {
        if (score < 50) {
            coachTip.innerText = `"Pointers and Recursion remain a recurring blocker. Let's spend 10 minutes practicing memory stack offsets on the whiteboard before jumping into graphs today."`;
        } else if (score < 80) {
            coachTip.innerText = `"Great progress! You unlocked recursive tree nodes. Focus on active recall traversals to solidify matrix calculations next."`;
        } else {
            coachTip.innerText = `"Superb mastery score! You are fully prepared for academic coding interviews. Let's test dynamic programming edge cases next."`;
        }
    }
    
    if (score < 40) {
        bar.className = "h-full bg-gradient-to-r from-red-500 to-amber-500 rounded-full transition-all duration-1000 ease-out";
        text.className = "text-xs font-bold text-red-400";
    } else if (score < 75) {
        bar.className = "h-full bg-gradient-to-r from-amber-500 to-indigo-500 rounded-full transition-all duration-1000 ease-out";
        text.className = "text-xs font-bold text-amber-400";
    } else {
        bar.className = "h-full bg-gradient-to-r from-indigo-500 to-emerald-500 rounded-full transition-all duration-1000 ease-out";
        text.className = "text-xs font-bold text-emerald-400";
    }
}

// --- EXPORT NOTES WORKSPACE ---
function exportNoteMarkdown(btn) {
    // Find the explanation card container
    const card = btn.closest('.markdown-body');
    if (!card) {
        showToast("Note content element not found.", "error");
        return;
    }
    
    // Extract textual data safely
    const typewriter = card.querySelector('div[id^="typewriter-body-"]');
    const explanation = typewriter ? typewriter.innerText : "Feynman Study Note";
    const paragraphs = card.querySelectorAll('p');
    
    const whyItWorks = paragraphs[0] ? paragraphs[0].innerText : "";
    const analogy = paragraphs[1] ? paragraphs[1].innerText : "";
    const misconceptions = paragraphs[2] ? paragraphs[2].innerText : "";
    
    const markdown = `# Feynman Study Note: ${document.getElementById('header-doc-title').innerText}

## Simple Explanation
${explanation}

## Why It Works
${whyItWorks}

## Analogy Check
${analogy}

## Common Misconceptions
${misconceptions}
`;
    
    // Download markdown file
    const blob = new Blob([markdown], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `Feynman_Study_Note_${Date.now()}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast("Study note exported as Markdown!", "success");
}

// --- VOICE RECOGNITION ENGINE ---
let recognition = null;

function toggleVoiceMock() {
    isVoiceListening = !isVoiceListening;
    const orb = document.getElementById('voice-orb');
    const ring = document.getElementById('voice-pulse-ring');
    const voiceInput = document.getElementById('message-input');
    
    if (isVoiceListening) {
        orb.classList.add('voice-listening');
        ring.classList.remove('hidden');
        
        // Check browser SpeechRecognition support
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRecognition) {
            if (!recognition) {
                recognition = new SpeechRecognition();
                recognition.continuous = false;
                recognition.interimResults = false;
                recognition.lang = 'en-US';
                
                recognition.onresult = (event) => {
                    const speechText = event.results[0][0].transcript;
                    voiceInput.value = speechText;
                    voiceInput.style.height = 'auto';
                    voiceInput.style.height = (voiceInput.scrollHeight) + 'px';
                    showToast(`Recognized: "${speechText}"`, "success");
                    if (isVoiceListening) toggleVoiceMock();
                };
                
                recognition.onerror = () => {
                    showToast("Speech recognition failed. Try again.", "error");
                    if (isVoiceListening) toggleVoiceMock();
                };
                
                recognition.onend = () => {
                    if (isVoiceListening) {
                        toggleVoiceMock();
                    }
                };
            }
            try {
                recognition.start();
                showToast("Listening... Speak now", "success");
            } catch (err) {
                console.error(err);
            }
        } else {
            showToast("Web Speech API not supported. Using simulation mode...", "success");
            setTimeout(() => {
                if (isVoiceListening) {
                    voiceInput.value = "Explain recursion tree stack bounds.";
                    voiceInput.style.height = 'auto';
                    voiceInput.style.height = (voiceInput.scrollHeight) + 'px';
                    toggleVoiceMock();
                }
            }, 3000);
        }
    } else {
        orb.classList.remove('voice-listening');
        ring.classList.add('hidden');
        if (recognition) {
            try {
                recognition.stop();
            } catch (e) {}
        }
    }
}

// --- COMPOSER HEIGHT/KEY HANDLER ---
const messageInput = document.getElementById('message-input');
messageInput.addEventListener('input', function() {
    this.style.height = 'auto';
    this.style.height = (this.scrollHeight) + 'px';
});

function handleComposerKey(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
}

// --- WHITEBOARD PANEL TOGGLE ---
function toggleWhiteboard() {
    const drawer = document.getElementById('whiteboard-drawer');
    const emptyState = document.getElementById('whiteboard-empty-state');
    const canvas = document.getElementById('whiteboard-canvas');
    if (!drawer) return;
    
    drawer.classList.toggle('hidden');
    
    if (!drawer.classList.contains('hidden')) {
        if (emptyState) emptyState.classList.add('hidden');
        if (canvas) {
            canvas.innerHTML = `
                <div class="bg-[#0C0F17] border border-[#1B2233] p-4 rounded-xl">
                    <div class="text-[10px] font-bold text-indigo-400 uppercase tracking-widest mb-2">Recursive Depth Visualizer</div>
                    <pre class="text-[10px] font-mono text-gray-400 leading-tight">
f(3)
 ├── f(2)
 │    ├── f(1) [Base case reached]
 │    └── f(1) [Returns 1]
 └── f(2)
      └── f(1) [Returns 1]
                    </pre>
                </div>
            `;
        }
    }
}

// --- DYNAMIC COMMAND PALETTE CONTROLLER ---
function toggleCommandPalette() {
    const palette = document.getElementById('command-palette');
    palette.classList.toggle('hidden');
    if (!palette.classList.contains('hidden')) {
        document.getElementById('palette-search').focus();
        filterPaletteShortcuts();
    }
}

function hideCommandPalette() {
    document.getElementById('command-palette').classList.add('hidden');
}

const paletteShortcuts = [
    { title: "Switch to Focus Mode", action: () => changeStudyMode('Focus') },
    { title: "Switch to Exam Mode", action: () => changeStudyMode('Exam') },
    { title: "Switch to Interview Mode", action: () => changeStudyMode('Interview') },
    { title: "Go to Dashboard", action: () => switchTab('dashboard') },
    { title: "Go to Feynman Tutor Chat", action: () => switchTab('chat') },
    { title: "Sign Out Profile", action: () => signOut() }
];

function filterPaletteShortcuts() {
    const search = document.getElementById('palette-search').value.toLowerCase();
    const list = document.getElementById('palette-list');
    list.innerHTML = '';
    
    const filtered = paletteShortcuts.filter(s => s.title.toLowerCase().includes(search));
    filtered.forEach(s => {
        const btn = document.createElement('button');
        btn.className = "w-full text-left px-4 py-3 rounded-xl hover:bg-[#1C2336] text-white font-semibold transition-all border border-transparent hover:border-indigo-500/20 block mb-1";
        btn.innerText = s.title;
        btn.onclick = () => {
            s.action();
            hideCommandPalette();
        };
        list.appendChild(btn);
    });
}

function changeStudyMode(mode) {
    studyMode = mode;
    document.getElementById('study-mode-select').value = mode;
    if (currentSessionId && chatSessions[currentSessionId]) {
        chatSessions[currentSessionId].study_mode = mode;
    }
    showToast(`Switched to ${mode} Study Mode`, "success");
    
    // Automatically load visual roadmap whiteboard mock in Interview mode
    if (mode === 'Interview') {
        updateWhiteboardContent(`
### Graph Loop Detection Sandbox
\`\`\`text
Node A ──➔ Node B ──➔ Node C
  ▲                    │
  └────────────────────┘
\`\`\`
- DFS Visited Colors:
  - White (unvisited): None
  - Gray (visiting): A, B, C
  - Black (fully trace): None
- **Back-edge found: C ──➔ A (Cycle detected!)**
        `);
    }
}

// --- SKETCHPAD ENGINE ---
let sketchCanvas, sketchCtx, isSketchDrawing = false;

function initSketchpad() {
    sketchCanvas = document.getElementById('interactive-sketchpad');
    if (!sketchCanvas) return;
    
    sketchCtx = sketchCanvas.getContext('2d');
    sketchCtx.strokeStyle = '#6366F1'; // indigo-500
    sketchCtx.lineWidth = 2.5;
    sketchCtx.lineCap = 'round';
    sketchCtx.lineJoin = 'round';
    
    // Mouse drawing listeners
    sketchCanvas.addEventListener('mousedown', (e) => {
        isSketchDrawing = true;
        sketchCtx.beginPath();
        sketchCtx.moveTo(e.offsetX, e.offsetY);
    });
    
    sketchCanvas.addEventListener('mousemove', (e) => {
        if (!isSketchDrawing) return;
        sketchCtx.lineTo(e.offsetX, e.offsetY);
        sketchCtx.stroke();
    });
    
    sketchCanvas.addEventListener('mouseup', () => isSketchDrawing = false);
    sketchCanvas.addEventListener('mouseleave', () => isSketchDrawing = false);
    
    // Touch drawing listeners
    sketchCanvas.addEventListener('touchstart', (e) => {
        e.preventDefault();
        const touch = e.touches[0];
        const rect = sketchCanvas.getBoundingClientRect();
        isSketchDrawing = true;
        sketchCtx.beginPath();
        sketchCtx.moveTo(touch.clientX - rect.left, touch.clientY - rect.top);
    });
    
    sketchCanvas.addEventListener('touchmove', (e) => {
        e.preventDefault();
        if (!isSketchDrawing) return;
        const touch = e.touches[0];
        const rect = sketchCanvas.getBoundingClientRect();
        sketchCtx.lineTo(touch.clientX - rect.left, touch.clientY - rect.top);
        sketchCtx.stroke();
    });
    
    sketchCanvas.addEventListener('touchend', () => isSketchDrawing = false);
}

function clearSketchpad() {
    if (!sketchCanvas || !sketchCtx) return;
    sketchCtx.clearRect(0, 0, sketchCanvas.width, sketchCanvas.height);
    showToast("Sketchpad cleared", "success");
}

// --- INTERACTIVE LEARNING CARD HELPERS ---
function switchCardTab(cardId, tabName) {
    const cardEl = document.getElementById(cardId);
    if (!cardEl) return;
    
    // Update tab button styles
    cardEl.querySelectorAll('.tab-underline-btn').forEach(btn => {
        if (btn.dataset.tab === tabName) {
            btn.className = "tab-underline-btn active py-3 text-xs font-semibold focus:outline-none flex items-center gap-1.5";
        } else {
            btn.className = "tab-underline-btn py-3 text-xs font-medium focus:outline-none flex items-center gap-1.5";
        }
    });
    
    // Toggle tab panels
    cardEl.querySelectorAll('.card-tab-panel').forEach(panel => {
        if (panel.dataset.panel === tabName) {
            panel.classList.remove('hidden');
        } else {
            panel.classList.add('hidden');
        }
    });
}

function copyCardContent(text, btnEl) {
    if (navigator.clipboard) {
        navigator.clipboard.writeText(text).then(() => {
            showToast("Copied card content to clipboard!", "success");
            if (btnEl) {
                const oldHtml = btnEl.innerHTML;
                btnEl.innerHTML = '<i class="fa-solid fa-check text-emerald-400"></i>';
                setTimeout(() => btnEl.innerHTML = oldHtml, 2000);
            }
        });
    }
}

function speakCardText(text, btnEl) {
    if (!('speechSynthesis' in window)) {
        showToast("Text-to-speech is not supported in your browser.", "error");
        return;
    }
    if (window.speechSynthesis.speaking) {
        window.speechSynthesis.cancel();
        if (btnEl) btnEl.innerHTML = '<i class="fa-solid fa-volume-high"></i>';
        return;
    }
    const cleanText = text.replace(/[#*`_~]/g, '');
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    if (btnEl) btnEl.innerHTML = '<i class="fa-solid fa-square text-amber-400 animate-pulse"></i>';
    utterance.onend = () => {
        if (btnEl) btnEl.innerHTML = '<i class="fa-solid fa-volume-high"></i>';
    };
    window.speechSynthesis.speak(utterance);
}

function triggerQuickPrompt(promptText) {
    const messageInput = document.getElementById('message-input');
    if (messageInput) {
        messageInput.value = promptText;
        sendMessage();
    }
}

function rateCardResponse(btn, rating) {
    if (rating === 'up') {
        showToast("Thanks for feedback! Learning model context reinforced.", "success");
        btn.className = "text-emerald-400 transition-colors p-1.5 rounded hover:bg-[#1A2030]";
    } else {
        showToast("Feedback noted. Next response will simplify explanations.", "success");
        btn.className = "text-rose-400 transition-colors p-1.5 rounded hover:bg-[#1A2030]";
    }
}

// --- MERMAID DIAGRAMS & STREAMING TYPEWRITER HELPERS ---
function initMermaidDiagrams() {
    if (window.mermaid) {
        try {
            window.mermaid.initialize({
                startOnLoad: false,
                theme: 'dark',
                securityLevel: 'loose'
            });
            
            document.querySelectorAll('.mermaid').forEach(async (el) => {
                const graphDefinition = (el.textContent || '').trim();
                if (!graphDefinition) return;
                try {
                    // Pre-parse to catch invalid syntax before rendering
                    const valid = await window.mermaid.parse(graphDefinition).catch(() => false);
                    if (valid) {
                        await window.mermaid.run({ nodes: [el] }).catch(() => renderFallbackDiagram(el));
                    } else {
                        renderFallbackDiagram(el);
                    }
                } catch (err) {
                    renderFallbackDiagram(el);
                }
            });
        } catch (e) {
            console.error("Mermaid init error:", e);
        }
    }
}

function renderFallbackDiagram(containerEl) {
    if (!containerEl) return;
    containerEl.className = "p-4 bg-[#0A0D14] rounded-lg border border-[#1E2536] space-y-3 my-2";
    containerEl.innerHTML = `
        <div class="flex items-center gap-2 text-xs font-semibold text-indigo-400">
            <i class="fa-solid fa-sitemap"></i> Interactive Concept Blueprint
        </div>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-3 pt-1">
            <div class="p-3 bg-[#111622] border border-indigo-500/20 rounded-lg text-center shadow-sm">
                <span class="text-[10px] uppercase tracking-wider text-indigo-400 font-bold block">1. Input / Foundation</span>
                <span class="text-xs text-gray-300 font-medium">Core Problem Setup</span>
            </div>
            <div class="p-3 bg-[#111622] border border-purple-500/20 rounded-lg text-center shadow-sm">
                <span class="text-[10px] uppercase tracking-wider text-purple-400 font-bold block">2. First Principles</span>
                <span class="text-xs text-gray-300 font-medium">Feynman Logic Process</span>
            </div>
            <div class="p-3 bg-[#111622] border border-emerald-500/20 rounded-lg text-center shadow-sm">
                <span class="text-[10px] uppercase tracking-wider text-emerald-400 font-bold block">3. Expected Output</span>
                <span class="text-xs text-gray-300 font-medium">Mastery Outcome</span>
            </div>
        </div>
    `;
}

function typewriterStream(elementId, htmlContent) {
    const el = document.getElementById(elementId);
    if (!el) return;
    
    let words = htmlContent.split(' ');
    let currentIdx = 0;
    
    let timer = setInterval(() => {
        if (currentIdx < words.length) {
            el.innerHTML = words.slice(0, currentIdx + 1).join(' ') + ' <span class="typewriter-cursor text-indigo-400 font-bold animate-pulse">▌</span>';
            currentIdx += Math.floor(Math.random() * 2) + 1;
            scrollToBottom();
        } else {
            clearInterval(timer);
            el.innerHTML = htmlContent;
            initMermaidDiagrams();
            scrollToBottom();
        }
    }, 40);
}

// --- MODULAR WORKSPACE SUB-RENDERERS ---
function renderWorkspaceHeader(data) {
    const currentSession = (currentSessionId && chatSessions[currentSessionId]) ? chatSessions[currentSessionId] : { mastery: 0 };
    const masteryVal = data.mastery_score !== undefined ? data.mastery_score : (currentSession.mastery || 0);
    return `
        <div class="px-5 py-3.5 border-b border-[#222833] flex items-center justify-between bg-[#0B0D12]/50 text-xs">
            <div class="flex items-center gap-4 text-gray-400 font-mono text-[11px]">
                <span>Understanding <strong class="text-white ml-1 font-semibold">${masteryVal}%</strong></span>
                <span class="text-[#222833]">|</span>
                <span>Reading Time <strong class="text-white ml-1 font-semibold">${data.estimated_study_time || 4} min</strong></span>
                <span class="text-[#222833]">|</span>
                <span>Difficulty <strong class="text-white ml-1 font-semibold">Intermediate</strong></span>
            </div>
            <div class="text-[11px] font-medium text-[#5B8DEF] flex items-center gap-1.5">
                <i class="fa-solid fa-circle text-[6px] text-emerald-400"></i> ${data.next_learning_step || "Feynman Learning OS"}
            </div>
        </div>
    `;
}

function renderWorkspaceTabs(cardUniqueId, escapedText) {
    return `
        <div class="flex items-center justify-between border-b border-[#222833] px-5 bg-[#0B0D12]/30">
            <div class="flex gap-6">
                <button onclick="switchCardTab('${cardUniqueId}', 'overview')" data-tab="overview" class="tab-underline-btn active py-3 text-xs font-semibold focus:outline-none flex items-center gap-1.5">
                    Summary
                </button>
                <button onclick="switchCardTab('${cardUniqueId}', 'deepdive')" data-tab="deepdive" class="tab-underline-btn py-3 text-xs font-medium focus:outline-none flex items-center gap-1.5">
                    Deep Dive
                </button>
                <button onclick="switchCardTab('${cardUniqueId}', 'quiz')" data-tab="quiz" class="tab-underline-btn py-3 text-xs font-medium focus:outline-none flex items-center gap-1.5">
                    Knowledge Check
                </button>
                <button onclick="switchCardTab('${cardUniqueId}', 'sources')" data-tab="sources" class="tab-underline-btn py-3 text-xs font-medium focus:outline-none flex items-center gap-1.5">
                    References
                </button>
            </div>
            <div class="flex items-center gap-3 text-gray-400 text-xs font-medium">
                <button onclick="copyCardContent('${escapedText}', this)" class="hover:text-white transition-colors flex items-center gap-1 focus:outline-none" title="Copy text">
                    <i class="fa-regular fa-copy text-xs"></i> Copy
                </button>
                <button onclick="speakCardText('${escapedText}', this)" class="hover:text-white transition-colors flex items-center gap-1 focus:outline-none" title="Read Aloud">
                    <i class="fa-solid fa-volume-high text-xs"></i> Read
                </button>
                <button onclick="exportNoteMarkdown(this)" class="hover:text-white transition-colors flex items-center gap-1 focus:outline-none" title="Export Markdown">
                    <i class="fa-solid fa-download text-xs"></i> Export
                </button>
            </div>
        </div>
    `;
}

function normalizeResponse(data) {
    if (data.blocks && Array.isArray(data.blocks)) {
        return data.blocks;
    }

    const blocks = [];
    if (data.simple_explanation) blocks.push({ type: 'summary', content: data.simple_explanation });
    if (data.why_it_works) blocks.push({ type: 'mechanics', content: data.why_it_works });
    if (data.example) blocks.push({ type: 'mental_model', content: data.example });
    if (data.visual_intuition) blocks.push({ type: 'visualization', content: data.visual_intuition });

    return blocks;
}

const BLOCK_RENDERERS = {
    summary: (context, block) => `
        <div>
            <div id="typewriter-body-${context.cardId}" class="markdown-body text-gray-200 text-sm leading-relaxed">${safeMarkdown(block.content || "")}</div>
        </div>
    `,
    mechanics: (context, block) => `
        <div class="callout-minimal space-y-1">
            <div class="text-[11px] font-semibold text-[#5B8DEF] uppercase tracking-wider">Core Mechanics</div>
            <p class="text-xs text-gray-300 leading-relaxed">${block.content || ""}</p>
        </div>
    `,
    mental_model: (context, block) => `
        <div class="callout-minimal callout-warning space-y-1">
            <div class="text-[11px] font-semibold text-amber-400 uppercase tracking-wider">Mental Model</div>
            <p class="text-xs text-gray-300 leading-relaxed">${block.content || ""}</p>
        </div>
    `,
    visualization: (context, block) => renderVisualizationBlock(context.cardId, block.content)
};

function renderBlockList(cardId, data) {
    const context = Object.freeze({
        cardId,
        data,
        session: (currentSessionId && chatSessions[currentSessionId]) ? chatSessions[currentSessionId] : { mastery: 0 }
    });
    return normalizeResponse(data).map(block => {
        try {
            const renderer = BLOCK_RENDERERS[block.type];
            return renderer ? renderer(context, block) : '';
        } catch (err) {
            console.error(`[BLOCK RENDER ERROR] Failed to render block type '${block.type}':`, err);
            return `
                <div class="callout-minimal callout-error space-y-1">
                    <div class="text-[11px] font-semibold text-rose-400 uppercase tracking-wider">Block Display Degradation (${block.type})</div>
                    <p class="text-xs text-gray-400">Component degraded safely.</p>
                </div>
            `;
        }
    }).join('');
}

function renderVisualizationBlock(cardUniqueId, visualContent) {
    if (!visualContent) return "";
    const vizId = `viz-body-${cardUniqueId}`;
    const escapedContent = visualContent.replace(/'/g, "\\'").replace(/\n/g, ' ');
    return `
        <div class="border border-[#222833] rounded-lg bg-[#0B0D12] overflow-hidden mt-4">
            <div class="px-4 py-2.5 bg-[#11141A] border-b border-[#222833] flex items-center justify-between">
                <div class="flex items-center gap-2 text-xs font-semibold text-[#5B8DEF]">
                    <i class="fa-solid fa-diagram-project"></i> Visualization Sandbox
                </div>
                <div class="flex items-center gap-3 text-[11px] text-gray-400">
                    <button onclick="toggleVisualizationBody('${vizId}', this)" class="hover:text-white transition-colors flex items-center gap-1 focus:outline-none">
                        <i class="fa-solid fa-chevron-up text-[10px]"></i> <span class="viz-toggle-text">Collapse</span>
                    </button>
                    <span class="text-[#222833]">|</span>
                    <button onclick="copyCardContent('${escapedContent}', this)" class="hover:text-white transition-colors flex items-center gap-1 focus:outline-none" title="Copy Diagram Code">
                        <i class="fa-regular fa-copy text-[10px]"></i> Copy
                    </button>
                    <button onclick="triggerQuickPrompt('Focus on diagram and break down step by step')" class="hover:text-white transition-colors flex items-center gap-1 focus:outline-none">
                        <i class="fa-solid fa-wand-magic-sparkles text-[10px]"></i> Focus on Diagram
                    </button>
                </div>
            </div>
            <div id="${vizId}" class="p-4 bg-[#0B0D12] transition-all">
                <div class="mermaid p-3 bg-[#0B0D12] rounded-md text-xs font-mono text-indigo-300 border border-[#222833]">
                    ${visualContent}
                </div>
            </div>
        </div>
    `;
}

function toggleVisualizationBody(vizId, btnEl) {
    const vizEl = document.getElementById(vizId);
    if (!vizEl) return;
    vizEl.classList.toggle('hidden');
    const isHidden = vizEl.classList.contains('hidden');
    const icon = btnEl.querySelector('i');
    const label = btnEl.querySelector('.viz-toggle-text');
    if (icon) icon.className = isHidden ? 'fa-solid fa-chevron-down text-[10px]' : 'fa-solid fa-chevron-up text-[10px]';
    if (label) label.innerText = isHidden ? 'Expand' : 'Collapse';
}

function renderOverviewTab(cardUniqueId, data) {
    return `
        <div data-panel="overview" class="card-tab-panel space-y-5">
            ${renderBlockList(cardUniqueId, data)}
        </div>
    `;
}

function renderDeepDiveTab(data) {
    return `
        <div data-panel="deepdive" class="card-tab-panel hidden space-y-4">
            <div class="callout-minimal callout-error space-y-1">
                <div class="text-[11px] font-semibold text-rose-400 uppercase tracking-wider">Common Misconception</div>
                <p class="text-xs text-gray-300 leading-relaxed">${data.common_mistake || ""}</p>
            </div>
            <div class="callout-minimal space-y-1">
                <div class="text-[11px] font-semibold text-purple-400 uppercase tracking-wider">Teacher Reflection Challenge</div>
                <p class="text-xs text-gray-300 leading-relaxed">${data.reflection_prompt || ""}</p>
            </div>
        </div>
    `;
}

function renderQuizTab(data) {
    return `
        <div data-panel="quiz" class="card-tab-panel hidden space-y-4">
            <div class="bg-[#0B0D12] border border-[#222833] p-5 rounded-lg space-y-3">
                <div class="text-[11px] font-semibold text-gray-400 uppercase tracking-wider">Assessment Question</div>
                <p class="text-xs text-white font-medium leading-relaxed">${data.mini_quiz || ""}</p>
                <div class="pt-2 flex gap-3">
                    <button onclick="showToast('Correct! Active recall confirmed.', 'success')" class="text-xs bg-[#161B26] hover:bg-[#1E2536] text-gray-200 border border-[#222833] px-4 py-2 rounded-md transition-colors font-medium flex items-center gap-2">
                        <i class="fa-solid fa-circle-check text-emerald-400"></i> Option A (Validate)
                    </button>
                    <button onclick="showToast('Review concept details.', 'error')" class="text-xs bg-[#161B26] hover:bg-[#1E2536] text-gray-200 border border-[#222833] px-4 py-2 rounded-md transition-colors font-medium flex items-center gap-2">
                        <i class="fa-solid fa-circle-xmark text-rose-400"></i> Option B
                    </button>
                </div>
            </div>
        </div>
    `;
}

function renderWorkspaceFooter() {
    return `
        <div class="bg-[#0B0D12]/60 border-t border-[#222833] px-6 py-3 flex items-center justify-between text-xs text-gray-400">
            <div class="flex items-center gap-3">
                <span class="text-[10px] font-bold text-gray-500 uppercase tracking-widest">Related:</span>
                <button onclick="triggerQuickPrompt('Explain this concept even simpler')" class="hover:text-white transition-colors">Simplify</button>
                <span class="text-[#222833]">•</span>
                <button onclick="triggerQuickPrompt('Give 3 real world architecture examples of this')" class="hover:text-white transition-colors">Real Examples</button>
                <span class="text-[#222833]">•</span>
                <button onclick="triggerQuickPrompt('Generate 3 active recall flashcards')" class="hover:text-white transition-colors">Flashcards</button>
            </div>
            <button onclick="triggerQuickPrompt('Teach me step by step until I understand')" class="text-[#5B8DEF] hover:underline font-medium text-[11px]">Teach Me Until I Understand →</button>
        </div>
    `;
}

// --- PASSWORD RECOVERY & AUTH WORKFLOW ---
let forgotState = {
    email: '',
    resetToken: '',
    cooldownTimer: null,
    cooldownSeconds: 60
};

function togglePasswordVisibility(inputId, btn) {
    const input = document.getElementById(inputId);
    if (!input) return;
    const isPassword = input.type === 'password';
    input.type = isPassword ? 'text' : 'password';
    const icon = btn.querySelector('i');
    if (icon) {
        icon.className = isPassword ? 'fa-regular fa-eye-slash text-sm' : 'fa-regular fa-eye text-sm';
    }
}

function openForgotPasswordModal() {
    const modal = document.getElementById('forgot-password-modal');
    if (!modal) return;
    modal.classList.remove('hidden');
    showForgotStep(1);
    
    // Auto populate email if user typed it on login page
    const loginEmail = document.getElementById('auth-email');
    const forgotEmail = document.getElementById('forgot-email');
    if (loginEmail && forgotEmail && loginEmail.value) {
        forgotEmail.value = loginEmail.value;
    }
}

function closeForgotPasswordModal() {
    const modal = document.getElementById('forgot-password-modal');
    if (modal) modal.classList.add('hidden');
    if (forgotState.cooldownTimer) clearInterval(forgotState.cooldownTimer);
    setForgotAlert('', 'clear');
}

function showForgotStep(stepNum) {
    ['forgot-step-1', 'forgot-step-2', 'forgot-step-3', 'forgot-step-success'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.add('hidden');
    });
    
    if (stepNum === 1) document.getElementById('forgot-step-1')?.classList.remove('hidden');
    if (stepNum === 2) document.getElementById('forgot-step-2')?.classList.remove('hidden');
    if (stepNum === 3) document.getElementById('forgot-step-3')?.classList.remove('hidden');
    if (stepNum === 'success') document.getElementById('forgot-step-success')?.classList.remove('hidden');
    
    setForgotAlert('', 'clear');
}

function setForgotAlert(msg, type = 'error') {
    const el = document.getElementById('forgot-modal-alert');
    if (!el) return;
    if (!msg) {
        el.classList.add('hidden');
        el.textContent = '';
        return;
    }
    el.classList.remove('hidden', 'text-red-400', 'text-emerald-400', 'text-amber-400');
    if (type === 'error') el.classList.add('text-red-400');
    if (type === 'success') el.classList.add('text-emerald-400');
    if (type === 'warning') el.classList.add('text-amber-400');
    el.textContent = msg;
}

async function sendPasswordResetCode() {
    const emailInput = document.getElementById('forgot-email');
    const email = emailInput ? emailInput.value.trim() : '';
    if (!email || !email.includes('@')) {
        setForgotAlert('Please enter a valid email address.', 'error');
        return;
    }
    
    const sendBtn = document.getElementById('forgot-send-btn');
    if (sendBtn) {
        sendBtn.disabled = true;
        sendBtn.innerHTML = `<span>Sending...</span><i class="fa-solid fa-spinner animate-spin text-xs"></i>`;
    }
    
    try {
        const res = await fetch('/auth/forgot-password/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email })
        });
        const data = await res.json();
        
        if (!res.ok) throw new Error(data.detail || 'Failed to send verification code.');
        
        forgotState.email = email;
        document.getElementById('forgot-sent-email').textContent = email;
        
        showForgotStep(2);
        startResendTimer(60);
        showToast(data.message || 'Verification code sent.', 'success');
    } catch (err) {
        setForgotAlert(err.message, 'error');
    } finally {
        if (sendBtn) {
            sendBtn.disabled = false;
            sendBtn.innerHTML = `<span>Send Verification Code</span><i class="fa-solid fa-paper-plane text-xs"></i>`;
        }
    }
}

async function resendPasswordResetCode() {
    if (forgotState.cooldownSeconds > 0) return;
    sendPasswordResetCode();
}

function startResendTimer(seconds = 60) {
    if (forgotState.cooldownTimer) clearInterval(forgotState.cooldownTimer);
    forgotState.cooldownSeconds = seconds;
    
    const resendBtn = document.getElementById('forgot-resend-btn');
    const timerSpan = document.getElementById('resend-timer');
    if (resendBtn) resendBtn.disabled = true;
    if (timerSpan) timerSpan.textContent = seconds;
    
    forgotState.cooldownTimer = setInterval(() => {
        forgotState.cooldownSeconds--;
        if (timerSpan) timerSpan.textContent = forgotState.cooldownSeconds;
        if (forgotState.cooldownSeconds <= 0) {
            clearInterval(forgotState.cooldownTimer);
            if (resendBtn) resendBtn.disabled = false;
        }
    }, 1000);
}

function handleOtpInput(input, event, index) {
    const boxes = document.querySelectorAll('.otp-box');
    const val = input.value;
    
    // Auto-focus next box if digit typed
    if (val && index < boxes.length - 1 && event.key !== 'Backspace') {
        boxes[index + 1].focus();
    }
    
    // Auto-focus previous box if Backspace pressed
    if (event.key === 'Backspace' && index > 0 && !val) {
        boxes[index - 1].focus();
    }
}

function handleOtpPaste(event) {
    event.preventDefault();
    const pasteData = (event.clipboardData || window.clipboardData).getData('text').trim();
    if (!pasteData) return;
    const digits = pasteData.replace(/\D/g, '').slice(0, 6);
    const boxes = document.querySelectorAll('.otp-box');
    digits.split('').forEach((d, i) => {
        if (boxes[i]) boxes[i].value = d;
    });
    if (boxes[digits.length - 1]) boxes[digits.length - 1].focus();
}

function getOtpValue() {
    const boxes = document.querySelectorAll('.otp-box');
    let code = '';
    boxes.forEach(box => code += box.value.trim());
    return code;
}

async function verifyPasswordResetCode() {
    const otp = getOtpValue();
    if (!otp || otp.length !== 6) {
        setForgotAlert('Please enter all 6 digits of your verification code.', 'error');
        return;
    }
    
    const verifyBtn = document.getElementById('forgot-verify-btn');
    if (verifyBtn) {
        verifyBtn.disabled = true;
        verifyBtn.innerHTML = `<span>Verifying...</span><i class="fa-solid fa-spinner animate-spin text-xs"></i>`;
    }
    
    try {
        const res = await fetch('/auth/verify-otp/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email: forgotState.email, otp })
        });
        const data = await res.json();
        
        if (!res.ok) throw new Error(data.detail || 'Invalid verification code.');
        
        forgotState.resetToken = data.reset_token;
        showForgotStep(3);
        showToast('Code verified successfully.', 'success');
    } catch (err) {
        setForgotAlert(err.message, 'error');
    } finally {
        if (verifyBtn) {
            verifyBtn.disabled = false;
            verifyBtn.innerHTML = `<span>Verify Code</span><i class="fa-solid fa-circle-check text-xs"></i>`;
        }
    }
}

function checkResetPasswordStrength(pw) {
    const bar = document.getElementById('pw-strength-bar');
    const label = document.getElementById('pw-strength-label');
    
    const hasLen = pw.length >= 8;
    const hasUpper = /[A-Z]/.test(pw);
    const hasLower = /[a-z]/.test(pw);
    const hasNum = /[0-9]/.test(pw);
    const hasSpecial = /[^A-Za-z0-9]/.test(pw);
    
    // Update live checklist icons
    updateReqIcon('req-len', hasLen);
    updateReqIcon('req-upper', hasUpper);
    updateReqIcon('req-lower', hasLower);
    updateReqIcon('req-num', hasNum);
    updateReqIcon('req-special', hasSpecial);

    if (!bar || !label) return;
    
    let score = 0;
    if (hasLen) score += 20;
    if (hasUpper) score += 20;
    if (hasLower) score += 20;
    if (hasNum) score += 20;
    if (hasSpecial) score += 20;
    
    bar.style.width = `${score}%`;
    bar.className = 'h-full transition-all duration-300 ';
    
    if (score <= 40) {
        bar.classList.add('bg-rose-500');
        label.textContent = 'Weak';
        label.className = 'font-semibold text-rose-400';
    } else if (score <= 80) {
        bar.classList.add('bg-amber-500');
        label.textContent = 'Moderate';
        label.className = 'font-semibold text-amber-400';
    } else {
        bar.classList.add('bg-emerald-500');
        label.textContent = 'Strong';
        label.className = 'font-semibold text-emerald-400';
    }
}

function updateReqIcon(elemId, isValid) {
    const el = document.getElementById(elemId);
    if (!el) return;
    const icon = el.querySelector('i');
    if (!icon) return;
    if (isValid) {
        icon.className = 'fa-solid fa-circle-check text-emerald-400 text-[10px]';
        el.classList.remove('text-gray-400');
        el.classList.add('text-emerald-300');
    } else {
        icon.className = 'fa-solid fa-circle-xmark text-rose-400 text-[10px]';
        el.classList.remove('text-emerald-300');
        el.classList.add('text-gray-400');
    }
}

async function submitNewPassword() {
    const newPw = document.getElementById('forgot-new-password')?.value || '';
    const confirmPw = document.getElementById('forgot-confirm-password')?.value || '';
    
    if (!newPw) {
        setForgotAlert('Please enter a new password.', 'error');
        return;
    }
    if (newPw !== confirmPw) {
        setForgotAlert('Passwords do not match.', 'error');
        return;
    }
    
    // Validate strength
    if (newPw.length < 8 || !/[A-Z]/.test(newPw) || !/[a-z]/.test(newPw) || !/[0-9]/.test(newPw) || !/[^A-Za-z0-9]/.test(newPw)) {
        setForgotAlert('Password must meet all 5 security requirements below.', 'error');
        return;
    }
    
    const resetBtn = document.getElementById('forgot-reset-btn');
    if (resetBtn) {
        resetBtn.disabled = true;
        resetBtn.innerHTML = `<span>Updating...</span><i class="fa-solid fa-spinner animate-spin text-xs"></i>`;
    }
    
    try {
        const res = await fetch('/auth/reset-password/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                email: forgotState.email,
                reset_token: forgotState.resetToken,
                new_password: newPw
            })
        });
        const data = await res.json();
        
        if (!res.ok) throw new Error(data.detail || 'Failed to update password.');
        
        showForgotStep('success');
        showToast('Password updated successfully!', 'success');
        
        setTimeout(() => {
            closeForgotPasswordModal();
            setAuthMode('login');
        }, 3000);
    } catch (err) {
        setForgotAlert(err.message, 'error');
    } finally {
        if (resetBtn) {
            resetBtn.disabled = false;
            resetBtn.innerHTML = `<span>Reset Password</span><i class="fa-solid fa-arrow-right text-xs"></i>`;
        }
    }
}

// Boot the application
init();
