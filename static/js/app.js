/* 口语AI伴侣 - 前端逻辑 */

const API_BASE = "";

// ========== 工具函数 ==========
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const ua = navigator.userAgent;
const isWeChat = /MicroMessenger/i.test(ua);
const isIOS = /iPad|iPhone|iPod/i.test(ua);

function showStatus(msg, type = "system") {
    if (type === "error") {
        alert(msg);
    }
}

async function postJSON(url, body) {
    const res = await fetch(API_BASE + url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    return await res.json();
}

async function getJSON(url) {
    const res = await fetch(API_BASE + url);
    return await res.json();
}

function saveHistory(mode, content) {
    postJSON("/api/save-history", { mode, content }).catch(() => {});
}

// ========== 录音/识别能力检测 ==========
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const hasMediaRecorder = !!(window.MediaRecorder && navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
const canUseSpeechRecognition = !!(SpeechRecognition && !isIOS && !isWeChat);
const synth = window.speechSynthesis;

let recognition = null;
let isRecording = false;
let recordButton = null;

// Web Speech API 相关
let speechCallback = null;

// MediaRecorder 相关
let mediaRecorder = null;
let recordedChunks = [];
let mediaStream = null;
let fallbackCallback = null;
let audioStopCallback = null;

function setMicButton(btn, recording) {
    if (recording) {
        btn.classList.add("recording");
        btn.textContent = "⏹ 停止录音";
    } else {
        btn.classList.remove("recording");
        btn.textContent = "🎤 开始录音";
    }
}

// ========== Web Speech API 封装 ==========
function initRecognition() {
    if (!SpeechRecognition) return null;
    const r = new SpeechRecognition();
    r.continuous = false;
    r.interimResults = true;
    r.lang = "en-US";

    r.onstart = () => {
        isRecording = true;
        if (recordButton) setMicButton(recordButton, true);
    };

    r.onend = () => {
        isRecording = false;
        if (recordButton) setMicButton(recordButton, false);
        recordButton = null;
    };

    r.onresult = (event) => {
        let final = "";
        let interim = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
            const t = event.results[i][0].transcript;
            if (event.results[i].isFinal) final += t;
            else interim += t;
        }
        if (speechCallback) speechCallback(final || interim, event.results[event.results.length - 1].isFinal);
    };

    r.onerror = (e) => {
        console.error("Recognition error:", e);
        isRecording = false;
        if (recordButton) setMicButton(recordButton, false);
        recordButton = null;
        let msg = "语音识别出错，请检查麦克风权限或换用 Chrome/Edge 浏览器。";
        if (e.error === "not-allowed") msg = "麦克风权限被拒绝，请在浏览器地址栏允许使用麦克风。";
        if (e.error === "no-speech") msg = "没有检测到语音，请大声、清晰地说英文。";
        if (e.error === "network") msg = "语音识别网络错误，请检查网络连接。";
        showStatus(msg, "error");
    };

    return r;
}

function startSpeechRecording(btn, callback) {
    if (!recognition) {
        showStatus("你的浏览器不支持语音识别，请使用 Chrome 或 Edge。", "error");
        return;
    }
    if (isRecording) return;
    recordButton = btn;
    speechCallback = callback;
    try {
        recognition.start();
    } catch (e) {
        console.error("start() failed:", e);
        isRecording = false;
        setMicButton(btn, false);
        recordButton = null;
    }
}

function stopSpeechRecording() {
    if (recognition && isRecording) recognition.stop();
}

// ========== MediaRecorder 纯录音（话题/跟读/表达用） ==========
async function startAudioRecording(btn, onStop) {
    if (isRecording) return;
    if (!hasMediaRecorder) {
        showStatus("当前浏览器不支持录音，请使用 Chrome/Edge 桌面版或手动输入。", "error");
        return;
    }
    try {
        mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const options = {};
        if (MediaRecorder.isTypeSupported("audio/webm")) options.mimeType = "audio/webm";
        else if (MediaRecorder.isTypeSupported("audio/mp4")) options.mimeType = "audio/mp4";

        mediaRecorder = new MediaRecorder(mediaStream, options);
        recordedChunks = [];
        audioStopCallback = onStop;

        mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) recordedChunks.push(e.data);
        };

        mediaRecorder.onstop = () => {
            if (mediaStream) mediaStream.getTracks().forEach((t) => t.stop());
            setMicButton(btn, false);
            isRecording = false;
            recordButton = null;

            const mimeType = mediaRecorder.mimeType || "audio/webm";
            const blob = new Blob(recordedChunks, { type: mimeType });
            const url = URL.createObjectURL(blob);
            if (audioStopCallback) audioStopCallback(blob, url);
        };

        mediaRecorder.start();
        isRecording = true;
        recordButton = btn;
        setMicButton(btn, true);
    } catch (e) {
        console.error("audio recording error:", e);
        showStatus("无法访问麦克风，请检查浏览器权限设置。", "error");
        setMicButton(btn, false);
        isRecording = false;
        recordButton = null;
    }
}

