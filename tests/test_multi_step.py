from tools.escalation import create_escalation, prepare_escalation


def test_escalation_requires_prepare_before_create():
    result = create_escalation(confirmed=True, pending_action=None)
    assert "error" in result


def test_escalation_requires_confirmation():
    draft = prepare_escalation(
        issue="Late pickup",
        reason="Policy exception",
        current_account_id="ACCT-001"
    )
    result = create_escalation(
        confirmed=False,
        pending_action=draft["pending_action"]
    )
    assert "error" in result


def test_escalation_succeeds_after_prepare_and_confirm(tmp_path, monkeypatch):
    import tools.escalation as esc_module
    monkeypatch.setattr(esc_module, "DB_PATH", tmp_path / "test.db")

    draft = prepare_escalation(
        issue="Late pickup",
        reason="Policy exception",
        current_account_id="ACCT-001"
    )
    result = create_escalation(
        confirmed=True,
        pending_action=draft["pending_action"]
    )

    assert "result" in result
    assert result["result"]["status"] == "created"