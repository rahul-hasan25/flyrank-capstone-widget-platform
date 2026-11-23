import uuid
import logging
from typing import Dict, Any, Optional
from app.database import get_db

logger = logging.getLogger("side_effects")

def execute_submission_side_effects(
    submission_id: str,
    widget_id: str,
    payload: Dict[str, Any],
    simulate_failure: bool = False
) -> None:
    """
    Background worker for post-submission side effects (e.g. notifications / webhooks).
    Crucial contract: Exceptions must NEVER propagate to the HTTP response or break caller.
    """
    effect_id = f"eff_{uuid.uuid4().hex[:12]}"
    status = "success"
    error_message = None

    try:
        if simulate_failure:
            raise RuntimeError("Forced side-effect failure: simulated email/webhook downstream error")

        # Simulate email delivery / webhook dispatch
        email = payload.get("email", "unknown")
        logger.info(f"[SideEffect] Dispatched confirmation email to '{email}' for submission {submission_id}")

    except Exception as exc:
        status = "failed"
        error_message = str(exc)
        logger.error(f"[SideEffect] Side effect failed safely for submission {submission_id}: {exc}")

    # Record audit log for transparency
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO side_effect_logs (id, submission_id, effect_type, status, error_message)
                VALUES (?, ?, ?, ?, ?)
                """,
                (effect_id, submission_id, "email_notification", status, error_message)
            )
    except Exception as db_err:
        logger.error(f"[SideEffect] Failed to write side effect log to database: {db_err}")
