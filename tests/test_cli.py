from prodrag.cli import _model_json
from prodrag.models import ConfidenceLevel, QueryResponse, TicketCategory


def test_model_json_is_safe_for_legacy_windows_consoles() -> None:
    response = QueryResponse(
        request_id="request-1",
        category=TicketCategory.API_LIMITS,
        confidence=ConfidenceLevel.HIGH,
        requires_human_review=False,
        answered=True,
        answer="Too\u202fMany\u202fRequests",
    )

    payload = _model_json(response)

    payload.encode("ascii")
    assert r"\u202f" in payload
