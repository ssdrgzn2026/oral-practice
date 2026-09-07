/* 访问统计心跳：上报会话开始/持续/结束，用于统计停留时长 */
(function () {
    if (location.protocol === "http:" && ["127.0.0.1", "localhost"].includes(location.hostname)) return;

    let sid = sessionStorage.getItem("mischub_sid");
    if (!sid) {
        sid = Date.now().toString(36) + Math.random().toString(36).slice(2, 10);
        sessionStorage.setItem("mischub_sid", sid);
    }

    function payload(event) {
        return JSON.stringify({
            sid: sid,
            event: event,
            path: location.pathname,
            user_id: localStorage.getItem("oral_user_id") || "",
        });
    }

    function send(event, beacon) {
        const body = payload(event);
        if (beacon && navigator.sendBeacon) {
            navigator.sendBeacon("/api/visit-beat", new Blob([body], { type: "application/json" }));
        } else {
            fetch("/api/visit-beat", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: body,
                keepalive: true,
            }).catch(function () {});
        }
    }

    send("enter");
    setInterval(function () {
        if (document.visibilityState === "visible") send("beat");
    }, 30000);
    window.addEventListener("pagehide", function () { send("leave", true); });
})();