// ========== MediaRecorder + 后端 Whisper 转写（AI 对话 fallback 用） ==========
async function startTranscribeRecording(btn, callback) {
    if (isRecording) return;
    if (!hasMediaRecorder) {
        showStatus("当前浏览器不支持录音，请使用 Chrome/Edge 桌面版或手动输入。", "error");
        return;
    }
    try {
        mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const options = {};
        if (MediaRecorder.isTypeSupported("audio/webm")) options.mimeType = "audio/webm";
        else if (MediaRecorder.isTypeSupported("audio/mp4")) options.mimeType = "audio/mp4";

        mediaRecorder = new MediaRecorder(mediaStream, options);
        recordedChunks = [];
        fallbackCallback = callback;

        mediaRecorder.ondataavailable = (e) => {
            if (e.data.size > 0) recordedChunks.push(e.data);
        };

        mediaRecorder.onstop = async () => {
            if (mediaStream) mediaStream.getTracks().forEach((t) => t.stop());
            setMicButton(btn, false);
            isRecording = false;
            recordButton = null;

            const mimeType = mediaRecorder.mimeType || "audio/webm";
            const ext = mimeType.includes("mp4") ? "mp4" : "webm";
            const blob = new Blob(recordedChunks, { type: mimeType });
            const text = await transcribeAudio(blob, ext);
            if (fallbackCallback) fallbackCallback(text, true);
        };

        mediaRecorder.start();
        isRecording = true;
        recordButton = btn;
        setMicButton(btn, true);
    } catch (e) {
        console.error("transcribe recording error:", e);
        showStatus("无法访问麦克风，请检查浏览器权限设置。", "error");
        setMicButton(btn, false);
        isRecording = false;
        recordButton = null;
    }
}

function stopMediaRecorder() {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
        mediaRecorder.stop();
    }
}

async function transcribeAudio(blob, ext) {
    const formData = new FormData();
    formData.append("audio", blob, `recording.${ext}`);
    try {
        const res = await fetch(API_BASE + "/api/transcribe", { method: "POST", body: formData });
        const data = await res.json();
        if (data.error) return `（转写失败：${data.error}）`;
        return data.text || "";
    } catch (e) {
        return "（转写请求失败，请检查网络或 API 配置）";
    }
}

function stopRecording() {
    if (canUseSpeechRecognition && recognition && isRecording) {
        stopSpeechRecording();
    } else {
        stopMediaRecorder();
    }
}

function speak(text, lang = "en-US", rate = 0.9) {
    if (!synth) return;
    if (synth.speaking) synth.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = lang;
    u.rate = rate;
    synth.speak(u);
}

function unlockSpeech() {
    // iOS / 微信需要在用户手势内激活 speechSynthesis，否则异步回调里无法播放
    if (!synth) return;
    try {
        if (synth.paused) synth.resume();
        // 部分浏览器需要 speak 一次才能真正解锁
        const u = new SpeechSynthesisUtterance(" ");
        u.volume = 0;
        synth.speak(u);
    } catch (e) {
        console.error("unlock speech failed:", e);
    }
}

function showAudioPlayer(wrapId, url) {
    const wrap = $(`#${wrapId}`);
    if (!wrap) return;
    wrap.innerHTML = "";
    const audio = document.createElement("audio");
    audio.controls = true;
    audio.src = url;
    audio.className = "playback-audio";
    wrap.appendChild(audio);
}

// ========== Tab 切换 ==========
function switchTab(mode) {
    $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.mode === mode));
    $$(".panel").forEach((p) => p.classList.toggle("active", p.id === `panel-${mode}`));
    if (mode === "history") loadHistory();
}

