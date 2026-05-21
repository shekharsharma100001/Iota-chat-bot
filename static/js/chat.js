document.addEventListener('DOMContentLoaded', () => {
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatContainer = document.getElementById('chat-container');
    const uploadBtn = document.getElementById('upload-btn');
    const logFile = document.getElementById('log-file');
    const uploadStatus = document.getElementById('upload-status');
    const activeChatView = document.getElementById('active-chat-view');
    const newChatBtn = document.getElementById('new-chat-btn');
    const createReplicaBtn = document.getElementById('create-replica-btn');
    const replicaNameInput = document.getElementById('replica-name');
    const replicaStatus = document.getElementById('replica-status');
    const step1Upload = document.getElementById('step-1-upload');
    const step2Configure = document.getElementById('step-2-configure');
    const targetPersonaSelect = document.getElementById('target-persona-select');
    let uploadedFilename = "";

    const newChatHub = document.getElementById('new-chat-hub');
    const uploadWizardView = document.getElementById('upload-wizard-view');
    const manualWizardView = document.getElementById('manual-wizard-view');
    
    // Make functions globally accessible for inline HTML onClick handlers
    window.showActiveChat = function() {
        newChatHub.classList.add('hidden');
        uploadWizardView.classList.add('hidden');
        manualWizardView.classList.add('hidden');
        activeChatView.classList.remove('hidden');
    };

    window.showNewChatHub = function() {
        activeChatView.classList.add('hidden');
        uploadWizardView.classList.add('hidden');
        manualWizardView.classList.add('hidden');
        newChatHub.classList.remove('hidden');
    };
    
    window.showUploadWizard = function() {
        newChatHub.classList.add('hidden');
        uploadWizardView.classList.remove('hidden');
    };
    
    window.showManualWizard = function() {
        newChatHub.classList.add('hidden');
        manualWizardView.classList.remove('hidden');
    };

    if (newChatBtn) {
        newChatBtn.addEventListener('click', showNewChatHub);
    }

    function appendMessage(text, isUser) {
        const div = document.createElement('div');
        div.className = `flex ${isUser ? 'justify-end' : 'justify-start'}`;
        
        const bubble = document.createElement('div');
        bubble.className = `max-w-[70%] rounded-2xl px-5 py-3 shadow-md border ${
            isUser 
            ? 'bg-msgUser text-white rounded-tr-sm border-blue-500' 
            : 'bg-msgAI text-gray-100 rounded-tl-sm border-gray-700'
        }`;
        
        const p = document.createElement('p');
        p.className = 'text-[15px] leading-relaxed whitespace-pre-wrap';
        p.innerText = text;
        
        bubble.appendChild(p);
        div.appendChild(bubble);
        chatContainer.appendChild(div);
        
        // Scroll to bottom
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }

    function showTypingIndicator() {
        hideTypingIndicator();
        const div = document.createElement('div');
        div.id = 'typing-indicator';
        div.className = 'flex justify-start';
        div.innerHTML = `
            <div class="max-w-[70%] bg-msgAI text-gray-400 rounded-2xl rounded-tl-sm px-5 py-3 shadow-md border border-gray-700 flex items-center gap-2">
                <span class="text-[15px] leading-relaxed">typing</span>
                <span class="flex gap-1 items-center h-2">
                    <span class="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 0ms"></span>
                    <span class="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 150ms"></span>
                    <span class="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style="animation-delay: 300ms"></span>
                </span>
            </div>
        `;
        chatContainer.appendChild(div);
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
    
    function hideTypingIndicator() {
        const indicator = document.getElementById('typing-indicator');
        if (indicator) {
            indicator.remove();
        }
    }

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const text = chatInput.value.trim();
        if (!text) return;
        
        // Display user message
        appendMessage(text, true);
        chatInput.value = '';
        chatInput.style.height = 'auto'; // Reset height
        
        showTypingIndicator();
        
        try {
            const res = await fetch('/chat/send', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text })
            });
            
            hideTypingIndicator();
            
            if (!res.ok) {
                const data = await res.json();
                appendMessage(`Error: ${data.error || 'Failed to get response'}`, false);
                return;
            }
            
            const data = await res.json();
            appendMessage(data.message, false);
            
        } catch (err) {
            hideTypingIndicator();
            console.error(err);
            appendMessage("Network error occurred.", false);
        }
    });

    // Handle Enter to submit (Shift+Enter for new line)
    chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatForm.dispatchEvent(new Event('submit'));
        }
    });

    uploadBtn.addEventListener('click', async () => {
        const file = logFile.files[0];
        if (!file) {
            uploadStatus.innerText = 'Please select a file first.';
            uploadStatus.classList.remove('hidden', 'text-green-400');
            uploadStatus.classList.add('text-red-400');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        uploadBtn.disabled = true;
        uploadBtn.innerText = 'Analyzing...';
        uploadStatus.innerText = 'Scanning chat log for speakers...';
        uploadStatus.classList.remove('hidden', 'text-red-400');
        uploadStatus.classList.add('text-blue-400');

        try {
            const res = await fetch('/chat/upload_and_analyze', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();

            if (res.ok) {
                uploadedFilename = data.filename;
                uploadStatus.innerText = data.message;
                uploadStatus.classList.replace('text-blue-400', 'text-green-400');
                
                // Populate dropdown
                targetPersonaSelect.innerHTML = '<option value="" disabled selected>Select the person to clone...</option>';
                data.speakers.forEach(speaker => {
                    const opt = document.createElement('option');
                    opt.value = speaker;
                    opt.innerText = speaker;
                    targetPersonaSelect.appendChild(opt);
                });
                
                // Transition to Step 2
                setTimeout(() => {
                    step1Upload.classList.add('opacity-50', 'pointer-events-none');
                    step2Configure.classList.remove('hidden');
                }, 500);
            } else {
                uploadStatus.innerText = `Error: ${data.error}`;
                uploadStatus.classList.replace('text-blue-400', 'text-red-400');
                uploadBtn.disabled = false;
                uploadBtn.innerText = 'Analyze File';
            }
        } catch (err) {
            console.error(err);
            uploadStatus.innerText = 'A network error occurred.';
            uploadStatus.classList.replace('text-blue-400', 'text-red-400');
            uploadBtn.disabled = false;
            uploadBtn.innerText = 'Analyze File';
        }
    });

    if (createReplicaBtn) {
        createReplicaBtn.addEventListener('click', async () => {
            const cloneName = replicaNameInput.value.trim();
            const targetPersona = targetPersonaSelect.value;
            
            if (!targetPersona) {
                replicaStatus.innerText = 'Please select a target persona.';
                replicaStatus.classList.remove('hidden', 'text-green-400');
                replicaStatus.classList.add('text-red-400');
                return;
            }
            if (!cloneName) {
                replicaStatus.innerText = 'Please enter a replica name.';
                replicaStatus.classList.remove('hidden', 'text-green-400');
                replicaStatus.classList.add('text-red-400');
                return;
            }

            createReplicaBtn.disabled = true;
            createReplicaBtn.innerText = 'Extracting & Training...';
            replicaStatus.innerText = 'Generating semantic vectors... this may take a minute.';
            replicaStatus.classList.remove('hidden', 'text-red-400');
            replicaStatus.classList.add('text-purple-400');

            try {
                const res = await fetch('/chat/finalize_replica', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        clone_name: cloneName,
                        target_persona: targetPersona,
                        filename: uploadedFilename
                    })
                });
                const data = await res.json();

                if (res.ok) {
                    replicaStatus.innerText = data.message;
                    replicaStatus.classList.replace('text-purple-400', 'text-green-400');
                    
                    setTimeout(() => {
                        window.location.reload();
                    }, 1500);
                } else {
                    replicaStatus.innerText = `Error: ${data.error}`;
                    replicaStatus.classList.replace('text-purple-400', 'text-red-400');
                    createReplicaBtn.disabled = false;
                    createReplicaBtn.innerText = 'Extract Knowledge & Create';
                }
            } catch (err) {
                console.error(err);
                replicaStatus.innerText = 'A network error occurred.';
                replicaStatus.classList.replace('text-purple-400', 'text-red-400');
                createReplicaBtn.disabled = false;
                createReplicaBtn.innerText = 'Extract Knowledge & Create';
            }
        });
    }

    // ==========================================
    // DYNAMIC SIDEBAR & PERSONA SWITCHING
    // ==========================================
    const chatList = document.getElementById('chat-list');
    const chatListEmpty = document.getElementById('chat-list-empty');
    const activeChatName = document.getElementById('active-chat-name');
    const activeChatAvatar = document.getElementById('active-chat-avatar');

    async function fetchClones() {
        try {
            const res = await fetch('/chat/get_clones');
            const data = await res.json();
            if (data.clones) {
                window.currentActiveCloneId = data.active_clone_id;
                renderClones(data.clones);
            }
        } catch (err) {
            console.error("Failed to fetch clones:", err);
        }
    }

    function renderClones(clones) {
        // Remove existing rendered clones
        document.querySelectorAll('.clone-item').forEach(el => el.remove());
        
        if (clones.length === 0) {
            chatListEmpty.classList.remove('hidden');
            return;
        }
        
        chatListEmpty.classList.add('hidden');
        
        clones.forEach(clone => {
            const div = document.createElement('div');
            const isActive = clone.clone_id === window.currentActiveCloneId;
            
            // Highlight active clone in sidebar
            if (isActive) {
                div.className = 'clone-item p-3 bg-gray-800/80 hover:bg-gray-800 cursor-pointer transition flex items-center gap-3 border-b border-gray-800/50 border-l-4 border-blue-500 group';
                // Update UI Header to show replica name
                activeChatName.innerText = clone.name;
                activeChatAvatar.innerText = clone.name.charAt(0).toUpperCase();
                
                if (clone.is_manual) {
                    activeChatAvatar.className = "w-10 h-10 bg-gradient-to-tr from-purple-500 to-pink-500 rounded-full flex items-center justify-center text-white font-bold";
                } else {
                    activeChatAvatar.className = "w-10 h-10 bg-gradient-to-tr from-blue-500 to-indigo-500 rounded-full flex items-center justify-center text-white font-bold";
                }
            } else {
                div.className = 'clone-item p-3 hover:bg-gray-800 cursor-pointer transition flex items-center gap-3 border-b border-gray-800/50 group';
            }
            
            div.onclick = () => switchClone(clone.clone_id, clone.name, clone.is_manual);
            
            const isManual = clone.is_manual;
            const gradient = isManual ? 'from-purple-500 to-pink-500' : 'from-blue-500 to-indigo-500';
            const initial = clone.name.charAt(0).toUpperCase();
            const badgeStr = isManual ? 'Custom Persona' : 'WhatsApp Clone';
            const pinBadge = clone.pinned ? `<svg class="w-3.5 h-3.5 text-blue-400 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20"><path d="M5 4a2 2 0 012-2h6a2 2 0 012 2v14l-5-2.5L5 18V4z"/></svg>` : '';
            
            div.innerHTML = `
                <div class="w-12 h-12 bg-gradient-to-tr ${gradient} rounded-full flex-shrink-0 flex items-center justify-center text-white font-bold text-lg shadow-lg group-hover:scale-105 transition">
                    ${initial}
                </div>
                <div class="flex-1 overflow-hidden">
                    <div class="flex items-center gap-1.5">
                        <h3 class="text-sm font-semibold text-gray-200 truncate flex-1">${clone.name}</h3>
                        ${pinBadge}
                    </div>
                    <p class="text-xs text-gray-500 truncate">${badgeStr}</p>
                </div>
                <div class="relative flex-shrink-0">
                    <button class="menu-btn p-1.5 hover:bg-gray-700 text-gray-400 hover:text-white rounded-lg transition" onclick="event.stopPropagation(); toggleMenu(event, '${clone.clone_id}')">
                        <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24"><path d="M12 8c1.1 0 2-.9 2-2s-.9-2-2-2-2 .9-2 2 .9 2 2 2zm0 2c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2zm0 6c-1.1 0-2 .9-2 2s.9 2 2 2 2-.9 2-2-.9-2-2-2z"/></svg>
                    </button>
                    <div id="menu-${clone.clone_id}" class="clone-menu hidden absolute right-0 mt-1 w-32 bg-gray-900 border border-gray-750 text-gray-200 rounded-lg shadow-xl py-1 z-30 text-xs">
                        <button class="w-full text-left px-3 py-2 hover:bg-gray-800 flex items-center gap-2" onclick="event.stopPropagation(); pinClone('${clone.clone_id}', ${clone.pinned})">
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/></svg>
                            ${clone.pinned ? 'Unpin Chat' : 'Pin to Top'}
                        </button>
                        <button class="w-full text-left px-3 py-2 hover:bg-gray-800 flex items-center gap-2" onclick="event.stopPropagation(); renameClonePrompt('${clone.clone_id}', '${clone.name}')">
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z"/></svg>
                            Rename
                        </button>
                        <button class="w-full text-left px-3 py-2 text-red-400 hover:bg-red-950/30 hover:text-red-300 flex items-center gap-2" onclick="event.stopPropagation(); deleteClone('${clone.clone_id}')">
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>
                            Delete
                        </button>
                    </div>
                </div>
            `;
            chatList.appendChild(div);
        });
    }

    async function switchClone(cloneId, cloneName, isManual) {
        try {
            const res = await fetch('/chat/switch_clone', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ clone_id: cloneId })
            });
            const data = await res.json();
            
            if (data.success) {
                window.currentActiveCloneId = cloneId;
                
                // Re-render clones to show active highlight state
                fetchClones();
                
                // Clear chat container and show loading state
                chatContainer.innerHTML = `
                    <div class="flex justify-center items-center h-full text-gray-500">
                        <svg class="animate-spin -ml-1 mr-3 h-5 w-5 text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                        Loading history...
                    </div>
                `;
                
                showActiveChat();
                await fetchHistory(); // Hydrate the chat window
            } else {
                alert("Error switching clone: " + data.error);
            }
        } catch (err) {
            console.error("Switch failed:", err);
        }
    }

    // ==========================================
    // MENU ACTIONS (PIN, RENAME, DELETE)
    // ==========================================
    window.toggleMenu = function(event, cloneId) {
        event.stopPropagation();
        document.querySelectorAll('.clone-menu').forEach(menu => {
            if (menu.id !== `menu-${cloneId}`) {
                menu.classList.add('hidden');
            }
        });
        const targetMenu = document.getElementById(`menu-${cloneId}`);
        if (targetMenu) {
            targetMenu.classList.toggle('hidden');
        }
    };

    // Close any open menus when clicking elsewhere
    document.addEventListener('click', () => {
        document.querySelectorAll('.clone-menu').forEach(menu => menu.classList.add('hidden'));
    });

    window.pinClone = async function(cloneId, isCurrentlyPinned) {
        try {
            const res = await fetch('/chat/pin_clone', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ clone_id: cloneId, pinned: !isCurrentlyPinned })
            });
            const data = await res.json();
            if (data.success) {
                fetchClones();
            } else {
                alert("Pin error: " + data.error);
            }
        } catch (err) {
            console.error("Pin request failed:", err);
        }
    };

    window.renameClonePrompt = async function(cloneId, currentName) {
        const newName = prompt("Enter a new name for this replica:", currentName);
        if (newName === null || newName.trim() === "" || newName.trim() === currentName) {
            return;
        }
        try {
            const res = await fetch('/chat/rename_clone', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ clone_id: cloneId, new_name: newName.trim() })
            });
            const data = await res.json();
            if (data.success) {
                if (window.currentActiveCloneId === cloneId) {
                    activeChatName.innerText = newName.trim();
                    activeChatAvatar.innerText = newName.trim().charAt(0).toUpperCase();
                }
                fetchClones();
            } else {
                alert("Rename error: " + data.error);
            }
        } catch (err) {
            console.error("Rename request failed:", err);
        }
    };

    window.deleteClone = async function(cloneId) {
        if (!confirm("Are you sure you want to delete this replica? This will delete all chat history and the Pinecone vector memory namespace permanently.")) {
            return;
        }
        try {
            const res = await fetch('/chat/delete_clone', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ clone_id: cloneId })
            });
            const data = await res.json();
            if (data.success) {
                if (window.currentActiveCloneId === cloneId) {
                    window.location.reload();
                } else {
                    fetchClones();
                }
            } else {
                alert("Delete error: " + data.error);
            }
        } catch (err) {
            console.error("Delete request failed:", err);
        }
    };

    async function fetchHistory() {
        try {
            const res = await fetch('/chat/get_history');
            const data = await res.json();
            
            chatContainer.innerHTML = ''; // Clear loading/placeholder state
            
            if (data.history && data.history.length > 0) {
                data.history.forEach(msg => {
                    const isUser = msg.speaker === 'user';
                    appendMessage(msg.message, isUser);
                });
            } else {
                // Empty state for brand new persona
                chatContainer.innerHTML = `
                    <div class="flex justify-start">
                        <div class="max-w-[70%] bg-msgAI text-gray-100 rounded-2xl rounded-tl-sm px-5 py-3 shadow-md border border-gray-700">
                            <p class="text-[15px] leading-relaxed">Hello! I am ready to chat. Send a message to begin our conversation.</p>
                        </div>
                    </div>
                `;
            }
            
            // Scroll to bottom
            chatContainer.scrollTop = chatContainer.scrollHeight;
        } catch (err) {
            console.error("Failed to fetch history:", err);
            chatContainer.innerHTML = `<div class="text-red-400 text-center">Failed to load history.</div>`;
        }
    }

    // Call on load
    fetchClones();
    
    // Only fetch history on load if we are looking at the active chat view
    if (!activeChatView.classList.contains('hidden')) {
        fetchHistory();
    }

    // ==========================================
    // MANUAL PERSONA 7-STEP WIZARD LOGIC
    // ==========================================
    let currentStep = 1;
    const totalSteps = 7;
    const wizardProgress = document.getElementById('wizard-progress');
    const mErrorMsg = document.getElementById('m-error-msg');
    const mBackBtn = document.getElementById('m-back-btn');
    const mNextBtn = document.getElementById('m-next-btn');
    const mCreateBtn = document.getElementById('m-create-btn');

    const personaState = {
        name: '', gender: '', language: '',
        relationship: '',
        traits: [],
        tone: '', length: '', emoji: '',
        expertise: [],
        examples: []
    };

    function showError(msg) {
        mErrorMsg.innerText = msg;
        mErrorMsg.classList.remove('opacity-0');
        setTimeout(() => mErrorMsg.classList.add('opacity-0'), 3000);
    }

    function updateWizardUI() {
        // Progress bar
        wizardProgress.style.width = `${(currentStep / totalSteps) * 100}%`;

        // Buttons
        mBackBtn.classList.toggle('invisible', currentStep === 1);
        
        if (currentStep === totalSteps) {
            mNextBtn.classList.add('hidden');
            mCreateBtn.classList.remove('hidden');
            populateReview();
        } else {
            mNextBtn.classList.remove('hidden');
            mCreateBtn.classList.add('hidden');
        }

        // Steps visibility (transitions)
        for (let i = 1; i <= totalSteps; i++) {
            const stepEl = document.getElementById(`m-step-${i}`);
            if (i === currentStep) {
                stepEl.classList.remove('hidden');
                // Small delay to allow CSS transition to work after display:block
                setTimeout(() => {
                    stepEl.classList.remove('opacity-0', 'pointer-events-none');
                }, 10);
            } else {
                stepEl.classList.add('opacity-0', 'pointer-events-none');
                setTimeout(() => {
                    if (i !== currentStep) stepEl.classList.add('hidden');
                }, 300); // Matches transition duration
            }
        }
    }

    function validateStep(step) {
        if (step === 1) {
            personaState.name = document.getElementById('m-name').value.trim();
            if (!personaState.name || !personaState.gender || !personaState.language) {
                showError('Please provide a name, gender, and language.');
                return false;
            }
        } else if (step === 2) {
            if (!personaState.relationship) {
                showError('Please select a relationship type.');
                return false;
            }
        } else if (step === 3) {
            if (personaState.traits.length === 0 || personaState.traits.length > 3) {
                showError('Please select exactly 3 traits.');
                return false;
            }
        } else if (step === 4) {
            if (!personaState.tone || !personaState.length || !personaState.emoji) {
                showError('Please complete all communication preferences.');
                return false;
            }
        } else if (step === 5) {
            if (personaState.expertise.length === 0) {
                showError('Please select at least 1 area of expertise.');
                return false;
            }
        } else if (step === 6) {
            personaState.examples = [];
            const pairs = document.querySelectorAll('.example-pair');
            for (let pair of pairs) {
                const userMsg = pair.querySelector('.ex-user').value.trim();
                const aiMsg = pair.querySelector('.ex-ai').value.trim();
                if (userMsg && aiMsg) {
                    personaState.examples.push({ user: userMsg, ai: aiMsg });
                }
            }
            if (personaState.examples.length === 0) {
                showError('Please add at least one complete example conversation.');
                return false;
            }
        }
        return true;
    }

    mNextBtn?.addEventListener('click', () => {
        if (validateStep(currentStep)) {
            currentStep++;
            updateWizardUI();
        }
    });

    mBackBtn?.addEventListener('click', () => {
        if (currentStep > 1) {
            currentStep--;
            updateWizardUI();
        }
    });

    // Helper: Single Select Logic
    function setupSingleSelect(containerId, stateKey, selectedClass, defaultClass) {
        const container = document.getElementById(containerId);
        if(!container) return;
        const buttons = container.querySelectorAll('.m-select-btn, .m-seg-btn');
        buttons.forEach(btn => {
            btn.addEventListener('click', () => {
                buttons.forEach(b => {
                    b.classList.remove(...selectedClass.split(' '));
                    b.classList.add(...defaultClass.split(' '));
                });
                btn.classList.remove(...defaultClass.split(' '));
                btn.classList.add(...selectedClass.split(' '));
                personaState[stateKey] = btn.getAttribute('data-value');
            });
        });
    }

    setupSingleSelect('m-gender-group', 'gender', 'border-purple-500 bg-purple-600/10 text-white', 'border-gray-700 bg-gray-900 text-gray-400');
    setupSingleSelect('m-lang-group', 'language', 'border-purple-500 bg-purple-600/10 text-white', 'border-gray-700 bg-gray-900 text-gray-400');
    setupSingleSelect('m-rel-group', 'relationship', 'border-purple-500 bg-purple-600/10', 'border-gray-700 bg-gray-900');
    setupSingleSelect('m-tone-group', 'tone', 'bg-gray-700 text-white shadow-sm', 'text-gray-400');
    setupSingleSelect('m-len-group', 'length', 'bg-gray-700 text-white shadow-sm', 'text-gray-400');
    setupSingleSelect('m-emoji-group', 'emoji', 'bg-gray-700 text-white shadow-sm', 'text-gray-400');

    // Helper: Multi Select Logic
    function setupMultiSelect(containerId, stateKey, maxCount, countElId) {
        const container = document.getElementById(containerId);
        if(!container) return;
        const countEl = document.getElementById(countElId);
        const buttons = container.querySelectorAll('.m-multi-btn, .m-multi-btn-expert');
        
        buttons.forEach(btn => {
            btn.addEventListener('click', () => {
                const val = btn.getAttribute('data-value');
                const idx = personaState[stateKey].indexOf(val);
                
                if (idx > -1) {
                    // Deselect
                    personaState[stateKey].splice(idx, 1);
                    btn.classList.remove('border-purple-500', 'bg-purple-600/20', 'text-white');
                    btn.classList.add('border-gray-700', 'bg-gray-900', 'text-gray-400');
                } else {
                    // Select
                    if (personaState[stateKey].length < maxCount) {
                        personaState[stateKey].push(val);
                        btn.classList.remove('border-gray-700', 'bg-gray-900', 'text-gray-400');
                        btn.classList.add('border-purple-500', 'bg-purple-600/20', 'text-white');
                    } else {
                        showError(`You can only select up to ${maxCount} options.`);
                    }
                }
                countEl.innerText = personaState[stateKey].length;
            });
        });
    }

    setupMultiSelect('m-traits-group', 'traits', 3, 'trait-count');
    setupMultiSelect('m-expert-group', 'expertise', 5, 'expert-count');

    // Dynamic Examples
    const addExampleBtn = document.getElementById('add-example-btn');
    const examplesContainer = document.getElementById('m-examples-container');
    
    addExampleBtn?.addEventListener('click', () => {
        const newPair = document.createElement('div');
        newPair.className = 'example-pair bg-gray-900/50 p-4 rounded-xl border border-gray-700 relative group';
        newPair.innerHTML = `
            <button type="button" class="delete-example-btn absolute top-2 right-2 text-gray-500 hover:text-red-400 hidden group-hover:block"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg></button>
            <label class="block text-xs font-semibold text-gray-500 mb-1">User Message</label>
            <textarea class="ex-user w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-purple-500 resize-none" rows="1" placeholder="e.g. I had a bad day..."></textarea>
            <label class="block text-xs font-semibold text-gray-500 mt-2 mb-1">AI Reply</label>
            <textarea class="ex-ai w-full bg-gray-800 border border-gray-700 text-white rounded-lg px-3 py-2 text-sm focus:ring-1 focus:ring-purple-500 resize-none" rows="2" placeholder="How should the AI respond?"></textarea>
        `;
        
        newPair.querySelector('.delete-example-btn').addEventListener('click', () => {
            newPair.remove();
        });
        
        examplesContainer.appendChild(newPair);
        examplesContainer.scrollTop = examplesContainer.scrollHeight;
    });

    // Populate Review Step
    function populateReview() {
        document.getElementById('rev-identity').innerText = `${personaState.name} (${personaState.gender}, ${personaState.language})`;
        document.getElementById('rev-rel').innerText = personaState.relationship;
        document.getElementById('rev-traits').innerText = personaState.traits.join(', ');
        document.getElementById('rev-comms').innerText = `${personaState.tone}, ${personaState.length}, ${personaState.emoji} Emojis`;
        document.getElementById('rev-expert').innerText = personaState.expertise.join(', ');
    }

    // Submit API Call
    mCreateBtn?.addEventListener('click', async () => {
        mCreateBtn.disabled = true;
        mCreateBtn.innerHTML = 'Deploying...';
        
        try {
            const res = await fetch('/chat/create_manual_persona', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(personaState)
            });
            const data = await res.json();
            
            if (res.ok) {
                mCreateBtn.innerHTML = 'Deployed Successfully!';
                setTimeout(() => {
                    window.location.reload();
                }, 1500);
            } else {
                showError(data.error);
                mCreateBtn.disabled = false;
                mCreateBtn.innerHTML = 'Deploy Persona';
            }
        } catch (err) {
            console.error(err);
            showError('A network error occurred.');
            mCreateBtn.disabled = false;
            mCreateBtn.innerHTML = 'Deploy Persona';
        }
    });

});
