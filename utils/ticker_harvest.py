#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════╗
║              🌾  tickerharvest.py                    ║
║   Harvest every NYSE & NASDAQ ticker in one shot     ║
║   Source: Alpha Vantage LISTING_STATUS API           ║
╚══════════════════════════════════════════════════════╝

Usage:
    Fetch & save:  python tickerharvest.py
    Read H5:       python tickerharvest.py --read
    Custom file:   python tickerharvest.py --read --out tickers_NYSE+NASDAQ_20260514.h5

    Optional fetch flags:
         --exchange NYSE         → filter to one exchange
         --status   delisted     → include delisted tickers too
         --out      custom.h5    → custom output filename

Dependencies:
    pip install pandas tables
"""

import argparse
import csv
import io
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
import yfinance as yf
import json
from typing import Any

import pandas as pd

# ─── Config ───────────────────────────────────────────────────────────────────

BASE_URL = "https://www.alphavantage.co/query"
API_KEY = "K5W8ZOSXZC4SK29W"  # hardcoded for testing
OUTPUT_DIR = Path(r"C:\Users\steve\OneDrive\Python Project\Yikai Code\stock ticker database")
H5_KEY = "tickers"  # key/table name inside the HDF5 file

ENRICH_SECTOR = True
BANNER = """
╔══════════════════════════════════════════════════════╗
║              🌾  tickerharvest.py                    ║
╚══════════════════════════════════════════════════════╝
"""


# ─── Fetch ────────────────────────────────────────────────────────────────────
def fetch_yf_info(symbol: str) -> dict[str, Any]:
    """从 Yahoo Finance 取完整 info dict；失败返回 {}。"""
    try:
        return yf.Ticker(symbol).info or {}
    except Exception:
        return {}

def _serialize_yf_value(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False, default=str)
    return str(v)

def merge_yf_info_into_row(row: dict, info: dict[str, Any], *, prefix: str = "yf_") -> None:
    """把 info 全部写入 row，键名为 yf_sector, yf_industry, yf_marketCap, ..."""
    for key, value in info.items():
        col = f"{prefix}{key}"
        row[col] = _serialize_yf_value(value)

def enrich_yf_info(
    rows: list[dict],
    *,
    sleep_sec: float = 0.05,
    stocks_only: bool = True,
    show_progress: bool = True,
    prefix: str = "yf_",
) -> list[dict]:
    total = len(rows)
    for i, row in enumerate(rows, 1):
        atype = (row.get("asset_type") or "").strip().upper()
        if stocks_only and atype != "STOCK":
            continue  # 非 STOCK 不拉 yfinance，保留 LISTING_STATUS 字段即可
        info = fetch_yf_info(row["symbol"])
        merge_yf_info_into_row(row, info, prefix=prefix)
        if sleep_sec > 0:
            time.sleep(sleep_sec)
        if show_progress and i % 200 == 0:
            print(f"  … enriched {i:,}/{total:,}")
    return rows

def build_url(apikey: str, status: str) -> str:
    """Construct the Alpha Vantage LISTING_STATUS endpoint URL."""
    return f"{BASE_URL}?function=LISTING_STATUS&state={status}&apikey={apikey}"


def fetch_listings(apikey: str, status: str) -> list[dict]:
    """Fetch ticker listings from Alpha Vantage and return as list of dicts."""
    url = build_url(apikey, status)
    print(f"  → Fetching [{status}] listings from Alpha Vantage...")

    try:
        with urlopen(url, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except HTTPError as e:
        print(f"  ✗ HTTP Error {e.code}: {e.reason}")
        sys.exit(1)
    except URLError as e:
        print(f"  ✗ Network error: {e.reason}")
        sys.exit(1)

    if not raw.strip():
        print("  ✗ Empty response — check your API key.")
        sys.exit(1)

    if "Thank you for using Alpha Vantage" in raw or "{" in raw[:50]:
        print("  ✗ API limit hit or invalid key. Response:")
        print("   ", raw[:300])
        sys.exit(1)

    reader = csv.DictReader(io.StringIO(raw))
    rows = list(reader)
    print(f"  ✓ Retrieved {len(rows):,} rows")
    return rows


# ─── Filter ───────────────────────────────────────────────────────────────────

def filter_rows(rows: list[dict], exchange: str) -> list[dict]:
    """Filter by exchange and status, normalize field names."""
    filtered = []
    exchange = exchange.upper()  # normalize for comparison
    for row in rows:
        exch = row.get("exchange", "").strip().upper()

        # Exchange filter
        if exchange == "ALL":
            pass
        elif exchange == "NYSE+NASDAQ":
            if not (exch.startswith("NYSE") or exch == "NASDAQ"):
                continue
        elif exchange == "NYSE":
            if not exch.startswith("NYSE"):
                continue
        elif exch != exchange:
            continue

        filtered.append({
            "symbol": row.get("symbol", "").strip(),
            "name": row.get("name", "").strip(),
            "exchange": row.get("exchange", "").strip(),
            "asset_type": row.get("assetType", "").strip(),
            "ipo_date": row.get("ipoDate", "").strip(),
            "delisting_date": row.get("delistingDate", "").strip(),
            "status": row.get("status", "active").strip(),
        })
    return filtered


# ─── Save H5 ──────────────────────────────────────────────────────────────────

def save_h5(data: list[dict], filepath: Path):
    """Save ticker data to HDF5 (.h5) format using pandas."""
    if not data:
        print("  ⚠ No data to save.")
        return

    df = pd.DataFrame(data)

    # Ensure output directory exists
    filepath.parent.mkdir(parents=True, exist_ok=True)

    df.to_hdf(filepath, key=H5_KEY, mode="w", complevel=5, complib="blosc")

    size_kb = filepath.stat().st_size / 1024
    print(f"  ✓ Saved H5  → {filepath}")
    print(f"     Rows   : {len(df):,}")
    print(f"     Columns: {list(df.columns)}")
    print(f"     Size   : {size_kb:.1f} KB")


# ─── Read H5 ──────────────────────────────────────────────────────────────────

def read_h5(filepath: Path) -> pd.DataFrame:
    """
    Read ticker data back from an HDF5 (.h5) file.
    Returns a pandas DataFrame and prints a summary.
    """
    if not filepath.exists():
        print(f"  ✗ File not found: {filepath}")
        sys.exit(1)

    print(f"  → Reading H5 file: {filepath}")
    df = pd.read_hdf(filepath, key=H5_KEY)

    print(f"  ✓ Loaded {len(df):,} tickers")
    print(f"\n  📊 Shape     : {df.shape}")
    print(f"  📋 Columns   : {list(df.columns)}")
    print(f"\n  🏦 By Exchange:")
    print(df["exchange"].value_counts().to_string(header=False))
    print(f"\n  📦 By Asset Type:")
    print(df["asset_type"].value_counts().to_string(header=False))
    print(f"\n  👀 Sample (first 5 rows):")
    print(df.head().to_string(index=False))

    return df


# ─── Summary ──────────────────────────────────────────────────────────────────

def print_summary(data: list[dict]):
    """Print a breakdown by exchange and asset type."""
    exchange_counts: dict[str, int] = {}
    asset_counts: dict[str, int] = {}

    for row in data:
        e = row.get("exchange", "UNKNOWN")
        a = row.get("asset_type", "UNKNOWN")
        exchange_counts[e] = exchange_counts.get(e, 0) + 1
        asset_counts[a] = asset_counts.get(a, 0) + 1

    print("\n  📊 Summary by Exchange:")
    for exch, count in sorted(exchange_counts.items(), key=lambda x: -x[1]):
        print(f"     {exch:<20} {count:>6,}")

    print("\n  📦 Summary by Asset Type:")
    for atype, count in sorted(asset_counts.items(), key=lambda x: -x[1]):
        print(f"     {atype:<20} {count:>6,}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(BANNER)
    parser = argparse.ArgumentParser(
        description="🌾 tickerharvest — fetch all NYSE & NASDAQ tickers via Alpha Vantage"
    )
    parser.add_argument(
        "--enrich-sector",
        default = ENRICH_SECTOR,
        action="store_true",
        help="yfinance sector/industry 补充（更快）",
    )
    parser.add_argument(
        "--enrich-limit",
        type=int,
        default=None,
        help="仅 enrich 前 N 只（调试用）",
    )
    parser.add_argument(
        "--yf-sleep",
        type=float,
        default=0.05,
        help="yfinance 每只间隔秒数，降低被限流概率",
    )
    parser.add_argument(
        "--apikey", default=API_KEY,
        help="Alpha Vantage API key (default: hardcoded test key)"
    )
    parser.add_argument(
        "--exchange", default="NYSE+NASDAQ",
        choices=["NYSE", "NASDAQ", "NYSE+NASDAQ", "NYSE ARCA", "NYSE MKT", "ALL"],
        help="Filter by exchange (default: NYSE+NASDAQ)"
    )
    parser.add_argument(
        "--status", default="active",
        choices=["active", "delisted", "both"],
        help="Listing status to fetch (default: active)"
    )
    parser.add_argument(
        "--out", default=None,
        help="Output .h5 filename or full path (default: auto-generated in OUTPUT_DIR)"
    )
    parser.add_argument(
        "--read", action="store_true",
        help="Read and display an existing H5 file instead of fetching new data"
    )

    args = parser.parse_args()

    # ── READ MODE ──
    if args.read:
        if args.out:
            h5_path = Path(args.out)
        else:
            # Auto-select the most recent .h5 file in OUTPUT_DIR
            h5_files = sorted(OUTPUT_DIR.glob("tickers_*.h5"), reverse=True)
            if not h5_files:
                print(f"  ✗ No .h5 files found in:\n     {OUTPUT_DIR}")
                sys.exit(1)
            h5_path = h5_files[0]
            print(f"  ℹ Auto-selected latest file: {h5_path.name}")

        read_h5(h5_path)
        return

    # ── FETCH MODE ──
    print(f"  Exchange : {args.exchange}")
    print(f"  Status   : {args.status}")
    print()

    all_data: list[dict] = []
    statuses_to_fetch = (
        ["active", "delisted"] if args.status == "both" else [args.status]
    )

    for i, status in enumerate(statuses_to_fetch):
        rows = fetch_listings(args.apikey, status)
        filtered = filter_rows(rows, args.exchange)
        all_data.extend(filtered)
        if i < len(statuses_to_fetch) - 1:
            print("  ⏳ Pausing 1s between calls...")
            time.sleep(1)

    # Deduplicate
    seen = set()
    unique_data = []
    for row in all_data:
        key = (row["symbol"], row["exchange"], row["status"])
        if key not in seen:
            seen.add(key)
            unique_data.append(row)

    print(f"\n  Total unique tickers: {len(unique_data):,}")
    print_summary(unique_data)

    # Build output path
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.out:
        h5_path = Path(args.out)
    else:
        exch_tag = args.exchange.replace(" ", "_")
        h5_path = OUTPUT_DIR / f"tickers_{exch_tag}_{timestamp}.h5"

    print()
    if args.enrich_sector:
        to_enrich = unique_data
        if args.enrich_limit is not None:
            to_enrich = unique_data[: args.enrich_limit]
        print(f"\n  → Enriching sector/industry for {len(to_enrich):,} tickers (yfinance)...")
        enrich_yf_info(to_enrich, sleep_sec=args.yf_sleep)
        # 若 enrich_limit 只 enrich 子集，其余行 sector/industry 仍为 None
    save_h5(unique_data, h5_path)
    print(f"\n  🌾 Harvest complete! {len(unique_data):,} tickers saved.\n")


if __name__ == "__main__":
    main()
