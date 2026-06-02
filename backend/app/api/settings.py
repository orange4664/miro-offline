"""
Settings API — let users edit LLM / Embedding config (model / baseURL / apiKey)
from the UI. Changes apply globally and immediately (in-memory Config +
os.environ, so newly spawned OASIS subprocesses inherit them) and are
persisted to the project-root .env.
"""

import logging
import requests
from flask import request, jsonify
from openai import OpenAI

from . import settings_bp
from ..config import Config

logger = logging.getLogger('mirofish.api.settings')


def _mask(secret: str) -> str:
    """Mask an api key for display: keep last 4 chars."""
    if not secret:
        return ""
    s = str(secret)
    if len(s) <= 4:
        return "****"
    return f"****{s[-4:]}"


@settings_bp.route('/llm', methods=['GET'])
def get_settings():
    """Return current config. API keys are masked (never returned in clear)."""
    return jsonify({
        "success": True,
        "data": {
            "llm": {
                "model": Config.LLM_MODEL_NAME or "",
                "base_url": Config.LLM_BASE_URL or "",
                "api_key_masked": _mask(Config.LLM_API_KEY),
                "api_key_set": bool(Config.LLM_API_KEY),
            },
            "embedding": {
                "provider": Config.EMBEDDING_PROVIDER or "openai",
                "model": Config.EMBEDDING_MODEL or "",
                "base_url": Config.EMBEDDING_BASE_URL or "",
                "api_key_masked": _mask(getattr(Config, 'EMBEDDING_API_KEY', '')),
                "api_key_set": bool(getattr(Config, 'EMBEDDING_API_KEY', '')),
                "dimension": getattr(Config, 'EMBEDDING_DIMENSION', 768),
            },
        }
    })


@settings_bp.route('/llm', methods=['POST'])
def save_settings():
    """
    Save settings. Body (all optional; empty/missing = keep current):
      {
        "llm": {"model","base_url","api_key"},
        "embedding": {"provider","model","base_url","api_key","dimension"}
      }
    Applies in-memory + os.environ, then persists to .env.
    """
    try:
        data = request.get_json() or {}
        llm = data.get('llm') or {}
        emb = data.get('embedding') or {}

        updates = {}
        if llm.get('model') not in (None, ""):
            updates['LLM_MODEL_NAME'] = llm['model']
        if llm.get('base_url') not in (None, ""):
            updates['LLM_BASE_URL'] = llm['base_url']
        if llm.get('api_key') not in (None, ""):
            updates['LLM_API_KEY'] = llm['api_key']
            updates['OPENAI_API_KEY'] = llm['api_key']
        # keep OASIS base url in sync with LLM base url
        if llm.get('base_url') not in (None, ""):
            updates['OPENAI_API_BASE_URL'] = llm['base_url']

        if emb.get('provider') not in (None, ""):
            updates['EMBEDDING_PROVIDER'] = emb['provider']
        if emb.get('model') not in (None, ""):
            updates['EMBEDDING_MODEL'] = emb['model']
        if emb.get('base_url') not in (None, ""):
            updates['EMBEDDING_BASE_URL'] = emb['base_url']
        if emb.get('api_key') not in (None, ""):
            updates['EMBEDDING_API_KEY'] = emb['api_key']
        if emb.get('dimension') not in (None, ""):
            updates['EMBEDDING_DIMENSION'] = emb['dimension']

        applied = Config.apply_updates(updates)
        Config.persist_to_env_file(updates)

        # never echo secrets back
        changed_keys = [k for k in applied.keys() if 'KEY' not in k] + \
                       [f"{k}(masked)" for k in applied.keys() if 'KEY' in k]
        logger.info(f"Settings updated: {changed_keys}")

        return jsonify({
            "success": True,
            "message": "配置已保存，并对之后新建的模拟 / 报告 / 采访立即生效。",
            "changed": changed_keys,
        })
    except Exception as e:
        logger.error(f"Save settings failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@settings_bp.route('/test', methods=['POST'])
def test_connection():
    """
    Test a connection before saving. Body:
      {"target":"llm"|"embedding","model","base_url","api_key"}
    If a field is empty, fall back to the current saved value.
    """
    try:
        data = request.get_json() or {}
        target = (data.get('target') or 'llm').lower()

        if target == 'llm':
            api_key = data.get('api_key') or Config.LLM_API_KEY
            base_url = data.get('base_url') or Config.LLM_BASE_URL
            model = data.get('model') or Config.LLM_MODEL_NAME
            if not api_key or not base_url or not model:
                return jsonify({"success": False, "error": "缺少 model / base_url / api_key"}), 400
            try:
                client = OpenAI(api_key=api_key, base_url=base_url, timeout=30.0,
                                default_headers={"User-Agent": "curl/8.5.0"})
                resp = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "ping，请只回复: ok"}],
                    max_tokens=10,
                )
                content = (resp.choices[0].message.content or "").strip()
                return jsonify({"success": True, "message": f"连接成功，模型返回: {content[:40]}"})
            except Exception as e:
                return jsonify({"success": False, "error": f"LLM 连接失败: {str(e)[:200]}"}), 200

        elif target == 'embedding':
            api_key = data.get('api_key') or getattr(Config, 'EMBEDDING_API_KEY', '')
            base_url = (data.get('base_url') or Config.EMBEDDING_BASE_URL or '').rstrip('/')
            model = data.get('model') or Config.EMBEDDING_MODEL
            provider = (data.get('provider') or Config.EMBEDDING_PROVIDER or 'openai').lower()
            if provider == 'hash':
                return jsonify({"success": True, "message": "hash 本地兜底模式，无需联网测试。"})
            if not base_url or not model:
                return jsonify({"success": False, "error": "缺少 model / base_url"}), 400
            try:
                if provider == 'ollama':
                    url = f"{base_url}/api/embed"
                    payload = {"model": model, "input": ["ping"]}
                    r = requests.post(url, json=payload, timeout=30)
                    r.raise_for_status()
                    vecs = r.json().get("embeddings", [])
                    dim = len(vecs[0]) if vecs else 0
                else:  # openai-compatible
                    url = f"{base_url}/embeddings"
                    headers = {"Content-Type": "application/json", "User-Agent": "curl/8.5.0"}
                    if api_key:
                        headers["Authorization"] = f"Bearer {api_key}"
                    r = requests.post(url, json={"model": model, "input": "ping"},
                                      headers=headers, timeout=30)
                    r.raise_for_status()
                    items = r.json().get("data", [])
                    dim = len(items[0].get("embedding", [])) if items else 0
                return jsonify({"success": True, "message": f"连接成功，返回向量维度: {dim}"})
            except Exception as e:
                return jsonify({"success": False, "error": f"Embedding 连接失败: {str(e)[:200]}"}), 200

        return jsonify({"success": False, "error": f"未知 target: {target}"}), 400
    except Exception as e:
        logger.error(f"Test connection failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
