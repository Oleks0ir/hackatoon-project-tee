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

let realMatch = null;
let pollIntervalId = null;

// Toast helper function
function showToast(message, type = 'info') {
    // Remove existing toast if any
    const existing = document.getElementById('toast-notification');
    if (existing) {
        existing.remove();
    }

    const toast = document.createElement('div');
    toast.id = 'toast-notification';
    
    // Style the toast bubble
    toast.style.cssText = `
        position: fixed;
        bottom: 24px;
        left: 50%;
        transform: translateX(-50%) translateY(100px);
        background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#1e293b'};
        color: white;
        padding: 12px 24px;
        border-radius: 12px;
        font-family: 'Montserrat', sans-serif;
        font-size: 0.9rem;
        font-weight: 600;
        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
        z-index: 9999;
        transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        opacity: 0;
        display: flex;
        align-items: center;
        gap: 8px;
    `;
    
    const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
    toast.innerHTML = `<span>${icon}</span> <span>${message}</span>`;
    
    document.body.appendChild(toast);
    
    // Animate in
    setTimeout(() => {
        toast.style.transform = 'translateX(-50%) translateY(0)';
        toast.style.opacity = '1';
    }, 50);
    
    // Animate out after 4 seconds
    setTimeout(() => {
        toast.style.transform = 'translateX(-50%) translateY(100px)';
        toast.style.opacity = '0';
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 4000);
}

// Peer handle parser
function parsePeerHandle(handle) {
    if (!handle) return { name: 'Anonymous', emoji: '👤' };
    
    // Emoji pattern matching
    const emojiRegex = /[\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{1F1E6}-\u{1F1FF}\u{1F191}-\u{1F251}\u{1F600}-\u{1F64F}\u{1F680}-\u{1F6FF}\u{1F900}-\u{1F9FF}\u{1FA00}-\u{1FAFF}\u{200d}]/u;
    const match = handle.match(emojiRegex);
    const emoji = match ? match[0] : '👤';
    const name = handle.replace(emojiRegex, '').trim();
    return { name: name || 'User', emoji };
}

// Matching & Submitting
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
    const fname = document.getElementById('fname').value;
    const lname = document.getElementById('lname').value;
    const age = parseInt(document.getElementById('my-age').value, 10) || 0;
    const story = document.getElementById('story-text').value;
    
    const myGenderActive = document.querySelector('#my-gender-group .lang-chip.active');
    const myGender = myGenderActive ? myGenderActive.innerText : '';
    
    const targetGenderActive = document.querySelector('#target-gender-group .lang-chip.active');
    const targetGender = targetGenderActive ? targetGenderActive.innerText : '';
    
    const ageMinVal = parseInt(document.getElementById('age-min').value, 10) || 18;
    const ageMaxVal = parseInt(document.getElementById('age-max').value, 10) || 99;

    const avatarIndex = selectedAvatarIndex !== null && selectedAvatarIndex !== undefined ? selectedAvatarIndex : 1;
    const avatarEmoji = selectedAvatarIndex !== null && selectedAvatarIndex !== undefined ? emojis[selectedAvatarIndex] : '🦊';

    const payload = {
        profile: {
            first_name: fname,
            last_name: lname,
            age: age,
            avatar_index: avatarIndex,
            avatar_emoji: avatarEmoji
        },
        demographics: {
            my_gender: myGender,
            target_gender: targetGender,
            age_range: {
                min: ageMinVal,
                max: ageMaxVal
            },
            languages: selectedLangs
        },
        matching_data: {
            story: story
        },
        metadata: {
            client_timestamp: new Date().toISOString(),
            app_version: "1.0.0"
        }
    };
    
    // Save locally
    localStorage.setItem('kolosok_profile', JSON.stringify({
        fname: fname,
        lname: lname,
        age: age,
        story: story,
        timestamp: payload.metadata.client_timestamp
    }));

    // Establish secure connection and send POST request to the submission endpoint
    console.log("Establishing secure connection to TEE and submitting profile...");
    console.log("Payload:", JSON.stringify(payload, null, 2));
    
    fetch('http://10.217.111.34:8765/submit', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('Successfully submitted profile to TEE:', data);
        if (data.ok && data.token) {
            localStorage.setItem('kolosok_token', data.token);
            showToast("Profile submitted! Securing matchmaking enclave...", "success");
            startPolling(data.token);
        } else {
            const errorMsg = data.error || 'Unknown error occurred';
            showToast(`Submission error: ${errorMsg}`, "error");
            nav('screen-story'); // Revert back
        }
    })
    .catch(error => {
        console.error('Error submitting profile to TEE:', error);
        showToast(`Network error: ${error.message}`, "error");
        nav('screen-story'); // Revert back
    });
}

