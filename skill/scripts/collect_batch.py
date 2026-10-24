# -*- coding: utf-8 -*-
"""批量采集多个城市商圈的早餐/正餐菜单快照，合并成一个数据集。"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collect  # noqa: E402

CITIES = [
    ("北京市", "国贸", "北京"),
    ("上海市", "人民广场", "上海"),
    ("广州市", "天河城", "广州"),
    ("深圳市", "福田", "深圳"),
    ("成都市", "春熙路", "成都"),
    ("杭州市", "武林广场", "杭州"),
    ("西安市", "钟楼", "西安"),
    ("武汉市", "江汉路", "武汉"),
]


def main():
    tag = sys.argv[1] if len(sys.argv) > 1 else "breakfast"
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data",
                       "snapshot-%s.json" % tag)
    snapshots = []
    for city, landmark, short in CITIES:
        print("\n=== %s / %s" % (city, landmark))
        try:
            snap = collect.collect(city, landmark, n)
            snap["short"] = short
            snapshots.append(snap)
        except Exception as e:
            print("  ! 采集失败：%s" % e)
        time.sleep(1.2)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({"tag": tag, "cities": snapshots}, f, ensure_ascii=False, indent=1)
    total = sum(len(s["stores"]) for s in snapshots)
    print("\n完成：%d 个城市 / %d 家门店 -> %s" % (len(snapshots), total, out))


if __name__ == "__main__":
    main()