$$(".tab").forEach((t) => t.addEventListener("click", () => switchTab(t.dataset.mode)));

// ========== AI 情景对话 ==========
const chatMessages = $("#chat-messages");
const chatInput = $("#chat-input");
const chatScenario = $("#chat-scenario");
let chatHistory = [];
let autoSpeakEnabled = true;

function appendMessage(role, text) {
    const div = document.createElement("div");
    div.className = `message ${role}`;
    div.textContent = text;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function getScenarioPrompt(scenario) {
    const base = `You are a friendly native English speaker having a casual conversation with a Chinese learner who wants to practice spoken English.
Reply naturally to what the user just said.
Use only 2-3 short sentences.
Ask one simple follow-up question related to the same topic.
Only correct grammar if the mistake changes the meaning; keep corrections brief and friendly.
Do not lecture, do not repeat yourself, and do not change the topic unexpectedly.`;
    const scenarios = {
        daily: base + " Talk about daily life, hobbies, food, travel, school, or anything the user brings up.",
        interview: base + " You are the interviewer. Ask one common job interview question at a time, then react naturally to the answer.",
        debate: base + " You are debating a topic. Give a short opinion and ask what the user thinks about the same topic.",
        academic: base + " Discuss academic topics at a college level. Use clear language, but keep it like a real conversation, not a lecture.",
    };
    return scenarios[scenario] || scenarios.daily;
}

async function sendChat(text) {
    if (!text.trim()) return;
    appendMessage("user", text);
    chatInput.value = "";
    saveHistory("chat", text);

    const scenario = chatScenario.value;
    if (chatHistory.length === 0) {
        chatHistory.push({ role: "system", content: getScenarioPrompt(scenario) });
    }
    chatHistory.push({ role: "user", content: text });

    appendMessage("ai", "AI 正在思考…");
    const aiMsgDiv = chatMessages.lastElementChild;

    try {
        const res = await fetch(API_BASE + "/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ messages: chatHistory, stream: true }),
        });

        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            aiMsgDiv.textContent = `⚠️ ${data.error || "请求失败"}`;
            return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let fullText = "";
        let buffer = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop(); // keep incomplete line
            for (const line of lines) {
                const trimmed = line.trim();
                if (!trimmed.startsWith("data:")) continue;
                const dataStr = trimmed.slice(5).trim();
                if (dataStr === "[DONE]") continue;
                try {
                    const data = JSON.parse(dataStr);
                    const delta = data.choices?.[0]?.delta?.content || "";
                    if (delta) {
                        fullText += delta;
                        aiMsgDiv.textContent = fullText || "…";
                        chatMessages.scrollTop = chatMessages.scrollHeight;
                    }
                } catch (e) {
                    // ignore malformed SSE chunks
                }
            }
        }

        if (fullText) {
            chatHistory.push({ role: "assistant", content: fullText });
            if (autoSpeakEnabled) speak(fullText, "en-US", 0.95);
        } else {
            aiMsgDiv.textContent = "Sorry, I didn't get that.";
        }
    } catch (e) {
        aiMsgDiv.textContent = "⚠️ 请求失败，请检查后端是否启动或 API 配置是否正确。";
    }
}

$("#send-chat").addEventListener("click", () => {
    unlockSpeech();
    sendChat(chatInput.value);
});
chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        unlockSpeech();
        sendChat(chatInput.value);
    }
});

$("#new-chat").addEventListener("click", () => {
    chatHistory = [];
    chatMessages.innerHTML = "";
    appendMessage("system", "开始新对话。选择场景后输入或说出英文。");
});

const ttsToggle = $("#tts-toggle");
if (ttsToggle) {
    ttsToggle.addEventListener("click", () => {
        autoSpeakEnabled = !autoSpeakEnabled;
        ttsToggle.textContent = autoSpeakEnabled ? "🔊" : "🔇";
        ttsToggle.title = autoSpeakEnabled ? "自动朗读 AI 回复（已开启）" : "自动朗读 AI 回复（已关闭）";
    });
}

