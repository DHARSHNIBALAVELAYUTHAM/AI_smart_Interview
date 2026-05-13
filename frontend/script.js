// Global variables for interview
let currentQuestionIndex = 0;
let questions = [];
let faceEmotions = [];
let voiceEmotions = [];
let mediaRecorder;
let audioChunks = [];
let videoStream = null;
let canvas;
let audioBlob = null;

// Initialize webcam when page loads
async function initWebcam() {
    try {
        videoStream = await navigator.mediaDevices.getUserMedia({ 
            video: { width: 640, height: 480 },
            audio: true 
        });
        
        const video = document.getElementById("video");
        video.srcObject = videoStream;
        
        // Create canvas for capturing frames
        canvas = document.createElement("canvas");
        canvas.width = 640;
        canvas.height = 480;
        
        // Initialize audio recorder
        initAudioRecorder();
        
        console.log("Webcam and microphone initialized");
    } catch (err) {
        console.error("Error initializing webcam:", err);
    }
}

function initAudioRecorder() {
    if (!videoStream) return;
    
    mediaRecorder = new MediaRecorder(videoStream);
    audioChunks = [];
    
    mediaRecorder.ondataavailable = event => {
        audioChunks.push(event.data);
    };
    
    mediaRecorder.onstop = () => {
        audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
        audioChunks = [];
    };
}

async function startInterview() {
    const cid = document.getElementById("cid").value;
    const name = document.getElementById("name").value;
    
    if (!cid || !name) {
        alert("Please enter Candidate ID and Name");
        return;
    }
    
    // Initialize webcam
    await initWebcam();
    
    // Load questions from backend
    try {
        const res = await fetch(`http://127.0.0.1:5000/get_questions/${cid}`);
        const data = await res.json();
        
        if (data.questions && data.questions.length > 0) {
            questions = data.questions;
            currentQuestionIndex = 0;
            
            // Show interview section
            document.getElementById("setup-section").classList.add("hidden");
            document.getElementById("interview-section").classList.remove("hidden");
            
            // Start audio recording
            if (mediaRecorder && mediaRecorder.state === "inactive") {
                mediaRecorder.start();
            }
            
            // Capture initial face emotion
            await captureFaceEmotion();
            
            // Show first question
            showQuestion();
        } else {
            alert("No questions found for this candidate ID");
        }
    } catch (err) {
        console.error("Error loading questions:", err);
        alert("Error loading questions");
    }
}

async function captureFaceEmotion() {
    const video = document.getElementById("video");
    
    if (video && video.readyState === 4) {
        // Draw video frame to canvas
        const ctx = canvas.getContext("2d");
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        // Convert to base64
        const imageData = canvas.toDataURL("image/jpeg", 0.8);
        
        try {
            const res = await fetch("http://127.0.0.1:5000/face", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ image: imageData })
            });
            
            const data = await res.json();
            const emotion = data.emotion || "Neutral";
            faceEmotions.push(emotion);
            console.log("Face emotion captured:", emotion);
            return emotion;
        } catch (err) {
            console.error("Error capturing face emotion:", err);
            faceEmotions.push("Neutral");
            return "Neutral";
        }
    }
    
    faceEmotions.push("Neutral");
    return "Neutral";
}

async function captureVoiceEmotion() {
    if (!audioBlob) {
        console.log("No audio recorded yet");
        voiceEmotions.push("Neutral");
        return "Neutral";
    }
    
    const reader = new FileReader();
    
    return new Promise((resolve) => {
        reader.onloadend = async () => {
            try {
                const res = await fetch("http://127.0.0.1:5000/voice", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ audio: reader.result })
                });
                
                const data = await res.json();
                const emotion = data.emotion || "Neutral";
                voiceEmotions.push(emotion);
                console.log("Voice emotion captured:", emotion);
                resolve(emotion);
            } catch (err) {
                console.error("Error capturing voice emotion:", err);
                voiceEmotions.push("Neutral");
                resolve("Neutral");
            }
        };
        
        reader.readAsDataURL(audioBlob);
    });
}

function showQuestion() {
    if (currentQuestionIndex < questions.length) {
        document.getElementById("question-text").innerText = questions[currentQuestionIndex];
        document.getElementById("status").innerText = `Question ${currentQuestionIndex + 1} of ${questions.length}`;
        
        // Show submit button on last question
        if (currentQuestionIndex === questions.length - 1) {
            document.getElementById("next-btn").style.display = "none";
            document.getElementById("submit-btn").style.display = "inline-block";
        }
    }
}

async function nextQuestion() {
    // Capture emotions for current question
    await captureFaceEmotion();
    
    currentQuestionIndex++;
    
    if (currentQuestionIndex < questions.length) {
        showQuestion();
    }
}

