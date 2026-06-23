// Register Service Worker for PWA support
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('./sw.js')
            .then(reg => {
                console.log('[PWA] Service worker registered successfully', reg);
                // Handle messages from service worker (notification clicks)
                navigator.serviceWorker.addEventListener('message', (event) => {
                    if (event.data && event.data.type === 'NOTIFICATION_CLICK') {
                        const { matchId, isMatch } = event.data;
                        window.focus();
                        if (isMatch) {
                            nav('screen-waiting');
                        } else if (matchId) {
                            openChatForMatch(matchId);
                        }
                    }
                });
                
                console.log('[PWA] Notification permission state on load:', Notification.permission);
                // Attempt Web Push subscription if permission is already granted
                if (Notification.permission === 'granted') {
                    navigator.serviceWorker.ready.then(activeReg => {
                        console.log('[PWA] Service worker ready on load, starting push subscription...');
                        subscribeToWebPush(activeReg);
                    });
                } else {
                    console.log('[PWA] Notification permission not granted yet. Current state:', Notification.permission);
                }
            })
            .catch(err => console.error('[PWA] Service worker registration failed', err));
    });
}

// PWA Install Logic
let deferredPrompt;
window.addEventListener('beforeinstallprompt', (e) => {
    // Prevent the mini-infobar from appearing on mobile
    e.preventDefault();
    // Stash the event so it can be triggered later.
    deferredPrompt = e;
    // Update UI notify the user they can install the PWA
    const installBtn = document.getElementById('pwa-install-btn');
    if (installBtn) {
        installBtn.style.display = 'block';
    }
    console.log('[PWA] beforeinstallprompt event fired and captured');
});

function triggerPwaInstall() {
    if (!deferredPrompt) {
        return;
    }
    // Show the install prompt
    deferredPrompt.prompt();
    // Wait for the user to respond to the prompt
    deferredPrompt.userChoice.then((choiceResult) => {
        if (choiceResult.outcome === 'accepted') {
            console.log('[PWA] User accepted the install prompt');
        } else {
            console.log('[PWA] User dismissed the install prompt');
        }
        deferredPrompt = null;
        // Hide the install button
        const installBtn = document.getElementById('pwa-install-btn');
        if (installBtn) {
            installBtn.style.display = 'none';
        }
    });
}

window.addEventListener('appinstalled', (evt) => {
    console.log('[PWA] DayTEE has been installed successfully!');
    // Hide the install button
    const installBtn = document.getElementById('pwa-install-btn');
    if (installBtn) {
        installBtn.style.display = 'none';
    }
});

// Navigation System
function nav(screenId) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(screenId).classList.add('active');
    
    // Stop match polling if navigating back to user setup screens
    if (['screen-name', 'screen-avatar', 'screen-demographics', 'screen-story'].includes(screenId)) {
        if (pollIntervalId) {
            clearInterval(pollIntervalId);
            pollIntervalId = null;
        }
    }
    
    if (screenId === 'screen-name') {
        const ageInput = document.getElementById('my-age');
        const currentAge = ageInput ? ageInput.value : 18;
        setTimeout(() => {
            setAgePickerValue(currentAge);
        }, 50);
    }
}

function validateAndNavName() {
    // Request notification permission on user click gesture (required for modern browsers & iOS PWA support)
    requestNotificationPermission();

    const fname = document.getElementById('fname').value.trim();
    const lname = document.getElementById('lname').value.trim();
    const ageVal = document.getElementById('my-age').value;
    const age = parseInt(ageVal, 10);

    if (!fname) {
        showToast("First Name is required.", "error");
        return;
    }
    if (!lname) {
        showToast("Last Name is required.", "error");
        return;
    }
    if (!ageVal || isNaN(age) || age < 18) {
        showToast("You must enter a valid age (18 or older).", "error");
        return;
    }
    nav('screen-avatar');
}

function validateAndNavAvatar() {
    if (selectedAvatarIndex === null || selectedAvatarIndex === undefined) {
        showToast("Please select an avatar to proceed.", "error");
        return;
    }
    nav('screen-demographics');
}

function validateAndNavDemographics() {
    const myGenderActive = document.querySelector('#my-gender-group .lang-chip.active');
    const targetGenderActive = document.querySelector('#target-gender-group .lang-chip.active');
    
    if (!myGenderActive) {
        showToast("Please select your gender.", "error");
        return;
    }
    if (!targetGenderActive) {
        showToast("Please select who you are looking for.", "error");
        return;
    }
    if (selectedLangs.length === 0) {
        showToast("Please select at least one language.", "error");
        return;
    }
    nav('screen-story');
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
    saveProfileState();
}

// Language Selection Logic
let selectedLangs = [];

