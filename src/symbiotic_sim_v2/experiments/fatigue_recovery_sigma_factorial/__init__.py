"""Stage 8A.3.1 fatigue-recovery × exploration-width validation."""

from .conditions import FactorialValidationCondition, factorial_conditions
from .config import FactorialValidationConfig, factorial_plan_projection

__all__ = [
    "FactorialValidationCondition",
    "FactorialValidationConfig",
    "factorial_conditions",
    "factorial_plan_projection",
]
