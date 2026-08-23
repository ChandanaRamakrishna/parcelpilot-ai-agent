from tools.escalation import (
    prepare_escalation,
    create_escalation,
)


def test_prepare_does_not_create():
    result = prepare_escalation(
        issue="Conflicting cancellation rules",
        reason="Two equally authoritative sources conflict",
        current_account_id="ACCT-001",
        related_order="ORD-1001",
    )

    assert "pending_action" in result
    assert result["pending_action"]["type"] == "create_escalation"
    assert result["pending_action"]["data"]["account_id"] == "ACCT-001"


def test_create_requires_confirmation():
    prepared = prepare_escalation(
        issue="Test issue",
        reason="Test reason",
        current_account_id="ACCT-001",
    )

    result = create_escalation(
        confirmed=False,
        pending_action=prepared["pending_action"],
    )

    assert "error" in result
    assert "confirmation" in result["error"].lower()


def test_create_requires_pending_action():
    result = create_escalation(
        confirmed=True,
        pending_action=None,
    )

    assert "error" in result
    assert "pending escalation" in result["error"].lower()


def test_confirmed_escalation_is_created():
    prepared = prepare_escalation(
        issue="Test escalation",
        reason="Testing confirmed escalation creation",
        current_account_id="ACCT-001",
        related_order="ORD-1001",
    )

    result = create_escalation(
        confirmed=True,
        pending_action=prepared["pending_action"],
    )

    assert "result" in result
    assert result["result"]["status"] == "created"
    assert result["result"]["escalation_id"].startswith("ESC-")