function saveProfileState() {
    try {
        const fname = document.getElementById('fname') ? document.getElementById('fname').value.trim() : "";
        const lname = document.getElementById('lname') ? document.getElementById('lname').value.trim() : "";
        const ageVal = document.getElementById('my-age') ? document.getElementById('my-age').value : "";
        const story = document.getElementById('story-text') ? document.getElementById('story-text').value.trim() : "";
        
        const myGenderActive = document.querySelector('#my-gender-group .lang-chip.active');
        const targetGenderActive = document.querySelector('#target-gender-group .lang-chip.active');
        const myGender = myGenderActive ? (myGenderActive.getAttribute('data-val') || myGenderActive.innerText.trim()) : "";
        const targetGender = targetGenderActive ? (targetGenderActive.getAttribute('data-val') || targetGenderActive.innerText.trim()) : "";
        
        const ageMinVal = document.getElementById('age-min') ? parseInt(document.getElementById('age-min').value, 10) : 18;
        const ageMaxVal = document.getElementById('age-max') ? parseInt(document.getElementById('age-max').value, 10) : 99;

        localStorage.setItem('kolosok_profile', JSON.stringify({
            fname: fname,
            lname: lname,
            age: ageVal,
            story: story,
            myGender: myGender,
            targetGender: targetGender,
            ageMin: ageMinVal,
            ageMax: ageMaxVal,
            languages: selectedLangs,
            timestamp: new Date().toISOString()
        }));
    } catch (e) {
        console.error("Error saving profile state:", e);
    }
}

function restoreProfileFromLocalStorage() {
    try {
        const profileJson = localStorage.getItem('kolosok_profile');
        if (!profileJson) return;
        
        const profileObj = JSON.parse(profileJson);
        
        // 1. Text Fields
        if (document.getElementById('fname')) document.getElementById('fname').value = profileObj.fname || "";
        if (document.getElementById('lname')) document.getElementById('lname').value = profileObj.lname || "";
        if (document.getElementById('my-age')) {
            document.getElementById('my-age').value = profileObj.age || "18";
            setTimeout(() => setAgePickerValue(profileObj.age), 150);
        }
        if (document.getElementById('story-text')) document.getElementById('story-text').value = profileObj.story || "";
        
        // 2. Avatar
        const avatarVal = localStorage.getItem('kolosok_avatar');
        if (avatarVal !== null) {
            selectedAvatarIndex = parseInt(avatarVal, 10);
            setTimeout(() => {
                const avatarItems = document.querySelectorAll('.avatar-item');
                avatarItems.forEach(el => el.classList.remove('selected'));
                if (avatarItems[selectedAvatarIndex]) {
                    avatarItems[selectedAvatarIndex].classList.add('selected');
                }
            }, 100);
        }
        
        // 3. Genders
        if (profileObj.myGender) {
            const myGenderGroup = document.getElementById('my-gender-group');
            if (myGenderGroup) {
                myGenderGroup.querySelectorAll('.lang-chip').forEach(btn => {
                    const val = btn.getAttribute('data-val') || btn.innerText.trim();
                    if (val === profileObj.myGender) {
                        btn.classList.add('active');
                    } else {
                        btn.classList.remove('active');
                    }
                });
            }
        }
        if (profileObj.targetGender) {
            const targetGenderGroup = document.getElementById('target-gender-group');
            if (targetGenderGroup) {
                targetGenderGroup.querySelectorAll('.lang-chip').forEach(btn => {
                    const val = btn.getAttribute('data-val') || btn.innerText.trim();
                    if (val === profileObj.targetGender) {
                        btn.classList.add('active');
                    } else {
                        btn.classList.remove('active');
                    }
                });
            }
        }
        
        // 4. Age Range
        if (profileObj.ageMin !== undefined && profileObj.ageMax !== undefined) {
            const ageMinEl = document.getElementById('age-min');
            const ageMaxEl = document.getElementById('age-max');
            const ageValEl = document.getElementById('age-val');
            if (ageMinEl && ageMaxEl) {
                ageMinEl.value = profileObj.ageMin;
                ageMaxEl.value = profileObj.ageMax;
                if (ageValEl) {
                    ageValEl.innerText = ageMinEl.value + " - " + ageMaxEl.value;
                }
                updateSliderTrack();
            }
        }
        
        // 5. Languages
        if (profileObj.languages) {
            selectedLangs = profileObj.languages;
            
            // Update selection UI text
            const langText = document.getElementById('selected-langs-text');
            if (langText) {
                if (selectedLangs.length > 0) {
                    langText.innerText = 'Selected: ' + selectedLangs.join(', ');
                } else {
                    langText.innerText = '';
                }
            }
            
            // Highlight corresponding buttons in the modal
            const langModal = document.getElementById('lang-modal');
            if (langModal) {
                langModal.querySelectorAll('.lang-chip').forEach(btn => {
                    const val = btn.getAttribute('data-val') || btn.innerText.trim();
                    if (selectedLangs.includes(val)) {
                        btn.classList.add('active');
                    } else {
                        btn.classList.remove('active');
                    }
                });
            }
        }
        
        const storyTextEl = document.getElementById('story-text');
        if (storyTextEl) {
            storyTextEl.dispatchEvent(new Event('input'));
        }
    } catch (e) {
        console.error("Error restoring profile from local storage:", e);
    }
}

