# -*- coding: utf-8 -*-
"""
DCF 估值分析系统 - Streamlit 前端
支持手动输入年报数据，进行两阶段/三阶段 DCF 估值
"""
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import sys
import io
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.dcf_engine import (calculate_wacc, project_financials,
                              calculate_dcf_value, sensitivity_analysis,
                              build_full_report, recalculate_fcf_with_adjustments)
from core.data_fetcher import fetch_financial_data

# ========== 文件链接下载（微信/iOS PWA 下 blob 下载会失败或跳走页面） ==========
import time
import uuid
from pathlib import Path
from urllib.parse import quote

DOWNLOAD_DIR = Path(os.environ.get("MISC_DOWNLOAD_DIR", str(Path(__file__).parent / "downloads")))
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)


def dl(label, data, filename):
    """下载按钮：暂存文件并渲染真实下载链接（替代 st.download_button）"""
    try:
        now = time.time()
        for f in DOWNLOAD_DIR.iterdir():
            if f.is_file() and now - f.stat().st_mtime > 7200:
                f.unlink()
    except OSError:
        pass
    token = uuid.uuid4().hex[:16]
    suffix = Path(str(filename)).suffix
    (DOWNLOAD_DIR / f"{token}{suffix}").write_bytes(bytes(data))
    url = f"/files/{token}/{quote(str(filename))}"
    st.markdown(
        f"<a href='{url}' download style='display:block;text-align:center;background:#4f46e5;color:#fff;"
        f"padding:10px 22px;border-radius:10px;text-decoration:none;font-weight:600;margin:6px 0;'>"
        f"{label}</a>",
        unsafe_allow_html=True,
    )


# 设置中文字体
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS"]
plt.rcParams["axes.unicode_minus"] = False

