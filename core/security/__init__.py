"""
Core Security Module for AntiHalu / Godmode.
Contains standalone implementations of:
- parseltongue: text obfuscation & evasive transform pipeline
- race: multi-model race & benchmarking engine
- auto_jailbreak: iterative vulnerability testing & automated guardrail evaluation
"""

from .parseltongue import (
    generate_variants,
    detect_triggers,
    TRIGGER_WORDS,
)
from .race import (
    race_models,
    race_godmode_classic,
    ULTRAPLINIAN_MODELS,
)
from .auto_jailbreak import (
    auto_jailbreak,
    undo_jailbreak,
    _detect_model_family,
    _get_current_model,
)

# Convenience alias
classic_race = race_godmode_classic

__all__ = [
    "generate_variants",
    "detect_triggers",
    "TRIGGER_WORDS",
    "race_models",
    "race_godmode_classic",
    "classic_race",
    "ULTRAPLINIAN_MODELS",
    "auto_jailbreak",
    "undo_jailbreak",
    "_detect_model_family",
    "_get_current_model",
]
