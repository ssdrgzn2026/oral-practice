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

    return { start: start, stop: stop };
})();
