# -*- coding: utf-8 -*-
"""从 .env 读取“模型档位(profile)”与“各 Agent 的模型路由”配置。

设计：
- profile：一套 OpenAI 兼容的 base_url / api_key / model，命名任意（如 cheap / strong / my_model）。
- agent  ：一个会调用 LLM 的角色（normalize / key_points / actions_decisions / repair / v1_all）。
- 路由   ：每个 agent 指向某个 profile；即“哪个模型用在哪个 Agent 上”。
不预设任何具体模型名，全部由 .env 决定；未配置则直接报错。
"""

import os

# Core 根目录（本文件在 shared/ 下）
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WORKSPACE_ROOT = os.path.dirname(_ROOT)
_ENV_CANDIDATES = [
    os.path.join(_ROOT, ".env"),
    os.path.join(_WORKSPACE_ROOT, ".env"),
    os.path.join(_WORKSPACE_ROOT, "Lab", ".env"),
]
_PRODUCTION_MODES = {"production", "prod", "deploy"}

# 默认路由策略：这是“架构策略”而非具体模型；可被 .env 的 AGENT_* 覆盖
_DEFAULT_AGENT_PROFILE = {
    "normalize": "light",           # 说话人/角色归一：最轻，纯抽取
    "repair": "light",              # 校验自修复：照错改格式，无需推理
    "key_points": "standard",       # 要点抽取：归纳类，中档更稳
    "actions_decisions": "strong",  # 待办+决策：需推理，用强档
    "v1_all": "strong",             # V1 单次调用：基线用强档
    "lab_judge": "strong",    # Lab 评委：统一走强档
}


def _load_one_dotenv(path):
    """极简 .env 解析：KEY=VALUE，支持 # 注释与行内 ' #' 注释，不覆盖已有环境变量。"""
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key, val = key.strip(), val.strip()
            if " #" in val:                       # 去掉行内注释
                val = val.split(" #", 1)[0].strip()
            val = val.strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


def config_mode():
    return os.getenv("MINSIGHT_CONFIG_MODE", "development").strip().lower()


def env_file_candidates(mode=None):
    if (mode or config_mode()) in _PRODUCTION_MODES:
        return []
    return list(_ENV_CANDIDATES)


def load_dotenv():
    """按候选路径加载 .env：优先 Core/.env，其次工作区根目录，再其次 Lab/.env。"""
    for path in env_file_candidates():
        if os.path.exists(path):
            _load_one_dotenv(path)
            return path
    return None


_LOADED_ENV_PATH = load_dotenv()  # 导入即加载


def get_profile(name):
    """按 profile 名取 {name, base_url, api_key, model}；缺 model 或 api_key 视为未配置，返回 None。"""
    up = name.upper()
    model = os.getenv(f"LLM_{up}_MODEL")
    api_key = os.getenv(f"LLM_{up}_API_KEY")
    if not model or not api_key:
        return None
    return {"name": name.lower(),
            "base_url": os.getenv(f"LLM_{up}_BASE_URL") or None,
            "api_key": api_key, "model": model}


def configured_profiles():
    """扫描环境变量，返回所有已配置好的 profile：{name: profile}。"""
    names = {k[4:-6].lower() for k in os.environ
             if k.startswith("LLM_") and k.endswith("_MODEL")}
    out = {}
    for n in names:
        p = get_profile(n)
        if p:
            out[n] = p
    return out


def agent_profile_name(agent):
    """某 agent 用哪个 profile：优先 .env 的 AGENT_<AGENT>，否则默认策略。"""
    return os.getenv(f"AGENT_{agent.upper()}") or _DEFAULT_AGENT_PROFILE.get(agent, "strong")


def any_profile_configured():
    """是否至少配置了一个可用 profile（决定是否进入真实模式）。"""
    return bool(configured_profiles())
