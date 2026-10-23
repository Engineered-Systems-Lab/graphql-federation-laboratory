"""Shared helpers of the study harness: the results folder, hashing, atomic writes and the secret redactor.

Standard library only. Nothing here derives a location from the path or the name of the lab checkout.
"""
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

RESULTS_ENV = 'LAB_RESULTS_DIR'
DEFAULT_RESULTS_DIR = Path.home() / 'lab-results'
SECRET_ENV_NAMES = ('ANTHROPIC_API_KEY', 'OPENAI_API_KEY')


def results_dir():
    """The machine-local root of raw run results (setting LAB_RESULTS_DIR, default the folder lab-results in the user's home)."""
    return Path(os.environ.get(RESULTS_ENV) or DEFAULT_RESULTS_DIR)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds')


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def sha256_json(value):
    return sha256_bytes(canonical_json(value).encode('utf-8'))


def write_json_atomic(path, value):
    """Write a JSON file (UTF-8, LF) through a temporary file and an atomic replace."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + '\n'
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + '.', suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def append_jsonl(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a', encoding='utf-8', newline='\n') as handle:
        handle.write(json.dumps(value, sort_keys=True, ensure_ascii=False) + '\n')
        handle.flush()
        os.fsync(handle.fileno())


def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    with open(path, encoding='utf-8') as handle:
        return [json.loads(line) for line in handle if line.strip()]


class Redactor:
    """Replaces the exact values of secrets in anything the harness writes. A last line of defence: no code path is meant to hold a key
    in text it writes."""

    def __init__(self, secrets=()):
        self.secrets = sorted({s for s in secrets if s and len(s) >= 8}, key=len, reverse=True)

    @classmethod
    def from_env(cls, env=None):
        env = os.environ if env is None else env
        return cls(env.get(name) for name in SECRET_ENV_NAMES)

    def text(self, value):
        for secret in self.secrets:
            value = value.replace(secret, '[REDACTED]')
        return value

    def deep(self, value):
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, list):
            return [self.deep(item) for item in value]
        if isinstance(value, dict):
            return {self.text(str(key)): self.deep(item) for key, item in value.items()}
        return value


def child_environment(env=None, extra=None, strip=SECRET_ENV_NAMES):
    """The environment for a subprocess that does not need the API keys (the stack, docker compose, the MCP servers)."""
    env = dict(os.environ if env is None else env)
    for name in strip:
        env.pop(name, None)
    env.update(extra or {})
    return env
