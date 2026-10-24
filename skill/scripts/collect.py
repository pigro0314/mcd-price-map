# -*- coding: utf-8 -*-
"""采集一个城市的地标周边门店菜单，落成 snapshot JSON。

用法：
    MCD_MCP_TOKEN=xxx python collect.py --city 北京市 --landmark 国贸 --stores 4 \
        --out ../data/snapshot-beijing.json
"""
import argparse
import datetime as dt
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcd_client import MCPClient  # noqa: E402


def call_with_retry(cli, name, args, tries=3):
    for i in range(tries):
        try:
            return cli.call(name, args)
        except Exception as e:
            if i == tries - 1:
                raise
            wait = 2 ** i
            print("  ! %s 失败(%s)，%ss 后重试" % (name, type(e).__name__, wait), file=sys.stderr)
            time.sleep(wait)


def collect(city, landmark, max_stores, delay=0.35):
    cli = MCPClient().init()

    print("[1/2] 查询门店：%s / %s" % (city, landmark))
    found = call_with_retry(cli, "query-nearby-stores", {
        "beType": 1, "searchType": 2, "city": city, "keyword": landmark,
    })
    stores = (found.get("data") or []) if isinstance(found, dict) else []
    open_stores = [s for s in stores if s.get("businessStatus")]
    picked = open_stores[:max_stores]
    print("      返回 %d 家，营业中 %d 家，采样 %d 家" % (len(stores), len(open_stores), len(picked)))

    out_stores = []
    for i, s in enumerate(picked, 1):
        code = str(s.get("storeCode"))
        print("[2/2] (%d/%d) %s  %s" % (i, len(picked), code, s.get("storeName")))
        meals_raw = call_with_retry(cli, "query-meals", {
            "storeCode": code, "orderType": 1, "beType": 1,
        })
        meals = ((meals_raw.get("data") or {}) if isinstance(meals_raw, dict) else {}).get("meals") or {}
        slim = {}
        for code_key, m in meals.items():
            if not isinstance(m, dict):
                continue
            slim[str(code_key)] = {
                "name": m.get("name"),
                "price": m.get("currentPrice"),
                "original": m.get("originalPrice"),
            }
        print("      在售 %d 项" % len(slim))
        out_stores.append({
            "storeCode": code,
            "storeName": s.get("storeName"),
            "address": s.get("address"),
            "distance": s.get("distance"),
            "businessStartTime": s.get("businessStartTime"),
            "businessEndTime": s.get("businessEndTime"),
            "reservation": s.get("reservation"),
            "item_count": len(slim),
            "meals": slim,
        })
        time.sleep(delay)

    return {
        "city": city,
        "landmark": landmark,
        "collected_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "orderType": 1,
        "beType": 1,
        "stores": out_stores,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", required=True)
    ap.add_argument("--landmark", required=True)
    ap.add_argument("--stores", type=int, default=4)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    snap = collect(a.city, a.landmark, a.stores)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=1)
    print("已写入 %s（%d 家门店）" % (a.out, len(snap["stores"])))


if __name__ == "__main__":
    main()
