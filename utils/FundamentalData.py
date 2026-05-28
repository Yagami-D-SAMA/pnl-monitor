from __future__ import annotations
import os
import requests
os.environ["API_NINJAS_KEY"] = '4OSuOff0mb8jwkCfYYKkSWVu61OJFAIsYThjdfnm'
import time
from typing import Any, Iterable
import pandas as pd

API_NINJAS_BASE = "https://api.api-ninjas.com/v1"
DEFAULT_TIMEOUT = 30
def get_api_key() -> str:
    key = os.getenv("API_NINJAS_KEY")
    if not key:
        raise RuntimeError("请设置环境变量 API_NINJAS_KEY")
    return key
def api_ninjas_get(
    endpoint: str,
    params: dict[str, Any] | None = None,
    *,
    api_key: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict[str, Any] | list[Any] | None:
    """
    通用 GET。endpoint 如 'earnings'、'marketcap'（不要带前导 /）。
    成功返回 JSON；404/无数据返回 None；其它 HTTP 错误抛异常。
    """
    api_key = api_key or get_api_key()
    url = f"{API_NINJAS_BASE}/{endpoint.lstrip('/')}"
    headers = {"X-Api-Key": api_key}
    resp = requests.get(url, headers=headers, params=params or {}, timeout=timeout)
    if resp.status_code == 404:
        return None
    if resp.status_code == 429:
        raise RuntimeError(f"API Ninjas 限流: {resp.text[:200]}")
    resp.raise_for_status()
    return resp.json()
def fetch_earnings(
    ticker: str,
    *,
    year: int | None = None,
    period: str | None = None,  # q1|q2|q3|q4|fy
    api_key: str | None = None,
) -> dict[str, Any] | None:
    """
  单票 earnings。不传 year/period 时返回最近一期（API 默认行为）。
    """
    params: dict[str, Any] = {"ticker": ticker.upper()}
    if year is not None:
        params["year"] = year
    if period is not None:
        params["period"] = period.lower()
    if (year is None) ^ (period is None):
        raise ValueError("year 与 period 必须同时提供或同时省略")
    data = api_ninjas_get("earnings", params, api_key=api_key)
    if data is None:
        return None
    # 个别接口可能返回 list，取首条
    if isinstance(data, list):
        return data[0] if data else None
    return data
def _flatten_section(prefix: str, section: dict | None) -> dict[str, Any]:
    if not section:
        return {}
    return {f"{prefix}_{k}": v for k, v in section.items()}

def flatten_earnings_record(rec: dict[str, Any]) -> dict[str, Any]:
    inc = rec.get("income_statement") or {}
    bal = rec.get("balance_sheet") or {}
    cf = rec.get("cash_flow") or {}
    info = rec.get("company_info") or rec.get("filing_info") or {}
    row = {
        "ticker": rec.get("ticker"),
        "year": rec.get("year"),
        "quarter": rec.get("quarter"),
        "company_name": info.get("company_name"),
        "cik": info.get("cik"),
        "filing_type": info.get("filing_type") or info.get("form"),
        "filing_date": info.get("filing_date"),
        "period_end": info.get("period_end_date") or info.get("period_end"),
    }
    row.update(_flatten_section("inc", inc))   # inc_revenue, inc_net_income, ...
    row.update(_flatten_section("bal", bal))   # bal_total_assets, ...
    row.update(_flatten_section("cf", cf))     # cf_operating_cash_flow, ...
    return row

def fetch_earnings_batch(
    symbols: Iterable[str],
    *,
    year: int | None = None,
    period: str | None = None,
    sleep_sec: float = 0.2,
    limit: int | None = None,
    api_key: str | None = None,
    on_error: str = "skip",  # 'skip' | 'raise'
) -> pd.DataFrame:
    """
    对 universe['symbol'] 批量拉 earnings，返回扁平化 DataFrame。
    """
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for i, sym in enumerate(symbols):
        if limit is not None and i >= limit:
            break
        sym = str(sym).strip().upper()
        if not sym:
            continue
        try:
            raw = fetch_earnings(sym, year=year, period=period, api_key=api_key)
            if raw:
                rows.append(flatten_earnings_record(raw))
            else:
                errors.append({"symbol": sym, "error": "no_data"})
        except Exception as e:
            errors.append({"symbol": sym, "error": str(e)})
            if on_error == "raise":
                raise
        if sleep_sec > 0:
            time.sleep(sleep_sec)
    df = pd.DataFrame(rows)
    if errors:
        print(f"  ⚠ earnings 失败/无数据: {len(errors)} 只（示例: {errors[:3]}）")
    return df
# 可选：以后加估值
def fetch_market_cap(ticker: str, **kwargs) -> dict | None:
    return api_ninjas_get("marketcap", {"ticker": ticker.upper()}, **kwargs)