// Polling for results
function startPolling(token) {
    if (pollIntervalId) {
        clearInterval(pollIntervalId);
    }
    
    const pollUrl = `http://10.217.111.34:8765/result/${token}`;
    
    pollIntervalId = setInterval(() => {
        fetch(pollUrl)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log("Poll result:", data);
            if (data.round_done) {
                clearInterval(pollIntervalId);
                pollIntervalId = null;
                
                if (data.matched) {
                    showRealMatch(data);
                } else {
                    showNoMatch();
                }
            }
        })
        .catch(error => {
            console.error("Error polling result enclave:", error);
        });
    }, 2000); // Poll every 2 seconds
}

// Show Real Match UI
function showRealMatch(matchData) {
    const waitingScreen = document.getElementById('screen-waiting');
    if (!waitingScreen) return;

    const { name, emoji } = parsePeerHandle(matchData.peer_handle);
    const scoreText = typeof matchData.score === 'number' ? `${Math.round(matchData.score)}%` : matchData.score;
    const verdict = matchData.verdict || 'Match';
    const connectionCode = matchData.connection_code || '';

    // Save active real match data
    realMatch = {
        id: "real_match",
        name: name,
        avatar: emoji,
        score: scoreText,
        bio: `Verdict: ${verdict} | Connection Code: ${connectionCode}`,
        initialMessage: `Hey! The Confidential AI matched us with ${scoreText} compatibility. Connection Code: ${connectionCode}`
    };

    // Update chats with the initial message
    chats["real_match"] = [
        { sender: 'received', text: realMatch.initialMessage }
    ];

    waitingScreen.innerHTML = `
        <div class="content-wrapper" style="padding-bottom: 0; width: 100%;">
            <h2 style="text-align: center; margin-bottom: 4px;">Match Found!</h2>
            <p class="subtitle" style="text-align: center; margin-bottom: 24px;">The Confidential AI identified secure matches inside the TEE.</p>
            
            <div id="matches-list" style="display: flex; flex-direction: column; gap: 16px; width: 100%;">
                <!-- Match card is appended here -->
            </div>
        </div>
        <div class="button-container" style="margin-top: 24px;">
            <button class="btn-secondary" onclick="resetApp()">Change preferences</button>
        </div>
    `;

    const matchesList = document.getElementById('matches-list');
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
    
    card.onclick = () => openChatForMatch("real_match");
    
    card.innerHTML = `
        <div class="avatar-item selected" style="width: 56px; height: 56px; font-size: 2.2rem; margin: 0; cursor: pointer; flex-shrink: 0; background: #e0e7ff;">${emoji}</div>
        <div style="flex: 1; min-width: 0;">
            <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px;">
                <h3 style="font-size: 1.1rem; font-weight: 700; margin: 0; color: var(--text-main);">${name}</h3>
                <span style="background: #e2f0fd; color: #1d4ed8; font-size: 0.75rem; font-weight: 700; padding: 4px 10px; border-radius: 9999px;">${scoreText} Match</span>
            </div>
            <p style="font-size: 0.85rem; color: var(--text-muted); margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${realMatch.bio}</p>
        </div>
    `;
    matchesList.appendChild(card);
}

// Show No Match UI
function showNoMatch() {
    const waitingScreen = document.getElementById('screen-waiting');
    if (!waitingScreen) return;
    
    waitingScreen.innerHTML = `
        <div class="content-wrapper center-content" style="padding-bottom: 0; width: 100%;">
            <span style="font-size: 4rem; margin-bottom: 16px; display: block;">😔</span>
            <h2 style="text-align: center; margin-bottom: 8px;">No Matches This Round</h2>
            <p class="subtitle" style="text-align: center; margin-bottom: 24px; max-width: 320px; margin-left: auto; margin-right: auto;">The Confidential AI ran the matching protocol inside the TEE but did not find any highly compatible matches this round.</p>
        </div>
        <div class="button-container" style="margin-top: 32px;">
            <button class="btn-primary" onclick="resetApp()">Change preferences</button>
        </div>
    `;
}

function openChatForMatch(matchId) {
    activeMatchId = matchId;
    let match = mockMatches.find(m => m.id === matchId);
    if (!match && matchId === 'real_match') {
        match = realMatch;
    }
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
    if (pollIntervalId) {
        clearInterval(pollIntervalId);
        pollIntervalId = null;
    }
    nav('screen-demographics');
}