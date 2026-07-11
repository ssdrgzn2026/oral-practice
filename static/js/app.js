/* 口语练习系统 - 前端逻辑 */

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

// ========== 语音识别能力检测 ==========
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
const hasMediaRecorder = !!(window.MediaRecorder && navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
const synth = window.speechSynthesis;

let recognition = null;
let isRecording = false;
let recordButton = null;

// Web Speech API 相关
let speechCallback = null;

// MediaRecorder  fallback 相关
let mediaRecorder = null;
let recordedChunks = [];
let mediaStream = null;
let fallbackCallback = null;

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

// ========== MediaRecorder 后端转写 fallback ==========
async function startFallbackRecording(btn, callback) {
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
            mediaStream.getTracks().forEach((t) => t.stop());
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
        console.error("fallback recording error:", e);
        showStatus("无法访问麦克风，请检查浏览器权限设置。", "error");
        setMicButton(btn, false);
        isRecording = false;
        recordButton = null;
    }
}

function stopFallbackRecording() {
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

// ========== 统一录音入口 ==========
function startRecording(btn, callback) {
    if (SpeechRecognition) {
        startSpeechRecording(btn, callback);
    } else if (hasMediaRecorder) {
        startFallbackRecording(btn, callback);
    } else {
        showStatus("当前浏览器不支持录音，请使用 Chrome/Edge 桌面版或手动输入。", "error");
    }
}

function stopRecording() {
    if (SpeechRecognition) {
        stopSpeechRecording();
    } else if (hasMediaRecorder) {
        stopFallbackRecording();
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

function appendMessage(role, text) {
    const div = document.createElement("div");
    div.className = `message ${role}`;
    div.textContent = text;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function getScenarioPrompt(scenario) {
    const base = "You are a friendly English tutor helping a Chinese learner practice spoken English. Keep responses natural, conversational, and around 2-4 sentences. If the user makes mistakes, gently correct them.";
    const scenarios = {
        daily: base + " Chat about daily life, hobbies, and campus.",
        interview: base + " Conduct a short English job interview. Ask one question at a time.",
        debate: base + " Debate a thought-provoking topic. State your view briefly and ask the user's opinion.",
        academic: base + " Discuss academic topics at a college level. Use clear and precise language.",
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

    appendMessage("system", "AI 正在思考…");
    const systemMsg = chatMessages.lastElementChild;

    try {
        const data = await postJSON("/api/chat", { messages: chatHistory, model: "gpt-4o-mini" });
        systemMsg.remove();
        if (data.error) {
            appendMessage("system", `⚠️ ${data.error}`);
            return;
        }
        const reply = data.choices?.[0]?.message?.content || "Sorry, I didn't get that.";
        appendMessage("ai", reply);
        chatHistory.push({ role: "assistant", content: reply });
    } catch (e) {
        systemMsg.remove();
        appendMessage("system", "⚠️ 请求失败，请检查后端是否启动或 API 配置是否正确。");
    }
}

$("#send-chat").addEventListener("click", () => sendChat(chatInput.value));
chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") sendChat(chatInput.value);
});

$("#new-chat").addEventListener("click", () => {
    chatHistory = [];
    chatMessages.innerHTML = "";
    appendMessage("system", "开始新对话。选择场景后输入或说出英文。");
});

const micChat = $("#mic-chat");
micChat.addEventListener("click", () => {
    if (isRecording) {
        stopRecording();
        return;
    }
    chatInput.placeholder = "正在聆听，请说英文…";
    startRecording(micChat, (text, isFinal) => {
        chatInput.value = text;
        if (isFinal) {
            chatInput.placeholder = "输入英文，或点击麦克风录音…";
            sendChat(text);
        }
    });
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
    $("#topic-result").textContent = "点击麦克风后开始作答，系统会尝试识别你的发音。";
}

async function nextTopic() {
    const topic = await getJSON("/api/random-topic");
    renderTopic(topic);
}

$("#next-topic").addEventListener("click", nextTopic);

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
    $("#topic-result").textContent = "正在聆听…";
    topicTimer = setInterval(() => {
        topicSeconds++;
        const m = String(Math.floor(topicSeconds / 60)).padStart(2, "0");
        const s = String(topicSeconds % 60).padStart(2, "0");
        $("#timer").textContent = `${m}:${s}`;
    }, 1000);
    recordTopic.textContent = "⏹ 结束录音";
    startRecording(recordTopic, (text, isFinal) => {
        $("#topic-result").textContent = text;
        if (isFinal) {
            clearInterval(topicTimer);
            recordTopic.textContent = "🎤 开始录音";
            saveHistory("topic", `${currentTopic.title} | ${text}`);
        }
    });
});

// ========== 影子跟读 ==========
let currentShadow = null;

function renderShadow(shadow) {
    currentShadow = shadow;
    $("#shadow-title").textContent = shadow.title;
    $("#shadow-text").textContent = shadow.text;
    $("#shadow-hint").textContent = `💡 ${shadow.audioHint}`;
    $("#shadow-result").textContent = "录音后会显示识别结果。";
}

async function nextShadow() {
    const shadow = await getJSON("/api/random-shadow");
    renderShadow(shadow);
}

$("#next-shadow").addEventListener("click", nextShadow);
$("#play-shadow").addEventListener("click", () => {
    if (currentShadow) speak(currentShadow.text, "en-US", 0.85);
});

const recordShadow = $("#record-shadow");
recordShadow.addEventListener("click", () => {
    if (isRecording) {
        stopRecording();
        return;
    }
    $("#shadow-result").textContent = "正在聆听…";
    startRecording(recordShadow, (text, isFinal) => {
        $("#shadow-result").textContent = text;
        if (isFinal && currentShadow) {
            saveHistory("shadow", `${currentShadow.title} | ${text}`);
        }
    });
});

// ========== 每日表达 ==========
let currentExpr = null;

function renderExpression(expr) {
    currentExpr = expr;
    $("#expr-en").textContent = expr.en;
    $("#expr-zh").textContent = expr.zh;
    $("#expr-example").textContent = `例句：${expr.example}`;
    $("#expr-result").textContent = "";
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

const recordExpression = $("#record-expression");
recordExpression.addEventListener("click", () => {
    if (isRecording) {
        stopRecording();
        return;
    }
    $("#expr-result").textContent = "正在聆听…";
    startRecording(recordExpression, (text, isFinal) => {
        $("#expr-result").textContent = text;
        if (isFinal && currentExpr) {
            saveHistory("expression", `${currentExpr.en} | ${text}`);
        }
    });
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

// ========== 初始化 ==========
function setupBrowserTip() {
    const tip = $("#browser-tip");
    if (!tip) return;

    if (!SpeechRecognition && !hasMediaRecorder) {
        tip.textContent = "⚠️ 当前浏览器不支持语音识别和录音，建议使用 Chrome/Edge 桌面版，或手动输入英文。";
        tip.style.display = "block";
    } else if (!SpeechRecognition && isWeChat) {
        tip.innerHTML =
            "⚠️ 微信内置浏览器不支持实时语音识别。安卓用户请点击右上角 ··· → 在浏览器打开（Chrome/Edge）。<br>" +
            "iPhone 用户可继续点击录音按钮，使用录音上传转写（需配置 API Key）。";
        tip.style.display = "block";
    } else if (!SpeechRecognition && isIOS) {
        tip.textContent = "⚠️ iOS 浏览器不支持实时语音识别。可点击录音按钮使用录音上传转写（需配置 API Key）。";
        tip.style.display = "block";
    }
}

function setupMicButtons() {
    const canRecord = SpeechRecognition || hasMediaRecorder;
    ["#mic-chat", "#record-topic", "#record-shadow", "#record-expression"].forEach((sel) => {
        const btn = $(sel);
        if (!btn) return;
        if (!canRecord) {
            btn.disabled = true;
            btn.title = "当前浏览器不支持录音，请使用 Chrome/Edge 桌面版";
            btn.style.opacity = "0.6";
            btn.style.cursor = "not-allowed";
        } else if (!SpeechRecognition && hasMediaRecorder) {
            btn.title = "当前浏览器使用录音上传转写（需配置 API Key）";
        }
    });
}

async function init() {
    recognition = initRecognition();
    setupBrowserTip();
    setupMicButtons();

    if (!SpeechRecognition && !hasMediaRecorder) {
        appendMessage("system", "⚠️ 当前浏览器不支持语音识别和录音，请使用 Chrome/Edge 桌面版，或手动输入英文。");
    } else if (!SpeechRecognition && hasMediaRecorder) {
        appendMessage("system", "当前浏览器使用录音上传转写，点击麦克风录音，说完后点击停止（需配置 API Key）。");
    } else {
        appendMessage("system", "欢迎来到口语练习系统！点击麦克风即可开始录音说英文。");
    }

    await nextTopic();
    await nextShadow();
    await nextExpression();
}

init();