const micChat = $("#mic-chat");
micChat.addEventListener("click", () => {
    if (isRecording) {
        stopRecording();
        return;
    }
    unlockSpeech();
    chatInput.placeholder = "正在聆听，请说英文…";
    if (canUseSpeechRecognition) {
        startSpeechRecording(micChat, (text, isFinal) => {
            chatInput.value = text;
            if (isFinal) {
                chatInput.placeholder = "输入英文，或点击麦克风录音…";
                sendChat(text);
            }
        });
    } else if (hasMediaRecorder) {
        startTranscribeRecording(micChat, (text) => {
            chatInput.value = text;
            chatInput.placeholder = "输入英文，或点击麦克风录音…";
            if (text && !text.startsWith("（")) sendChat(text);
        });
    } else {
        showStatus("当前浏览器不支持录音，请手动输入。", "error");
    }
});

// ========== 雅思口语 ==========
const ieltsMessages = $("#ielts-messages");
const ieltsInput = $("#ielts-input");
const ieltsPartBadge = $("#ielts-part-badge");
const ieltsCard = $("#ielts-card");
const ieltsPartTitle = $("#ielts-part-title");
const ieltsQuestion = $("#ielts-question");
const ieltsPoints = $("#ielts-points");
const ieltsStatus = $("#ielts-status");

let ieltsHistory = [];
let ieltsPart = 0;
let ieltsStep = 0;
let ieltsInProgress = false;

const IELTS_SYSTEM = `You are a professional IELTS Speaking examiner conducting a realistic mock test in English.
Rules:
- Ask exactly ONE question at a time.
- Part 1: ask 3 short warm-up questions one by one.
- Part 2: present ONE cue card topic with 4 bullet points, then tell the candidate to speak for 1-2 minutes.
- Part 3: ask 3 deeper discussion questions related to the Part 2 topic.
- After the last Part 3 answer, give brief encouraging feedback and end the test.
- Keep your language natural and examiner-like. Do not dump all questions at once.`;

function appendIeltsMessage(role, text) {
    const div = document.createElement("div");
    div.className = `message ${role}`;
    div.textContent = text;
    ieltsMessages.appendChild(div);
    ieltsMessages.scrollTop = ieltsMessages.scrollHeight;
}

function updateIeltsCard(title, question, points = []) {
    ieltsPartTitle.textContent = title;
    ieltsQuestion.textContent = question;
    ieltsPoints.innerHTML = points.map((p) => `<li>${p}</li>`).join("");
    ieltsCard.style.display = "block";
}

function getIeltsInstruction() {
    if (ieltsPart === 1) return `Now at Part 1, question ${ieltsStep + 1} of 3. Ask the next warm-up question naturally. Only one question.`;
    if (ieltsPart === 2) return `Now at Part 2. Present ONE cue card topic with 4 bullet points. Then say: "You have one minute to prepare if you wish, then please speak for 1 to 2 minutes."`;
    if (ieltsPart === 3) return `Now at Part 3, question ${ieltsStep + 1} of 3. Ask a deeper discussion question related to the Part 2 topic. Only one question.`;
    return "The test is complete. Give brief overall feedback and say goodbye.";
}

async function streamIeltsReply(messages) {
    const res = await fetch(API_BASE + "/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ messages, stream: true }),
    });

    if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        appendIeltsMessage("system", `⚠️ ${data.error || "请求失败"}`);
        return "";
    }

    appendIeltsMessage("ai", "AI 正在思考…");
    const aiMsgDiv = ieltsMessages.lastElementChild;

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let fullText = "";
    let buffer = "";

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();
        for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith("data:")) continue;
            const dataStr = trimmed.slice(5).trim();
            if (dataStr === "[DONE]") continue;
            try {
                const data = JSON.parse(dataStr);
                const delta = data.choices?.[0]?.delta?.content || "";
                if (delta) {
                    fullText += delta;
                    aiMsgDiv.textContent = fullText || "…";
                    ieltsMessages.scrollTop = ieltsMessages.scrollHeight;
                }
            } catch (e) {
                // ignore malformed chunks
            }
        }
    }

    if (!fullText) {
        aiMsgDiv.textContent = "Sorry, I didn't get that.";
    }
    return fullText;
}

async function askIeltsQuestion() {
    const messages = [
        { role: "system", content: IELTS_SYSTEM + " " + getIeltsInstruction() },
        ...ieltsHistory,
    ];
    const reply = await streamIeltsReply(messages);
    if (reply) {
        ieltsHistory.push({ role: "assistant", content: reply });
        if (autoSpeakEnabled) speak(reply, "en-US", 0.95);
    }
}

