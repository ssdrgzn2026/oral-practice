/* 演示器通用闯关引擎
 * 用法：DemoQuiz.init({
 *   tabsEl, bodyEl,          // 关卡标签容器、关卡内容容器
 *   levels,                  // [{name, lines:[[行文本, 空1答案, ...]]}]，行内 @@ 为空位
 *   storageKey,              // localStorage 进度键
 *   onBack                   // 可选，"返回演示"回调
 * })
 * 判分忽略空白差异，答案支持 | 分隔多个等价写法。
 */
window.DemoQuiz = (function () {
    var cfg = null, curLevel = 0, unlocked = 0;

    function norm(s) { return s.replace(/\s+/g, '').replace(/；/g, ';'); }

    function renderTabs() {
        var t = cfg.tabsEl; t.innerHTML = '';
        cfg.levels.forEach(function (L, i) {
            var b = document.createElement('button');
            b.className = 'level-tab' + (i === curLevel ? ' cur' : '') + (i < unlocked ? ' done' : '') + (i > unlocked ? ' locked' : '');
            b.textContent = (i < unlocked ? '✓ ' : '') + (i > unlocked ? '🔒 ' : '') + L.name.split(' · ')[0];
            b.title = L.name;
            b.onclick = function () { if (i <= unlocked) { curLevel = i; renderLevel(); renderTabs(); } };
            t.appendChild(b);
        });
    }

    function renderLevel() {
        var body = cfg.bodyEl; body.innerHTML = '';
        if (curLevel >= cfg.levels.length) {
            var pass = document.createElement('div');
            pass.className = 'pass-banner';
            pass.innerHTML = '🎉 全部通关！' + (cfg.passText || '') + '<br><br>';
            if (cfg.onBack) {
                var rb = document.createElement('button'); rb.className = 'btn'; rb.textContent = '回到演示';
                rb.onclick = cfg.onBack; pass.appendChild(rb);
            }
            body.appendChild(pass);
            return;
        }
        var L = cfg.levels[curLevel];
        var h = document.createElement('h3');
        h.style.margin = '0 0 10px'; h.style.fontSize = '15px'; h.textContent = L.name;
        body.appendChild(h);
        var code = document.createElement('div'); code.className = 'quiz-code';
        L.lines.forEach(function (row) {
            var text = row[0], answers = row.slice(1);
            var parts = text.split('@@');
            parts.forEach(function (p, k) {
                code.appendChild(document.createTextNode(p));
                if (k < parts.length - 1) {
                    var inp = document.createElement('input');
                    inp.className = 'blank'; inp.dataset.ans = answers[k] || '';
                    var w = Math.max(70, answers[0] ? answers[0].split('|')[0].length * 9 + 26 : 70);
                    inp.style.width = Math.min(w, 340) + 'px';
                    code.appendChild(inp);
                }
            });
            code.appendChild(document.createTextNode('\n'));
        });
        body.appendChild(code);
        var foot = document.createElement('div'); foot.className = 'quiz-foot';
        var btn = document.createElement('button'); btn.className = 'btn'; btn.textContent = '提交验收';
        var msg = document.createElement('span'); msg.className = 'quiz-msg';
        btn.onclick = function () {
            var blanks = body.querySelectorAll('.blank'), wrong = 0;
            blanks.forEach(function (inp) {
                var ok = inp.dataset.ans.split('|').some(function (a) { return norm(inp.value) === norm(a); });
                inp.classList.remove('right', 'wrong');
                inp.classList.add(ok ? 'right' : 'wrong');
                if (!ok) wrong++;
            });
            if (wrong === 0) {
                msg.style.color = 'var(--ok)'; msg.textContent = '✓ 全部正确！';
                if (curLevel + 1 > unlocked) {
                    unlocked = curLevel + 1;
                    try { localStorage.setItem(cfg.storageKey, String(unlocked)); } catch (e) {}
                }
                setTimeout(function () { curLevel++; renderLevel(); renderTabs(); }, 900);
            } else {
                msg.style.color = 'var(--bad)';
                msg.textContent = '还有 ' + wrong + ' 个空不对（红色）。提示：回到演示环节，观察高亮的那几行代码。';
            }
        };
        foot.appendChild(btn);
        if (cfg.onBack) {
            var backB = document.createElement('button'); backB.className = 'btn gray'; backB.textContent = '← 返回演示';
            backB.onclick = cfg.onBack; foot.appendChild(backB);
        }
        foot.appendChild(msg);
        body.appendChild(foot);
    }

    return {
        init: function (options) {
            cfg = options; curLevel = 0;
            unlocked = 0;
            try { unlocked = parseInt(localStorage.getItem(cfg.storageKey) || '0', 10) || 0; } catch (e) {}
            unlocked = Math.min(unlocked, cfg.levels.length);
            renderTabs(); renderLevel();
        }
    };
})();
