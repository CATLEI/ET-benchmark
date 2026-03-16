# Preprocessing step: callable(signal, params) -> signal
from typing import Dict, Any, Callable
StepFn = Callable[[Any, Dict[str, Any]], Any]