async function startIelts() {
    ieltsHistory = [];
    ieltsPart = 1;
    ieltsStep = 0;
    ieltsInProgress = true;
    ieltsMessages.innerHTML = "";
    ieltsPartBadge.textContent = "Part 1";
    ieltsStatus.style.display = "none";
    updateIeltsCard("Part 1", "我会先问你 3 个简单的热身问题，请用英语回答。");
    await askIeltsQuestion();
}

async function submitIeltsAnswer(text) {
    if (!text.trim() || !ieltsInProgress) return;
    appendIeltsMessage("user", text);
    ieltsHistory.push({ role: "user", content: text });

    ieltsStep++;
    if (ieltsPart === 1 && ieltsStep >= 3) {
        ieltsPart = 2;
        ieltsStep = 0;
        ieltsPartBadge.textContent = "Part 2";
        updateIeltsCard("Part 2 话题卡", "请根据话题卡准备并连续说 1-2 分钟。");
    } else if (ieltsPart === 2 && ieltsStep >= 1) {
        ieltsPart = 3;
        ieltsStep = 0;
        ieltsPartBadge.textContent = "Part 3";
        updateIeltsCard("Part 3", "接下来是 3 个与话题相关的深入讨论问题。");
    } else if (ieltsPart === 3 && ieltsStep >= 3) {
        ieltsInProgress = false;
        ieltsPartBadge.textContent = "已完成";
        updateIeltsCard("考试结束", "下面是考官的整体反馈。");
    }

    await askIeltsQuestion();
}

$("#start-ielts").addEventListener("click", () => {
    unlockSpeech();
    startIelts();
});

$("#send-ielts").addEventListener("click", () => {
    unlockSpeech();
    submitIeltsAnswer(ieltsInput.value);
    ieltsInput.value = "";
});
ieltsInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
        unlockSpeech();
        submitIeltsAnswer(ieltsInput.value);
        ieltsInput.value = "";
    }
});

const micIelts = $("#mic-ielts");
micIelts.addEventListener("click", () => {
    if (isRecording) {
        stopRecording();
        return;
    }
    if (!ieltsInProgress) {
        showStatus("请先点击“开始模拟”启动雅思口语考试。", "error");
        return;
    }
    unlockSpeech();
    ieltsInput.placeholder = "正在聆听，请说英文…";
    if (canUseSpeechRecognition) {
        startSpeechRecording(micIelts, (text, isFinal) => {
            ieltsInput.value = text;
            if (isFinal) {
                ieltsInput.placeholder = "输入英文，或点击麦克风录音…";
                submitIeltsAnswer(text);
            }
        });
    } else if (hasMediaRecorder) {
        startTranscribeRecording(micIelts, (text) => {
            ieltsInput.value = text;
            ieltsInput.placeholder = "输入英文，或点击麦克风录音…";
            if (text && !text.startsWith("（")) submitIeltsAnswer(text);
        });
    } else {
        showStatus("当前浏览器不支持录音，请手动输入。", "error");
    }
});

// ========== 话题独白 ==========
let currentTopic = null;
let topicTimer = null;
let topicSeconds = 0;

function renderTopic(topic) {
    currentTopic = topic;
    $("#topic-category").textContent = topic.category;
    $("#topic-title").textContent = topic.title;
    $("#topic-hints").innerHTML = topic.hints.map((h) => `<li>${h}</li>`).join("");
    $("#topic-result").textContent = "点击麦克风开始作答；无法录音时可在下方输入英文回答。";
    $("#topic-audio-wrap").innerHTML = "";
}

async function nextTopic() {
    const topic = await getJSON("/api/random-topic");
    renderTopic(topic);
}

$("#next-topic").addEventListener("click", nextTopic);

async function submitTopicAnswer(text) {
    if (!text.trim()) {
        showStatus("请输入你的英文回答后再提交。", "error");
        return;
    }
    $("#topic-result").textContent = "正在评分…";
    const prompt = `Topic: ${currentTopic ? currentTopic.title : ""}\nUser's answer: ${text}\nPlease evaluate the answer based on relevance to the topic, grammar correctness, vocabulary use, and completeness. Return score 0-10.`;
    const result = await evaluateAnswer(prompt);
    $("#topic-result").innerHTML = `${escapeHtml(text)}<br><strong>得分：${result.score}/10</strong> · ${result.comment}`;
    if (currentTopic) saveHistory("topic", `${currentTopic.title} | ${text} | 得分：${result.score}`);
    $("#topic-answer").value = "";
}