st.set_page_config(
    page_title="DCF 估值分析系统",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============ 自定义主题（MiscHub 紫罗兰 + 统一排版） ============
st.markdown("""
<style>
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
    }
    h1 { font-size: 1.75rem !important; }
    h2 { font-size: 1.4rem !important; }
    h3 { font-size: 1.15rem !important; }
    p, li, .stMarkdown { font-size: 1rem; line-height: 1.7; }
    @media (max-width: 640px) {
        h1 { font-size: 1.3rem !important; }
        h2 { font-size: 1.15rem !important; }
        h3 { font-size: 1.05rem !important; }
        p, li, .stMarkdown { font-size: 0.95rem; }
    }
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #f5f7fa 0%, #e4e8ec 100%);
    }
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #4f46e5 0%, #6366f1 100%) !important;
    }
    [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: #FFFFFF !important;
    }
    h1 { color: #4f46e5 !important; font-weight: 700 !important; font-size: 1.75rem !important; }
    h2, h3 { color: #6366f1 !important; font-weight: 600 !important; }
    /* 手机端标题再缩小，避免两行 */
    @media (max-width: 640px) {
        h1 { font-size: 1.3rem !important; white-space: nowrap; }
        h2 { font-size: 1.15rem !important; }
        h3 { font-size: 1.05rem !important; }
    }
    .stButton > button {
        background: linear-gradient(135deg, #4f46e5 0%, #8b5cf6 100%) !important;
        color: white !important; border: none !important; border-radius: 10px !important;
        font-weight: 600 !important; box-shadow: 0 4px 15px rgba(26, 35, 126, 0.3) !important;
    }
    [data-testid="stMetric"] {
        background: white !important; border-radius: 12px !important; padding: 16px !important;
        box-shadow: 0 2px 12px rgba(26, 35, 126, 0.08) !important;
        border-left: 4px solid #4f46e5 !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("📈 DCF 估值分析系统")
st.caption("基于上市公司年报的自由现金流折现估值模型")
st.markdown(
    "<a href='/' target='_self' style='color:#4f46e5;text-decoration:none;font-size:14px;'>← 返回 MiscHub 首页</a>",
    unsafe_allow_html=True,
)

# 在侧边栏渲染前处理公司名称更新（避免组件实例化后修改 session_state）
if "_pending_company_name" in st.session_state:
    st.session_state.company_name = st.session_state._pending_company_name
    del st.session_state._pending_company_name

# ============ 侧边栏 ============
with st.sidebar:
    st.markdown(
        "<a href='/' target='_self' style='display:block;text-align:center;background:#ffffff;color:#4f46e5;"
        "padding:8px 0;border-radius:8px;text-decoration:none;font-weight:600;'>🧰 返回 MiscHub 首页</a>",
        unsafe_allow_html=True,
    )
    st.header("⚙️ 公司基本信息")
    if "company_name" not in st.session_state:
        st.session_state.company_name = "示例科技"
    company_name = st.text_input("公司名称", key="company_name")
    stock_code = st.text_input("股票代码", value="600000.SH", key="stock_code")

    # 数据抓取
    if st.button("📡 抓取年报数据", use_container_width=True):
        with st.spinner(f"正在抓取 {stock_code} 年报数据..."):
            fetched = fetch_financial_data(stock_code, years=4)
            if fetched.get("error"):
                st.error(f"抓取失败: {fetched['error']}")
            else:
                st.session_state.fetched_data = fetched
                if fetched.get("company_name"):
                    st.session_state._pending_company_name = fetched["company_name"]
                st.success(f"✅ 已抓取 {len(fetched['history'])} 年年报")
                if fetched.get("latest_price"):
                    st.info(f"当前股价: ¥{fetched['latest_price']:.2f}")
                st.rerun()

    fetched_data = st.session_state.get("fetched_data", None)

    # 自动填充抓取的数据
    default_price = 25.0
    default_shares = 10.0
    default_net_debt = 5.0
    default_revenue = 100.0
    default_ebit = 15.0
    default_da = 5.0
    default_capex = 8.0
    default_wc = 20.0

    if fetched_data and fetched_data.get("history"):
        hist = fetched_data["history"]
        latest = hist[0]  # 最近一年作为基期
        default_price = fetched_data.get("latest_price", 25.0) or 25.0
        default_shares = fetched_data.get("shares", 10.0) or 10.0
        default_net_debt = latest.get("净债务(估)", 5.0)
        default_revenue = latest.get("营业收入", 100.0)
        default_ebit = latest.get("EBIT", 15.0)
        default_da = latest.get("折旧摊销(估)", 5.0)
        default_capex = latest.get("资本支出(估)", 8.0)
        default_wc = latest.get("营运资本(估)", 20.0)

        # 显示历史数据
        with st.expander("📋 查看历史财务数据"):
            hist_df = pd.DataFrame(hist)
            st.dataframe(hist_df, width='stretch', hide_index=True)

    current_price = st.number_input("当前股价（元）", value=default_price, step=0.1, format="%.2f")
    shares_outstanding = st.number_input("总股本（亿股）", value=default_shares, step=0.1, format="%.2f")
    net_debt = st.number_input("净债务（亿元，债务-现金）", value=default_net_debt, step=0.1, format="%.2f")

    st.divider()
    st.header("📊 基期财务数据（亿元）")
    base_revenue = st.number_input("基期营业收入", value=default_revenue, step=1.0, format="%.2f")
    base_ebit = st.number_input("基期 EBIT", value=default_ebit, step=1.0, format="%.2f")
    base_da = st.number_input("基期折旧摊销", value=default_da, step=1.0, format="%.2f")
    base_capex = st.number_input("基期资本支出", value=default_capex, step=1.0, format="%.2f")
    base_wc = st.number_input("基期营运资本", value=default_wc, step=1.0, format="%.2f")

    st.divider()
    st.header("📈 WACC 参数")
    risk_free = st.number_input("无风险利率（%）", value=2.5, step=0.1, format="%.2f") / 100
    market_premium = st.number_input("市场风险溢价（%）", value=6.0, step=0.1, format="%.2f") / 100
    beta = st.number_input("Beta", value=1.1, step=0.05, format="%.2f")
    cost_of_debt = st.number_input("债务成本（%）", value=4.5, step=0.1, format="%.2f") / 100
    debt_ratio = st.number_input("债务比例（%）", value=30.0, step=1.0, format="%.2f") / 100
    tax_rate = st.number_input("所得税率（%）", value=25.0, step=1.0, format="%.2f") / 100

    st.divider()
    st.header("🔮 预测假设")
    forecast_years = st.slider("预测年数", 3, 10, 5)

    st.subheader("增长率设置")
    growth_mode = st.radio("增长模式", ["单阶段", "两阶段", "三阶段"], index=1)

    if growth_mode == "单阶段":
        g1 = st.number_input("永续增长率（%）", value=3.0, step=0.5, format="%.2f") / 100
        growth_rates = [g1] * forecast_years
    elif growth_mode == "两阶段":
        g1_years = st.slider("高速增长期年数", 1, forecast_years - 1, 3)
        g1 = st.number_input("高速增长期增长率（%）", value=10.0, step=1.0, format="%.2f") / 100
        g2 = st.number_input("稳定增长率（%）", value=3.0, step=0.5, format="%.2f") / 100
        growth_rates = [g1] * g1_years + [g2] * (forecast_years - g1_years)
    else:  # 三阶段
        g1_years = st.slider("高速增长期", 1, forecast_years - 2, 2)
        g2_years = st.slider("过渡期", 1, forecast_years - g1_years - 1, 2)
        g1 = st.number_input("高速增长期（%）", value=15.0, step=1.0, format="%.2f") / 100
        g2 = st.number_input("过渡期增长率（%）", value=8.0, step=1.0, format="%.2f") / 100
        g3 = st.number_input("稳定增长率（%）", value=3.0, step=0.5, format="%.2f") / 100
        growth_rates = [g1] * g1_years + [g2] * g2_years + [g3] * (forecast_years - g1_years - g2_years)

    # 基于基期数据自动计算默认比率
    default_ebit_margin = (base_ebit / base_revenue * 100) if base_revenue > 0 else 15.0
    default_da_ratio = (base_da / base_revenue * 100) if base_revenue > 0 else 5.0
    default_capex_ratio = (base_capex / base_revenue * 100) if base_revenue > 0 else 8.0
    default_wc_ratio = (base_wc / base_revenue * 100) if base_revenue > 0 else 20.0

    ebit_margin = st.number_input("EBIT利润率（%）", value=round(default_ebit_margin, 2), step=0.5, format="%.2f") / 100
    st.caption(f"基期实际EBIT利润率：{default_ebit_margin:.2f}%")
    da_ratio = st.number_input("折旧摊销/收入（%）", value=round(default_da_ratio, 2), step=0.5, format="%.2f") / 100
    capex_ratio = st.number_input("资本支出/收入（%）", value=round(default_capex_ratio, 2), step=0.5, format="%.2f") / 100
    wc_ratio = st.number_input("营运资本/收入（%）", value=round(default_wc_ratio, 2), step=0.5, format="%.2f") / 100
    terminal_growth = st.number_input("永续增长率（终值）（%）", value=3.0, step=0.5, format="%.2f") / 100

    st.divider()
    run_clicked = st.button("🚀 运行估值分析", type="primary", use_container_width=True)
    if run_clicked:
        st.session_state.ran_base = True
        st.session_state.ran_adjust = False


# ============ 主区域 ============
if st.session_state.get("ran_base", False):
    # 1. 计算 WACC 和基础预测
    with st.spinner("正在运行 DCF 基础预测..."):
        wacc_result = calculate_wacc(risk_free, market_premium, beta,
                                     cost_of_debt, debt_ratio, tax_rate)
        wacc = wacc_result["WACC"]

        # 2. 预测财务数据（初始值，按比例估算）
        fcf_df = project_financials(
            base_revenue, base_ebit, base_da, base_capex, base_wc,
            growth_rates, ebit_margin, da_ratio, capex_ratio,
            wc_ratio, tax_rate, forecast_years
        )

    st.success("✅ 基础预测完成，请在下表微调关键项目后点击【估值微调】")

    # ========== 历史数据对照（供微调参考）==========
    if fetched_data and fetched_data.get("history"):
        st.subheader("📋 历史财务数据（对照）")
        hist_df = pd.DataFrame(fetched_data["history"])
        ordered_cols = ["年份", "营业收入", "EBIT", "归母净利润", "经营现金流",
                        "折旧摊销(估)", "资本支出(估)", "营运资本(估)", "净债务(估)", "资产负债率"]
        display_hist = hist_df[[c for c in ordered_cols if c in hist_df.columns]].copy()
        for col in display_hist.columns:
            if col not in ("年份", "资产负债率"):
                display_hist[col] = display_hist[col].apply(lambda x: f"{x:,.2f}")
        st.dataframe(display_hist, width='stretch', hide_index=True)
        st.markdown("<small>💡 带'(估)'字段为基于收入比例估算，建议根据年报现金流量表/资产负债表手动修正</small>", unsafe_allow_html=True)
        st.divider()

    # ========== 自由现金流预测（基础估算）==========
    st.subheader("🔮 自由现金流预测（基础估算）")
    display_df = fcf_df.copy()
    for col in display_df.columns:
        if col != "预测年度":
            display_df[col] = display_df[col].apply(lambda x: f"{x:,.2f}")
    st.dataframe(display_df, width='stretch', hide_index=True)

    fig, ax = plt.subplots(figsize=(10, 4))
    x = range(len(fcf_df))
    ax.bar(x, fcf_df["自由现金流(FCF)"], color="#4f46e5", alpha=0.8, label="FCF")
    ax2 = ax.twinx()
    ax2.plot(x, fcf_df["营业收入"], color="#e53935", marker="o", linewidth=2, label="营业收入")
    ax.set_xticks(x)
    ax.set_xticklabels(fcf_df["预测年度"])
    ax.set_ylabel("FCF (亿元)")
    ax2.set_ylabel("营业收入 (亿元)")
    ax.legend(loc="upper left")
    ax2.legend(loc="upper right")
    ax.set_title("预测期自由现金流与营业收入")
    plt.tight_layout()
    st.pyplot(fig)

    # ========== 估值微调区域 ==========
    st.divider()
    st.subheader("🔧 估值微调")
    st.markdown("💡 以下三项按收入比例自动估算，如基期存在大额投资/折旧导致后续年份失真，请手动修正：")

    editor_key = "fcf_adjust_editor"
    adjust_cols = ["预测年度", "营业收入", "EBIT", "NOPAT",
                   "加：折旧摊销", "减：资本支出", "减：营运资本增加"]
    adjust_df = fcf_df[adjust_cols].copy()

    edited_df = st.data_editor(
        adjust_df,
        key=editor_key,
        num_rows="fixed",
        disabled=["预测年度", "营业收入", "EBIT", "NOPAT"],
        hide_index=True,
        use_container_width=True,
        column_config={
            "加：折旧摊销": st.column_config.NumberColumn(format="%.2f"),
            "减：资本支出": st.column_config.NumberColumn(format="%.2f"),
            "减：营运资本增加": st.column_config.NumberColumn(format="%.2f"),
        }
    )

    # ========== 估值微调按钮 ==========
    adjust_clicked = st.button("🎯 估值微调", type="primary", use_container_width=True, key="btn_adjust")
    if adjust_clicked:
        st.session_state.ran_adjust = True

    if st.session_state.get("ran_adjust", False):
        with st.spinner("正在用调整后的参数重新计算估值..."):
            # 重新计算 FCF
            adjusted_fcf_df = recalculate_fcf_with_adjustments(
                fcf_df,
                adjusted_da=edited_df["加：折旧摊销"].values,
                adjusted_capex=edited_df["减：资本支出"].values,
                adjusted_wc_change=edited_df["减：营运资本增加"].values
            )

            # DCF 估值
            dcf_result = calculate_dcf_value(adjusted_fcf_df, wacc, terminal_growth,
                                             net_debt, shares_outstanding)

            # 敏感性分析
            wacc_range = [wacc - 0.02, wacc - 0.01, wacc, wacc + 0.01, wacc + 0.02]
            g_range = [terminal_growth - 0.01, terminal_growth, terminal_growth + 0.01]
            sens_df = sensitivity_analysis(
                {"fcf_df": adjusted_fcf_df, "net_debt": net_debt, "shares_outstanding": shares_outstanding},
                wacc_range, g_range
            )

        st.success("✅ 估值微调完成！")

        # ========== 关键指标 ==========
        st.header(f"📌 {company_name} ({stock_code}) 估值结果")
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.metric("每股内在价值", f"¥{dcf_result['每股价值']:.2f}")
        with c2:
            st.metric("当前股价", f"¥{current_price:.2f}")
        with c3:
            upside = (dcf_result['每股价值'] / current_price - 1) if current_price > 0 else 0
            st.metric("上涨空间", f"{upside:.1%}", delta_color="inverse")
        with c4:
            st.metric("企业价值", f"¥{dcf_result['企业价值']:.1f}亿")
        with c5:
            st.metric("WACC", f"{wacc:.2%}")

        # ========== 估值详情 ==========
        tab1, tab2, tab3, tab4 = st.tabs(["预测现金流", "WACC计算", "估值详情", "敏感性分析"])

        with tab1:
            st.subheader("调整后的自由现金流预测")
            display_adj = adjusted_fcf_df.copy()
            for col in display_adj.columns:
                if col != "预测年度":
                    display_adj[col] = display_adj[col].apply(lambda x: f"{x:,.2f}")
            st.dataframe(display_adj, width='stretch', hide_index=True)

            fig, ax = plt.subplots(figsize=(10, 4))
            x = range(len(adjusted_fcf_df))
            ax.bar(x, adjusted_fcf_df["自由现金流(FCF)"], color="#4f46e5", alpha=0.8, label="FCF")
            ax2 = ax.twinx()
            ax2.plot(x, adjusted_fcf_df["营业收入"], color="#e53935", marker="o", linewidth=2, label="营业收入")
            ax.set_xticks(x)
            ax.set_xticklabels(adjusted_fcf_df["预测年度"])
            ax.set_ylabel("FCF (亿元)")
            ax2.set_ylabel("营业收入 (亿元)")
            ax.legend(loc="upper left")
            ax2.legend(loc="upper right")
            ax.set_title("预测期自由现金流与营业收入（调整后）")
            plt.tight_layout()
            st.pyplot(fig)

        with tab2:
            st.subheader("WACC 计算明细")
            wacc_display = pd.DataFrame([{
                "无风险利率": f"{risk_free:.2%}",
                "市场风险溢价": f"{market_premium:.2%}",
                "Beta": beta,
                "股权成本": f"{wacc_result['股权成本']:.2%}",
                "债务成本(税前)": f"{cost_of_debt:.2%}",
                "债务比例": f"{debt_ratio:.1%}",
                "税率": f"{tax_rate:.1%}",
                "WACC": f"{wacc:.2%}",
            }])
            st.dataframe(wacc_display, width='stretch', hide_index=True)

            fig2, ax2 = plt.subplots(figsize=(6, 4))
            labels = ["股权成本", "债务成本(税后)"]
            sizes = [wacc_result['股权成本'] * (1 - debt_ratio), wacc_result['债务成本(税后)'] * debt_ratio]
            colors = ["#4f46e5", "#a78bfa"]
            ax2.pie(sizes, labels=labels, colors=colors, autopct="%1.1f%%", startangle=90)
            ax2.set_title("WACC 构成")
            plt.tight_layout()
            st.pyplot(fig2)

        with tab3:
            st.subheader("DCF 估值明细")
            detail = pd.DataFrame({
                "项目": ["预测期FCF现值", "终值", "终值现值", "企业价值", "减：净债务", "股权价值", "总股本（亿股）", "每股内在价值"],
                "金额": [f"{dcf_result['预测期FCF现值']:,.2f}",
                        f"{dcf_result['终值']:,.2f}",
                        f"{dcf_result['终值现值']:,.2f}",
                        f"{dcf_result['企业价值']:,.2f}",
                        f"{dcf_result['净债务']:,.2f}",
                        f"{dcf_result['股权价值']:,.2f}",
                        f"{dcf_result['总股本']:,.2f}",
                        f"¥{dcf_result['每股价值']:,.2f}/股"],
                "说明": ["各年FCF折现求和", f"FCF_n×(1+g)/(WACC-g)", "终值折现到当前",
                        "PV(FCF)+PV(终值)", "债务-现金", "企业价值-净债务", "", ""],
            })
            st.dataframe(detail, width='stretch', hide_index=True)

        with tab4:
            st.subheader("敏感性分析：每股价值")
            st.markdown(f"<small>基准情景：WACC={wacc:.2%}, 永续增长率={terminal_growth:.2%}</small>", unsafe_allow_html=True)
            st.dataframe(sens_df.style.background_gradient(cmap="RdYlGn", axis=None), width='stretch')

            fig3, ax3 = plt.subplots(figsize=(8, 5))
            im = ax3.imshow(sens_df.values, cmap="RdYlGn", aspect="auto")
            ax3.set_xticks(range(len(sens_df.columns)))
            ax3.set_yticks(range(len(sens_df.index)))
            ax3.set_xticklabels(sens_df.columns)
            ax3.set_yticklabels(sens_df.index)
            for i in range(len(sens_df.index)):
                for j in range(len(sens_df.columns)):
                    ax3.text(j, i, f"{sens_df.iloc[i, j]:.2f}", ha="center", va="center", color="black", fontsize=10)
            ax3.set_title("敏感性分析：WACC vs 永续增长率")
            plt.colorbar(im, ax=ax3, label="每股价值（元）")
            plt.tight_layout()
            st.pyplot(fig3)

        # ========== 导出估值报告 ==========
        st.divider()
        st.subheader("📥 导出估值报告")

        # 样式工具函数
        def _h(ws, r, c1, c2):
            for c in range(c1, c2 + 1):
                cell = ws.cell(row=r, column=c)
                cell.font = Font(bold=True, color="FFFFFF", size=11, name="微软雅黑")
                cell.fill = PatternFill(start_color="1A237E", end_color="1A237E", fill_type="solid")
                cell.alignment = Alignment(horizontal="center", vertical="center")
                cell.border = Border(left=Side(style='thin', color="CCCCCC"),
                                    right=Side(style='thin', color="CCCCCC"),
                                    top=Side(style='thin', color="CCCCCC"),
                                    bottom=Side(style='thin', color="CCCCCC"))

        def _d(ws, r, c1, c2, num=True):
            for c in range(c1, c2 + 1):
                cell = ws.cell(row=r, column=c)
                cell.font = Font(size=10, name="微软雅黑")
                cell.alignment = Alignment(horizontal="right" if num else "left", vertical="center")
                cell.border = Border(left=Side(style='thin', color="CCCCCC"),
                                    right=Side(style='thin', color="CCCCCC"),
                                    top=Side(style='thin', color="CCCCCC"),
                                    bottom=Side(style='thin', color="CCCCCC"))
                if num:
                    cell.number_format = '#,##0.00'

        def _k(ws, r, c1, c2):
            for c in range(c1, c2 + 1):
                cell = ws.cell(row=r, column=c)
                cell.font = Font(bold=True, size=11, color="1A237E", name="微软雅黑")
                cell.fill = PatternFill(start_color="E8EAF6", end_color="E8EAF6", fill_type="solid")
                cell.alignment = Alignment(horizontal="right", vertical="center")
                cell.border = Border(left=Side(style='thin', color="CCCCCC"),
                                    right=Side(style='thin', color="CCCCCC"),
                                    top=Side(style='thin', color="CCCCCC"),
                                    bottom=Side(style='thin', color="CCCCCC"))
                cell.number_format = '#,##0.00'

        def _w(ws):
            for col in ws.columns:
                max_len = 0
                letter = get_column_letter(col[0].column)
                for cell in col:
                    try:
                        if cell.value:
                            max_len = max(max_len, len(str(cell.value)))
                    except:
                        pass
                ws.column_dimensions[letter].width = min(max_len + 2, 30)

        wb = Workbook()
        ny = forecast_years

        # ===== Sheet 1: 估值摘要 =====
        ws1 = wb.active
        ws1.title = "估值摘要"
        ws1.merge_cells("A1:B1")
        ws1["A1"] = f"{company_name} ({stock_code}) DCF 估值摘要"
        ws1["A1"].font = Font(bold=True, size=14, color="1A237E", name="微软雅黑")
        ws1["A1"].alignment = Alignment(horizontal="center", vertical="center")
        ws1.row_dimensions[1].height = 30

        items = [
            ["公司名称", company_name],
            ["股票代码", stock_code],
            ["当前股价（元）", current_price],
            ["每股内在价值（元）", dcf_result['每股价值']],
            ["上涨空间", f"{(dcf_result['每股价值']/current_price-1):.1%}" if current_price > 0 else "N/A"],
            ["企业价值（亿元）", dcf_result['企业价值']],
            ["股权价值（亿元）", dcf_result['股权价值']],
            ["WACC", wacc],
            ["永续增长率", terminal_growth],
            ["总股本（亿股）", shares_outstanding],
            ["净债务（亿元）", net_debt],
        ]
        for i, (k, v) in enumerate(items, 3):
            ws1.append([k, v])
            _d(ws1, i, 1, 2, num=False)
            ws1.cell(row=i, column=1).alignment = Alignment(horizontal="left", vertical="center")
            ws1.cell(row=i, column=2).alignment = Alignment(horizontal="right", vertical="center")
            if isinstance(v, (int, float)):
                ws1.cell(row=i, column=2).number_format = '#,##0.00'
        _k(ws1, 6, 1, 2)
        _k(ws1, 7, 1, 2)
        _w(ws1)

        # ===== Sheet 2: 历史财务数据 =====
        if fetched_data and fetched_data.get("history"):
            ws2 = wb.create_sheet("历史财务数据")
            hist = pd.DataFrame(fetched_data["history"])
            # 用简单方式写入
            hdr = list(hist.columns)
            for j, h in enumerate(hdr, 1):
                ws2.cell(row=1, column=j, value=h)
            _h(ws2, 1, 1, len(hdr))
            for i, row in hist.iterrows():
                for j, v in enumerate(row, 1):
                    ws2.cell(row=i+2, column=j, value=v)
                _d(ws2, i+2, 1, len(hdr), num=True)
                ws2.cell(row=i+2, column=1).alignment = Alignment(horizontal="center", vertical="center")
            _w(ws2)

        # ===== Sheet 3: FCF预测(基础) =====
        ws3 = wb.create_sheet("FCF预测(基础)")
        ws3.merge_cells("A1:J1")
        ws3["A1"] = "自由现金流预测（基础估算）"
        ws3["A1"].font = Font(bold=True, size=14, color="1A237E", name="微软雅黑")
        ws3["A1"].alignment = Alignment(horizontal="center", vertical="center")
        ws3.row_dimensions[1].height = 28

        params = [
            ["参数", "数值"],
            ["基期营业收入", base_revenue],
            ["EBIT利润率", ebit_margin],
            ["税率", tax_rate],
            ["折旧摊销/收入", da_ratio],
            ["资本支出/收入", capex_ratio],
            ["营运资本/收入", wc_ratio],
            ["基期营运资本", base_wc],
        ]
        for i, row in enumerate(params, 3):
            for j, v in enumerate(row, 1):
                ws3.cell(row=i, column=j, value=v)
            if i == 3:
                _h(ws3, i, 1, 2)
            else:
                _d(ws3, i, 1, 2, num=True)
                ws3.cell(row=i, column=1).alignment = Alignment(horizontal="left", vertical="center")
                ws3.cell(row=i, column=2).number_format = '0.00%'

        hdr = ["预测年度", "营业收入", "EBIT", "归母净利润", "NOPAT",
               "加：折旧摊销", "减：资本支出", "营运资本(绝对额)",
               "减：营运资本增加", "自由现金流(FCF)"]
        for j, h in enumerate(hdr, 1):
            ws3.cell(row=11, column=j, value=h)
        _h(ws3, 11, 1, 10)

        for i, row in fcf_df.iterrows():
            r = 12 + i
            ws3.cell(row=r, column=1, value=row["预测年度"])
            ws3.cell(row=r, column=2, value=row["营业收入"])
            ws3.cell(row=r, column=3, value=f"=B{r}*$B$5")
            ws3.cell(row=r, column=4, value=f"=E{r}")
            ws3.cell(row=r, column=5, value=f"=C{r}*(1-$B$6)")
            ws3.cell(row=r, column=6, value=f"=B{r}*$B$7")
            ws3.cell(row=r, column=7, value=f"=B{r}*$B$8")
            ws3.cell(row=r, column=8, value=f"=B{r}*$B$9")
            if i == 0:
                ws3.cell(row=r, column=9, value=f"=H{r}-$B$10")
            else:
                ws3.cell(row=r, column=9, value=f"=H{r}-H{r-1}")
            ws3.cell(row=r, column=10, value=f"=E{r}+F{r}-G{r}-I{r}")
            _d(ws3, r, 1, 10, num=True)
            ws3.cell(row=r, column=1).alignment = Alignment(horizontal="center", vertical="center")
        _w(ws3)

        # ===== Sheet 4: FCF预测(调整后) =====
        ws4 = wb.create_sheet("FCF预测(调整后)")
        ws4.merge_cells("A1:I1")
        ws4["A1"] = "自由现金流预测（用户微调后）"
        ws4["A1"].font = Font(bold=True, size=14, color="1A237E", name="微软雅黑")
        ws4["A1"].alignment = Alignment(horizontal="center", vertical="center")
        ws4.row_dimensions[1].height = 28

        params2 = [
            ["参数", "数值"],
            ["EBIT利润率", ebit_margin],
            ["税率", tax_rate],
        ]
        for i, row in enumerate(params2, 3):
            for j, v in enumerate(row, 1):
                ws4.cell(row=i, column=j, value=v)
            if i == 3:
                _h(ws4, i, 1, 2)
            else:
                _d(ws4, i, 1, 2, num=True)
                ws4.cell(row=i, column=1).alignment = Alignment(horizontal="left", vertical="center")
                ws4.cell(row=i, column=2).number_format = '0.00%'

        hdr2 = ["预测年度", "营业收入", "EBIT", "归母净利润", "NOPAT",
                "加：折旧摊销", "减：资本支出", "减：营运资本增加", "自由现金流(FCF)"]
        for j, h in enumerate(hdr2, 1):
            ws4.cell(row=6, column=j, value=h)
        _h(ws4, 6, 1, 9)

        for i, row in adjusted_fcf_df.iterrows():
            r = 7 + i
            ws4.cell(row=r, column=1, value=row["预测年度"])
            ws4.cell(row=r, column=2, value=row["营业收入"])
            ws4.cell(row=r, column=3, value=f"=B{r}*$B$4")
            ws4.cell(row=r, column=4, value=f"=E{r}")
            ws4.cell(row=r, column=5, value=f"=C{r}*(1-$B$5)")
            ws4.cell(row=r, column=6, value=row["加：折旧摊销"])
            ws4.cell(row=r, column=7, value=row["减：资本支出"])
            ws4.cell(row=r, column=8, value=row["减：营运资本增加"])
            ws4.cell(row=r, column=9, value=f"=E{r}+F{r}-G{r}-H{r}")
            _d(ws4, r, 1, 9, num=True)
            ws4.cell(row=r, column=1).alignment = Alignment(horizontal="center", vertical="center")
        _w(ws4)

        # ===== Sheet 5: WACC计算 =====
        ws5 = wb.create_sheet("WACC计算")
        ws5.merge_cells("A1:C1")
        ws5["A1"] = "WACC 计算明细"
        ws5["A1"].font = Font(bold=True, size=14, color="1A237E", name="微软雅黑")
        ws5["A1"].alignment = Alignment(horizontal="center", vertical="center")
        ws5.row_dimensions[1].height = 28

        wacc_items = [
            ["参数", "数值", "公式说明"],
            ["无风险利率", risk_free, ""],
            ["市场风险溢价", market_premium, ""],
            ["Beta", beta, ""],
            ["股权成本", None, "Rf + β × ERP"],
            ["债务成本(税前)", cost_of_debt, ""],
            ["税率", tax_rate, ""],
            ["债务成本(税后)", None, "Kd × (1-T)"],
            ["债务比例", debt_ratio, ""],
            ["股权比例", None, "1 - 债务比例"],
            ["WACC", None, "E/V×Ke + D/V×Kd(1-T)"],
        ]
        for i, row in enumerate(wacc_items, 3):
            for j, v in enumerate(row, 1):
                ws5.cell(row=i, column=j, value=v)
            if i == 3:
                _h(ws5, i, 1, 3)
            else:
                _d(ws5, i, 1, 3, num=False)
                ws5.cell(row=i, column=1).alignment = Alignment(horizontal="left", vertical="center")
                ws5.cell(row=i, column=2).alignment = Alignment(horizontal="right", vertical="center")
                ws5.cell(row=i, column=3).alignment = Alignment(horizontal="left", vertical="center")
                ws5.cell(row=i, column=2).number_format = '0.00%'

        ws5.cell(row=7, column=2, value="=B4+B6*B5")
        ws5.cell(row=10, column=2, value="=B8*(1-B9)")
        ws5.cell(row=12, column=2, value="=1-B11")
        ws5.cell(row=13, column=2, value="=B12*B7+B11*B10")
        _k(ws5, 7, 1, 3)
        _k(ws5, 10, 1, 3)
        _k(ws5, 13, 1, 3)
        _w(ws5)

        # ===== Sheet 6: DCF估值明细 =====
        ws6 = wb.create_sheet("DCF估值明细")
        ws6.merge_cells("A1:E1")
        ws6["A1"] = "DCF 估值明细"
        ws6["A1"].font = Font(bold=True, size=14, color="1A237E", name="微软雅黑")
        ws6["A1"].alignment = Alignment(horizontal="center", vertical="center")
        ws6.row_dimensions[1].height = 28

        ws6.append(["参数", "数值"])
        ws6.append(["永续增长率", terminal_growth])
        _h(ws6, 3, 1, 2)
        _d(ws6, 4, 1, 2, num=True)
        ws6.cell(row=4, column=1).alignment = Alignment(horizontal="left", vertical="center")
        ws6.cell(row=4, column=2).number_format = '0.00%'

        ws6.append([])
        ws6.append(["项目", "金额", "年数", "折现因子", "现值"])
        _h(ws6, 6, 1, 5)

        fcf_start = 7
        for i in range(ny):
            r = fcf_start + i
            ws6.cell(row=r, column=1, value=f"第{i+1}年FCF")
            ws6.cell(row=r, column=2, value=f"='FCF预测(调整后)'!I{7+i}")
            ws6.cell(row=r, column=3, value=i+1)
            ws6.cell(row=r, column=4, value=f"=(1+'WACC计算'!$B$13)^(C{r}-0.5)")
            ws6.cell(row=r, column=5, value=f"=B{r}/D{r}")
            _d(ws6, r, 1, 5, num=True)
            ws6.cell(row=r, column=1).alignment = Alignment(horizontal="left", vertical="center")
            ws6.cell(row=r, column=3).alignment = Alignment(horizontal="center", vertical="center")

        sum_r = fcf_start + ny
        ws6.cell(row=sum_r, column=1, value="预测期FCF现值合计")
        ws6.cell(row=sum_r, column=5, value=f"=SUM(E{fcf_start}:E{fcf_start+ny-1})")
        _k(ws6, sum_r, 1, 5)

        tv_r = sum_r + 2
        last_fcf_r = fcf_start + ny - 1
        ws6.cell(row=tv_r, column=1, value="终值")
        ws6.cell(row=tv_r, column=2, value=f"=B{last_fcf_r}*(1+$B$3)/('WACC计算'!$B$13-$B$3)")
        ws6.cell(row=tv_r, column=5, value=f"=B{tv_r}/D{last_fcf_r}")
        _d(ws6, tv_r, 1, 5, num=True)
        ws6.cell(row=tv_r, column=1).alignment = Alignment(horizontal="left", vertical="center")

        ev_r = tv_r + 1
        ws6.cell(row=ev_r, column=1, value="企业价值")
        ws6.cell(row=ev_r, column=5, value=f"=E{sum_r}+E{tv_r}")
        _k(ws6, ev_r, 1, 5)

        nd_r = ev_r + 1
        ws6.cell(row=nd_r, column=1, value="减：净债务")
        ws6.cell(row=nd_r, column=2, value=net_debt)
        _d(ws6, nd_r, 1, 5, num=True)
        ws6.cell(row=nd_r, column=1).alignment = Alignment(horizontal="left", vertical="center")

        eq_r = nd_r + 1
        ws6.cell(row=eq_r, column=1, value="股权价值")
        ws6.cell(row=eq_r, column=5, value=f"=E{ev_r}-B{nd_r}")
        _k(ws6, eq_r, 1, 5)

        sh_r = eq_r + 1
        ws6.cell(row=sh_r, column=1, value="总股本（亿股）")
        ws6.cell(row=sh_r, column=2, value=shares_outstanding)
        _d(ws6, sh_r, 1, 5, num=True)
        ws6.cell(row=sh_r, column=1).alignment = Alignment(horizontal="left", vertical="center")

        ps_r = sh_r + 1
        ws6.cell(row=ps_r, column=1, value="每股内在价值")
        ws6.cell(row=ps_r, column=5, value=f"=E{eq_r}/B{sh_r}")
        _k(ws6, ps_r, 1, 5)
        _w(ws6)

        # ===== Sheet 7: 敏感性分析 =====
        ws7 = wb.create_sheet("敏感性分析")
        ws7.merge_cells(f"A1:{get_column_letter(len(sens_df.columns)+1)}1")
        ws7["A1"] = "敏感性分析：每股价值（WACC vs 永续增长率）"
        ws7["A1"].font = Font(bold=True, size=14, color="1A237E", name="微软雅黑")
        ws7["A1"].alignment = Alignment(horizontal="center", vertical="center")
        ws7.row_dimensions[1].height = 28

        # 表头
        ws7.cell(row=3, column=1, value=r"WACC \ 永续增长率")
        for j, col in enumerate(sens_df.columns, 2):
            ws7.cell(row=3, column=j, value=col)
        _h(ws7, 3, 1, len(sens_df.columns)+1)

        for i, (idx, row) in enumerate(sens_df.iterrows(), 4):
            ws7.cell(row=i, column=1, value=idx)
            for j, v in enumerate(row, 2):
                ws7.cell(row=i, column=j, value=v)
            _d(ws7, i, 1, len(sens_df.columns)+1, num=True)
            ws7.cell(row=i, column=1).alignment = Alignment(horizontal="left", vertical="center")
        _w(ws7)

        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        file_name = f"{company_name}_{stock_code}_DCF估值报告.xlsx".replace(" ", "_")
        dl("📥 下载估值报告 (Excel)", output.getvalue(), file_name)

else:
    st.info("👈 请在左侧输入公司财务数据和预测假设，然后点击 **🚀 运行估值分析**")
    st.markdown("""
    ### 📖 使用说明

    **1. 输入公司基本信息**
    - 公司名称、股票代码、当前股价、总股本、净债务

    **2. 输入基期财务数据**
    - 基期营业收入、EBIT、折旧摊销、资本支出、营运资本

    **3. 设置 WACC 参数**
    - 无风险利率、市场风险溢价、Beta、债务成本、债务比例、税率

    **4. 设定预测假设**
    - 选择增长模式（单阶段/两阶段/三阶段）
    - 设置各阶段增长率、利润率、资本支出比例等

    **5. 运行分析**
    - 系统自动计算 WACC、预测自由现金流、折现估值
    - 输出每股内在价值、上涨空间、敏感性分析矩阵
    """)
