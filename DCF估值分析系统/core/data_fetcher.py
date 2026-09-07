# -*- coding: utf-8 -*-
"""
A股数据抓取模块
基于 akshare 获取上市公司年报数据和实时行情
"""
import pandas as pd


def _normalize_code(stock_code):
    """标准化股票代码"""
    code = stock_code.strip().upper().replace(".SH", "").replace(".SZ", "").replace(".BJ", "")
    return code


def _safe_float(val):
    """安全转换数值"""
    if val is None or pd.isna(val):
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        return 0.0


def fetch_financial_data(stock_code, years=4):
    """
    抓取上市公司历史财务数据和实时行情
    """
    try:
        import akshare as ak
    except ImportError:
        return {"error": "请先安装 akshare: pip install akshare"}

    code = _normalize_code(stock_code)
    result = {
        "stock_code": code,
        "history": [],
        "latest_price": None,
        "shares": None,
        "company_name": None,
        "error": None,
    }

    try:
        # 1. 财务摘要（历史数据）- 通常0.5-1秒
        try:
            abstract_df = ak.stock_financial_abstract(symbol=code)
        except Exception as e:
            result["error"] = f"财务数据接口调用失败: {str(e)}"
            return result

        if abstract_df is None or abstract_df.empty or abstract_df.shape[1] < 3:
            result["error"] = "未找到该股票的财务数据，请检查股票代码是否正确"
            return result

        # 列名：第0列指标类型，第1列指标名称，第2列开始是报告期
        report_cols = abstract_df.columns.tolist()[2:]
        # 过滤年度数据（列名以1231结尾）
        yearly_cols = [c for c in report_cols if str(c).endswith("1231")]
        yearly_cols = yearly_cols[:years]

        if not yearly_cols:
            result["error"] = "未找到年度财务数据"
            return result

        for col in yearly_cols:
            year_str = str(col)[:4]
            try:
                # 营业总收入（亿元）- Row 1
                revenue_raw = abstract_df.iloc[1][col] if abstract_df.shape[0] > 1 else 0
                revenue = _safe_float(revenue_raw) / 1e8

                # 息税前利润率 → 计算 EBIT（亿元）- Row 39
                ebit_margin_raw = abstract_df.iloc[39][col] if abstract_df.shape[0] > 39 else 0
                ebit_margin_val = _safe_float(ebit_margin_raw)
                ebit_margin = ebit_margin_val / 100 if ebit_margin_val > 1 else ebit_margin_val
                ebit = revenue * ebit_margin

                # 归母净利润（亿元，Row 0）
                net_profit_raw = abstract_df.iloc[0][col] if abstract_df.shape[0] > 0 else 0
                net_profit = _safe_float(net_profit_raw) / 1e8

                # 经营现金流（亿元，Row 7）
                op_cashflow_raw = abstract_df.iloc[7][col] if abstract_df.shape[0] > 7 else 0
                op_cashflow = _safe_float(op_cashflow_raw) / 1e8

                # 资产负债率（Row 16）
                debt_ratio_raw = abstract_df.iloc[16][col] if abstract_df.shape[0] > 16 else 0
                debt_ratio_val = _safe_float(debt_ratio_raw)
                debt_ratio = debt_ratio_val / 100 if debt_ratio_val > 1 else debt_ratio_val

                # 估算值（基于行业平均，用户抓取后可手动调整）
                da = revenue * 0.04
                capex = revenue * 0.06
                wc = revenue * 0.18
                total_assets = revenue if revenue > 0 else 1
                total_liab = total_assets * debt_ratio
                cash = revenue * 0.05
                net_debt = total_liab - cash

                result["history"].append({
                    "年份": year_str,
                    "营业收入": round(revenue, 2),
                    "EBIT": round(ebit, 2),
                    "归母净利润": round(net_profit, 2),
                    "经营现金流": round(op_cashflow, 2),
                    "折旧摊销(估)": round(da, 2),
                    "资本支出(估)": round(capex, 2),
                    "营运资本(估)": round(wc, 2),
                    "净债务(估)": round(net_debt, 2),
                    "资产负债率": f"{debt_ratio:.1%}",
                })
            except Exception:
                continue

        if not result["history"]:
            result["error"] = "未能解析出有效的年度财务数据"
            return result

        # 2. 个股信息（总股本、市值、行业）- 通常0.3-0.5秒
        try:
            info_df = ak.stock_individual_info_em(symbol=code)
            if info_df is not None and not info_df.empty:
                info_dict = dict(zip(info_df.iloc[:, 0], info_df.iloc[:, 1]))
                total_shares = _safe_float(info_dict.get("总股本", 0))
                total_mv = _safe_float(info_dict.get("总市值", 0))
                result["shares"] = total_shares / 1e8 if total_shares > 0 else None
                result["latest_price"] = total_mv / total_shares if total_shares > 0 else 0
                result["company_name"] = str(info_dict.get("股票简称", code))
        except Exception:
            pass

    except Exception as e:
        result["error"] = f"数据抓取失败: {str(e)}"

    return result