function toggleLang(btn) {
    const lang = btn.getAttribute('data-val') || btn.innerText.trim();
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
    saveProfileState();
}

// Exclusive Selection for Gender Groups
function selectGender(groupId, btn) {
    const group = document.getElementById(groupId);
    // Remove active class from all buttons of this specific group
    group.querySelectorAll('.lang-chip').forEach(el => el.classList.remove('active'));
    // Set clicked button to active
    btn.classList.add('active');
    saveProfileState();
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
    saveProfileState();
}

function slideMax() {
    if (parseInt(ageMax.value) - parseInt(ageMin.value) <= minGap) {
        ageMax.value = parseInt(ageMin.value) + minGap;
    }
    ageVal.innerText = ageMin.value + " - " + ageMax.value;
    updateSliderTrack();
    ageMin.style.zIndex = "2";
    ageMax.style.zIndex = "3";
    saveProfileState();
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

let chats = {};
let activeMatchId = null;

// Initialize or reset chats history
function initChats() {
    chats = {};
}

// Initialize on page load
initChats();

// Store original waiting screen HTML to restore on consecutive matches
let originalWaitingHtml = "";
window.addEventListener('DOMContentLoaded', () => {
    // Initialize age vertical carousel
    initAgePicker();

    const waitingScreen = document.getElementById('screen-waiting');
    if (waitingScreen) {
        originalWaitingHtml = waitingScreen.innerHTML;
    }
    
    // Check URL parameters for notification click routing
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('notification') === 'true') {
        const isMatch = urlParams.get('isMatch') === 'true';
        const matchId = urlParams.get('matchId');
        if (isMatch) {
            const savedToken = localStorage.getItem('kolosok_token');
            if (savedToken) {
                restoreSession(savedToken);
            } else {
                nav('screen-waiting');
            }
        } else if (matchId) {
            const savedToken = localStorage.getItem('kolosok_token');
            if (savedToken) {
                restoreSession(savedToken);
                setTimeout(() => {
                    openChatForMatch(matchId);
                }, 300);
            }
        }
        window.history.replaceState({}, document.title, window.location.pathname);
    } else {
        // Attempt to restore existing session
        const savedToken = localStorage.getItem('kolosok_token');
        if (savedToken) {
            restoreSession(savedToken);
        } else {
            restoreProfileFromLocalStorage();
        }
    }
    
    // Request notification permission
    requestNotificationPermission();

    // Bind input listeners for text changes to auto-save profile
    ['fname', 'lname', 'story-text'].forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', saveProfileState);
        }
    });

    const storyText = document.getElementById('story-text');
    if (storyText) {
        const updateWordCount = () => {
            const text = storyText.value.trim();
            const words = text ? text.split(/\s+/).filter(w => w.length > 0) : [];
            const count = words.length;
            const indicator = document.getElementById('word-count-indicator');
            if (indicator) {
                indicator.innerText = `${count} / 10 words`;
                if (count >= 10) {
                    indicator.style.color = '#10b981'; // Green
                } else {
                    indicator.style.color = 'var(--text-muted)';
                }
            }
        };
        storyText.addEventListener('input', updateWordCount);
        setTimeout(updateWordCount, 250);
    }
});

