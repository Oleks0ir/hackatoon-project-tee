// Navigation System
function nav(screenId) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(screenId).classList.add('active');
}

// Generate random avatars (Github Identicon Style Mockup)
const avatarGrid = document.getElementById('avatar-grid');
const emojis = ['👾', '🦊', '🦉', '🐱', '🤖', '👻', '🐙', '🦖', '🐸'];

emojis.forEach((emoji, index) => {
    const div = document.createElement('div');
    div.className = 'avatar-item';
    div.innerHTML = emoji;
    div.onclick = () => selectAvatar(div, index);
    avatarGrid.appendChild(div);
});

let selectedAvatarIndex = null;
function selectAvatar(element, index) {
    document.querySelectorAll('.avatar-item').forEach(el => el.classList.remove('selected'));
    element.classList.add('selected');
    selectedAvatarIndex = index;
    // Simulate local storage of Key/Profile
    localStorage.setItem('kolosok_avatar', index);
}

// Language Selection Logic
let selectedLangs = [];
function toggleLang(btn) {
    const lang = btn.innerText;
    if (btn.classList.contains('active')) {
        btn.classList.remove('active');
        selectedLangs = selectedLangs.filter(l => l !== lang);
    } else {
        btn.classList.add('active');
        selectedLangs.push(lang);
    }
    
    const langText = document.getElementById('selected-langs-text');
    if (selectedLangs.length > 0) {
        langText.innerText = 'Selected: ' + selectedLangs.join(', ');
    } else {
        langText.innerText = '';
    }
}

// Exclusive Selection for Gender Groups
function selectGender(groupId, btn) {
    const group = document.getElementById(groupId);
    // Remove active class from all buttons of this specific group
    group.querySelectorAll('.lang-chip').forEach(el => el.classList.remove('active'));
    // Set clicked button to active
    btn.classList.add('active');
}

// Dual Range Slider Logic
const ageMin = document.getElementById("age-min");
const ageMax = document.getElementById("age-max");
const ageVal = document.getElementById("age-val");
const sliderTrack = document.querySelector(".slider-track");
const minGap = 0; // minimum age range gap

function slideMin() {
    if (parseInt(ageMax.value) - parseInt(ageMin.value) <= minGap) {
        ageMin.value = parseInt(ageMax.value) - minGap;
    }
    ageVal.innerText = ageMin.value + " - " + ageMax.value;
    updateSliderTrack();
    ageMin.style.zIndex = "3";
    ageMax.style.zIndex = "2";
}

function slideMax() {
    if (parseInt(ageMax.value) - parseInt(ageMin.value) <= minGap) {
        ageMax.value = parseInt(ageMin.value) + minGap;
    }
    ageVal.innerText = ageMin.value + " - " + ageMax.value;
    updateSliderTrack();
    ageMin.style.zIndex = "2";
    ageMax.style.zIndex = "3";
}

function updateSliderTrack() {
    const minVal = parseInt(ageMin.value);
    const maxVal = parseInt(ageMax.value);
    const minPercent = ((minVal - 18) / (99 - 18)) * 100;
    const maxPercent = ((maxVal - 18) / (99 - 18)) * 100;
    sliderTrack.style.background = `linear-gradient(to right, #cbd5e1 ${minPercent}%, var(--primary) ${minPercent}%, var(--primary) ${maxPercent}%, #cbd5e1 ${maxPercent}%)`;
}

// Initialize the dual range slider color track on load
if (ageMin && ageMax) {
    updateSliderTrack();
}

// Multi-match logic definition
const mockMatches = [
    {
        id: "felix",
        name: "Felix",
        avatar: "🦊",
        score: "98%",
        bio: "AI Researcher at TUM. Loves bouldering and zero-knowledge proofs.",
        initialMessage: "Hey! The Confidential AI matched us with 98% compatibility. Let's chat!"
    },
    {
        id: "sophie",
        name: "Sophie",
        avatar: "🐱",
        score: "94%",
        bio: "Cybersecurity student. Passionate about TEEs and coffee.",
        initialMessage: "Hi there! It says we both love cryptography. What projects are you working on?"
    },
    {
        id: "lukas",
        name: "Lukas",
        avatar: "🤖",
        score: "89%",
        bio: "Software Engineer. Tinkers with hardware enclaves and IoT.",
        initialMessage: "Hey! Looks like we've got a lot in common according to the secure match."
    }
];

let chats = {};
let activeMatchId = null;

// Initialize or reset chats history
function initChats() {
    chats = {
        felix: [
            { sender: 'received', text: mockMatches[0].initialMessage }
        ],
        sophie: [
            { sender: 'received', text: mockMatches[1].initialMessage }
        ],
        lukas: [
            { sender: 'received', text: mockMatches[2].initialMessage }
        ]
    };
}

// Initialize on page load
initChats();

// Store original waiting screen HTML to restore on consecutive matches
let originalWaitingHtml = "";
window.addEventListener('DOMContentLoaded', () => {
    const waitingScreen = document.getElementById('screen-waiting');
    if (waitingScreen) {
        originalWaitingHtml = waitingScreen.innerHTML;
    }
});

