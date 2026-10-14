/* 物理知识地图 - 自制 canvas 动画演示
 * 每个动画是一个函数(canvas) => 返回停止函数
 */
window.PhyAnims = (function () {
    var registry = {};
    var current = null;

    function stop() {
        if (current) { current(); current = null; }
    }

    function start(id, canvas) {
        stop();
        var fn = registry[id];
        if (!fn) return false;
        current = fn(canvas);
        return true;
    }

    function loop(step) {
        var alive = true;
        var raf;
        function frame(t) {
            if (!alive) return;
            step(t);
            raf = requestAnimationFrame(frame);
        }
        raf = requestAnimationFrame(frame);
        return function () { alive = false; cancelAnimationFrame(raf); };
    }

    function ctx2d(canvas) {
        var dpr = window.devicePixelRatio || 1;
        var w = canvas.clientWidth, h = canvas.clientHeight;
        canvas.width = w * dpr;
        canvas.height = h * dpr;
        var ctx = canvas.getContext("2d");
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        return { ctx: ctx, w: w, h: h };
    }

    /* 时间膨胀：静止光钟 vs 运动光钟（光子斜线路径更长，滴答更慢） */
    registry["time-dilation"] = function (canvas) {
        var g = ctx2d(canvas), ctx = g.ctx;
        var t0 = performance.now();
        var ticks1 = 0, ticks2 = 0;
        return loop(function (t) {
            var dt = (t - t0) / 1000;
            var w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var midY = h * 0.55, gap = h * 0.28;
            var speed = w * 0.08; // 运动钟横向速度

            // 静止钟
            var x1 = w * 0.22;
            ctx.strokeStyle = "#4f46e5"; ctx.lineWidth = 2;
            [x1].forEach(function (x) {
                ctx.beginPath(); ctx.moveTo(x - 30, midY - gap); ctx.lineTo(x + 30, midY - gap); ctx.stroke();
                ctx.beginPath(); ctx.moveTo(x - 30, midY + gap); ctx.lineTo(x + 30, midY + gap); ctx.stroke();
            });
            var ph1 = (dt * 0.9) % 2;
            var y1 = ph1 < 1 ? midY - gap + ph1 * 2 * gap : midY + gap - (ph1 - 1) * 2 * gap;
            ctx.fillStyle = "#f59e0b";
            ctx.beginPath(); ctx.arc(x1, y1, 6, 0, 7); ctx.fill();
            ticks1 = Math.floor(dt * 0.9 / 2);
            ctx.fillStyle = "#374151"; ctx.font = "13px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("静止的钟", x1, midY + gap + 22);
            ctx.fillText("滴答 " + ticks1, x1, midY + gap + 40);

            // 运动钟
            var x2 = w * 0.6 + ((dt * speed) % (w * 0.2));
            ctx.strokeStyle = "#4f46e5";
            ctx.beginPath(); ctx.moveTo(x2 - 30, midY - gap); ctx.lineTo(x2 + 30, midY - gap); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(x2 - 30, midY + gap); ctx.lineTo(x2 + 30, midY + gap); ctx.stroke();
            // 光子走斜线：周期被拉长（洛伦兹因子演示，取 γ=1.5）
            var gamma = 1.5;
            var ph2 = (dt * 0.9 / gamma) % 2;
            var offY2 = ph2 < 1 ? ph2 * 2 * gap : 2 * gap - (ph2 - 1) * 2 * gap;
            ctx.fillStyle = "#f59e0b";
            ctx.beginPath(); ctx.arc(x2, midY - gap + offY2, 6, 0, 7); ctx.fill();
            // 斜线轨迹提示
            ctx.strokeStyle = "rgba(245,158,11,0.35)"; ctx.setLineDash([4, 4]);
            ctx.beginPath(); ctx.moveTo(x2 - speed * 0.9 * gamma * 2, midY - gap); ctx.lineTo(x2, midY - gap + offY2); ctx.stroke();
            ctx.setLineDash([]);
            ticks2 = Math.floor(dt * 0.9 / gamma / 2);
            ctx.fillStyle = "#374151";
            ctx.fillText("运动的钟 →", w * 0.7, midY + gap + 22);
            ctx.fillText("滴答 " + ticks2, w * 0.7, midY + gap + 40);

            ctx.fillStyle = "#6b7280"; ctx.font = "12px sans-serif";
            ctx.fillText("光速不变：运动的钟里光子要走更长的斜线，所以时间变慢（图中 γ=1.5）", w / 2, 20);
        });
    };

    /* 大爆炸：星系退行，越远越快（哈勃定律） */
    registry["bigbang"] = function (canvas) {
        var g = ctx2d(canvas), ctx = g.ctx;
        var t0 = performance.now();
        var pts = [];
        for (var i = 0; i < 60; i++) {
            pts.push({ a: Math.random() * Math.PI * 2, r0: 0.05 + Math.random() * 0.45 });
        }
        return loop(function (t) {
            var dt = (t - t0) / 1000;
            var w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var cx = w / 2, cy = h / 2;
            var scale = Math.min(w, h) * 0.9;
            var R = 0.05 + (dt * 0.04) % 0.9; // 宇宙尺度缓慢增大后循环
            pts.forEach(function (p) {
                var r = p.r0 * R * scale / 0.45;
                var x = cx + Math.cos(p.a) * r, y = cy + Math.sin(p.a) * r;
                ctx.fillStyle = "#4f46e5";
                ctx.beginPath(); ctx.arc(x, y, 3, 0, 7); ctx.fill();
                // 速度矢量：径向向外，越远越长
                ctx.strokeStyle = "rgba(239,68,68,0.6)"; ctx.lineWidth = 1.5;
                ctx.beginPath(); ctx.moveTo(x, y);
                ctx.lineTo(x + Math.cos(p.a) * r * 0.25, y + Math.sin(p.a) * r * 0.25);
                ctx.stroke();
            });
            ctx.fillStyle = "#374151"; ctx.font = "13px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("哈勃定律：离我们越远的星系，退行速度越快（红箭头）", w / 2, 20);
            ctx.fillStyle = "#6b7280"; ctx.font = "12px sans-serif";
            ctx.fillText("不是星系在空间中飞奔，而是空间本身在膨胀", w / 2, h - 12);
        });
    };

    /* 暗能量：膨胀先减速后加速 */
    registry["darkenergy"] = function (canvas) {
        var g = ctx2d(canvas), ctx = g.ctx;
        var t0 = performance.now();
        return loop(function (t) {
            var dt = ((t - t0) / 1000) % 14;
            var w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            // 时间轴
            var pad = 40;
            ctx.strokeStyle = "#9ca3af"; ctx.lineWidth = 1;
            ctx.beginPath(); ctx.moveTo(pad, h - pad); ctx.lineTo(w - pad, h - pad); ctx.stroke(); // t 轴
            ctx.beginPath(); ctx.moveTo(pad, h - pad); ctx.lineTo(pad, pad); ctx.stroke();         // R 轴
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("时间 →", w / 2, h - pad + 18);
            ctx.save(); ctx.translate(pad - 14, h / 2); ctx.rotate(-Math.PI / 2);
            ctx.fillText("宇宙尺度 →", 0, 0); ctx.restore();

            // 膨胀曲线：R(t) 先缓后急（暗能量驱动加速）
            function R(tt) { return Math.pow(tt / 14, 2.2); }
            ctx.strokeStyle = "#4f46e5"; ctx.lineWidth = 2.5;
            ctx.beginPath();
            for (var x = 0; x <= 14; x += 0.1) {
                var px = pad + (x / 14) * (w - 2 * pad);
                var py = h - pad - R(x) * (h - 2 * pad);
                x === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
            }
            ctx.stroke();
            // 当前点
            var cpx = pad + (dt / 14) * (w - 2 * pad);
            var cpy = h - pad - R(dt) * (h - 2 * pad);
            ctx.fillStyle = "#ef4444";
            ctx.beginPath(); ctx.arc(cpx, cpy, 6, 0, 7); ctx.fill();

            ctx.fillStyle = "#6b7280"; ctx.textAlign = "center";
            ctx.fillText("前半段：引力让膨胀减速", w * 0.3, pad + 10);
            ctx.fillText("后半段：暗能量让膨胀加速", w * 0.72, pad + 10);
        });
    };

    /* 熵增：粒子从半边逐渐混合均匀 */
    registry["entropy"] = function (canvas) {
        var g = ctx2d(canvas), ctx = g.ctx;
        var balls = [];
        var N = 80;
        function reset() {
            balls = [];
            for (var i = 0; i < N; i++) {
                balls.push({
                    x: 8 + Math.random() * (g.w / 2 - 16),
                    y: 8 + Math.random() * (g.h - 16),
                    vx: (Math.random() - 0.5) * 120,
                    vy: (Math.random() - 0.5) * 120,
                });
            }
        }
        reset();
        canvas.addEventListener("click", reset);
        var lastT = null;
        return loop(function (t) {
            if (lastT === null) lastT = t;
            var dt = Math.min((t - lastT) / 1000, 0.05);
            lastT = t;
            var w = g.w, h = g.h;
            // 统计左右数量
            var left = 0;
            balls.forEach(function (b) {
                b.x += b.vx * dt; b.y += b.vy * dt;
                if (b.x < 6) { b.x = 6; b.vx = Math.abs(b.vx); }
                if (b.x > w - 6) { b.x = w - 6; b.vx = -Math.abs(b.vx); }
                if (b.y < 6) { b.y = 6; b.vy = Math.abs(b.vy); }
                if (b.y > h - 6) { b.y = h - 6; b.vy = -Math.abs(b.vy); }
                if (b.x < w / 2) left++;
            });
            ctx.clearRect(0, 0, w, h);
            // 中线
            ctx.strokeStyle = "#d1d5db"; ctx.setLineDash([5, 5]);
            ctx.beginPath(); ctx.moveTo(w / 2, 0); ctx.lineTo(w / 2, h); ctx.stroke();
            ctx.setLineDash([]);
            ctx.fillStyle = "#4f46e5";
            balls.forEach(function (b) { ctx.beginPath(); ctx.arc(b.x, b.y, 4, 0, 7); ctx.fill(); });
            ctx.fillStyle = "#374151"; ctx.font = "13px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("左 " + left + " : " + (N - left) + " 右", w / 2, 18);
            ctx.fillStyle = "#6b7280"; ctx.font = "12px sans-serif";
            ctx.fillText("有序 → 无序是大概率方向，这就是熵增（点画面重来）", w / 2, h - 10);
        });
    };

    /* 量子叠加：测量前概率弥散，点击测量塌缩 */
    registry["superposition"] = function (canvas) {
        var g = ctx2d(canvas), ctx = g.ctx;
        var collapsedAt = null, collapsedX = 0;
        var t0 = performance.now();
        canvas.addEventListener("click", function () {
            if (collapsedAt === null) {
                collapsedAt = performance.now();
                collapsedX = g.w * (0.3 + Math.random() * 0.4);
            } else {
                collapsedAt = null;
                t0 = performance.now();
            }
        });
        return loop(function (t) {
            var dt = (t - t0) / 1000;
            var w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            ctx.fillStyle = "#374151"; ctx.font = "13px sans-serif"; ctx.textAlign = "center";
            if (collapsedAt === null) {
                // 波函数：两个峰之间振荡弥散
                ctx.fillText("叠加态：粒子同时「既在左又在右」（点击测量）", w / 2, 18);
                var base = h * 0.75;
                ctx.strokeStyle = "#4f46e5"; ctx.lineWidth = 2;
                ctx.beginPath();
                for (var x = 0; x <= w; x += 3) {
                    var u = x / w;
                    var y1 = Math.exp(-Math.pow((u - 0.3) / 0.09, 2));
                    var y2 = Math.exp(-Math.pow((u - 0.7) / 0.09, 2));
                    var phase = Math.cos(dt * 3) * 0.25;
                    var amp = (y1 * (0.8 + phase) + y2 * (1.2 - phase)) * h * 0.42;
                    x === 0 ? ctx.moveTo(x, base) : ctx.lineTo(x, base - amp);
                }
                ctx.stroke();
                ctx.fillStyle = "#6b7280"; ctx.font = "12px sans-serif";
                ctx.fillText("|左⟩ + |右⟩ 两种状态同时存在", w / 2, h - 12);
            } else {
                var since = (t - collapsedAt) / 1000;
                var shrink = Math.max(0.02, 0.12 - since * 0.12);
                ctx.fillText("测量后：波函数塌缩到一个确定位置（再点一次重置）", w / 2, 18);
                var base2 = h * 0.75;
                ctx.strokeStyle = "#ef4444"; ctx.lineWidth = 2;
                ctx.beginPath();
                for (var x2 = 0; x2 <= w; x2 += 2) {
                    var u2 = (x2 - collapsedX) / w;
                    var amp2 = Math.exp(-Math.pow(u2 / shrink, 2)) * h * 0.5;
                    x2 === 0 ? ctx.moveTo(x2, base2) : ctx.lineTo(x2, base2 - amp2);
                }
                ctx.stroke();
                ctx.fillStyle = "#6b7280"; ctx.font = "12px sans-serif";
                ctx.fillText("只剩一个确定结果——叠加消失了", w / 2, h - 12);
            }
        });
    };

    return { start: start, stop: stop };
})();
