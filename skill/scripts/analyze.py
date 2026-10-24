# -*- coding: utf-8 -*-
"""把 snapshot 变成可复现的比价结论。

核心纪律：**同款判定只看商品编码（code），不看名称。**
不同编码可能同名（如「芝芝火腿扒堡套餐」9900011873 / 9900011874），
名称匹配会把不同商品当成同款，得出假的价差。这是本项目最容易出错的地方。

用法：
    python analyze.py --snap ../data/snapshot-breakfast.json --out ../data/analysis.json
"""
import argparse
import json
import os
import statistics


def pct(a, b):
    if not b:
        return None
    return round((a - b) / b * 100, 1)


def build(snapshot):
    cities = snapshot["cities"]
    # code -> city -> [prices]
    by_code = {}
    # city -> store
    store_meta = []
    for c in cities:
        short = c["short"]
        for s in c["stores"]:
            store_meta.append({
                "city": short,
                "storeName": s["storeName"],
                "storeCode": s["storeCode"],
                "items": s["item_count"],
                "open": "%s-%s" % (s["businessStartTime"], s["businessEndTime"]),
                "distance": s.get("distance"),
            })
            for code, m in s["meals"].items():
                try:
                    price = float(m["price"])
                except (TypeError, ValueError):
                    continue
                node = by_code.setdefault(code, {"name": m["name"], "city": {}})
                node["city"].setdefault(short, []).append({"store": s["storeName"], "price": price})
    city_names = [c["short"] for c in cities]

    # 跨城共有编码
    cross = {code: v for code, v in by_code.items() if len(v["city"]) == len(city_names)}

    # 同码跨店价差（全样本）
    spreads = []
    for code, v in cross.items():
        allp = [p["price"] for c in v["city"].values() for p in c]
        if len(allp) < 2:
            continue
        lo, hi = min(allp), max(allp)
        spreads.append({
            "code": code,
            "name": v["name"],
            "min": lo,
            "max": hi,
            "spread": round(hi - lo, 2),
            "pct": pct(hi, lo),
            "city_median": {c: round(statistics.median([p["price"] for p in ps]), 2)
                            for c, ps in v["city"].items()},
        })
    spreads.sort(key=lambda x: (-x["spread"], x["name"]))

    # 同城同码价差
    intra = []
    for code, v in by_code.items():
        for city, ps in v["city"].items():
            prices = [p["price"] for p in ps]
            if len(prices) < 2:
                continue
            lo, hi = min(prices), max(prices)
            if hi - lo > 0.001:
                intra.append({
                    "city": city, "code": code, "name": v["name"],
                    "min": lo, "max": hi, "spread": round(hi - lo, 2), "pct": pct(hi, lo),
                    "cheap": [p["store"] for p in ps if p["price"] == lo][0],
                    "dear": [p["store"] for p in ps if p["price"] == hi][0],
                })
    intra.sort(key=lambda x: -x["spread"])

    # 城市早餐篮子：取 8 城全覆盖的编码，逐城取中位价后求和
    basket_codes = [s for s in spreads if s["min"] > 0]
    # 只保留在每城多数门店都出现的编码，避免用冷门单品凑篮子
    coverage = {}
    for code, v in cross.items():
        n = sum(len(ps) for ps in v["city"].values())
        coverage[code] = n / max(1, len(store_meta))
    basket_codes = sorted(basket_codes, key=lambda x: -coverage.get(x["code"], 0))[:14]
    baskets = {}
    for city in city_names:
        total = 0.0
        for it in basket_codes:
            total += it["city_median"].get(city, 0)
        baskets[city] = round(total, 2)
    basket_items = [{"code": it["code"], "name": it["name"]} for it in basket_codes]

    # 门店溢价识别：该店价格高于同城同码中位数的比例
    store_premium = []
    for s in store_meta:
        pass
    prem = []
    for c in cities:
        for s in c["stores"]:
            over = 0
            total = 0
            gap = 0.0
            for code, m in s["meals"].items():
                try:
                    price = float(m["price"])
                except (TypeError, ValueError):
                    continue
                peers = [p["price"] for p in by_code[code]["city"].get(c["short"], [])]
                if len(peers) < 2:
                    continue
                med = statistics.median(peers)
                total += 1
                if price > med + 0.001:
                    over += 1
                    gap += price - med
            prem.append({
                "city": c["short"],
                "storeName": s["storeName"],
                "items": s["item_count"],
                "compared": total,
                "over_median": over,
                "ratio": round(over / total * 100, 1) if total else 0,
                "extra": round(gap, 2),
            })
    prem.sort(key=lambda x: (-x["ratio"], -x["extra"]))

    items = [s["items"] for s in store_meta]
    return {
        "generated_from": os.path.basename(snapshot.get("_source", "snapshot")),
        "cities": len(cities),
        "stores": len(store_meta),
        "unique_codes": len(by_code),
        "cross_city_codes": len(cross),
        "menu_items_min": min(items),
        "menu_items_max": max(items),
        "top_spreads": spreads[:15],
        "top_intra_city": intra[:12],
        "basket": {"items": basket_items, "total_by_city": baskets},
        "store_rows": store_meta,
        "store_premium": prem[:10],
        "diff_code_same_name": _same_name_diff_code(by_code),
        "collected_at": snapshot.get("collected_at") or cities[0].get("collected_at"),
        "city_names": city_names,
    }


def _same_name_diff_code(by_code):
    """同名不同码的清单：证明「按名称比价」会得出错误结论。"""
    by_name = {}
    for code, v in by_code.items():
        by_name.setdefault(v["name"], []).append(code)
    out = []
    for name, codes in by_name.items():
        if len(codes) > 1:
            samples = []
            for code in codes:
                prices = sorted({p["price"] for c in by_code[code]["city"].values() for p in c})
                samples.append({"code": code, "prices": prices})
            out.append({"name": name, "variants": samples})
    out.sort(key=lambda x: -len(x["variants"]))
    return out[:8]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snap", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    with open(a.snap, "r", encoding="utf-8") as f:
        snap = json.load(f)
    snap["_source"] = os.path.basename(a.snap)
    res = build(snap)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)

    print("%d 城 / %d 店 / %d 个商品编码 / 跨城共有 %d 个"
          % (res["cities"], res["stores"], res["unique_codes"], res["cross_city_codes"]))
    print("门店在售款数：%d - %d" % (res["menu_items_min"], res["menu_items_max"]))
    print("\n同码最大价差：")
    for s in res["top_spreads"][:5]:
        print("  %-14s %s → %s 元（%+.1f%%）" % (s["name"], s["min"], s["max"], s["pct"]))
    print("\n城市篮子（%d 件）：" % len(res["basket"]["items"]))
    for c, v in sorted(res["basket"]["total_by_city"].items(), key=lambda x: -x[1]):
        print("  %-4s %.2f" % (c, v))
    print("\n同城同码价差前 5：")
    for s in res["top_intra_city"][:5]:
        print("  %s %s %s→%s（%s vs %s）" % (s["city"], s["name"], s["min"], s["max"], s["cheap"][:14], s["dear"][:14]))


if __name__ == "__main__":
    main()