$("#submit-topic").addEventListener("click", () => {
    submitTopicAnswer($("#topic-answer").value);
});

const recordTopic = $("#record-topic");
recordTopic.addEventListener("click", () => {
    if (isRecording) {
        stopRecording();
        clearInterval(topicTimer);
        recordTopic.textContent = "🎤 开始录音";
        return;
    }
    topicSeconds = 0;
    $("#timer").textContent = "00:00";
    $("#topic-result").textContent = "正在录音…";
    $("#topic-audio-wrap").innerHTML = "";
    topicTimer = setInterval(() => {
        topicSeconds++;
        const m = String(Math.floor(topicSeconds / 60)).padStart(2, "0");
        const s = String(topicSeconds % 60).padStart(2, "0");
        $("#timer").textContent = `${m}:${s}`;
    }, 1000);
    recordTopic.textContent = "⏹ 结束录音";

    if (canUseSpeechRecognition) {
        startSpeechRecording(recordTopic, (text, isFinal) => {
            $("#topic-result").textContent = text;
            if (isFinal) {
                clearInterval(topicTimer);
                recordTopic.textContent = "🎤 开始录音";
                $("#topic-answer").value = text;
                if (isMobileDevice()) submitTopicAnswer(text);
            }
        });
    } else {
        startAudioRecording(recordTopic, async (blob) => {
            clearInterval(topicTimer);
            recordTopic.textContent = "🎤 开始录音";
            $("#topic-result").textContent = "正在转写…";
            showAudioPlayer("topic-audio-wrap", URL.createObjectURL(blob));
            const ext = blob.type.includes("mp4") ? "mp4" : "webm";
            const text = await transcribeAudio(blob, ext);
            $("#topic-result").textContent = text || "（未能识别到文字）";
            if (text && !text.startsWith("（")) {
                $("#topic-answer").value = text;
                if (isMobileDevice()) submitTopicAnswer(text);
            }
        });
    }
});

// ========== 影子跟读 ==========
let currentShadow = null;

function renderShadow(shadow) {
    currentShadow = shadow;
    $("#shadow-title").textContent = shadow.title;
    $("#shadow-text").textContent = shadow.text;
    $("#shadow-hint").textContent = `💡 ${shadow.audioHint}`;
    $("#shadow-result").textContent = "录音后会显示识别结果；无法录音时可在下方输入跟读内容。";
    $("#shadow-audio-wrap").innerHTML = "";
}

async function nextShadow() {
    const shadow = await getJSON("/api/random-shadow");
    renderShadow(shadow);
}

$("#next-shadow").addEventListener("click", nextShadow);
$("#play-shadow").addEventListener("click", () => {
    if (currentShadow) speak(currentShadow.text, "en-US", 0.85);
});

function showShadowResult(text) {
    if (!currentShadow) {
        $("#shadow-result").textContent = text;
        return;
    }
    const score = scoreShadowing(currentShadow.text, text);
    const comment = shadowingComment(score);
    $("#shadow-result").innerHTML = `${escapeHtml(text)}<br><strong>得分：${score}/10</strong> · ${comment}`;
}

$("#submit-shadow").addEventListener("click", () => {
    const text = $("#shadow-answer").value.trim();
    if (!text) {
        showStatus("请输入跟读内容后再提交。", "error");
        return;
    }
    showShadowResult(text);
    if (currentShadow) saveHistory("shadow", `${currentShadow.title} | ${text}`);
    $("#shadow-answer").value = "";
    showStatus("跟读内容已保存到练习记录。", "system");
});

