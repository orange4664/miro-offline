"""
Offline (disk-backed) interview service.

Lets "send survey to the world" / agent interviews work even when the live
OASIS simulation process is gone (e.g. backend restarted, machine rebooted).

Why this is possible: an OASIS interview only needs (1) the agent's persona
and (2) some context of what the agent did. The persona is persisted to
reddit_profiles.json / twitter_profiles.csv, and the agent's posts/comments
are persisted in the simulation SQLite DB. The only thing NOT persisted is the
agent's in-RAM CAMEL memory — which is lost the moment the process exits and
cannot be recovered by any means. We approximate it from the DB activity,
which is good enough for survey-style questions and, crucially, always works
from disk.
"""

import os
import csv
import json
import sqlite3
import logging
from typing import Dict, Any, List, Optional

from ..config import Config
from ..utils.llm_client import LLMClient

logger = logging.getLogger('mirofish.offline_interview')

INTERVIEW_PROMPT_PREFIX = (
    "结合你的人设、过往经历与发言，不要调用任何工具，直接用中文自然语言回答下面的问题：\n\n"
)


class OfflineInterviewService:
    """Reconstruct an agent from disk (profiles + DB) and interview it via LLM."""

    def __init__(self, simulation_id: str, llm_client: Optional[LLMClient] = None):
        self.simulation_id = simulation_id
        self.sim_dir = os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)
        self.llm = llm_client or LLMClient()
        self._profiles_cache: Optional[Dict[int, Dict[str, Any]]] = None

    # ---------- persona loading ----------

    def _load_profiles(self) -> Dict[int, Dict[str, Any]]:
        """Load agent profiles keyed by integer agent/user id."""
        if self._profiles_cache is not None:
            return self._profiles_cache

        profiles: Dict[int, Dict[str, Any]] = {}

        reddit_json = os.path.join(self.sim_dir, "reddit_profiles.json")
        twitter_csv = os.path.join(self.sim_dir, "twitter_profiles.csv")

        if os.path.exists(reddit_json):
            try:
                with open(reddit_json, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for item in (data if isinstance(data, list) else data.values()):
                    aid = item.get('user_id', item.get('agent_id'))
                    if aid is None:
                        continue
                    profiles[int(aid)] = {
                        "username": item.get('username') or item.get('name') or f"agent_{aid}",
                        "persona": item.get('persona') or item.get('user_profile') or item.get('bio') or "",
                        "bio": item.get('bio', ""),
                        "profession": item.get('profession', ""),
                    }
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to read reddit_profiles.json: {e}")

        if not profiles and os.path.exists(twitter_csv):
            try:
                with open(twitter_csv, 'r', encoding='utf-8') as f:
                    for i, row in enumerate(csv.DictReader(f)):
                        persona = row.get('persona') or row.get('user_profile') or row.get('description') or ""
                        profiles[i] = {
                            "username": row.get('username') or row.get('name') or f"agent_{i}",
                            "persona": persona,
                            "bio": row.get('bio', ""),
                            "profession": row.get('profession', ""),
                        }
            except OSError as e:
                logger.warning(f"Failed to read twitter_profiles.csv: {e}")

        self._profiles_cache = profiles
        return profiles

    # ---------- activity reconstruction from DB ----------

    def _load_agent_activity(self, agent_id: int, max_items: int = 8) -> List[str]:
        """Pull an agent's own posts/comments from the simulation DB."""
        activity: List[str] = []
        for db_name in ("reddit_simulation.db", "twitter_simulation.db"):
            db_path = os.path.join(self.sim_dir, db_name)
            if not os.path.exists(db_path):
                continue
            try:
                conn = sqlite3.connect(db_path)
                conn.text_factory = str
                tables = {r[0] for r in conn.execute(
                    "select name from sqlite_master where type='table'").fetchall()}
                if 'post' in tables:
                    for (content,) in conn.execute(
                            "select content from post where user_id=? and content is not null "
                            "order by created_at limit ?", (agent_id, max_items)):
                        if content and content.strip():
                            activity.append(f"[发帖] {content.strip()}")
                if 'comment' in tables:
                    for (content,) in conn.execute(
                            "select content from comment where user_id=? and content is not null "
                            "order by created_at limit ?", (agent_id, max_items)):
                        if content and content.strip():
                            activity.append(f"[评论] {content.strip()}")
                conn.close()
            except sqlite3.Error as e:
                logger.warning(f"DB read failed ({db_name}) for agent {agent_id}: {e}")
        return activity[: max_items * 2]

    # ---------- interview ----------

    def _interview_one(self, agent_id: int, prompt: str) -> Dict[str, Any]:
        profiles = self._load_profiles()
        profile = profiles.get(int(agent_id))
        if not profile:
            return {"agent_id": agent_id, "response": "", "error": f"未找到该 Agent 的人设: {agent_id}"}

        persona = profile["persona"] or profile["bio"] or "一名普通的社交媒体用户。"
        activity = self._load_agent_activity(int(agent_id))

        system_content = (
            "你正在扮演一个社交媒体用户，请始终保持以下人设来回答问题。\n\n"
            f"【人设】\n{persona}\n"
        )
        if activity:
            system_content += (
                "\n【你在本次模拟中的历史发言】\n" + "\n".join(activity) +
                "\n\n请保持与上述立场和语气一致。"
            )

        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": f"{INTERVIEW_PROMPT_PREFIX}{prompt}"},
        ]

        try:
            content = self.llm.chat(messages=messages, temperature=0.7, max_tokens=800)
            return {"agent_id": agent_id, "response": content or ""}
        except Exception as e:
            logger.error(f"Offline interview failed for agent {agent_id}: {e}")
            return {"agent_id": agent_id, "response": "", "error": str(e)}

    def interview_batch(self, interviews: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Run a disk-backed batch interview.

        Returns a payload shaped like the live OASIS batch result so the
        existing frontend keeps working:
            {"interviews_count": N, "results": {"<agent_id>": {...}, ...}}
        """
        results: Dict[str, Any] = {}
        success_count = 0
        for item in interviews:
            agent_id = item.get('agent_id')
            prompt = item.get('prompt', '')
            if agent_id is None or not prompt:
                continue
            r = self._interview_one(agent_id, prompt)
            results[str(agent_id)] = r
            if r.get('response', '').strip():
                success_count += 1

        return {
            "success": success_count > 0,
            "interviews_count": len(results),
            "result": {"interviews_count": len(results), "results": results},
            "mode": "offline",
        }