let realMatch = null;
let realMatches = [];
let pollIntervalId = null;
let chatPollIntervalId = null;
let lastMatchData = null;

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
    // Request notification permission on user click gesture
    requestNotificationPermission();

    const fname = document.getElementById('fname').value.trim();
    const lname = document.getElementById('lname').value.trim();
    const ageVal = document.getElementById('my-age').value;
    const age = parseInt(ageVal, 10);
    const story = document.getElementById('story-text').value.trim();

    if (!fname) {
        showToast("First Name is required.", "error");
        nav('screen-name');
        return;
    }
    if (!lname) {
        showToast("Last Name is required.", "error");
        nav('screen-name');
        return;
    }
    if (!ageVal || isNaN(age) || age < 18) {
        showToast("You must enter a valid age (18 or older).", "error");
        nav('screen-name');
        return;
    }
    if (selectedAvatarIndex === null || selectedAvatarIndex === undefined) {
        showToast("Please select an avatar.", "error");
        nav('screen-avatar');
        return;
    }
    const myGenderActive = document.querySelector('#my-gender-group .lang-chip.active');
    const targetGenderActive = document.querySelector('#target-gender-group .lang-chip.active');
    if (!myGenderActive) {
        showToast("Please select your gender.", "error");
        nav('screen-demographics');
        return;
    }
    if (!targetGenderActive) {
        showToast("Please select who you are looking for.", "error");
        nav('screen-demographics');
        return;
    }
    if (selectedLangs.length === 0) {
        showToast("Please select at least one language.", "error");
        nav('screen-demographics');
        return;
    }
    if (!story) {
        showToast("Please write your story before submitting.", "error");
        return;
    }
    const storyWords = story.split(/\s+/).filter(w => w.length > 0);
    if (storyWords.length < 10) {
        showToast("Please write a longer story (minimum 10 words) for accurate matching.", "error");
        return;
    }

    // Restore waiting screen to loader state
    const waitingScreen = document.getElementById('screen-waiting');
    if (waitingScreen && originalWaitingHtml) {
        waitingScreen.innerHTML = originalWaitingHtml;
    }

    // Ensure chats history has mock matches initialized on first run, but don't reset on new submissions
    if (!chats || Object.keys(chats).length === 0) {
        initChats();
    }

    // Switch to Waiting Screen
    nav('screen-waiting');

    // Collect data
    const myGender = myGenderActive.getAttribute('data-val') || myGenderActive.innerText.trim();
    const targetGender = targetGenderActive.getAttribute('data-val') || targetGenderActive.innerText.trim();
    const ageMinVal = parseInt(document.getElementById('age-min').value, 10) || 18;
    const ageMaxVal = parseInt(document.getElementById('age-max').value, 10) || 99;

    const avatarIndex = selectedAvatarIndex;
    const avatarEmoji = emojis[selectedAvatarIndex];

    const payload = {
        token: localStorage.getItem('kolosok_token') || null,
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
    saveProfileState();

    // Establish secure connection and send POST request to the submission endpoint
    console.log("Establishing secure connection to TEE and submitting profile...");
    console.log("Payload:", JSON.stringify(payload, null, 2));
    
    const apiHost = window.location.hostname || 'localhost';
    fetch(`/submit`, {
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
            
            // Subscribe to Web Push for the new token
            if ('serviceWorker' in navigator) {
                console.log('[PWA] Attempting push subscription for new token. Permission:', Notification.permission);
                if (Notification.permission === 'granted') {
                    navigator.serviceWorker.ready.then(reg => {
                        console.log('[PWA] Service worker ready for new token, subscribing...');
                        subscribeToWebPush(reg);
                    });
                }
            }
            
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
    
    const apiHost = window.location.hostname || 'localhost';
    const pollUrl = `/result/${token}`;
    
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
                if (data.matched && data.matches) {
                    // Check if there are any new matches that we haven't seen in realMatches
                    const existingCodes = new Set(realMatches.map(m => m.connection_code));
                    const newMatches = data.matches.filter(m => !existingCodes.has(m.connection_code));
                    
                    if (newMatches.length > 0) {
                        // Found new matches! Re-render UI
                        showRealMatch(data);
                        
                        // Notify the user about each new match
                        newMatches.forEach(m => {
                            const { name } = parsePeerHandle(m.peer_handle);
                            showWebNotification("New Match Found! 🎉", `The enclave matched you with ${name}.`, `real_match_${m.connection_code}`, true);
                        });
                    }
                } else {
                    // Check if we are already displaying the "No Matches Found" screen to avoid layout flashing
                    const waitingScreen = document.getElementById('screen-waiting');
                    const matchesList = document.getElementById('matches-list');
                    const isNoMatchesScreen = waitingScreen && matchesList && waitingScreen.querySelector('h2') && waitingScreen.querySelector('h2').innerText.includes("No Matches Found");
                    
                    if (!isNoMatchesScreen) {
                        showNoMatch();
                    }
                }
            }
        })
        .catch(error => {
            console.error("Error polling result enclave:", error);
        });
    }, 5000); // Poll every 5 seconds
}

// Helper to create match cards
function createMatchCard(match) {
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
    
    card.onclick = () => openChatForMatch(match.id);
    
    // Determine the subtitle text (show last message if conversation started, fallback to placeholder)
    let displaySub = "No messages yet";
    const matchChats = chats[match.id];
    if (matchChats && matchChats.length > 0) {
        const lastMsg = matchChats[matchChats.length - 1];
        if (lastMsg.sender === 'sent') {
            displaySub = `You: ${lastMsg.text}`;
        } else {
            displaySub = lastMsg.text;
        }
    }
    
    card.innerHTML = `
        <div class="avatar-item selected" style="width: 56px; height: 56px; font-size: 2.2rem; margin: 0; cursor: pointer; flex-shrink: 0; background: #e0e7ff;">${match.avatar}</div>
        <div style="flex: 1; min-width: 0;">
            <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 4px;">
                <h3 style="font-size: 1.1rem; font-weight: 700; margin: 0; color: var(--text-main);">${match.name}</h3>
                <span style="background: #e2f0fd; color: #1d4ed8; font-size: 0.75rem; font-weight: 700; padding: 4px 10px; border-radius: 9999px;">${match.score} Match</span>
            </div>
            <p id="subtitle-${match.id}" style="font-size: 0.85rem; color: var(--text-muted); margin: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${displaySub}</p>
        </div>
    `;
    return card;
}

