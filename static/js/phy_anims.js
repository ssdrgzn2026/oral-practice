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
        var w = canvas.clientWidth || 300, h = canvas.clientHeight || 200;
        canvas.width = w * dpr;
        canvas.height = h * dpr;
        var ctx = canvas.getContext("2d");
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        return { ctx: ctx, w: w, h: h };
    }

    /* 时间膨胀：静止光钟 vs 运动光钟（光子斜线路径更长，滴答更慢） */
    registry["time-dilation"] = function (canvas) {
        var g, ctx;
        var t0 = performance.now();
        var ticks1 = 0, ticks2 = 0;
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
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
        var g, ctx;
        var t0 = performance.now();
        var pts = [];
        for (var i = 0; i < 60; i++) {
            pts.push({ a: Math.random() * Math.PI * 2, r0: 0.05 + Math.random() * 0.45 });
        }
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
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
        var g, ctx;
        var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
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
        var g, ctx;
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
            g = ctx2d(canvas); ctx = g.ctx;
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
        var g, ctx;
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
            g = ctx2d(canvas); ctx = g.ctx;
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


    /* 能带理论：导体 / 半导体 / 绝缘体的能带对比 */
    registry["band"] = function (canvas) {
        var g, ctx;
        var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000;
            var w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            ctx.textAlign = "center";

            var panels = [
                { name: "导体", gapRatio: -0.12, elec: 8, note: "能带重叠，自由移动", espeed: 50 },
                { name: "半导体", gapRatio: 0.30, elec: 2, note: "带隙小，少量跃迁", espeed: 15 },
                { name: "绝缘体", gapRatio: 0.60, elec: 0, note: "带隙大，几乎不导电", espeed: 0 },
            ];
            var pw = w / 3;
            var barH = Math.max(14, h * 0.09);
            panels.forEach(function (pnl, i) {
                var cx = i * pw + pw / 2;
                var bw = pw * 0.56;
                var x0 = cx - bw / 2;
                var topY = h * 0.16;                 // 导带顶
                var botY = h * 0.66;                 // 价带底
                var gapPx = pnl.gapRatio * (botY - topY);
                var cbY = topY;                      // 导带上沿
                var cbB = topY + barH;               // 导带下沿
                var vbT = cbB + gapPx;               // 价带上沿
                var vbB = vbT + barH;                // 价带下沿
                if (pnl.gapRatio < 0) { vbT = cbB + gapPx; vbB = vbT + barH; }  // 负gap=重叠

                // 导带
                ctx.fillStyle = "rgba(99,102,241,0.20)";
                ctx.fillRect(x0, cbY, bw, barH);
                // 价带
                ctx.fillStyle = "rgba(79,70,229,0.45)";
                ctx.fillRect(x0, vbT, bw, barH);
                // 左侧文字标签
                ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "right";
                ctx.fillText("导带", x0 - 6, cbY + barH / 2 + 4);
                ctx.fillText("价带", x0 - 6, vbT + barH / 2 + 4);

                // Eg 标注（价导带之间居中）
                if (pnl.gapRatio > 0.02) {
                    var midY = (cbB + vbT) / 2;
                    ctx.strokeStyle = "#f59e0b"; ctx.lineWidth = 1.5;
                    ctx.beginPath(); ctx.moveTo(cx + bw / 4, cbB); ctx.lineTo(cx + bw / 4, vbT); ctx.stroke();
                    ctx.fillStyle = "#b45309"; ctx.textAlign = "left"; ctx.font = "11px sans-serif";
                    ctx.fillText("Eg", cx + bw / 4 + 4, midY + 4);
                }

                // 导带电子（红点跑动）
                ctx.fillStyle = "#ef4444";
                for (var e = 0; e < pnl.elec; e++) {
                    var ex = x0 + 5 + ((e * 31 + dt * pnl.espeed) % (bw - 10));
                    var ey = cbY + barH / 2 + Math.sin(dt * 3 + e) * 3;
                    ctx.beginPath(); ctx.arc(ex, ey, 3.5, 0, 7); ctx.fill();
                }
                // 价带电子（白点密集微振）
                ctx.fillStyle = "rgba(255,255,255,0.95)";
                for (var v = 0; v < 7; v++) {
                    var vx = x0 + 8 + (v / 7) * (bw - 16);
                    var vy = vbT + barH / 2 + Math.sin(dt * 2 + v * 1.7) * 2.5;
                    ctx.beginPath(); ctx.arc(vx, vy, 2.5, 0, 7); ctx.fill();
                }

                ctx.fillStyle = "#111827"; ctx.font = "bold 14px sans-serif"; ctx.textAlign = "center";
                ctx.fillText(pnl.name, cx, h - 30);
                ctx.fillStyle = "#6b7280"; ctx.font = "11px sans-serif";
                ctx.fillText(pnl.note, cx, h - 14);
            });
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("红点 = 导带中可自由移动的电子；Eg = 禁带宽度", w / 2, 14);
        });
    };


    /* 晶体点阵：规则排列的原子振动，电子穿行 */
    registry["lattice"] = function (canvas) {
        var g, ctx;
        var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000;
            var w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var nx = 8, ny = 4;
            var gx = w / (nx + 1), gy = h / (ny + 2);
            for (var i = 1; i <= nx; i++) {
                for (var j = 1; j <= ny; j++) {
                    var bx = i * gx, by = j * gy;
                    var ox = Math.sin(dt * 6 + i * 0.8 + j) * 3;
                    var oy = Math.cos(dt * 5 + j * 0.7 + i) * 3;
                    ctx.fillStyle = "#6366f1";
                    ctx.beginPath(); ctx.arc(bx + ox, by + oy, 7, 0, 7); ctx.fill();
                }
            }
            var ex = (dt * 60) % (w + 20) - 10;
            var ey = h * 0.5 + Math.sin(dt * 2) * gy;
            ctx.fillStyle = "#ef4444";
            ctx.beginPath(); ctx.arc(ex, ey, 5, 0, 7); ctx.fill();
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("晶体：原子规则排列并微振，红点 = 自由电子穿行其中", w / 2, h - 12);
        });
    };

    /* 晶体管：小信号输入放大为大信号 */
    registry["transistor"] = function (canvas) {
        var g, ctx;
        var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000;
            var w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            ctx.strokeStyle = "#6b7280"; ctx.lineWidth = 2;
            ctx.beginPath();
            for (var x = 0; x < w * 0.42; x++) {
                var y = h * 0.35 + Math.sin(x * 0.08 + dt * 4) * h * 0.06;
                x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
            }
            ctx.stroke();
            ctx.fillStyle = "#6b7280"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("输入：微弱信号", w * 0.2, h * 0.18);
            var tx = w * 0.5, ty = h * 0.4, ts = h * 0.16;
            ctx.strokeStyle = "#4f46e5"; ctx.lineWidth = 2.5;
            ctx.beginPath(); ctx.moveTo(tx - ts, ty - ts); ctx.lineTo(tx - ts, ty + ts); ctx.lineTo(tx + ts, ty); ctx.closePath(); ctx.stroke();
            ctx.fillText("晶体管", tx, ty + ts + 18);
            ctx.strokeStyle = "#4f46e5";
            ctx.beginPath();
            for (var x2 = w * 0.6; x2 < w; x2++) {
                var y2 = h * 0.35 + Math.sin((x2 - w * 0.6) * 0.08 + dt * 4) * h * 0.2;
                x2 === w * 0.6 ? ctx.moveTo(x2, y2) : ctx.lineTo(x2, y2);
            }
            ctx.stroke();
            ctx.fillStyle = "#4f46e5";
            ctx.fillText("输出：被放大", w * 0.8, h * 0.12);
            ctx.fillStyle = "#6b7280"; ctx.font = "12px sans-serif";
            ctx.fillText("小电流控制大电流——放大与开关是所有芯片的基础", w / 2, h - 12);
        });
    };

    /* 超导：电阻-温度曲线，Tc 处骤降为零 */
    registry["supercond"] = function (canvas) {
        var g, ctx;
        var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = ((t - t0) / 1000) % 8;
            var w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var pad = 46, tcX = w * 0.45;
            ctx.strokeStyle = "#9ca3af"; ctx.lineWidth = 1;
            ctx.beginPath(); ctx.moveTo(pad, h - pad); ctx.lineTo(w - pad, h - pad); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(pad, h - pad); ctx.lineTo(pad, pad); ctx.stroke();
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("温度 T →", w / 2, h - pad + 18);
            ctx.fillText("Tc", tcX, h - pad + 18);
            ctx.save(); ctx.translate(pad - 16, h / 2); ctx.rotate(-Math.PI / 2);
            ctx.fillText("电阻 R →", 0, 0); ctx.restore();
            ctx.strokeStyle = "#4f46e5"; ctx.lineWidth = 2.5;
            ctx.beginPath();
            var prog = Math.min(1, dt / 5);
            for (var x = pad; x <= pad + (w - 2 * pad) * prog; x += 3) {
                var y;
                if (x < tcX) y = h - pad - (1 - (x - pad) / (tcX - pad)) * (h * 0.55);
                else y = h - pad - 1;
                x === pad ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
            }
            ctx.stroke();
            ctx.strokeStyle = "#f59e0b"; ctx.setLineDash([4, 4]);
            ctx.beginPath(); ctx.moveTo(tcX, pad); ctx.lineTo(tcX, h - pad); ctx.stroke();
            ctx.setLineDash([]);
            ctx.fillStyle = "#b45309"; ctx.textAlign = "left";
            ctx.fillText("临界温度以下：电阻突然降为零", tcX + 8, pad + 16);
        });
    };

    /* BCS：两个电子通过晶格振动结成库珀对 */
    registry["cooper"] = function (canvas) {
        var g, ctx;
        var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000;
            var w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var nx = 10, ny = 3, gx = w / (nx + 1), gy = h / (ny + 1.5);
            var i, j;
            for (i = 1; i <= nx; i++) for (j = 1; j <= ny; j++) {
                ctx.fillStyle = "#c7d2fe";
                ctx.beginPath(); ctx.arc(i * gx, j * gy, 5, 0, 7); ctx.fill();
            }
            var cyc = (dt % 6) / 6;
            var d = cyc < 0.5 ? cyc * 2 : 1;
            var e1x = w * 0.15 + (w * 0.35 - w * 0.15) * d;
            var e2x = w * 0.85 - (w * 0.85 - w * 0.65) * d;
            var ey = h * 0.5;
            for (i = 1; i <= nx; i++) {
                var bx = i * gx;
                var dip = Math.max(0, 1 - Math.abs(bx - (e1x + e2x) / 2) / (gx * 1.5)) * 12 * d;
                ctx.fillStyle = "#818cf8";
                ctx.beginPath(); ctx.arc(bx, ey + 8 + dip, 6, 0, 7); ctx.fill();
            }
            ctx.fillStyle = "#ef4444";
            ctx.beginPath(); ctx.arc(e1x, ey - 10, 7, 0, 7); ctx.fill();
            ctx.beginPath(); ctx.arc(e2x, ey - 10, 7, 0, 7); ctx.fill();
            if (d >= 1) {
                ctx.strokeStyle = "#f59e0b"; ctx.lineWidth = 2;
                ctx.beginPath(); ctx.arc((e1x + e2x) / 2, ey - 10, 26 + Math.sin(dt * 5) * 4, 0, 7); ctx.stroke();
            }
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("一个电子使晶格轻微下陷，吸引另一个电子——结成库珀对", w / 2, h - 12);
        });
    };

    /* 磁性材料：磁畴从无序到外加磁场取向一致 */
    registry["domains"] = function (canvas) {
        var g, ctx;
        var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000;
            var w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var align = (Math.sin(dt * 0.7) + 1) / 2;
            var nx = 8, ny = 4;
            for (var i = 0; i < nx; i++) for (var j = 0; j < ny; j++) {
                var cx = (i + 0.5) * w / nx, cy = (j + 0.6) * h / (ny + 0.8);
                var rand = Math.sin(i * 12.9 + j * 78.2) * Math.PI;
                var ang = rand * (1 - align);
                var col = align > 0.6 ? "#4f46e5" : "#9ca3af";
                ctx.strokeStyle = col; ctx.fillStyle = col;
                ctx.lineWidth = 2;
                var L = Math.min(w / nx, h / ny) * 0.32;
                ctx.beginPath();
                ctx.moveTo(cx - Math.cos(ang) * L, cy - Math.sin(ang) * L);
                ctx.lineTo(cx + Math.cos(ang) * L, cy + Math.sin(ang) * L);
                ctx.stroke();
                ctx.beginPath(); ctx.arc(cx + Math.cos(ang) * L, cy + Math.sin(ang) * L, 3, 0, 7); ctx.fill();
            }
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText(align > 0.6 ? "外加磁场：磁畴取向一致 → 表现磁性" : "无外加磁场：磁畴杂乱 → 对外不显磁性", w / 2, h - 12);
        });
    };

    /* 石墨烯：蜂窝晶格 */
    registry["graphene"] = function (canvas) {
        var g, ctx;
        var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000;
            var w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var r = Math.min(w, h) / 12;
            var dx = r * 1.5, dy = r * Math.sqrt(3) / 2;
            for (var row = 0; row * dy * 2 < h + r * 2; row++) {
                for (var col = 0; col * dx < w + r * 2; col++) {
                    var x = col * dx, y = row * dy * 2 + (col % 2 ? dy : 0);
                    var ox = Math.sin(dt * 3 + row + col) * 1.5;
                    var oy = Math.cos(dt * 2.5 + col) * 1.5;
                    ctx.fillStyle = "#4f46e5";
                    ctx.beginPath(); ctx.arc(x + ox, y + oy, r * 0.28, 0, 7); ctx.fill();
                }
            }
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("石墨烯：碳原子排成单原子层的蜂窝晶格", w / 2, h - 12);
        });
    };

    /* 量子霍尔：霍尔电阻平台阶梯 */
    registry["qhall"] = function (canvas) {
        var g, ctx;
        var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = ((t - t0) / 1000) % 10;
            var w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var pad = 46;
            ctx.strokeStyle = "#9ca3af"; ctx.lineWidth = 1;
            ctx.beginPath(); ctx.moveTo(pad, h - pad); ctx.lineTo(w - pad, h - pad); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(pad, h - pad); ctx.lineTo(pad, pad); ctx.stroke();
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("磁场 B →", w / 2, h - pad + 18);
            ctx.save(); ctx.translate(pad - 16, h / 2); ctx.rotate(-Math.PI / 2);
            ctx.fillText("霍尔电阻 →", 0, 0); ctx.restore();
            ctx.strokeStyle = "#4f46e5"; ctx.lineWidth = 2.5;
            ctx.beginPath();
            var steps = 4, sw = (w - 2 * pad) / steps, prog = Math.min(1, dt / 6);
            for (var i2 = 0; i2 < steps * prog; i2++) {
                var x0 = pad + i2 * sw, x1 = Math.min(x0 + sw, pad + (w - 2 * pad) * prog);
                var y = h - pad - (h - 2 * pad) * (i2 + 1) / steps;
                if (i2 === 0) ctx.moveTo(x0, h - pad);
                ctx.lineTo(x0, y); ctx.lineTo(x1, y);
            }
            ctx.stroke();
            ctx.fillStyle = "#6b7280";
            ctx.fillText("霍尔电阻不是连续变化，而是一级级精确的平台（量子化）", w / 2, pad - 8);
        });
    };

    /* 软物质/液晶：分子取向排列 */
    registry["lcd"] = function (canvas) {
        var g, ctx;
        var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000;
            var w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var align = (Math.sin(dt * 0.8) + 1) / 2;
            var nx = 9, ny = 5;
            for (var i = 0; i < nx; i++) for (var j = 0; j < ny; j++) {
                var cx = (i + 0.5) * w / nx, cy = (j + 0.5) * h / ny;
                var rand = Math.sin(i * 91.7 + j * 37.3) * 0.9;
                var ang = rand * (1 - align) + (-Math.PI / 2) * align;
                var L = Math.min(w / nx, h / ny) * 0.35;
                ctx.strokeStyle = align > 0.6 ? "#4f46e5" : "#94a3b8";
                ctx.lineWidth = 4; ctx.lineCap = "round";
                ctx.beginPath();
                ctx.moveTo(cx - Math.cos(ang) * L, cy - Math.sin(ang) * L);
                ctx.lineTo(cx + Math.cos(ang) * L, cy + Math.sin(ang) * L);
                ctx.stroke();
            }
            ctx.lineCap = "butt";
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText(align > 0.6 ? "加电：液晶分子排列整齐 → 透光改变" : "不加电：液晶分子取向杂乱", w / 2, h - 10);
        });
    };


    /* 惯性：冰球无外力匀速滑行 */
    registry["inertia"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var x = (dt * 70) % (w + 60) - 30, y = h * 0.55;
            ctx.strokeStyle = "#cbd5e1"; ctx.lineWidth = 4;
            ctx.beginPath(); ctx.moveTo(0, y + 16); ctx.lineTo(w, y + 16); ctx.stroke();
            ctx.fillStyle = "#4f46e5";
            ctx.beginPath(); ctx.arc(x, y, 14, 0, 7); ctx.fill();
            ctx.strokeStyle = "#ef4444"; ctx.lineWidth = 2;
            ctx.beginPath(); ctx.moveTo(x + 18, y); ctx.lineTo(x + 44, y); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(x + 44, y); ctx.lineTo(x + 36, y - 5); ctx.moveTo(x + 44, y); ctx.lineTo(x + 36, y + 5); ctx.stroke();
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("冰面光滑（无外力）：冰球永远匀速直线滑行", w / 2, 22);
            ctx.fillStyle = "#ef4444"; ctx.fillText("v 恒定", x + 40, y - 16);
        });
    };

    /* 作用力与反作用力：两车互推 */
    registry["reactio"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var cyc = (dt % 4) / 4;
            var sep = cyc < 0.25 ? 0 : (cyc < 0.8 ? (cyc - 0.25) / 0.55 : 1);
            var cx = w / 2, y = h * 0.5, d = sep * w * 0.22;
            ctx.fillStyle = "#4f46e5";
            ctx.fillRect(cx - d - 54, y - 16, 54, 26);
            ctx.fillStyle = "#f59e0b";
            ctx.fillRect(cx + d, y - 16, 54, 26);
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("甲", cx - d - 27, y + 4);
            ctx.fillText("乙", cx + d + 27, y + 4);
            if (sep > 0.05) {
                ctx.strokeStyle = "#ef4444"; ctx.lineWidth = 2;
                ctx.beginPath(); ctx.moveTo(cx - 8, y - 28); ctx.lineTo(cx - 40, y - 28); ctx.stroke();
                ctx.beginPath(); ctx.moveTo(cx - 40, y - 28); ctx.lineTo(cx - 32, y - 33); ctx.moveTo(cx - 40, y - 28); ctx.lineTo(cx - 32, y - 23); ctx.stroke();
                ctx.beginPath(); ctx.moveTo(cx + 8, y - 28); ctx.lineTo(cx + 40, y - 28); ctx.stroke();
                ctx.beginPath(); ctx.moveTo(cx + 40, y - 28); ctx.lineTo(cx + 32, y - 33); ctx.moveTo(cx + 40, y - 28); ctx.lineTo(cx + 32, y - 23); ctx.stroke();
                ctx.fillText("F", cx + 34, y - 34); ctx.fillText("F", cx - 34, y - 34);
            }
            ctx.fillStyle = "#374151";
            ctx.fillText("甲推乙的力 = 乙推甲的力，大小相等方向相反", w / 2, h - 14);
        });
    };

    /* 单摆能量：动能势能此消彼长 */
    registry["pendulum"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var px = w * 0.35, py = h * 0.12, L = h * 0.55;
            var ang = Math.sin(dt * 1.6) * 0.7;
            var bx = px + Math.sin(ang) * L, by = py + Math.cos(ang) * L;
            ctx.strokeStyle = "#9ca3af"; ctx.lineWidth = 2;
            ctx.beginPath(); ctx.moveTo(px, py); ctx.lineTo(bx, by); ctx.stroke();
            ctx.fillStyle = "#4f46e5";
            ctx.beginPath(); ctx.arc(bx, by, 13, 0, 7); ctx.fill();
            ctx.beginPath(); ctx.arc(px, py, 4, 0, 7); ctx.fill();
            // 能量条
            var ke = Math.pow(Math.cos(dt * 1.6), 2), pe = 1 - ke;
            var bx0 = w * 0.68, bw = w * 0.11, bh = h * 0.5, by0 = h * 0.25;
            ctx.fillStyle = "#ef4444";
            ctx.fillRect(bx0, by0 + bh * (1 - ke), bw, bh * ke);
            ctx.strokeStyle = "#374151"; ctx.lineWidth = 1;
            ctx.strokeRect(bx0, by0, bw, bh);
            ctx.fillStyle = "#3b82f6";
            ctx.fillRect(bx0 + bw + 12, by0 + bh * (1 - pe), bw, bh * pe);
            ctx.strokeRect(bx0 + bw + 12, by0, bw, bh);
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("动能", bx0 + bw / 2, by0 + bh + 16);
            ctx.fillText("势能", bx0 + bw + 12 + bw / 2, by0 + bh + 16);
            ctx.fillText("最低点动能最大，最高点势能最大，总量不变", w / 2, h - 10);
        });
    };

    /* 角动量：收臂加速 */
    registry["skater"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var cycle = (dt % 4) / 4;
            var armIn = cycle > 0.4 && cycle < 0.9;
            var spin = armIn ? 3.2 : 1.0;
            var cx = w / 2, cy = h / 2;
            var armL = armIn ? h * 0.1 : h * 0.26;
            var a = dt * spin * Math.PI;
            ctx.fillStyle = "#4f46e5";
            ctx.beginPath(); ctx.arc(cx, cy, h * 0.07, 0, 7); ctx.fill();
            ctx.strokeStyle = "#f59e0b"; ctx.lineWidth = 4; ctx.lineCap = "round";
            ctx.beginPath();
            ctx.moveTo(cx - Math.cos(a) * armL, cy - Math.sin(a) * armL * 0.3);
            ctx.lineTo(cx + Math.cos(a) * armL, cy + Math.sin(a) * armL * 0.3);
            ctx.stroke(); ctx.lineCap = "butt";
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText(armIn ? "收臂：转得更快！" : "伸臂：转得慢", cx, h - 14);
            ctx.fillStyle = "#6b7280";
            ctx.fillText("角动量守恒：转动惯量变小，转速必然变大", cx, 20);
        });
    };

    /* 潮汐：月球引力造成两侧涨潮 */
    registry["tide"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var cx = w * 0.42, cy = h / 2, R = Math.min(w, h) * 0.2;
            // 地球
            ctx.fillStyle = "#3b82f6";
            ctx.beginPath(); ctx.arc(cx, cy, R, 0, 7); ctx.fill();
            // 两侧水鼓包
            ctx.fillStyle = "rgba(147,197,253,0.85)";
            ctx.beginPath(); ctx.ellipse(cx, cy, R * 1.55, R * 1.08, 0, 0, 7); ctx.fill();
            ctx.fillStyle = "#3b82f6";
            ctx.beginPath(); ctx.arc(cx, cy, R, 0, 7); ctx.fill();
            // 月球绕转
            var ma = dt * 0.5;
            var mx = cx + Math.cos(ma) * w * 0.32, my = cy + Math.sin(ma) * h * 0.36;
            ctx.fillStyle = "#9ca3af";
            ctx.beginPath(); ctx.arc(mx, my, R * 0.27, 0, 7); ctx.fill();
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("月", mx, my + 4);
            ctx.fillText("正对月球和背对月球两侧都涨潮", w / 2, h - 12);
        });
    };

    /* 伯努利：管道收窄处流速快、压强小 */
    registry["venturi"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var top = h * 0.28, bot = h * 0.72, narrowX0 = w * 0.4, narrowX1 = w * 0.6;
            var nTop = h * 0.4, nBot = h * 0.6;
            ctx.strokeStyle = "#6b7280"; ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(10, top); ctx.lineTo(narrowX0, top); ctx.lineTo(narrowX0 + 15, nTop); ctx.lineTo(narrowX1 - 15, nTop); ctx.lineTo(narrowX1, top); ctx.lineTo(w - 10, top);
            ctx.moveTo(10, bot); ctx.lineTo(narrowX0, bot); ctx.lineTo(narrowX0 + 15, nBot); ctx.lineTo(narrowX1 - 15, nBot); ctx.lineTo(narrowX1, bot); ctx.lineTo(w - 10, bot);
            ctx.stroke();
            // 流线粒子：宽处慢、窄处快
            ctx.fillStyle = "#4f46e5";
            for (var i = 0; i < 16; i++) {
                var px = (i / 16 + dt * 0.12) % 1 * w;
                var inNarrow = px > narrowX0 && px < narrowX1;
                var speed = inNarrow ? 2.2 : 1;
                var yy = inNarrow ? (nTop + nBot) / 2 + Math.sin(i * 2.1) * (nBot - nTop) * 0.28
                                  : (top + bot) / 2 + Math.sin(i * 2.1) * (bot - top) * 0.32;
                ctx.beginPath(); ctx.arc(px, yy, 3.5, 0, 7); ctx.fill();
            }
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("窄处流得快、压强反而小（伯努利原理）", w / 2, h - 12);
            ctx.fillText("宽", w * 0.2, top - 10); ctx.fillText("窄", w * 0.5, nTop - 10); ctx.fillText("宽", w * 0.8, top - 10);
        });
    };

    /* 湍流：层流逐渐失稳成涡 */
    registry["turbulence"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        var pts = [];
        for (var i = 0; i < 90; i++) pts.push({ x: Math.random(), y: Math.random(), s: 0.4 + Math.random() });
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = t / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            pts.forEach(function (p) {
                p.x += 0.0012 * p.s;
                var chaos = Math.max(0, p.x - 0.35) * 2;
                p.y += Math.sin(p.x * 30 + dt * 4 + p.s * 20) * 0.004 * chaos;
                if (p.x > 1) { p.x = 0; p.y = Math.random(); }
                ctx.fillStyle = chaos > 0.3 ? "#ef4444" : "#4f46e5";
                ctx.beginPath(); ctx.arc(p.x * w, p.y * h, 3, 0, 7); ctx.fill();
            });
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("左侧平稳层流 → 右侧失稳成湍流（红点）", w / 2, 18);
            ctx.fillStyle = "#6b7280";
            ctx.fillText("湍流至今没有完整的解析理论——物理著名难题", w / 2, h - 12);
        });
    };

    /* 安培定律：直电流的环形磁场 */
    registry["ampere"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var cx = w / 2, cy = h / 2;
            // 导线（点=电流向外）
            ctx.fillStyle = "#f59e0b";
            ctx.beginPath(); ctx.arc(cx, cy, 10, 0, 7); ctx.fill();
            ctx.fillStyle = "#fff"; ctx.font = "bold 14px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("·", cx, cy + 5);
            // 同心圆磁场
            for (var r = 30; r < Math.min(w, h) * 0.45; r += 26) {
                ctx.strokeStyle = "rgba(79,70,229,0.7)"; ctx.lineWidth = 1.5;
                ctx.beginPath(); ctx.arc(cx, cy, r, 0, 7); ctx.stroke();
                var a = dt * (40 / r) + r;
                var ax = cx + Math.cos(a) * r, ay = cy + Math.sin(a) * r;
                ctx.fillStyle = "#4f46e5";
                ctx.beginPath(); ctx.arc(ax, ay, 3.5, 0, 7); ctx.fill();
            }
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif";
            ctx.fillText("电流（· 流出纸面）周围产生环形磁场，右手螺旋定则", w / 2, h - 12);
        });
    };

    /* 洛伦兹力：带电粒子在磁场中做圆周运动 */
    registry["lorentz"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            // 磁场叉号
            ctx.strokeStyle = "#cbd5e1"; ctx.lineWidth = 1.5;
            for (var x = 30; x < w; x += 44) for (var y = 30; y < h; y += 44) {
                ctx.beginPath(); ctx.moveTo(x - 5, y - 5); ctx.lineTo(x + 5, y + 5);
                ctx.moveTo(x + 5, y - 5); ctx.lineTo(x - 5, y + 5); ctx.stroke();
            }
            var cx = w / 2, cy = h / 2, R = Math.min(w, h) * 0.3;
            var a = dt * 1.4;
            var px = cx + Math.cos(a) * R, py = cy + Math.sin(a) * R;
            ctx.strokeStyle = "rgba(79,70,229,0.4)"; ctx.setLineDash([5, 5]);
            ctx.beginPath(); ctx.arc(cx, cy, R, 0, 7); ctx.stroke(); ctx.setLineDash([]);
            ctx.fillStyle = "#ef4444";
            ctx.beginPath(); ctx.arc(px, py, 8, 0, 7); ctx.fill();
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("B 指向纸内（×），正电荷做圆周运动", w / 2, 20);
            ctx.fillText("洛伦兹力始终垂直于速度，只改变方向不改变快慢", w / 2, h - 12);
        });
    };

    /* 电磁波：E 和 B 相互垂直向前传播 */
    registry["emwave2"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var cyE = h * 0.32, cyB = h * 0.68;
            ctx.strokeStyle = "#4f46e5"; ctx.lineWidth = 2.5;
            ctx.beginPath();
            for (var x = 0; x < w; x += 3) {
                var y = cyE + Math.sin(x * 0.045 - dt * 4) * h * 0.17;
                x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
            }
            ctx.stroke();
            ctx.strokeStyle = "#f59e0b";
            ctx.beginPath();
            for (var x2 = 0; x2 < w; x2 += 3) {
                var y2 = cyB + Math.sin(x2 * 0.045 - dt * 4) * h * 0.17;
                x2 === 0 ? ctx.moveTo(x2, y2) : ctx.lineTo(x2, y2);
            }
            ctx.stroke();
            ctx.fillStyle = "#4f46e5"; ctx.font = "12px sans-serif"; ctx.textAlign = "left";
            ctx.fillText("电场 E", 12, cyE - h * 0.2);
            ctx.fillStyle = "#f59e0b";
            ctx.fillText("磁场 B（与 E 垂直，俯视示意）", 12, cyB - h * 0.2);
            ctx.fillStyle = "#374151"; ctx.textAlign = "center";
            ctx.fillText("E 和 B 相互垂直、同相振荡，以光速向前传播 →", w / 2, h - 10);
        });
    };

    /* 卡诺循环：p-V 图上的四步循环 */
    registry["carnot"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var pad = 46;
            ctx.strokeStyle = "#9ca3af"; ctx.lineWidth = 1;
            ctx.beginPath(); ctx.moveTo(pad, h - pad); ctx.lineTo(w - pad, h - pad); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(pad, h - pad); ctx.lineTo(pad, pad); ctx.stroke();
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("体积 V →", w / 2, h - pad + 18);
            ctx.save(); ctx.translate(pad - 16, h / 2); ctx.rotate(-Math.PI / 2);
            ctx.fillText("压强 p →", 0, 0); ctx.restore();
            // 循环路径（近似等温+绝热围成的环）
            function P(V) { return 1 / V; }
            var cx0 = pad + 30, cy0 = h - pad - 20, cw = w - 2 * pad - 60, chh = h - 2 * pad - 40;
            var pts = [];
            var N = 40;
            for (var i = 0; i <= N; i++) {  // 上边：等温膨胀
                var V = 0.2 + 0.6 * i / N;
                pts.push([V, 1 / V + 0.25]);
            }
            for (var i2 = N; i2 >= 0; i2--) { // 下边：绝热压缩
                var V2 = 0.2 + 0.6 * i2 / N;
                pts.push([V2, Math.pow(0.2 / V2, 1.4) * 0.7]);
            }
            ctx.strokeStyle = "#4f46e5"; ctx.lineWidth = 2.5;
            ctx.beginPath();
            pts.forEach(function (p2, i3) {
                var X = cx0 + (p2[0] - 0.2) / 0.6 * cw;
                var Y = cy0 - (p2[1] - 0.7) / 1.5 * chh;
                i3 === 0 ? ctx.moveTo(X, Y) : ctx.lineTo(X, Y);
            });
            ctx.closePath(); ctx.stroke();
            // 运行点
            var k = Math.floor((dt * 10) % pts.length);
            var cur = pts[k];
            ctx.fillStyle = "#ef4444";
            ctx.beginPath(); ctx.arc(cx0 + (cur[0] - 0.2) / 0.6 * cw, cy0 - (cur[1] - 0.7) / 1.5 * chh, 6, 0, 7); ctx.fill();
            ctx.fillStyle = "#6b7280";
            ctx.fillText("卡诺循环：热机效率的理论上限由两个温度决定", w / 2, 20);
        });
    };

    /* 玻尔兹曼分布：速率分布逐渐形成 */
    registry["boltzmann"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        var speeds = [];
        for (var i = 0; i < 300; i++) speeds.push(Math.random());
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            // 每次循环给速度一点随机扰动 → 趋于麦克斯韦分布
            if (Math.floor(dt * 10) % 2 === 0) {
                for (var k = 0; k < 5; k++) {
                    var a = Math.floor(Math.random() * 300), b = Math.floor(Math.random() * 300);
                    var tot = speeds[a] + speeds[b];
                    speeds[a] = tot * Math.random(); speeds[b] = tot - speeds[a];
                }
            }
            var bins = new Array(20).fill(0);
            speeds.forEach(function (v) { bins[Math.min(19, Math.floor(v * 14))]++; });
            var maxB = Math.max.apply(null, bins);
            var bw = (w - 80) / 20;
            for (var i2 = 0; i2 < 20; i2++) {
                var bh = bins[i2] / maxB * (h - 90);
                ctx.fillStyle = "#6366f1";
                ctx.fillRect(50 + i2 * bw, h - 40 - bh, bw - 4, bh);
            }
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("分子速率 →", w / 2, h - 22);
            ctx.fillText("随机碰撞后，分子速率自动形成钟形偏右的分布（麦克斯韦-玻尔兹曼分布）", w / 2, 18);
        });
    };

    /* 衍射：波穿过狭缝后绕射 */
    registry["diffraction2"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var wallX = w * 0.45, gapC = h / 2, gapH = h * 0.16;
            // 墙
            ctx.fillStyle = "#6b7280";
            ctx.fillRect(wallX, 0, 8, gapC - gapH);
            ctx.fillRect(wallX, gapC + gapH, 8, h - gapC - gapH);
            // 左侧平面波
            ctx.strokeStyle = "rgba(79,70,229,0.6)"; ctx.lineWidth = 2;
            for (var i = 0; i < 6; i++) {
                var xw = ((dt * 40 + i * 34) % (wallX - 20));
                ctx.beginPath(); ctx.moveTo(xw, h * 0.15); ctx.lineTo(xw, h * 0.85); ctx.stroke();
            }
            // 右侧半圆波
            ctx.strokeStyle = "rgba(239,68,68,0.6)";
            for (var j = 1; j < 8; j++) {
                var rr = ((dt * 40 + j * 34) % (w * 0.6));
                ctx.beginPath(); ctx.arc(wallX + 4, gapC, rr, -Math.PI / 2, Math.PI / 2); ctx.stroke();
            }
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("平面波（蓝）经过狭缝后向四周绕射（红）", w / 2, 18);
        });
    };

    /* 质能方程：一点质量 ↔ 巨大能量 */
    registry["emc2"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var cyc = (dt % 5) / 5;
            var burst = Math.max(0, Math.sin(cyc * Math.PI));
            var cx = w / 2, cy = h / 2;
            // 质量块
            ctx.fillStyle = "#4f46e5";
            var mSize = 26 * (1 - burst * 0.7);
            ctx.fillRect(cx - mSize / 2, cy - mSize / 2, mSize, mSize);
            // 能量光芒
            ctx.strokeStyle = "rgba(245,158,11," + (0.3 + burst * 0.7) + ")";
            ctx.lineWidth = 3;
            for (var i = 0; i < 12; i++) {
                var a = i / 12 * Math.PI * 2;
                var r1 = 30 + burst * 20, r2 = 30 + burst * (h * 0.38);
                ctx.beginPath();
                ctx.moveTo(cx + Math.cos(a) * r1, cy + Math.sin(a) * r1);
                ctx.lineTo(cx + Math.cos(a) * r2, cy + Math.sin(a) * r2);
                ctx.stroke();
            }
            ctx.fillStyle = "#374151"; ctx.font = "13px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("E = mc² ：c² 是天文数字，一点点质量就是巨大能量", w / 2, 20);
            ctx.fillStyle = "#6b7280"; ctx.font = "12px sans-serif";
            ctx.fillText("1 克质量完全转化 ≈ 2 万吨 TNT 炸药", w / 2, h - 12);
        });
    };

    /* 广义相对论：质量压弯时空网格 */
    registry["gravity2"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var cx = w / 2, cy = h * 0.45;
            var dent = (Math.sin(dt * 0.8) + 1) / 2 * h * 0.2;
            ctx.strokeStyle = "#a5b4fc"; ctx.lineWidth = 1;
            var N = 18;
            for (var i = 0; i <= N; i++) {
                ctx.beginPath();
                for (var x = 0; x <= w; x += 8) {
                    var y0 = i / N * h;
                    var d2 = Math.pow(x - cx, 2) + Math.pow(y0 - cy, 2);
                    var yy = y0 + dent * Math.exp(-d2 / (2 * Math.pow(w * 0.13, 2)));
                    x === 0 ? ctx.moveTo(x, yy) : ctx.lineTo(x, yy);
                }
                ctx.stroke();
            }
            for (var j = 0; j <= N; j++) {
                ctx.beginPath();
                for (var y = 0; y <= h; y += 8) {
                    var x0 = j / N * w;
                    var d3 = Math.pow(x0 - cx, 2) + Math.pow(y - cy, 2);
                    var xx = x0 + dent * 0.4 * Math.exp(-d3 / (2 * Math.pow(w * 0.13, 2))) * Math.sign(x0 - cx);
                    y === 0 ? ctx.moveTo(xx, y) : ctx.lineTo(xx, y);
                }
                ctx.stroke();
            }
            ctx.fillStyle = "#1f2937";
            ctx.beginPath(); ctx.arc(cx, cy + dent * 0.8, 16, 0, 7); ctx.fill();
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("大质量天体把时空压出凹陷——这就是引力", w / 2, h - 12);
        });
    };

    /* 引力波：双星互旋激发涟漪 */
    registry["gwaves"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var cx = w / 2, cy = h / 2;
            // 涟漪
            for (var i = 0; i < 6; i++) {
                var rr = ((dt * 50 + i * 42) % (Math.min(w, h) * 0.7));
                ctx.strokeStyle = "rgba(99,102,241," + (1 - rr / (Math.min(w, h) * 0.7)) * 0.8 + ")";
                ctx.lineWidth = 2;
                ctx.beginPath(); ctx.ellipse(cx, cy, rr, rr * 0.75, 0, 0, 7); ctx.stroke();
            }
            // 双星
            var a = dt * 2.2, R = Math.min(w, h) * 0.1;
            ctx.fillStyle = "#1f2937";
            ctx.beginPath(); ctx.arc(cx + Math.cos(a) * R, cy + Math.sin(a) * R * 0.75, 9, 0, 7); ctx.fill();
            ctx.beginPath(); ctx.arc(cx - Math.cos(a) * R, cy - Math.sin(a) * R * 0.75, 9, 0, 7); ctx.fill();
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("双黑洞互旋，时空泛起一圈圈涟漪（引力波）", w / 2, h - 12);
        });
    };

    /* 不确定性：波包越窄，动量越不确定 */
    registry["uncertainty"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var spread = 0.12 + (Math.sin(dt * 0.9) + 1) / 2 * 0.28;
            var cy = h * 0.45;
            ctx.strokeStyle = "#4f46e5"; ctx.lineWidth = 2.5;
            ctx.beginPath();
            for (var x = 0; x <= w; x += 3) {
                var u = (x / w - 0.5) / spread;
                var y = cy - Math.exp(-u * u) * Math.cos(u * 8) * h * 0.3;
                x === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
            }
            ctx.stroke();
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText(spread < 0.22 ? "位置确定（波包窄）→ 动量很不确定" : "位置弥散（波包宽）→ 动量较确定", w / 2, 18);
            ctx.fillStyle = "#6b7280";
            ctx.fillText("Δx · Δp ≥ ħ/2：两者不可兼得", w / 2, h - 12);
        });
    };

    /* 量子纠缠：两个粒子测量结果总是相反（点击测量） */
    registry["entangle"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        var measured = 0;
        canvas.addEventListener("click", function () { measured++; });
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var cx1 = w * 0.3, cx2 = w * 0.7, cy = h / 2;
            ctx.strokeStyle = "#c7d2fe"; ctx.setLineDash([4, 4]);
            ctx.beginPath(); ctx.moveTo(cx1, cy); ctx.lineTo(cx2, cy); ctx.stroke(); ctx.setLineDash([]);
            var up = measured % 2 === 0;
            var spinning = measured === 0 || (t / 300) % 2 < 1;
            function particle(cx, dirUp, spin) {
                ctx.fillStyle = "#4f46e5";
                ctx.beginPath(); ctx.arc(cx, cy, 18, 0, 7); ctx.fill();
                ctx.strokeStyle = "#fff"; ctx.lineWidth = 3;
                var a = spin ? dt * 6 : (dirUp ? -Math.PI / 2 : Math.PI / 2);
                ctx.beginPath(); ctx.moveTo(cx, cy);
                ctx.lineTo(cx + Math.cos(a) * 14, cy + Math.sin(a) * 14); ctx.stroke();
            }
            particle(cx1, up, spinning);
            particle(cx2, !up, spinning);
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("纠缠对：无论相距多远，测到一个就立即知道另一个", w / 2, 20);
            ctx.fillStyle = "#6b7280";
            ctx.fillText(spinning ? "测量前：两个都处于叠加态（点击测量）" : "测量后：自旋必定相反", w / 2, h - 12);
        });
    };

    /* 量子比特：|0⟩ 与 |1⟩ 的概率振荡 */
    registry["qubit"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var p0 = Math.pow(Math.cos(dt * 0.8), 2), p1 = 1 - p0;
            var bw = w * 0.2, base = h * 0.8, bh = h * 0.6;
            ctx.fillStyle = "#4f46e5";
            ctx.fillRect(w * 0.22, base - bh * p0, bw, bh * p0);
            ctx.fillStyle = "#f59e0b";
            ctx.fillRect(w * 0.58, base - bh * p1, bw, bh * p1);
            ctx.strokeStyle = "#374151"; ctx.lineWidth = 1;
            ctx.strokeRect(w * 0.22, base - bh, bw, bh);
            ctx.strokeRect(w * 0.58, base - bh, bw, bh);
            ctx.fillStyle = "#374151"; ctx.font = "13px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("|0⟩ " + Math.round(p0 * 100) + "%", w * 0.22 + bw / 2, base + 18);
            ctx.fillText("|1⟩ " + Math.round(p1 * 100) + "%", w * 0.58 + bw / 2, base + 18);
            ctx.fillText("量子比特测量前同时处于 0 和 1 的概率叠加", w / 2, 20);
        });
    };

    /* 量子通信：窃听必然扰动 */
    registry["qcomm"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        var bits = [];
        for (var i = 0; i < 12; i++) bits.push(Math.random() > 0.5 ? 1 : 0);
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("量子密钥分发：光子一个一个发送", w / 2, 18);
            // 发送方/接收方
            ctx.fillStyle = "#4f46e5"; ctx.fillRect(20, h / 2 - 24, 40, 48);
            ctx.fillStyle = "#4f46e5"; ctx.fillRect(w - 60, h / 2 - 24, 40, 48);
            ctx.fillStyle = "#fff";
            ctx.fillText("发", 32, h / 2 + 4); ctx.fillText("收", w - 48, h / 2 + 4);
            // 光子飞行
            for (var i = 0; i < 4; i++) {
                var px = 70 + ((dt * 60 + i * (w / 4)) % (w - 140));
                ctx.fillStyle = "#f59e0b";
                ctx.beginPath(); ctx.arc(px, h / 2, 6, 0, 7); ctx.fill();
            }
            // 窃听者被标红
            var ex = w / 2;
            ctx.fillStyle = "#ef4444";
            ctx.beginPath(); ctx.arc(ex, h / 2 - 50, 12, 0, 7); ctx.fill();
            ctx.fillStyle = "#ef4444";
            ctx.fillText("窃听者一测量就会改变量子态 → 必然被发现", w / 2, h - 12);
        });
    };

    /* 希格斯场：穿过场的粒子获得"惯性" */
    registry["higgs"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            // 希格斯场区域
            ctx.fillStyle = "rgba(99,102,241,0.12)";
            ctx.fillRect(w * 0.35, h * 0.15, w * 0.4, h * 0.7);
            ctx.fillStyle = "#6366f1"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("希格斯场", w * 0.55, h * 0.13);
            // 快粒子（几乎无相互作用）
            var x1 = ((dt * 90) % (w + 40)) - 20;
            ctx.fillStyle = "#22c55e";
            ctx.beginPath(); ctx.arc(x1, h * 0.3, 7, 0, 7); ctx.fill();
            // 慢粒子（强相互作用 → 获得质量）
            var x2 = w * 0.1;
            x2 = ((dt * 90) % (w + 40)) - 20;
            var inField = x2 > w * 0.35 && x2 < w * 0.75;
            var sp = inField ? 0.35 : 1;
            x2 = w * 0.1 + ((dt * 90 * sp) % (w * 0.9));
            ctx.fillStyle = "#ef4444";
            ctx.beginPath(); ctx.arc(x2, h * 0.65, 10, 0, 7); ctx.fill();
            ctx.fillStyle = "#374151";
            ctx.fillText("绿：几乎不与场作用（如光子，无质量、恒为光速）", w / 2, h - 30);
            ctx.fillText("红：与希格斯场强作用 → 变慢变「重」（获得质量）", w / 2, h - 12);
        });
    };

    /* 暗物质：星系旋转曲线异常 */
    registry["darkmatter"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = ((t - t0) / 1000) % 8, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var pad = 46;
            ctx.strokeStyle = "#9ca3af"; ctx.lineWidth = 1;
            ctx.beginPath(); ctx.moveTo(pad, h - pad); ctx.lineTo(w - pad, h - pad); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(pad, h - pad); ctx.lineTo(pad, pad); ctx.stroke();
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("离星系中心距离 →", w / 2, h - pad + 18);
            ctx.save(); ctx.translate(pad - 16, h / 2); ctx.rotate(-Math.PI / 2);
            ctx.fillText("旋转速度 →", 0, 0); ctx.restore();
            var prog = Math.min(1, dt / 5);
            // 预期：开普勒下降
            ctx.strokeStyle = "#9ca3af"; ctx.lineWidth = 2; ctx.setLineDash([5, 4]);
            ctx.beginPath();
            for (var x = pad; x <= pad + (w - 2 * pad) * prog; x += 4) {
                var r = (x - pad) / (w - 2 * pad) + 0.08;
                var y = h - pad - (0.3 / Math.sqrt(r)) * (h * 0.13);
                x === pad ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
            }
            ctx.stroke(); ctx.setLineDash([]);
            // 观测：平坦
            ctx.strokeStyle = "#ef4444"; ctx.lineWidth = 2.5;
            ctx.beginPath();
            for (var x2 = pad; x2 <= pad + (w - 2 * pad) * prog; x2 += 4) {
                var r2 = (x2 - pad) / (w - 2 * pad);
                var y2 = h - pad - Math.min(0.75, r2 * 1.8) * (h * 0.75);
                x2 === pad ? ctx.moveTo(x2, y2) : ctx.lineTo(x2, y2);
            }
            ctx.stroke();
            ctx.fillStyle = "#ef4444"; ctx.textAlign = "left";
            ctx.fillText("观测：外圈一样快", pad + 12, pad + 18);
            ctx.fillStyle = "#9ca3af";
            ctx.fillText("预期：越外越慢", w * 0.55, h - pad - 30);
            ctx.fillStyle = "#374151"; ctx.textAlign = "center";
            ctx.fillText("差异只能用「看不见的暗物质」解释", w / 2, 20);
        });
    };

    /* 中微子振荡：飞行中身份不断变换 */
    registry["neutrino"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var colors = ["#4f46e5", "#f59e0b", "#10b981"];
            var names = ["电子中微子", "μ中微子", "τ中微子"];
            var x = ((dt * 60) % (w + 80)) - 40;
            var cy = h / 2;
            var ci = Math.floor(dt * 1.2) % 3;
            ctx.fillStyle = colors[ci];
            ctx.beginPath(); ctx.arc(x, cy + Math.sin(dt * 5) * 10, 10, 0, 7); ctx.fill();
            ctx.fillStyle = colors[ci]; ctx.font = "13px sans-serif"; ctx.textAlign = "center";
            ctx.fillText(names[ci], x, cy - 24);
            // 轨迹
            ctx.strokeStyle = "#d1d5db"; ctx.setLineDash([3, 4]);
            ctx.beginPath(); ctx.moveTo(10, cy); ctx.lineTo(w - 10, cy); ctx.stroke(); ctx.setLineDash([]);
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif";
            ctx.fillText("中微子飞行时会在三种「味」之间振荡变身——证明它有质量", w / 2, h - 12);
        });
    };

    /* 超新星：大质量恒星坍缩爆发 */
    registry["supernova"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = ((t - t0) / 1000) % 6, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var cx = w / 2, cy = h / 2;
            var stage = dt / 6;
            if (stage < 0.35) {
                // 恒星膨胀
                var R = 20 + stage / 0.35 * 30;
                ctx.fillStyle = "#f59e0b";
                ctx.beginPath(); ctx.arc(cx, cy, R, 0, 7); ctx.fill();
                ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
                ctx.fillText("燃料耗尽，红巨星膨胀…", w / 2, h - 14);
            } else if (stage < 0.5) {
                // 坍缩
                var R2 = 50 - (stage - 0.35) / 0.15 * 44;
                ctx.fillStyle = "#ef4444";
                ctx.beginPath(); ctx.arc(cx, cy, R2, 0, 7); ctx.fill();
                ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
                ctx.fillText("引力坍缩！", w / 2, h - 14);
            } else {
                // 爆发
                var br = (stage - 0.5) / 0.5;
                for (var i = 0; i < 16; i++) {
                    var a = i / 16 * Math.PI * 2;
                    var rr = br * Math.min(w, h) * 0.45;
                    ctx.fillStyle = "rgba(245,158,11," + (1 - br * 0.7) + ")";
                    ctx.beginPath(); ctx.arc(cx + Math.cos(a) * rr, cy + Math.sin(a) * rr, 8 * (1 - br * 0.5), 0, 7); ctx.fill();
                }
                ctx.fillStyle = "#fff";
                ctx.beginPath(); ctx.arc(cx, cy, 6, 0, 7); ctx.fill();
                ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
                ctx.fillText("爆发！中心留下中子星，抛洒出重元素", w / 2, h - 14);
            }
        });
    };

    /* 脉冲星：旋转的灯塔 */
    registry["pulsar"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var cx = w / 2, cy = h / 2;
            // 星星背景
            ctx.fillStyle = "#c7d2fe";
            for (var i = 0; i < 30; i++) {
                var sx = (i * 97.3 % 1) * w, sy = (i * 57.7 % 1) * h;
                ctx.fillRect(sx, sy, 2, 2);
            }
            var a = dt * 2.5;
            // 两束辐射
            ctx.fillStyle = "rgba(245,158,11,0.5)";
            [-1, 1].forEach(function (s2) {
                ctx.beginPath();
                ctx.moveTo(cx, cy);
                var a2 = a + (s2 > 0 ? 0 : Math.PI);
                ctx.lineTo(cx + Math.cos(a2 - 0.12) * w, cy + Math.sin(a2 - 0.12) * w);
                ctx.lineTo(cx + Math.cos(a2 + 0.12) * w, cy + Math.sin(a2 + 0.12) * w);
                ctx.closePath(); ctx.fill();
            });
            ctx.fillStyle = "#1f2937";
            ctx.beginPath(); ctx.arc(cx, cy, 12, 0, 7); ctx.fill();
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("中子星高速自转，磁极辐射像灯塔一样扫过——地球上收到规则脉冲", w / 2, h - 12);
        });
    };

    /* 宇宙微波背景：大爆炸的余晖 */
    registry["cmb"] = function (canvas) {
        var g, ctx;
        var dots = [];
        for (var i = 0; i < 500; i++) {
            dots.push({ x: Math.random(), y: Math.random(), v: Math.random() });
        }
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            ctx.fillStyle = "#0f172a";
            ctx.fillRect(0, 0, w, h);
            var dt = t / 1000;
            dots.forEach(function (d) {
                var tw = 0.5 + Math.sin(dt * 2 + d.v * 20) * 0.5;
                ctx.fillStyle = d.v > 0.5 ? "rgba(248,113,113," + tw + ")" : "rgba(96,165,250," + tw + ")";
                ctx.beginPath(); ctx.arc(d.x * w, d.y * h, 1.6, 0, 7); ctx.fill();
            });
            ctx.fillStyle = "#e2e8f0"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("CMB 全天图：红蓝涨落是 138 亿年前宇宙的「婴儿照片」", w / 2, 20);
            ctx.fillText("微小温差藏着星系形成的种子", w / 2, h - 12);
        });
    };


    /* 四种基本力对比：强度与作用范围 */
    registry["forces"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        var forces = [
            { name: "强力", rel: 1, range: "10⁻¹⁵ m", carrier: "胶子", color: "#ef4444" },
            { name: "电磁力", rel: 1e-2, range: "∞", carrier: "光子", color: "#f59e0b" },
            { name: "弱力", rel: 1e-13, range: "10⁻¹⁸ m", carrier: "W/Z 玻色子", color: "#10b981" },
            { name: "引力", rel: 1e-38, range: "∞", carrier: "引力子（未证实）", color: "#6366f1" },
        ];
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var pad = 60, bh = (h - 110) / 4;
            // 对数坐标：log10(强度) 从 -38 到 0
            function xOf(v) { return pad + (Math.log10(v) + 38) / 38 * (w - pad - 30); }
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("相对强度（对数刻度，差 38 个数量级！）", w / 2, 16);
            forces.forEach(function (f, i) {
                var y = 34 + i * (bh + 8);
                var prog = Math.min(1, Math.max(0, dt - i * 0.4) / 1.2);
                var xe = xOf(f.rel);
                ctx.fillStyle = f.color;
                ctx.fillRect(pad, y, Math.max(3, (xe - pad) * prog), bh);
                ctx.fillStyle = "#111827"; ctx.textAlign = "right"; ctx.font = "bold 13px sans-serif";
                ctx.fillText(f.name, pad - 8, y + bh / 2 + 4);
                if (prog > 0.9) {
                    ctx.fillStyle = "#6b7280"; ctx.textAlign = "left"; ctx.font = "11px sans-serif";
                    ctx.fillText("范围 " + f.range + "　媒介 " + f.carrier, xe + 6, y + bh / 2 + 4);
                }
            });
            ctx.fillStyle = "#6b7280"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("引力最弱却主宰宇宙——因为它只有吸引、且可以无限叠加", w / 2, h - 10);
        });
    };


    /* 进化：种群颜色随选择漂变 */
    registry["evolution"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        var pop = [];
        for (var i = 0; i < 40; i++) pop.push({ x: Math.random(), y: Math.random(), green: Math.random() > 0.7 });
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            // 每 3 秒淘汰一部分棕色（不适应环境）
            if (Math.floor(dt) % 3 === 0 && Math.floor(dt * 10) % 10 === 0) {
                pop.forEach(function (p) { if (!p.green && Math.random() < 0.06) p.green = true; });
            }
            pop.forEach(function (p, i) {
                p.x += Math.sin(dt + i) * 0.0015; p.y += Math.cos(dt * 0.8 + i) * 0.0015;
                ctx.fillStyle = p.green ? "#10b981" : "#b45309";
                ctx.beginPath(); ctx.arc(p.x * w, p.y * h, 6, 0, 7); ctx.fill();
            });
            var ng = pop.filter(function (p) { return p.green; }).length;
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("适应者（绿）占比：" + Math.round(ng / 40 * 100) + "%——自然选择让有利性状扩散", w / 2, 18);
        });
    };

    /* 细胞分裂：一分为二 */
    registry["cell-division"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = ((t - t0) / 1000) % 6, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var cx = w / 2, cy = h / 2;
            var sep = Math.max(0, (dt - 1.5) / 3);
            var squeeze = Math.min(1, dt / 1.5);
            // 细胞
            ctx.fillStyle = "rgba(147,197,253,0.5)"; ctx.strokeStyle = "#3b82f6"; ctx.lineWidth = 2;
            var R = Math.min(w, h) * 0.22;
            ctx.beginPath();
            ctx.ellipse(cx - sep * w * 0.18, cy, R * (1 + squeeze * 0.2), R * (1 - squeeze * 0.15 + sep * 0.1), 0, 0, 7);
            ctx.fill(); ctx.stroke();
            if (sep > 0.3) {
                ctx.beginPath();
                ctx.ellipse(cx + sep * w * 0.18, cy, R * (1 + squeeze * 0.2), R, 0, 0, 7);
                ctx.fill(); ctx.stroke();
            }
            // 染色体排列分开
            ctx.strokeStyle = "#ef4444"; ctx.lineWidth = 3;
            var nChr = 4;
            for (var i = 0; i < nChr; i++) {
                var yy = cy - 24 + i * 16;
                if (dt < 1.5) {
                    ctx.beginPath(); ctx.moveTo(cx - 8, yy); ctx.lineTo(cx + 8, yy); ctx.stroke();
                } else {
                    ctx.beginPath(); ctx.moveTo(cx - sep * w * 0.18 - 10, yy); ctx.lineTo(cx - sep * w * 0.18, yy); ctx.stroke();
                    if (sep > 0.3) {
                        ctx.beginPath(); ctx.moveTo(cx + sep * w * 0.18, yy); ctx.lineTo(cx + sep * w * 0.18 + 10, yy); ctx.stroke();
                    }
                }
            }
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText(dt < 1.5 ? "染色体复制后排列到中央" : sep < 0.3 ? "染色体被拉向两极" : "细胞质分裂：一个变两个", w / 2, 18);
            ctx.fillStyle = "#6b7280";
            ctx.fillText("有丝分裂：每个子细胞得到一套完整遗传物质", w / 2, h - 12);
        });
    };

    /* 神经元：动作电位沿轴突传导 */
    registry["neuron"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            // 胞体
            ctx.fillStyle = "#818cf8";
            ctx.beginPath(); ctx.arc(w * 0.12, h / 2, 22, 0, 7); ctx.fill();
            // 轴突
            ctx.strokeStyle = "#818cf8"; ctx.lineWidth = 5;
            ctx.beginPath(); ctx.moveTo(w * 0.12, h / 2); ctx.lineTo(w * 0.88, h / 2); ctx.stroke();
            // 电信号脉冲
            var px = w * 0.12 + ((dt * 140) % (w * 0.76));
            ctx.fillStyle = "#f59e0b";
            ctx.beginPath(); ctx.arc(px, h / 2, 9, 0, 7); ctx.fill();
            // 突触释放
            if (px > w * 0.8) {
                ctx.fillStyle = "#ef4444";
                for (var i = 0; i < 6; i++) {
                    ctx.beginPath(); ctx.arc(w * 0.9 + Math.cos(i) * 12 * ((dt * 3) % 1), h / 2 + Math.sin(i * 2) * 16 * ((dt * 3) % 1), 3, 0, 7); ctx.fill();
                }
            }
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("动作电位（黄）沿轴突传导，末端释放神经递质（红）", w / 2, 18);
        });
    };

    /* 捕食者-猎物振荡（Lotka-Volterra） */
    registry["ecosystem"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var pad = 46;
            ctx.strokeStyle = "#9ca3af";
            ctx.beginPath(); ctx.moveTo(pad, h - pad); ctx.lineTo(w - pad, h - pad); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(pad, h - pad); ctx.lineTo(pad, pad); ctx.stroke();
            // 数值积分 Lotka-Volterra
            var prey = 40, pred = 9, x = 0, ddt = 0.02;
            var preyPts = [], predPts = [];
            for (var i = 0; i < 900; i++) {
                preyPts.push(prey); predPts.push(pred);
                var dp = (0.6 * prey - 0.02 * prey * pred) * ddt;
                var dq = (-0.5 * pred + 0.015 * prey * pred) * ddt;
                prey += dp; pred += dq;
            }
            function draw(pts, color, maxV) {
                ctx.strokeStyle = color; ctx.lineWidth = 2;
                ctx.beginPath();
                var show = Math.floor(Math.min(1, (dt % 12) / 4) * pts.length);
                for (var i2 = 0; i2 < show; i2++) {
                    var X = pad + i2 / pts.length * (w - 2 * pad);
                    var Y = h - pad - pts[i2] / maxV * (h - 2 * pad);
                    i2 === 0 ? ctx.moveTo(X, Y) : ctx.lineTo(X, Y);
                }
                ctx.stroke();
            }
            draw(preyPts, "#10b981", 120);
            draw(predPts, "#ef4444", 120);
            ctx.fillStyle = "#10b981"; ctx.font = "12px sans-serif"; ctx.textAlign = "left";
            ctx.fillText("猎物（兔）", pad + 10, pad + 4);
            ctx.fillStyle = "#ef4444";
            ctx.fillText("捕食者（狐）", pad + 80, pad + 4);
            ctx.fillStyle = "#374151"; ctx.textAlign = "center";
            ctx.fillText("兔多 → 狐多 → 兔少 → 狐少 → 兔多……生态系统的周期振荡", w / 2, h - 12);
        });
    };

    /* 导数：曲线上的切线与斜率 */
    registry["derivative"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var pad = 40;
            function f(x) { return (x - w * 0.3) * (x - w * 0.7) * 0.004; }
            function df(x) { return (2 * x - w) * 0.004; }
            ctx.strokeStyle = "#9ca3af";
            ctx.beginPath(); ctx.moveTo(pad, h - pad + 60); ctx.lineTo(w - pad, h - pad + 60); ctx.stroke();
            // 曲线
            ctx.strokeStyle = "#4f46e5"; ctx.lineWidth = 2.5;
            ctx.beginPath();
            for (var x = 20; x < w - 20; x += 4) {
                var y = h * 0.6 - (f(x) - f(w / 2)) * 30;
                x === 20 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
            }
            ctx.stroke();
            // 切线滑动
            var px = w * 0.3 + (Math.sin(dt * 0.7) + 1) / 2 * w * 0.4;
            var py = h * 0.6 - (f(px) - f(w / 2)) * 30;
            var slope = df(px) * 30;
            ctx.strokeStyle = "#ef4444"; ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(px - 50, py + slope * 50);
            ctx.lineTo(px + 50, py - slope * 50);
            ctx.stroke();
            ctx.fillStyle = "#ef4444";
            ctx.beginPath(); ctx.arc(px, py, 6, 0, 7); ctx.fill();
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("切线斜率 = 导数（该点的瞬时变化率）", w / 2, 20);
            ctx.fillStyle = "#ef4444";
            ctx.fillText("f'(x) = " + df(px).toFixed(2), px, py - 14);
        });
    };

    /* 单位圆生成正弦波 */
    registry["sine"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var cx = w * 0.22, cy = h * 0.55, R = Math.min(w, h) * 0.32;
            ctx.strokeStyle = "#9ca3af";
            ctx.beginPath(); ctx.arc(cx, cy, R, 0, 7); ctx.stroke();
            var a = dt * 1.5;
            var px = cx + Math.cos(-a) * R, py = cy + Math.sin(-a) * R;
            ctx.strokeStyle = "#4f46e5"; ctx.lineWidth = 2;
            ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(px, py); ctx.stroke();
            ctx.fillStyle = "#ef4444";
            ctx.beginPath(); ctx.arc(px, py, 6, 0, 7); ctx.fill();
            // 正弦波
            ctx.strokeStyle = "#ef4444";
            ctx.beginPath();
            for (var x = 0; x < w * 0.6; x += 3) {
                var y = cy + Math.sin(-(x / R + a)) * R * 0 + Math.sin(-(x / R + a)) * 0; // placeholder
                var yy = cy - Math.sin(x / R + a) * R * 0.6;
                x === 0 ? ctx.moveTo(w * 0.38 + x, yy) : ctx.lineTo(w * 0.38 + x, yy);
            }
            ctx.stroke();
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("单位圆上点的纵坐标展开成正弦波", w / 2, 18);
        });
    };

    /* 高尔顿板：正态分布的形成 */
    registry["normaldist"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        var balls = [];
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            // 钉子
            var rows = 7;
            ctx.fillStyle = "#9ca3af";
            for (var r = 0; r < rows; r++) {
                for (var i = 0; i <= r; i++) {
                    var nx = w / 2 + (i - r / 2) * w * 0.09;
                    var ny = h * 0.18 + r * h * 0.07;
                    ctx.beginPath(); ctx.arc(nx, ny, 3, 0, 7); ctx.fill();
                }
            }
            // 落球
            if (Math.floor(dt * 6) > balls.length && balls.length < 160) {
                var x = w / 2;
                for (var r2 = 0; r2 < rows; r2++) x += (Math.random() > 0.5 ? 1 : -1) * w * 0.045;
                balls.push(x);
            }
            // 底部分布
            var bins = {};
            balls.forEach(function (bx) {
                var b = Math.round(bx / (w * 0.045)) ;
                bins[b] = (bins[b] || 0) + 1;
            });
            ctx.fillStyle = "#6366f1";
            Object.keys(bins).forEach(function (k) {
                var bx = k * w * 0.045;
                var bh = bins[k] * 3;
                ctx.fillRect(bx - w * 0.02, h - 30 - bh, w * 0.04, bh);
            });
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("每个小球随机左右偏 → 底部自然堆成钟形曲线（正态分布）", w / 2, 16);
        });
    };

    /* 冒泡排序可视化 */
    registry["sortbars"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        var arr = [];
        for (var i = 0; i < 24; i++) arr.push(0.1 + Math.random() * 0.9);
        var ii = 0, jj = 0, sorted = false, lastSwap = 0;
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = t / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            if (!sorted && t - lastSwap > 90) {
                lastSwap = t;
                if (arr[jj] > arr[jj + 1]) { var tmp = arr[jj]; arr[jj] = arr[jj + 1]; arr[jj + 1] = tmp; }
                jj++;
                if (jj >= arr.length - 1 - ii) { jj = 0; ii++; }
                if (ii >= arr.length - 1) sorted = true;
            }
            var bw = w / arr.length;
            arr.forEach(function (v, i3) {
                var isActive = !sorted && (i3 === jj || i3 === jj + 1);
                ctx.fillStyle = sorted ? "#10b981" : isActive ? "#ef4444" : "#6366f1";
                ctx.fillRect(i3 * bw + 1, h - 40 - v * (h - 90), bw - 2, v * (h - 90));
            });
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText(sorted ? "排序完成！相邻比较、大的往后冒——冒泡排序" : "冒泡排序进行中：红色是正在比较的一对", w / 2, 18);
        });
    };

    /* 二分查找 */
    registry["binsearch"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        var N = 20;
        var arr = []; for (var i = 0; i < N; i++) arr.push(i * 5 + 2);
        var target = arr[Math.floor(Math.random() * N)];
        var lo = 0, hi = N - 1, mid = -1, done = false, stepT = 0;
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            if (!done && t - stepT > 1100) {
                stepT = t;
                mid = Math.floor((lo + hi) / 2);
                if (arr[mid] === target) done = true;
                else if (arr[mid] < target) lo = mid + 1;
                else hi = mid - 1;
            }
            var bw = (w - 60) / N;
            arr.forEach(function (v, i2) {
                var inRange = i2 >= lo && i2 <= hi;
                ctx.fillStyle = done && i2 === mid ? "#10b981" : i2 === mid ? "#ef4444" : inRange ? "#6366f1" : "#d1d5db";
                ctx.fillRect(30 + i2 * bw, h * 0.35, bw - 3, 26);
                ctx.fillStyle = "#fff"; ctx.font = "11px sans-serif"; ctx.textAlign = "center";
                ctx.fillText(v, 30 + i2 * bw + bw / 2 - 1, h * 0.35 + 17);
            });
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("在有序数组中找 " + target + "：每次排除一半（灰色已排除）", w / 2, 18);
            ctx.fillText(done ? "找到了！大约只用了 " + Math.ceil(Math.log2(20)) + " 步" : "查找中…", w / 2, h - 14);
        });
    };

    /* 二进制位 */
    registry["binarybits"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var n = Math.floor(dt * 2) % 256;
            var bits = n.toString(2).padStart(8, "0");
            var bw = w * 0.09;
            for (var i = 0; i < 8; i++) {
                var on = bits[i] === "1";
                var x = w / 2 + (i - 3.5) * bw * 1.25;
                ctx.fillStyle = on ? "#4f46e5" : "#e5e7eb";
                ctx.beginPath(); ctx.arc(x, h * 0.45, bw * 0.5, 0, 7); ctx.fill();
                ctx.fillStyle = on ? "#fff" : "#9ca3af";
                ctx.font = "bold 16px sans-serif"; ctx.textAlign = "center";
                ctx.fillText(bits[i], x, h * 0.45 + 6);
            }
            ctx.fillStyle = "#374151"; ctx.font = "13px sans-serif";
            ctx.fillText(bits + "₂ = " + n + "₁₀", w / 2, h * 0.72);
            ctx.font = "12px sans-serif"; ctx.fillStyle = "#6b7280";
            ctx.fillText("计算机只认识 0 和 1：8 位可以表示 0~255", w / 2, h - 12);
        });
    };

    /* 网络包路由 */
    registry["network"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        var nodes = [
            [0.12, 0.5], [0.35, 0.25], [0.35, 0.75], [0.6, 0.4], [0.6, 0.7], [0.88, 0.5],
        ];
        var edges = [[0, 1], [0, 2], [1, 3], [2, 4], [3, 5], [4, 5], [1, 4], [2, 3]];
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            ctx.strokeStyle = "#c7d2fe"; ctx.lineWidth = 2;
            edges.forEach(function (e) {
                ctx.beginPath();
                ctx.moveTo(nodes[e[0]][0] * w, nodes[e[0]][1] * h);
                ctx.lineTo(nodes[e[1]][0] * w, nodes[e[1]][1] * h);
                ctx.stroke();
            });
            nodes.forEach(function (n, i) {
                ctx.fillStyle = i === 0 ? "#10b981" : i === 5 ? "#ef4444" : "#6366f1";
                ctx.beginPath(); ctx.arc(n[0] * w, n[1] * h, 10, 0, 7); ctx.fill();
            });
            // 包沿路径飞行
            var route = [0, 1, 4, 5];
            var seg = Math.floor(dt * 1.5) % (route.length - 1);
            var frac = (dt * 1.5) % 1;
            var A = nodes[route[seg]], B = nodes[route[seg + 1]];
            var px = (A[0] + (B[0] - A[0]) * frac) * w, py = (A[1] + (B[1] - A[1]) * frac) * h;
            ctx.fillStyle = "#f59e0b";
            ctx.beginPath(); ctx.arc(px, py, 6, 0, 7); ctx.fill();
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText("数据包（黄）从绿节点出发，经路由器一跳一跳到达红节点", w / 2, h - 10);
        });
    };

    /* 机器学习分类：分割线自动学习 */
    registry["mlclass"] = function (canvas) {
        var g, ctx; var t0 = performance.now();
        var ptsA = [], ptsB = [];
        for (var i = 0; i < 18; i++) {
            ptsA.push([0.15 + Math.random() * 0.25, 0.2 + Math.random() * 0.5]);
            ptsB.push([0.6 + Math.random() * 0.25, 0.3 + Math.random() * 0.5]);
        }
        return loop(function (t) {
            g = ctx2d(canvas); ctx = g.ctx;
            var dt = (t - t0) / 1000, w = g.w, h = g.h;
            ctx.clearRect(0, 0, w, h);
            var learn = Math.min(1, dt / 5);
            var slope = -1.2 + learn * 0.6;
            var off = 0.35 + learn * 0.25;
            // 分割线
            ctx.strokeStyle = "#ef4444"; ctx.lineWidth = 2.5;
            ctx.beginPath();
            ctx.moveTo(0, h * (off));
            ctx.lineTo(w, h * (off + slope * 0.3));
            ctx.stroke();
            ptsA.forEach(function (p) { ctx.fillStyle = "#4f46e5"; ctx.beginPath(); ctx.arc(p[0] * w, p[1] * h, 6, 0, 7); ctx.fill(); });
            ptsB.forEach(function (p) { ctx.fillStyle = "#f59e0b"; ctx.beginPath(); ctx.arc(p[0] * w, p[1] * h, 6, 0, 7); ctx.fill(); });
            ctx.fillStyle = "#374151"; ctx.font = "12px sans-serif"; ctx.textAlign = "center";
            ctx.fillText(learn < 1 ? "训练：分割线不断调整，把两类点分开…" : "学会了！红线把蓝点和黄点分开了", w / 2, 18);
            ctx.fillStyle = "#6b7280";
            ctx.fillText("机器学习的本质：从数据中自动学出分界（参数）", w / 2, h - 12);
        });
    };

    return { start: start, stop: stop };
})();