const recordShadow = $("#record-shadow");
recordShadow.addEventListener("click", () => {
    if (isRecording) {
        stopRecording();
        return;
    }
    $("#shadow-result").textContent = "正在录音…";
    $("#shadow-audio-wrap").innerHTML = "";

    if (canUseSpeechRecognition) {
        startSpeechRecording(recordShadow, (text, isFinal) => {
            $("#shadow-result").textContent = text;
            if (isFinal) {
                $("#shadow-answer").value = text;
                showShadowResult(text);
                if (currentShadow) saveHistory("shadow", `${currentShadow.title} | ${text}`);
            }
        });
    } else {
        startAudioRecording(recordShadow, async (blob) => {
            $("#shadow-result").textContent = "正在转写…";
            showAudioPlayer("shadow-audio-wrap", URL.createObjectURL(blob));
            const ext = blob.type.includes("mp4") ? "mp4" : "webm";
            const text = await transcribeAudio(blob, ext);
            if (text && !text.startsWith("（")) {
                $("#shadow-answer").value = text;
                showShadowResult(text);
                if (currentShadow) saveHistory("shadow", `${currentShadow.title} | ${text}`);
            } else {
                $("#shadow-result").textContent = text || "（未能识别到文字）";
            }
        });
    }
});

// ========== 每日表达 ==========
let currentExpr = null;

function renderExpression(expr) {
    currentExpr = expr;
    $("#expr-en").textContent = expr.en;
    $("#expr-zh").textContent = expr.zh;
    $("#expr-example").textContent = `例句：${expr.example}`;
    $("#expr-result").textContent = "录音后会显示识别结果；无法录音时可在下方输入造句。";
    $("#expr-audio-wrap").innerHTML = "";
}

async function nextExpression() {
    const expr = await getJSON("/api/random-expression");
    renderExpression(expr);
}

$("#next-expression").addEventListener("click", nextExpression);
$("#play-expression").addEventListener("click", () => {
    if (currentExpr) {
        speak(currentExpr.en, "en-US", 0.85);
        setTimeout(() => speak(currentExpr.example, "en-US", 0.85), 1500);
    }
});

async function submitExpressionAnswer(text) {
    if (!text.trim()) {
        showStatus("请输入造句后再提交。", "error");
        return;
    }
    $("#expr-result").textContent = "正在评分…";
    const prompt = `Expression: ${currentExpr ? currentExpr.en : ""}\nUser's sentence: ${text}\nPlease evaluate whether the expression is used correctly and naturally. Return score 0-10.`;
    const result = await evaluateAnswer(prompt);
    $("#expr-result").innerHTML = `${escapeHtml(text)}<br><strong>得分：${result.score}/10</strong> · ${result.comment}`;
    if (currentExpr) saveHistory("expression", `${currentExpr.en} | ${text} | 得分：${result.score}`);
    $("#expr-answer").value = "";
}

$("#submit-expression").addEventListener("click", () => {
    submitExpressionAnswer($("#expr-answer").value);
});

const recordExpression = $("#record-expression");
recordExpression.addEventListener("click", () => {
    if (isRecording) {
        stopRecording();
        return;
    }
    $("#expr-result").textContent = "正在录音…";
    $("#expr-audio-wrap").innerHTML = "";

    if (canUseSpeechRecognition) {
        startSpeechRecording(recordExpression, (text, isFinal) => {
            $("#expr-result").textContent = text;
            if (isFinal) {
                $("#expr-answer").value = text;
                if (isMobileDevice()) submitExpressionAnswer(text);
            }
        });
    } else {
        startAudioRecording(recordExpression, async (blob) => {
            $("#expr-result").textContent = "正在转写…";
            showAudioPlayer("expr-audio-wrap", URL.createObjectURL(blob));
            const ext = blob.type.includes("mp4") ? "mp4" : "webm";
            const text = await transcribeAudio(blob, ext);
            $("#expr-result").textContent = text || "（未能识别到文字）";
            if (text && !text.startsWith("（")) {
                $("#expr-answer").value = text;
                if (isMobileDevice()) submitExpressionAnswer(text);
            }
        });
    }
});

// ========== 练习记录 ==========
async function loadHistory() {
    const list = $("#history-list");
    list.innerHTML = "<p>加载中…</p>";
    try {
        const records = await getJSON("/api/history");
        if (records.length === 0) {
            list.innerHTML = "<p>还没有记录，去练一练吧！</p>";
            return;
        }
        list.innerHTML = records
            .slice()
            .reverse()
            .map((r) => {
                const modeText = { chat: "AI对话", topic: "话题独白", shadow: "影子跟读", expression: "每日表达" }[r.mode] || r.mode;
                return `<div class="history-item"><time>${r.time}</time><strong>[${modeText}]</strong> ${escapeHtml(r.content)}</div>`;
            })
            .join("");
    } catch (e) {
        list.innerHTML = "<p>加载失败，请检查后端是否启动。</p>";
    }
}