async function submitInterview() {
    document.getElementById("status").innerText = "Processing...";
    
    // Stop audio recording
    if (mediaRecorder && mediaRecorder.state === "recording") {
        mediaRecorder.stop();
    }
    
    // Capture final emotions
    await captureFaceEmotion();
    await captureVoiceEmotion();
    
    // Calculate dominant emotions
    const dominantFace = getDominantEmotion(faceEmotions);
    const dominantVoice = getDominantEmotion(voiceEmotions);
    
    // Calculate score
    const score = calculateScore(dominantFace, dominantVoice);
    
    // Get candidate info
    const cid = document.getElementById("cid").value;
    const name = document.getElementById("name").value;
    
    // Capture final image
    const video = document.getElementById("video");
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const imageData = canvas.toDataURL("image/jpeg", 0.8);
    
    // Submit to backend
    try {
        const res = await fetch("http://127.0.0.1:5000/submit", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                candidate_id: cid,
                name: name,
                face_emotion: dominantFace,
                voice_emotion: dominantVoice,
                score: score,
                image: imageData
            })
        });
        
        const data = await res.json();
        
        // Show completion
        document.getElementById("interview-section").classList.add("hidden");
        document.getElementById("complete-section").classList.remove("hidden");
        
        // Display summary
        document.getElementById("status").innerText = "Interview Completed!";
        
        console.log("Interview submitted:", {
            face: dominantFace,
            voice: dominantVoice,
            score: score
        });
        
    } catch (err) {
        console.error("Error submitting interview:", err);
        alert("Error submitting interview");
    }
}

function getDominantEmotion(emotions) {
    if (!emotions || emotions.length === 0) return "Neutral";
    
    const counts = {};
    emotions.forEach(e => {
        counts[e] = (counts[e] || 0) + 1;
    });
    
    let maxCount = 0;
    let dominant = "Neutral";
    
    for (const [emotion, count] of Object.entries(counts)) {
        if (count > maxCount) {
            maxCount = count;
            dominant = emotion;
        }
    }
    
    return dominant;
}

function calculateScore(face, voice) {
    const faceMap = { "Happy": 0.9, "Neutral": 0.7, "Sad": 0.4, "Angry": 0.2 };
    const voiceMap = { "Happy": 0.9, "Neutral": 0.7, "Sad": 0.4, "Fear": 0.3, "Angry": 0.2 };
    
    const f = faceMap[face] || 0.5;
    const v = voiceMap[voice] || 0.5;
    
    return Math.round((f * 0.6 + v * 0.4) * 100) / 100;
}

// Load results for dashboard
async function loadResults() {
    const id = document.getElementById("searchId").value;
    
    if (!id) {
        alert("Please enter a Candidate ID");
        return;
    }
    
    try {
        const res = await fetch("http://127.0.0.1:5000/results");
        const data = await res.json();
        
        const table = document.getElementById("tableBody");
        table.innerHTML = "";
        
        let found = false;
        
        data.forEach(c => {
            if (c.candidate_id === id || c.id === id) {
                found = true;
                const decision = c.score > 0.7 ? "SELECTED" : "REJECTED";
                
                table.innerHTML += `
                <tr>
                    <td>${c.name}</td>
                    <td>${c.candidate_id || c.id}</td>
                    <td>${c.face || c.face_emotion}</td>
                    <td>${c.voice || c.voice_emotion}</td>
                    <td>${c.score}</td>
                    <td>${decision}</td>
                </tr>`;
            }
        });
        
        if (!found) {
            alert("No results found for this Candidate ID");
        }
        
    } catch (err) {
        console.error("Error loading results:", err);
        alert("Error loading results");
    }
}

// Login function
async function login() {
    const username = document.getElementById("username").value;
    const password = document.getElementById("password").value;
    const role = document.getElementById("role").value;
    
    try {
        const res = await fetch("http://127.0.0.1:5000/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ username, password, expected_role: role })
        });
        
        const data = await res.json();
        
        if (data.success) {
            sessionStorage.setItem("username", username);
            sessionStorage.setItem("role", role);
            
            if (role === "candidate") {
                window.location.href = "candidate.html";
            } else if (role === "hr") {
                window.location.href = "hr.html";
            }
        } else {
            alert(data.message);
        }
    } catch (err) {
        console.error("Login error:", err);
        alert("Login failed");
    }
}

// Logout function
function logout() {
    sessionStorage.clear();
    window.location.href = "login.html";
}

// Check session on page load
function checkSession() {
    const role = sessionStorage.getItem("role");
    const username = sessionStorage.getItem("username");
    
    if (username) {
        document.getElementById("user-display").innerText = username;
    }
    
    return { role, username };
}

// Initialize on candidate page
if (document.getElementById("cid")) {
    checkSession();
}