// Show Real Match UI (renders both real matches and mock matches)
function showRealMatch(matchData) {
    lastMatchData = matchData;
    const waitingScreen = document.getElementById('screen-waiting');
    if (!waitingScreen) return;

    realMatches = [];
    if (matchData.matched && matchData.matches) {
        matchData.matches.forEach(m => {
            const { name, emoji } = parsePeerHandle(m.peer_handle);
            const scoreText = typeof m.score === 'number' ? `${Math.round(m.score)}%` : m.score;
            const verdict = m.verdict || 'Match';
            const connectionCode = m.connection_code || '';
            
            const matchObj = {
                id: `real_match_${connectionCode}`,
                name: name,
                avatar: emoji,
                score: scoreText,
                bio: `Verdict: ${verdict} | Connection Code: ${connectionCode}`,
                initialMessage: `Hey! The Confidential AI matched us with ${scoreText} compatibility. Connection Code: ${connectionCode}`,
                connection_code: connectionCode
            };
            realMatches.push(matchObj);
            
            // Initialize chat history for this real match if not already present
            if (!chats[matchObj.id]) {
                chats[matchObj.id] = [];
            }
        });
    }

    // Helper to get numeric score for sorting
    const getNumericScore = (scoreStr) => {
        if (typeof scoreStr === 'number') return scoreStr;
        const clean = String(scoreStr || '').replace('%', '').trim();
        const parsed = parseFloat(clean);
        return isNaN(parsed) ? 0 : parsed;
    };

    const combined = [...realMatches];
    // Sort descending by score
    combined.sort((a, b) => getNumericScore(b.score) - getNumericScore(a.score));
    
    // Take only the top 3
    const top3 = combined.slice(0, 3);
    const hasMatches = combined.length > 0;

    waitingScreen.innerHTML = `
        <button class="back-btn" onclick="nav('screen-story')">←</button>
        <div class="content-wrapper" style="padding-bottom: 0; width: 100%;">
            <h2 style="margin-bottom: 4px;">${hasMatches ? "Matches Found!" : "No Matches Found"}</h2>
            <p class="subtitle" style="margin-bottom: 24px;">${hasMatches ? "The Confidential AI identified secure matches inside the TEE." : "The secure matchmaking algorithm didn't find compatible profiles in this round."}</p>
            
            <div id="matches-list" style="display: flex; flex-direction: column; gap: 16px; width: 100%;">
                <!-- Match cards will be appended here -->
            </div>
        </div>
        <div class="button-container" style="margin-top: 24px;">
            <button class="btn-secondary" onclick="resetApp()">Change preferences</button>
        </div>
    `;

    const matchesList = document.getElementById('matches-list');

    if (!hasMatches) {
        matchesList.innerHTML = `
            <div style="text-align: center; padding: 40px 20px; border: 1px dashed var(--border); border-radius: 16px; background: rgba(255,255,255,0.02); margin-top: 16px;">
                <div style="font-size: 3rem; margin-bottom: 16px;">💔</div>
                <h3 style="font-size: 1.1rem; font-weight: 700; margin-bottom: 8px; color: var(--text-main);">No matches found</h3>
                <p style="font-size: 0.85rem; color: var(--text-muted); line-height: 1.4; max-width: 280px; margin: 0 auto;">Try adjusting your preferences or life story to find compatible partners.</p>
            </div>
        `;
    } else {
        // Render top 3 matches
        top3.forEach(match => {
            const card = createMatchCard(match);
            matchesList.appendChild(card);
        });
    }

    // Start background polling for chat messages
    startBackgroundChatPolling();
}

// Show No Match UI
function showNoMatch() {
    // Deprecated in favor of showRealMatch which displays mock matches when no real matches exist.
    showRealMatch({ matched: false, matches: [] });
}