$("#refresh-history").addEventListener("click", loadHistory);

function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

// 影子跟读评分：基于词级别的 Levenshtein 距离，0-10 分
function normalizeWords(text) {
    return text
        .toLowerCase()
        .replace(/[^\w\s']/g, " ")
        .trim()
        .split(/\s+/)
        .filter(Boolean);
}

function levenshteinDistance(a, b) {
    const matrix = [];
    for (let i = 0; i <= b.length; i++) matrix[i] = [i];
    for (let j = 0; j <= a.length; j++) matrix[0][j] = j;
    for (let i = 1; i <= b.length; i++) {
        for (let j = 1; j <= a.length; j++) {
            matrix[i][j] =
                b[i - 1] === a[j - 1]
                    ? matrix[i - 1][j - 1]
                    : Math.min(matrix[i - 1][j - 1] + 1, matrix[i][j - 1] + 1, matrix[i - 1][j] + 1);
        }
    }
    return matrix[b.length][a.length];
}

function scoreShadowing(original, spoken) {
    const origWords = normalizeWords(original);
    const spokenWords = normalizeWords(spoken);
    if (origWords.length === 0) return 0;
    const maxLen = Math.max(origWords.length, spokenWords.length);
    if (maxLen === 0) return 0;
    const dist = levenshteinDistance(origWords, spokenWords);
    const similarity = 1 - dist / maxLen;
    return Math.min(10, Math.max(0, Math.round(similarity * 10)));
}

function shadowingComment(score) {
    if (score >= 9) return "Excellent! 几乎和原文一致。";
    if (score >= 7) return "Good job! 只漏掉或说错了少量词。";
    if (score >= 5) return "Not bad. 继续练习，注意漏掉的词。";
    if (score >= 3) return "Keep practicing. 和原文还有不少差距。";
    return "Try again. 再多听几遍范文再跟读。";
}

// AI 评分：根据回答内容和主题/表达的相关性、语法、完整性打分
async function evaluateAnswer(prompt) {
    try {
        const res = await fetch(API_BASE + "/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                messages: [
                    { role: "system", content: "You are a strict but fair English teacher. Evaluate the user's answer and return ONLY a JSON object like {\"score\": 7, \"comment\": \"...\"}. Score must be 0-10. Comment should be in Chinese, 1-2 sentences." },
                    { role: "user", content: prompt },
                ],
                stream: false,
            }),
        });
        const data = await res.json();
        const content = data.choices?.[0]?.message?.content || "";
        const match = content.match(/\{[\s\S]*?\}/);
        if (match) return JSON.parse(match[0]);
    } catch (e) {
        console.error("evaluate error:", e);
    }
    return { score: 0, comment: "评分失败，请重试。" };
}

function evaluationComment(score) {
    if (score >= 9) return "非常出色！";
    if (score >= 7) return "表现不错，继续加油。";
    if (score >= 5) return "基本达标，还有提升空间。";
    if (score >= 3) return "需要多练习。";
    return "建议再试一次。";
}

function isMobileDevice() {
    return isIOS || isWeChat || window.innerWidth < 640;
}

// ========== 初始化 ==========
function setupBrowserTip() {
    // 现在录音+后端转写已支持所有浏览器，不再显示能力警告
    const tip = $("#browser-tip");
    if (tip) tip.style.display = "none";
}

function setupMicButtons() {
    const canRecord = canUseSpeechRecognition || hasMediaRecorder;
    ["#mic-chat", "#record-topic", "#record-shadow", "#record-expression"].forEach((sel) => {
        const btn = $(sel);
        if (!btn) return;
        if (!canRecord) {
            btn.disabled = true;
            btn.title = "当前浏览器不支持录音，请使用 Chrome/Edge 桌面版";
            btn.style.opacity = "0.6";
            btn.style.cursor = "not-allowed";
        } else if (!canUseSpeechRecognition && hasMediaRecorder) {
            btn.title = "当前浏览器不支持实时识别，将录音并支持回听";
        }
    });
}

async function init() {
    recognition = canUseSpeechRecognition ? initRecognition() : null;
    setupBrowserTip();
    setupMicButtons();

    appendMessage("system", "欢迎来到口语AI伴侣！点击麦克风说英文，AI 会文字回复并自动朗读。");

    await nextTopic();
    await nextShadow();
    await nextExpression();
}

init();