// Matching & Socket Simulation
function startMatching() {
    // Restore waiting screen to loader state
    const waitingScreen = document.getElementById('screen-waiting');
    if (waitingScreen && originalWaitingHtml) {
        waitingScreen.innerHTML = originalWaitingHtml;
    }

    // Refresh chats history for a clean demo run
    initChats();

    // Switch to Waiting Screen
    nav('screen-waiting');

    // Collect data
    const profileData = {
        fname: document.getElementById('fname').value,
        lname: document.getElementById('lname').value,
        age: document.getElementById('my-age').value,
        story: document.getElementById('story-text').value,
        timestamp: new Date().toISOString()
    };
    
    // Save locally
    localStorage.setItem('kolosok_profile', JSON.stringify(profileData));

    // Simulate secure TEE connection
    console.log("Establishing secure connection to TEE...");
    
    // Mock WebSocket for demonstration purposes
    setTimeout(() => {
        simulateSocketMessage();
    }, 3500); // Waits 3.5 seconds before matches are found
}

function simulateSocketMessage() {
    const waitingScreen = document.getElementById('screen-waiting');
    if (!waitingScreen) return;

    // Convert waiting screen to the multi-match selector
    waitingScreen.innerHTML = `
        <div class="content-wrapper" style="padding-bottom: 0; width: 100%;">
            <h2 style="text-align: center; margin-bottom: 4px;">Matches Found!</h2>
            <p class="subtitle" style="text-align: center; margin-bottom: 24px;">The Confidential AI identified secure matches inside the TEE.</p>
            
            <div id="matches-list" style="display: flex; flex-direction: column; gap: 16px; width: 100%;">
                <!-- Match cards will be dynamically appended here -->
            </div>
        </div>
        <div class="button-container" style="margin-top: 24px;">
            <button class="btn-secondary" onclick="resetApp()">Change preferences</button>
        </div>
    `;

    const matchesList = document.getElementById('matches-list');
    mockMatches.forEach(match => {
        const card = document.createElement('div');
        card.className = 'match-card';
        card.style.cssText = `
            background: var(--card-bg);
            border: 1px solid #e2e8f0;
            border-radius: 16px;
            padding: 16px;
            display: flex;
            align-items: center;
            gap: 16px;
            cursor: pointer;
            transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
            box-shadow: 0 2px 4px rgba(0,0,0,0.01);
        `;
        
        // Dynamic hover animation in JS
        card.onmouseover = () => {
            card.style.borderColor = 'var(--primary)';
            card.style.transform = 'translateY(-2px)';
            card.style.boxShadow = '0 6px 16px rgba(99, 102, 241, 0.08)';
        };
        card.onmouseout = () => {
            card.style.borderColor = '#e2e8f0';
            card.style.transform = 'translateY(0)';
            card.style.boxShadow = '0 2px 4px rgba(0,0,0,0.01)';
        };
        
        card.onclick = () => openChatForMatch(match.id);
        
        card.innerHTML = `
            <div class="avatar-item selected" style="width: 56px; height: 56px; font-size: 2.2rem; margin: 0; cursor: pointer; flex-shrink: 0; background: #e0e7ff;">${match.avatar}</div>
            <div style="flex: 1; min-width: 0;">
                <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px;">
                    <h3 style="font-size: 1.1rem; font-weight: 700; margin: 0; color: var(--text-main);">${match.name}</h3>
                    <span style="background: #e2f0fd; color: #1d4ed8; font-size: 0.75rem; font-weight: 700; padding: 4px 10px; border-radius: 9999px;">${match.score} Match</span>
                </div>
                <p style="font-size: 0.85rem; color: var(--text-muted); margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${match.bio}</p>
            </div>
        `;
        matchesList.appendChild(card);
    });
}

function openChatForMatch(matchId) {
    activeMatchId = matchId;
    const match = mockMatches.find(m => m.id === matchId);
    if (!match) return;
    
    // Update Chat Header
    document.getElementById('chat-avatar').innerText = match.avatar;
    document.getElementById('chat-name').innerText = match.name;
    
    // Configure the Back button dynamically to return to matches list
    const chatHeader = document.querySelector('#screen-chat .chat-header');
    const backBtn = chatHeader.querySelector('.btn-icon');
    backBtn.setAttribute('onclick', "showMatchesList()");

    // Load messages list
    renderMessages();
    
    // Navigate to Chat Screen
    nav('screen-chat');
}

function showMatchesList() {
    nav('screen-waiting');
}

function renderMessages() {
    const messagesContainer = document.getElementById('chat-messages');
    if (!messagesContainer) return;
    
    messagesContainer.innerHTML = '';
    
    const messages = chats[activeMatchId] || [];
    messages.forEach(msg => {
        const msgElement = document.createElement('div');
        msgElement.className = `message ${msg.sender}`;
        msgElement.innerText = msg.text;
        messagesContainer.appendChild(msgElement);
    });
    
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Logic for sending messages in Chat
function sendMessage() {
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    
    if (!text || !activeMatchId) return; // Ignore empty messages
    
    // Save message to chat history
    if (!chats[activeMatchId]) {
        chats[activeMatchId] = [];
    }
    chats[activeMatchId].push({ sender: 'sent', text: text });
    
    // Render new messages and clear input
    renderMessages();
    input.value = '';
}

function resetApp() {
    nav('screen-demographics');
}