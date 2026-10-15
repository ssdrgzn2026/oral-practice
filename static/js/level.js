/* 学科星图 · 读者身份层次（中学生/普通成年人/专业研究人员）
 * 身份存 localStorage，AI 内容按层次调整深度
 */
window.AtlasLevel = (function () {
    var KEY = "atlas_level";
    var LEVELS = {
        middle: {
            name: "中学生",
            icon: "🎒",
            directive: "读者是一名中学生：请用最通俗的语言讲解，多举生活和校园中的例子，少用公式和专业术语；必须使用时请用一句话解释这个术语。",
        },
        adult: {
            name: "普通成年人",
            icon: "🧑",
            directive: "读者是普通成年人（非专业人士）：语言通俗但不必过分简化，可以使用常见公式和术语并简要解释。",
        },
        researcher: {
            name: "专业研究人员",
            icon: "🔬",
            directive: "读者是专业研究人员：请使用严谨的学术语言，包含关键公式、重要文献方向、当前开放问题，不必做通俗化解释。",
        },
    };
    function get() { return localStorage.getItem(KEY) || "adult"; }
    function set(lv) { if (LEVELS[lv]) localStorage.setItem(KEY, lv); }
    function info() { return LEVELS[get()]; }
    function directive() { return LEVELS[get()].directive; }
    return { get: get, set: set, info: info, directive: directive, LEVELS: LEVELS };
})();
