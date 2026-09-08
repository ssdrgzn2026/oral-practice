/* PWA 安装提示：引导用户“添加到主屏幕”
 * - 已是独立模式（已安装）则不显示
 * - iOS Safari：显示图文指引
 * - 安卓：提示条常显；Chrome 捕获到 beforeinstallprompt 后升级为「立即安装」按钮
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
        upgradeBanner(); // 已有提示条则加按钮，没有则直接弹带按钮的条
    });

    if (isIOS) {
        // iOS 只有 Safari 支持添加主屏幕
        var isSafari = /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS|MicroMessenger/.test(ua);
        showBanner(isSafari ? "ios" : "ios-other");
    } else {
        // 安卓：常显文字指引（不等 beforeinstallprompt）
        var isWechat = /MicroMessenger/.test(ua);
        var isChrome = /Chrome\//.test(ua) && !isWechat;
        showBanner(isWechat ? "android-wechat" : isChrome ? "android-chrome" : "android-other");
    }

    function showBanner(kind) {
        if (document.getElementById("a2hs-banner")) return;

        var text;
        if (kind === "ios") {
            text = "📲 点底部「分享」按钮 →「添加到主屏幕」，即可像 App 一样使用";
        } else if (kind === "ios-other") {
            text = "📲 建议用 Safari 打开本页，然后「添加到主屏幕」，像 App 一样使用（微信内无法下载文件）";
        } else if (kind === "android-chrome") {
            text = "📲 安装到主屏幕：点浏览器右上角「⋮」菜单 →「安装应用」或「添加到主屏幕」";
        } else if (kind === "android-wechat") {
            text = "📲 建议点右上角「···」→「在浏览器打开」，再添加到主屏幕（微信内无法下载文件）";
        } else {
            text = "📲 点浏览器菜单 →「添加到主屏幕/安装应用」，即可像 App 一样使用";
        }
        renderBanner(text, false);
    }

    // beforeinstallprompt 触发后，把提示条升级为带「立即安装」按钮
    function upgradeBanner() {
        if (!deferredPrompt) return;
        var bar = document.getElementById("a2hs-banner");
        if (bar) {
            if (!document.getElementById("a2hs-install")) {
                bar.querySelector(".a2hs-text").textContent = "📲 把 MiscHub 安装到主屏幕，像 App 一样使用";
                var btn = document.createElement("button");
                btn.className = "a2hs-btn";
                btn.id = "a2hs-install";
                btn.textContent = "立即安装";
                bar.insertBefore(btn, bar.querySelector(".a2hs-close"));
                bindInstall(btn);
            }
        } else {
            renderBanner("📲 把 MiscHub 安装到主屏幕，像 App 一样使用", true);
        }
    }

    function renderBanner(text, withInstallBtn) {
        var bar = document.createElement("div");
        bar.id = "a2hs-banner";
        bar.innerHTML =
            '<span class="a2hs-text">' + text + "</span>" +
            (withInstallBtn ? '<button class="a2hs-btn" id="a2hs-install">立即安装</button>' : "") +
            '<button class="a2hs-close" id="a2hs-close" aria-label="关闭">×</button>';
        document.body.appendChild(bar);

        document.getElementById("a2hs-close").onclick = function () {
            bar.remove();
            try { localStorage.setItem(DISMISS_KEY, String(Date.now())); } catch (e) {}
        };

        if (withInstallBtn) bindInstall(document.getElementById("a2hs-install"));
    }

    function bindInstall(btn) {
        if (!btn) return;
        btn.onclick = function () {
            if (!deferredPrompt) return;
            deferredPrompt.prompt();
            deferredPrompt.userChoice.finally(function () {
                var bar = document.getElementById("a2hs-banner");
                if (bar) bar.remove();
            });
            deferredPrompt = null;
        };
    }
})();
