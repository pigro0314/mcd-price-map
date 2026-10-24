# -*- coding: utf-8 -*-
"""麦当劳 MCP 最小客户端（streamable HTTP）。

只做三件事：握手、调工具、把 tool result 里的 JSON 抠出来。
Token 只从环境变量 MCD_MCP_TOKEN 读取，绝不落盘、绝不进日志。
"""
import json
import os
import urllib.request

MCP_URL = "https://mcp.mcd.cn"


def load_token():
    tok = (os.environ.get("MCD_MCP_TOKEN") or "").strip()
    if not tok:
        raise SystemExit("缺少环境变量 MCD_MCP_TOKEN，请先到 https://open.mcd.cn/mcp 申请")
    return tok


def extract_json(text):
    """工具返回是「人话 + JSON」的混合文本，这里定位第一个可解析的 JSON 对象。"""
    i = text.find("{")
    while i != -1:
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[i:])
            return obj
        except ValueError:
            i = text.find("{", i + 1)
    return None


class MCPClient:
    def __init__(self, token=None, timeout=45):
        self.token = token or load_token()
        self.timeout = timeout
        self.sid = None
        self._id = 0
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def _post(self, payload):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": "Bearer " + self.token,
            "MCP-Protocol-Version": "2025-06-18",
        }
        if self.sid:
            headers["Mcp-Session-Id"] = self.sid
        req = urllib.request.Request(
            MCP_URL, data=json.dumps(payload).encode(), headers=headers, method="POST"
        )
        with self.opener.open(req, timeout=self.timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
            for k, v in resp.headers.items():
                if k.lower() == "mcp-session-id":
                    self.sid = v
            ctype = resp.headers.get("Content-Type", "")
        if "text/event-stream" in ctype:
            last = {}
            for line in raw.splitlines():
                if line.startswith("data:"):
                    try:
                        last = json.loads(line[5:].strip())
                    except ValueError:
                        pass
            return last
        return json.loads(raw) if raw.strip() else {}

    def init(self):
        self._post({
            "jsonrpc": "2.0", "id": 0, "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "mcd-price-radar", "version": "1.0.0"},
            },
        })
        try:
            self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        except Exception:
            pass
        return self

    def call(self, name, args=None):
        self._id += 1
        resp = self._post({
            "jsonrpc": "2.0", "id": self._id, "method": "tools/call",
            "params": {"name": name, "arguments": args or {}},
        })
        if "error" in resp:
            raise RuntimeError(json.dumps(resp["error"], ensure_ascii=False)[:300])
        parts = (resp.get("result") or {}).get("content") or []
        text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
        data = extract_json(text)
        return data if data is not None else {"_raw": text}
