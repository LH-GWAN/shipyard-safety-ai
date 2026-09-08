"""규칙 카탈로그 로딩(프로세스 단위 캐시)."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.core.data_files import load_rules
from app.domain.models import RuleSpec


@lru_cache
def get_rules() -> tuple[RuleSpec, ...]:
    return tuple(load_rules(get_settings().rules_path))


def clear_rule_cache() -> None:
    get_rules.cache_clear()