function openChatForMatch(matchId) {
    activeMatchId = matchId;
    let match = null;
    if (matchId.startsWith('real_match_')) {
        const roomCode = matchId.replace('real_match_', '');
        match = realMatches.find(m => m.connection_code === roomCode);
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

    // Start/Stop chat polling
    if (matchId.startsWith('real_match_')) {
        startChatPolling();
    } else {
        stopChatPolling();
    }
}

function showMatchesList() {
    stopChatPolling();
    if (lastMatchData) {
        showRealMatch(lastMatchData);
    }
    nav('screen-waiting');
}

function renderMessages() {
    const messagesContainer = document.getElementById('chat-messages');
    if (!messagesContainer) return;
    
    messagesContainer.innerHTML = '';
    
    const messages = chats[activeMatchId] || [];
    
    if (messages.length === 0) {
        let match = realMatches.find(m => m.id === activeMatchId);
        const connectionCode = match ? (match.connection_code || '') : '';
        
        const introCard = document.createElement('div');
        introCard.className = 'chat-tee-intro';
        introCard.style.cssText = `
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
            padding: 24px;
            margin: auto;
            max-width: 320px;
            background: rgba(248, 250, 252, 0.95);
            border: 1px dashed #cbd5e1;
            border-radius: 20px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
            font-family: 'Montserrat', sans-serif;
            animation: fadeIn 0.4s ease-out;
        `;
        
        introCard.innerHTML = `
            <div style="font-size: 2.5rem; margin-bottom: 12px;">🛡️</div>
            <h4 style="margin: 0 0 8px 0; font-family: 'Outfit', sans-serif; font-size: 1.1rem; color: var(--text-main);">TEE Secure Chat</h4>
            <p style="margin: 0 0 16px 0; font-size: 0.8rem; color: var(--text-muted); line-height: 1.5; text-align: center;">
                This chat is completely isolated within a hardware-secured <strong>Trusted Execution Environment (TEE)</strong>. 
                Unlike standard messaging apps where metadata is exposed, here all message routing and contact pairs are fully hidden in CPU enclaves.
            </p>
            ${connectionCode ? `
                <div style="background: #e0e7ff; color: #4f46e5; font-size: 0.75rem; font-weight: 700; padding: 6px 12px; border-radius: 9999px; font-family: monospace; letter-spacing: 0.5px;">
                    Connection: ${connectionCode}
                </div>
            ` : ''}
        `;
        messagesContainer.appendChild(introCard);
        return;
    }
    
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
    
    if (activeMatchId.startsWith('real_match_')) {
        const token = localStorage.getItem('kolosok_token');
        if (!token) return;
        
        const roomCode = activeMatchId.replace('real_match_', '');
        const apiHost = window.location.hostname || 'localhost';
        
        fetch(`/chat/send`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ token: token, text: text, room_id: roomCode })
        })
        .then(response => {
            if (!response.ok) throw new Error("HTTP error: " + response.status);
            return response.json();
        })
        .then(data => {
            if (data.ok) {
                syncAllChatMessages();
            }
        })
        .catch(error => {
            console.error("Error sending chat message:", error);
            showToast("Failed to send message: " + error.message, "error");
        });
        
        input.value = '';
    } else {
        // Save message to chat history
        if (!chats[activeMatchId]) {
            chats[activeMatchId] = [];
        }
        chats[activeMatchId].push({ sender: 'sent', text: text });
        
        // Render new messages and clear input
        renderMessages();
        input.value = '';
    }
}

function startChatPolling() {
    if (chatPollIntervalId) {
        clearInterval(chatPollIntervalId);
    }
    // Immediate sync
    syncAllChatMessages();
    
    chatPollIntervalId = setInterval(() => {
        syncAllChatMessages();
    }, 1000);
}

function syncAllChatMessages() {
    const token = localStorage.getItem('kolosok_token');
    if (!token) return;
    
    const apiHost = window.location.hostname || 'localhost';
    const pollUrl = `/chat/all-messages?token=${token}`;
    
    fetch(pollUrl)
    .then(response => {
        if (!response.ok) throw new Error("HTTP status: " + response.status);
        return response.json();
    })
    .then(data => {
        if (data.ok && data.rooms) {
            let activeRoomUpdated = false;
            
            realMatches.forEach(match => {
                const roomCode = match.connection_code;
                const newMessages = data.rooms[roomCode] || [];
                const oldMessages = chats[match.id] || [];
                
                // Compare arrays
                let changed = oldMessages.length !== newMessages.length;
                if (!changed && newMessages.length > 0) {
                    const oldLast = oldMessages[oldMessages.length - 1];
                    const newLast = newMessages[newMessages.length - 1];
                    if (oldLast.text !== newLast.text || oldLast.sender !== newLast.sender) {
                        changed = true;
                    }
                }
                
                if (changed) {
                    // Trigger web notifications for new received messages
                    if (newMessages.length > oldMessages.length) {
                        const receivedMsgs = newMessages.slice(oldMessages.length).filter(m => m.sender === 'received');
                        if (receivedMsgs.length === 1) {
                            showWebNotification(match.name, receivedMsgs[0].text, match.id);
                        } else if (receivedMsgs.length > 1) {
                            const lastMsg = receivedMsgs[receivedMsgs.length - 1];
                            showWebNotification(match.name, `${receivedMsgs.length} new messages: "${lastMsg.text}"`, match.id);
                        }
                    }
                    
                    chats[match.id] = newMessages;
                    
                    if (activeMatchId === match.id) {
                        activeRoomUpdated = true;
                    } else {
                        // Update card subtitle
                        const subEl = document.getElementById(`subtitle-${match.id}`);
                        if (subEl) {
                            const lastMsg = newMessages[newMessages.length - 1];
                            let newSub = "No messages yet";
                            if (newMessages.length > 0) {
                                newSub = lastMsg.sender === 'sent' ? `You: ${lastMsg.text}` : lastMsg.text;
                            }
                            subEl.innerText = newSub;
                        }
                    }
                }
            });
            
            if (activeRoomUpdated) {
                renderMessages();
            }
        }
    })
    .catch(error => {
        console.error("Error syncing all chat messages:", error);
    });
}

