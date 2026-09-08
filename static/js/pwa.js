/* PWA 安装提示：引导用户“添加到主屏幕”
 * - 已是独立模式（已安装）则不显示
 * - iOS Safari：显示图文指引
 * - 安卓 Chrome：捕获 beforeinstallprompt，点击直接安装
 * - 关闭后 7 天内不再提示
 */
(function () {
    var DISMISS_KEY = "mischub_a2hs_dismissed";
    var DISMISS_DAYS = 7;

    // 已安装（standalone 模式）不提示
    if (window.matchMedia("(display-mode: standalone)").matches || navigator.standalone) return;

    // 7 天内关闭过不提示
    try {
        var ts = parseInt(localStorage.getItem(DISMISS_KEY) || "0", 10);
        if (ts && Date.now() - ts < DISMISS_DAYS * 864e5) return;
    } catch (e) {}

    var ua = navigator.userAgent;
    var isIOS = /iPhone|iPad|iPod/.test(ua);
    var isAndroid = /Android/.test(ua);
    if (!isIOS && !isAndroid) return; // 桌面端不提示

    var deferredPrompt = null;
    window.addEventListener("beforeinstallprompt", function (e) {
        e.preventDefault();
        deferredPrompt = e;
        if (isAndroid) showBanner("android");
    });

    if (isIOS) {
        // iOS 只有 Safari 支持添加主屏幕
        var isSafari = /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS|MicroMessenger/.test(ua);
        showBanner(isSafari ? "ios" : "ios-other");
    }

    function showBanner(kind) {
        if (document.getElementById("a2hs-banner")) return;

        var text, btnText;
        if (kind === "android") {
            text = "📲 把 MiscHub 安装到主屏幕，像 App 一样使用";
            btnText = "立即安装";
        } else if (kind === "ios") {
            text = "📲 点底部「分享」按钮 →「添加到主屏幕」，即可像 App 一样使用";
            btnText = null;
        } else {
            text = "📲 建议用 Safari 打开本页，然后「添加到主屏幕」，像 App 一样使用（微信内无法下载文件）";
            btnText = null;
        }

        var bar = document.createElement("div");
        bar.id = "a2hs-banner";
        bar.innerHTML =
            '<span class="a2hs-text">' + text + "</span>" +
            (btnText ? '<button class="a2hs-btn" id="a2hs-install">' + btnText + "</button>" : "") +
            '<button class="a2hs-close" id="a2hs-close" aria-label="关闭">×</button>';
        document.body.appendChild(bar);

        document.getElementById("a2hs-close").onclick = function () {
            bar.remove();
            try { localStorage.setItem(DISMISS_KEY, String(Date.now())); } catch (e) {}
        };

        var btn = document.getElementById("a2hs-install");
        if (btn) btn.onclick = function () {
            if (!deferredPrompt) return;
            deferredPrompt.prompt();
            deferredPrompt.userChoice.finally(function () { bar.remove(); });
            deferredPrompt = null;
        };
    }
})();
