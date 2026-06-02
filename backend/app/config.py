"""
Configuration Management
Loads configuration from .env file in project root directory
"""

import os
from dotenv import load_dotenv

# Load .env file from project root
# Path: MiroFish/.env (relative to backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # If no .env in root, try to load environment variables (for production)
    load_dotenv(override=True)


class Config:
    """Flask configuration class"""

    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'

    # JSON configuration - disable ASCII escaping to display Chinese directly (not as \uXXXX)
    JSON_AS_ASCII = False

    # LLM configuration (unified OpenAI format)
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'http://localhost:11434/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'qwen2.5:32b')

    # Neo4j configuration
    NEO4J_URI = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
    NEO4J_USER = os.environ.get('NEO4J_USER', 'neo4j')
    NEO4J_PASSWORD = os.environ.get('NEO4J_PASSWORD', 'mirofish')

    # Embedding configuration
    EMBEDDING_PROVIDER = os.environ.get('EMBEDDING_PROVIDER', 'ollama').lower()
    EMBEDDING_MODEL = os.environ.get('EMBEDDING_MODEL', 'nomic-embed-text')
    EMBEDDING_BASE_URL = os.environ.get('EMBEDDING_BASE_URL', 'http://localhost:11434')
    EMBEDDING_API_KEY = os.environ.get('EMBEDDING_API_KEY', '')
    EMBEDDING_DIMENSION = int(os.environ.get('EMBEDDING_DIMENSION', '768'))

    # File upload configuration
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}

    # Text processing configuration
    DEFAULT_CHUNK_SIZE = 500  # Default chunk size
    DEFAULT_CHUNK_OVERLAP = 50  # Default overlap size

    # OASIS simulation configuration
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')

    # OASIS platform available actions configuration
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]

    # Report Agent configuration
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))

    @classmethod
    def validate(cls):
        """Validate required configuration"""
        errors = []
        if not cls.LLM_API_KEY:
            errors.append("LLM_API_KEY not configured (set to any non-empty value, e.g. 'ollama')")
        if not cls.NEO4J_URI:
            errors.append("NEO4J_URI not configured")
        if not cls.NEO4J_PASSWORD:
            errors.append("NEO4J_PASSWORD not configured")
        return errors

    # Mapping of editable settings -> Config attribute name.
    # Only these can be changed via the settings API.
    _EDITABLE_KEYS = {
        "LLM_API_KEY": "LLM_API_KEY",
        "LLM_BASE_URL": "LLM_BASE_URL",
        "LLM_MODEL_NAME": "LLM_MODEL_NAME",
        "EMBEDDING_PROVIDER": "EMBEDDING_PROVIDER",
        "EMBEDDING_MODEL": "EMBEDDING_MODEL",
        "EMBEDDING_BASE_URL": "EMBEDDING_BASE_URL",
        "EMBEDDING_API_KEY": "EMBEDDING_API_KEY",
        "EMBEDDING_DIMENSION": "EMBEDDING_DIMENSION",
        # OASIS/CAMEL reads OPENAI_* from env; keep them in sync with LLM_*
        "OPENAI_API_KEY": "LLM_API_KEY",
        "OPENAI_API_BASE_URL": "LLM_BASE_URL",
    }

    @classmethod
    def apply_updates(cls, updates: dict):
        """
        Apply a dict of {ENV_KEY: value} to the in-memory Config class AND
        os.environ (so subsequently spawned OASIS subprocesses inherit them).

        - Keys not in _EDITABLE_KEYS are ignored.
        - Empty / None values are skipped (keep existing — "leave default").
        - EMBEDDING_DIMENSION is coerced to int.
        Returns the dict of keys actually changed (env_key -> new value).
        """
        applied = {}
        for env_key, raw in (updates or {}).items():
            if env_key not in cls._EDITABLE_KEYS:
                continue
            if raw is None:
                continue
            value = str(raw).strip()
            if value == "":
                continue  # leave default / unchanged

            attr = cls._EDITABLE_KEYS[env_key]
            if attr == "EMBEDDING_DIMENSION":
                try:
                    setattr(cls, attr, int(value))
                except ValueError:
                    continue
            elif attr == "EMBEDDING_PROVIDER":
                setattr(cls, attr, value.lower())
            else:
                setattr(cls, attr, value)

            # Mirror into the live process env so child processes inherit it
            os.environ[env_key] = value
            applied[env_key] = value
        return applied

    @classmethod
    def env_file_path(cls):
        """Absolute path to the project-root .env that should be persisted."""
        return os.path.abspath(os.path.join(os.path.dirname(__file__), '../../.env'))

    @classmethod
    def persist_to_env_file(cls, updates: dict):
        """
        Persist {ENV_KEY: value} into the project-root .env, updating existing
        lines in place and appending missing keys. Comments/blank lines and
        unrelated keys are preserved. Empty values are skipped.
        """
        path = cls.env_file_path()
        # Filter to editable, non-empty values
        clean = {}
        for k, v in (updates or {}).items():
            if k in cls._EDITABLE_KEYS and v is not None and str(v).strip() != "":
                clean[k] = str(v).strip()
        if not clean:
            return path

        lines = []
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                lines = f.read().splitlines()

        remaining = dict(clean)
        out = []
        for line in lines:
            stripped = line.lstrip()
            if stripped and not stripped.startswith('#') and '=' in stripped:
                key = stripped.split('=', 1)[0].strip()
                if key in remaining:
                    out.append(f"{key}={remaining.pop(key)}")
                    continue
            out.append(line)

        for key, val in remaining.items():
            out.append(f"{key}={val}")

        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(out) + '\n')
        return path