function stopChatPolling() {
    if (chatPollIntervalId) {
        clearInterval(chatPollIntervalId);
        chatPollIntervalId = null;
    }
}

function resetApp() {
    if (pollIntervalId) {
        clearInterval(pollIntervalId);
        pollIntervalId = null;
    }
    stopChatPolling();
    if (backgroundChatPollIntervalId) {
        clearInterval(backgroundChatPollIntervalId);
        backgroundChatPollIntervalId = null;
    }
    nav('screen-name');
}

function restoreSession(token) {
    console.log("Found existing token, attempting to restore session...");
    const apiHost = window.location.hostname || 'localhost';
    const pollUrl = `/result/${token}`;
    
    showToast("Restoring secure session...", "info");
    
    fetch(pollUrl)
    .then(response => {
        if (response.status === 404 || response.status === 403) {
            localStorage.removeItem('kolosok_token');
            throw new Error("Invalid token on server");
        }
        if (!response.ok) {
            throw new Error("Server error, status: " + response.status);
        }
        return response.json();
    })
    .then(data => {
        console.log("Session restore poll result:", data);
        
        // Attempt Web Push subscription to ensure server has our subscription for this restored token
        if ('serviceWorker' in navigator) {
            console.log('[PWA] Attempting push subscription for restored token. Permission:', Notification.permission);
            if (Notification.permission === 'granted') {
                navigator.serviceWorker.ready.then(reg => {
                    console.log('[PWA] Service worker ready for restored token, subscribing...');
                    subscribeToWebPush(reg);
                });
            }
        }
        
        // Restore local profile values from localStorage if available
        restoreProfileFromLocalStorage();
        
        if (data.round_done) {
            if (data.matched) {
                showRealMatch(data);
                nav('screen-waiting');
                startPolling(token); // Start polling to check for new/updated matches!
            } else {
                showNoMatch();
                nav('screen-waiting');
                startPolling(token); // Keep polling in the background!
            }
        } else {
            // Still waiting for round completion, resume polling
            nav('screen-waiting');
            startPolling(token);
        }
    })
    .catch(error => {
        console.warn("Session restoration failed:", error);
        
        // Populate local fields anyway from local storage if available
        restoreProfileFromLocalStorage();
        
        if (error.message !== "Invalid token on server") {
            showToast("Server offline. Displaying local profile data.", "warning");
        } else {
            showToast("Session expired. Please re-enter your details.", "info");
        }
        
        // Guide them back to name screen to review their details
        nav('screen-name');
    });
}



// Age Horizontal Carousel Selector
function initAgePicker() {
    const picker = document.getElementById('age-picker');
    const ageInput = document.getElementById('my-age');
    if (!picker || !ageInput) return;

    picker.innerHTML = '';

    // Add left padding element (1 slot)
    const leftPadding = document.createElement('div');
    leftPadding.className = 'age-padding';
    picker.appendChild(leftPadding);

    const minAge = 18;
    const maxAge = 99;
    const itemWidth = 60; // 60px width per item

    for (let age = minAge; age <= maxAge; age++) {
        const div = document.createElement('div');
        div.className = 'age-item';
        div.innerText = age;
        div.setAttribute('data-age', age);
        div.onclick = () => {
            picker.scrollTo({
                left: (age - minAge) * itemWidth,
                behavior: 'smooth'
            });
        };
        picker.appendChild(div);
    }

    // Add right padding element (1 slot)
    const rightPadding = document.createElement('div');
    rightPadding.className = 'age-padding';
    picker.appendChild(rightPadding);

    // Scroll listener
    picker.onscroll = () => {
        const scrollLeft = picker.scrollLeft;
        const activeIndex = Math.round(scrollLeft / itemWidth);
        const activeAge = minAge + activeIndex;
        const finalAge = Math.min(Math.max(activeAge, minAge), maxAge);

        picker.querySelectorAll('.age-item').forEach(el => {
            const ageVal = parseInt(el.getAttribute('data-age'), 10);
            if (ageVal === finalAge) {
                el.classList.add('selected');
            } else {
                el.classList.remove('selected');
            }
        });

        ageInput.value = finalAge;
        saveProfileState();
    };

    // Initial positioning (default to 18)
    setTimeout(() => {
        setAgePickerValue(18);
    }, 150);
}

function setAgePickerValue(age) {
    const picker = document.getElementById('age-picker');
    if (!picker) return;
    const minAge = 18;
    const maxAge = 99;
    const itemWidth = 60;
    const targetAge = Math.min(Math.max(parseInt(age, 10) || 18, minAge), maxAge);
    
    // Set input value
    const ageInput = document.getElementById('my-age');
    if (ageInput) ageInput.value = targetAge;
    
    // Highlight the selected age element directly
    picker.querySelectorAll('.age-item').forEach(el => {
        const val = parseInt(el.getAttribute('data-age'), 10);
        if (val === targetAge) {
            el.classList.add('selected');
        } else {
            el.classList.remove('selected');
        }
    });
    
    // Scroll to position
    picker.scrollLeft = (targetAge - minAge) * itemWidth;
    saveProfileState();
}

