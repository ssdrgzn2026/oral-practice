# -*- coding: utf-8 -*-
"""
DCF 估值分析引擎
支持两阶段/三阶段增长模型
"""
import pandas as pd
import numpy as np


def calculate_wacc(risk_free_rate, market_risk_premium, beta,
                   cost_of_debt, debt_ratio, tax_rate):
    """
    计算 WACC（加权平均资本成本）
    """
    equity_ratio = 1 - debt_ratio
    cost_of_equity = risk_free_rate + beta * market_risk_premium
    wacc = equity_ratio * cost_of_equity + debt_ratio * cost_of_debt * (1 - tax_rate)
    return {
        "股权成本": cost_of_equity,
        "债务成本(税后)": cost_of_debt * (1 - tax_rate),
        "WACC": wacc,
    }


def project_financials(base_revenue, base_ebit, base_da, base_capex,
                       base_working_capital,
                       growth_rates, ebit_margin, da_ratio, capex_ratio,
                       working_capital_ratio, tax_rate, forecast_years=5):
    """
    预测未来财务数据并计算自由现金流
    Args:
        base_revenue: 基期营业收入
        base_ebit: 基期EBIT
        base_da: 基期折旧摊销
        base_capex: 基期资本支出
        base_working_capital: 基期营运资本
        growth_rates: 增长率列表（每年一个，或最后一年用于后续）
        ebit_margin: EBIT利润率（小数）
        da_ratio: 折旧摊销/收入比（小数）
        capex_ratio: 资本支出/收入比（小数）
        working_capital_ratio: 营运资本/收入比（小数）
        tax_rate: 税率（小数）
        forecast_years: 预测年数
    Returns:
        DataFrame: 分年度预测数据
    """
    years = list(range(1, forecast_years + 1))
    revenues = []
    ebits = []
    nopats = []
    net_profits = []
    das = []
    capexes = []
    wc_changes = []
    fcfs = []

    prev_revenue = base_revenue
    prev_wc = base_working_capital

    for i, year in enumerate(years):
        g = growth_rates[min(i, len(growth_rates) - 1)]
        revenue = prev_revenue * (1 + g)
        ebit = revenue * ebit_margin
        nopat = ebit * (1 - tax_rate)
        da = revenue * da_ratio
        capex = revenue * capex_ratio
        wc = revenue * working_capital_ratio
        wc_change = wc - prev_wc
        fcf = nopat + da - capex - wc_change

        revenues.append(revenue)
        ebits.append(ebit)
        nopats.append(nopat)
        net_profits.append(nopat)  # 简化为 NOPAT，作为归母净利润近似
        das.append(da)
        capexes.append(capex)
        wc_changes.append(wc_change)
        fcfs.append(fcf)

        prev_revenue = revenue
        prev_wc = wc

    df = pd.DataFrame({
        "预测年度": [f"第{y}年" for y in years],
        "营业收入": revenues,
        "EBIT": ebits,
        "归母净利润": net_profits,
        "NOPAT": nopats,
        "加：折旧摊销": das,
        "减：资本支出": capexes,
        "减：营运资本增加": wc_changes,
        "自由现金流(FCF)": fcfs,
    })
    return df


def calculate_dcf_value(fcf_df, wacc, terminal_growth, net_debt, shares_outstanding):
    """
    计算 DCF 估值
    Args:
        fcf_df: project_financials 返回的 DataFrame
        wacc: WACC（小数）
        terminal_growth: 永续增长率（小数）
        net_debt: 净债务（债务 - 现金）
        shares_outstanding: 总股本（万股或亿股）
    Returns:
        dict: 估值结果
    """
    fcfs = fcf_df["自由现金流(FCF)"].values
    n = len(fcfs)

    # 折现因子
    discount_factors = [(1 + wacc) ** (i + 0.5) for i in range(n)]
    # 年中折现（假设现金流在年中发生）

    # 各期FCF现值
    pv_fcfs = [fcfs[i] / discount_factors[i] for i in range(n)]

    # 终值
    terminal_fcf = fcfs[-1] * (1 + terminal_growth)
    terminal_value = terminal_fcf / (wacc - terminal_growth)
    pv_terminal = terminal_value / discount_factors[-1]

    # 企业价值和股权价值
    enterprise_value = sum(pv_fcfs) + pv_terminal
    equity_value = enterprise_value - net_debt
    per_share_value = equity_value / shares_outstanding if shares_outstanding > 0 else 0

    return {
        "预测期FCF现值": sum(pv_fcfs),
        "终值": terminal_value,
        "终值现值": pv_terminal,
        "企业价值": enterprise_value,
        "净债务": net_debt,
        "股权价值": equity_value,
        "总股本": shares_outstanding,
        "每股价值": per_share_value,
        "WACC": wacc,
        "永续增长率": terminal_growth,
        "各期PV": pv_fcfs,
    }


def sensitivity_analysis(base_params, wacc_range, terminal_growth_range):
    """
    敏感性分析：WACC × 永续增长率的二维表格
    Args:
        base_params: 基础参数字典，包含计算DCF所需的所有参数
        wacc_range: WACC取值列表
        terminal_growth_range: 永续增长率取值列表
    Returns:
        DataFrame: 敏感性分析矩阵（每股价值）
    """
    matrix = []
    for g in terminal_growth_range:
        row = []
        for w in wacc_range:
            result = calculate_dcf_value(
                base_params["fcf_df"], w, g,
                base_params["net_debt"], base_params["shares_outstanding"]
            )
            row.append(result["每股价值"])
        matrix.append(row)

    df = pd.DataFrame(matrix,
                      index=[f"g={g:.1%}" for g in terminal_growth_range],
                      columns=[f"WACC={w:.1%}" for w in wacc_range])
    return df


def recalculate_fcf_with_adjustments(base_df, adjusted_da=None,
                                                      adjusted_capex=None,
                                                      adjusted_wc_change=None):
    """
    在用户调整折旧摊销、资本支出、营运资本增加后重新计算 FCF
    Args:
        base_df: project_financials 返回的 DataFrame
        adjusted_da: 调整后的折旧摊销序列（可选）
        adjusted_capex: 调整后的资本支出序列（可选）
        adjusted_wc_change: 调整后的营运资本增加序列（可选）
    Returns:
        DataFrame: 重新计算后的预测数据
    """
    df = base_df.copy()
    if adjusted_da is not None:
        df["加：折旧摊销"] = adjusted_da
    if adjusted_capex is not None:
        df["减：资本支出"] = adjusted_capex
    if adjusted_wc_change is not None:
        df["减：营运资本增加"] = adjusted_wc_change

    df["自由现金流(FCF)"] = (
        df["NOPAT"] + df["加：折旧摊销"]
        - df["减：资本支出"] - df["减：营运资本增加"]
    )
    return df


def build_full_report(historical_df, fcf_df, wacc_result, dcf_result,
                      current_price=None):
    """
    组装完整估值报告
    """
    report = {
        "历史财务数据": historical_df,
        "预测财务数据": fcf_df,
        "WACC计算": pd.DataFrame([wacc_result]),
        "估值结果": pd.DataFrame([{
            "企业价值": dcf_result["企业价值"],
            "股权价值": dcf_result["股权价值"],
            "每股内在价值": dcf_result["每股价值"],
            "当前股价": current_price if current_price else np.nan,
            "上涨/下跌空间": (dcf_result["每股价值"] / current_price - 1) if current_price else np.nan,
        }]),
    }
    return report
