from typing import Optional
import logging
from core.config import get_config

logger = logging.getLogger(__name__)

# Singleton orchestrator accessor placed outside app module to avoid circular imports
_v6_orchestrator = None

def get_v6_orchestrator():
    global _v6_orchestrator
    if _v6_orchestrator is None:
        config = get_config()
        try:
            module_path, class_name = config.orchestrator_class.split(":", 1)
            mod = __import__(module_path, fromlist=[class_name])
            OrchestratorClass = getattr(mod, class_name)
            _v6_orchestrator = OrchestratorClass()
            logger.info("Created V6 orchestrator singleton: %s", config.orchestrator_class)
        except Exception as error:
            logger.error("Failed to create V6 orchestrator: %s", error)
            raise
    return _v6_orchestrator


def get_task_scheduler():
    """Get the global task scheduler instance."""
    from core.services.task_scheduler import task_scheduler
    return task_scheduler
