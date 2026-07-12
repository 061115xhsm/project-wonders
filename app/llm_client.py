"""大模型客户端 —— OpenAI 兼容,首选讯飞 maas-coding(auto) + 备用智多云多模型 fallback

调用链(自动降级):
  1. 讯飞 maas-coding `auto`(200k 上下文,首选)
  2. 智多云 glm-5.2 → deepseek-v4-pro → kimi-k2.6

Streamlit 同步环境,用 openai SDK 同步接口。失败模型自动冷却 5 分钟。
所有调用带 @st.cache_data 或调用方缓存,避免重复计费。
"""
import os
import time
import json
import logging
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

logger = logging.getLogger(__name__)

# 加载 .env(项目根)
_PROJ_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_PROJ_ROOT, ".env"))

# ===== 配置 =====
PRIMARY_BASE = os.getenv("LLM_PRIMARY_BASE_URL", "")
PRIMARY_KEY = os.getenv("LLM_PRIMARY_API_KEY", "")
PRIMARY_MODEL = os.getenv("LLM_PRIMARY_MODEL", "auto")

FALLBACK_BASE = os.getenv("LLM_FALLBACK_BASE_URL", "")
FALLBACK_KEY = os.getenv("LLM_FALLBACK_API_KEY", "")
FALLBACK_MODELS = [m.strip() for m in os.getenv("LLM_FALLBACK_MODELS", "glm-5.2").split(",") if m.strip()]

LLM_TIMEOUT = int(os.getenv("LLM_TIMEOUT", "60"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "2048"))

# 候选模型列表(按优先级): (label, base_url, api_key, model)
_CANDIDATES = []
if PRIMARY_BASE and PRIMARY_KEY:
    _CANDIDATES.append(("讯飞auto", PRIMARY_BASE, PRIMARY_KEY, PRIMARY_MODEL))
for m in FALLBACK_MODELS:
    if FALLBACK_BASE and FALLBACK_KEY:
        _CANDIDATES.append((f"智多云{m}", FALLBACK_BASE.rstrip("/") + "/v1", FALLBACK_KEY, m))

# 模型状态:连续失败计数 + 冷却期
_status = {label: {"fails": 0, "disabled_until": 0} for label, *_ in _CANDIDATES}


def _available(label: str) -> bool:
    return _status[label]["disabled_until"] <= time.time()


def _mark_ok(label: str):
    _status[label]["fails"] = 0


def _mark_fail(label: str):
    st = _status[label]
    st["fails"] += 1
    if st["fails"] >= 3:
        st["disabled_until"] = time.time() + 300  # 冷却 5 分钟
        logger.warning(f"模型 {label} 连续失败 {st['fails']} 次,禁用 5 分钟")


def is_llm_ready() -> bool:
    """是否有至少一个可用模型(供 UI 判断是否点亮 AI 功能)"""
    return any(_available(l) for l, *_ in _CANDIDATES)


def chat(messages: list, temperature: float = 0.7, max_tokens: Optional[int] = None,
         json_mode: bool = False, timeout: Optional[int] = None) -> dict:
    """同步调用大模型,自动 fallback。

    Args:
        messages: OpenAI 格式 [{"role","content"}]
        temperature: 生成温度
        max_tokens: 最大输出 token
        json_mode: 是否要求 JSON 输出(response_format=json_object)
        timeout: 单次超时秒

    Returns: {"content": str, "model": str, "usage": dict}
    Raises: RuntimeError 所有模型均不可用
    """
    if not _CANDIDATES:
        raise RuntimeError("未配置大模型(检查 .env 中 LLM_*_BASE_URL/API_KEY)")

    last_err = None
    for label, base_url, api_key, model in _CANDIDATES:
        if not _available(label):
            continue
        for attempt_no_json in (False, True):
            try:
                client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout or LLM_TIMEOUT)
                kwargs = dict(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens or LLM_MAX_TOKENS,
                )
                # 讯飞 auto 等模型可能不支持 response_format;
                # 首次用 json_mode 调用,若报错则去掉 response_format 重试(宽松解析兜底)
                if json_mode and not attempt_no_json:
                    kwargs["response_format"] = {"type": "json_object"}
                resp = client.chat.completions.create(**kwargs)
                _mark_ok(label)
                return {
                    "content": resp.choices[0].message.content or "",
                    "model": f"{label}/{resp.model}",
                    "usage": resp.usage.model_dump() if resp.usage else {},
                }
            except Exception as e:
                last_err = e
                # 仅当本次是 json_mode 且尚未重试时,尝试去掉 response_format 再调一次
                if json_mode and not attempt_no_json:
                    logger.info(f"模型 {label}({model}) json_mode 调用失败,去掉 response_format 重试: {type(e).__name__}")
                    continue
                _mark_fail(label)
                logger.warning(f"模型 {label}({model}) 调用失败: {type(e).__name__} {str(e)[:200]}")
                break

    raise RuntimeError(f"所有大模型均不可用,最后错误: {last_err}")


def chat_text(messages: list, **kw) -> str:
    """便捷:直接返回文本内容"""
    return chat(messages, **kw)["content"]


def parse_json_response(content: str) -> Optional[object]:
    """解析大模型返回的 JSON(兼容 ```json 包裹 / 前后多余文字)"""
    if not content:
        return None
    s = content.strip()
    # 去 markdown 代码块
    if "```json" in s:
        s = s[s.index("```json") + 7:]
        s = s[:s.index("```")] if "```" in s else s
    elif "```" in s:
        s = s[s.index("```") + 3:]
        s = s[:s.index("```")] if "```" in s else s
    s = s.strip()
    # 直接解析
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # 找第一个 { 或 [ 到最后一个对应括号
    for opener, closer in [("{", "}"), ("[", "]")]:
        start = s.find(opener)
        end = s.rfind(closer)
        if start >= 0 and end > start:
            try:
                return json.loads(s[start:end + 1])
            except json.JSONDecodeError:
                continue
    return None


if __name__ == "__main__":
    # 自检
    print(f"候选模型数: {len(_CANDIDATES)} | 至少一个可用: {is_llm_ready()}")
    for label, base, _, model in _CANDIDATES:
        print(f"  - {label}: {model} @ {base}")
    print("\n--- 自检调用 ---")
    r = chat([{"role": "user", "content": "用一句话介绍普宁万泰新天地购物中心"}], max_tokens=100)
    print(f"model={r['model']}\n内容={r['content']}")
    print("\n--- JSON 自检 ---")
    r = chat(
        [{"role": "user", "content": '返回JSON: {"mall":"万泰新天地","city":"普宁","floors":5}'}],
        json_mode=True, max_tokens=100,
    )
    print("解析:", parse_json_response(r["content"]))