// Web Notification Permission & Dispatcher
function requestNotificationPermission() {
    if ('Notification' in window) {
        if (Notification.permission === 'default') {
            Notification.requestPermission().then(permission => {
                console.log("Notification permission state:", permission);
                if (permission === 'granted' && 'serviceWorker' in navigator) {
                    navigator.serviceWorker.ready.then(reg => {
                        subscribeToWebPush(reg);
                    });
                }
            });
        }
    }
}

function showWebNotification(title, body, matchId, isMatch = false) {
    if (!isMatch && activeMatchId === matchId && document.getElementById('screen-chat').classList.contains('active') && !document.hidden) {
        return; // Don't notify if user is already viewing the chat
    }
    
    if ('Notification' in window && Notification.permission === 'granted') {
        const options = {
            body: body,
            icon: './daytee_logo.png',
            tag: isMatch ? 'new-match' : `chat-${matchId}`,
            renotify: true,
            data: { matchId: matchId, isMatch: isMatch }
        };
        
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.ready.then(registration => {
                registration.showNotification(title, options);
            }).catch(err => {
                console.error("Service worker notification failed, trying fallback:", err);
                try {
                    const notification = new Notification(title, options);
                    notification.onclick = () => {
                        window.focus();
                        if (isMatch) {
                            nav('screen-waiting');
                        } else if (matchId) {
                            openChatForMatch(matchId);
                        }
                    };
                } catch (e) {
                    console.error("Standard Notification constructor not supported:", e);
                }
            });
        } else {
            try {
                const notification = new Notification(title, options);
                notification.onclick = () => {
                    window.focus();
                    if (isMatch) {
                        nav('screen-waiting');
                    } else if (matchId) {
                        openChatForMatch(matchId);
                    }
                };
            } catch (e) {
                console.error("Standard Notification constructor not supported:", e);
            }
        }
    }
}

// Background chat messages polling
let backgroundChatPollIntervalId = null;

function startBackgroundChatPolling() {
    if (backgroundChatPollIntervalId) {
        clearInterval(backgroundChatPollIntervalId);
    }
    
    // Immediate sync
    syncAllChatMessages();
    
    backgroundChatPollIntervalId = setInterval(() => {
        // If active chat is polling, we can skip or run it.
        // Since they both run syncAllChatMessages, running it is harmless but we can skip to avoid redundant requests.
        if (activeMatchId && chatPollIntervalId) {
            return;
        }
        syncAllChatMessages();
    }, 3000); // Poll every 3 seconds
}

// Web Push Helper Functions
function subscribeToWebPush(registration) {
    console.log("[PWA] Entering subscribeToWebPush function.");
    if (!registration.pushManager) {
        console.warn("[PWA] PushManager not supported in this browser.");
        return;
    }
    
    console.log("[PWA] Fetching VAPID public key from /admin/vapid-public-key...");
    // Fetch VAPID public key from backend
    fetch('/admin/vapid-public-key')
    .then(res => {
        console.log("[PWA] VAPID public key response status:", res.status);
        if (!res.ok) throw new Error("VAPID key endpoint returned status: " + res.status);
        return res.json();
    })
    .then(data => {
        console.log("[PWA] VAPID public key payload:", data);
        if (!data.public_key) {
            console.log("[PWA] VAPID keys not configured on server. Skipping push subscription.");
            return;
        }
        
        console.log("[PWA] Converting applicationServerKey...");
        const applicationServerKey = urlBase64ToUint8Array(data.public_key);
        console.log("[PWA] Subscribing with PushManager...");
        return registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: applicationServerKey
        });
    })
    .then(subscription => {
        console.log("[PWA] PushManager subscription obtained:", subscription);
        if (!subscription) {
            console.warn("[PWA] No subscription returned from PushManager.");
            return;
        }
        
        const token = localStorage.getItem('kolosok_token');
        console.log("[PWA] Current session token from localStorage:", token);
        if (!token) {
            console.warn("[PWA] No session token found in localStorage. Cannot map subscription on backend.");
            return;
        }
        
        console.log("[PWA] Sending subscription to backend /chat/subscribe...");
        // Send subscription object to backend
        return fetch('/chat/subscribe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ token: token, subscription: subscription })
        });
    })
    .then(res => {
        if (res) {
            console.log("[PWA] Backend subscribe response status:", res.status);
            if (res.ok) {
                console.log("[PWA] Registered push subscription on backend successfully.");
            } else {
                console.warn("[PWA] Backend subscribe failed with status:", res.status);
            }
        }
    })
    .catch(err => {
        console.error("[PWA] Web Push subscription workflow failed:", err);
    });
}

function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding)
        .replace(/\-/g, '+')
        .replace(/_/g, '/');

    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);

    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}