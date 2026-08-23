from retrieval.source_authority import Evidence, resolve


def test_current_policy_beats_deprecated():
    evidence = [
        Evidence(source="Policy v2", source_type="policy", status="DEPRECATED", content="Fee applies."),
        Evidence(source="Policy v3", source_type="policy", status="CURRENT", content="No fee for enterprise tier."),
    ]
    r = resolve(evidence)
    assert r.winning_evidence.source == "Policy v3"
    assert not r.should_escalate


def test_customer_agreement_overrides_general_policy():
    evidence = [
        Evidence(source="Policy v3", source_type="policy", status="CURRENT", content="Cancellation fee applies."),
        Evidence(source="Northstar Agreement", source_type="contract", account_scope="ACCT-001", content="No cancellation fee."),
    ]
    r = resolve(evidence, account_id="ACCT-001")
    assert r.winning_evidence.source == "Northstar Agreement"
    assert r.conflict_detected


def test_historical_ticket_never_authoritative_alone():
    evidence = [
        Evidence(source="Ticket #4821", source_type="historical_ticket", content="Agent granted refund last time."),
    ]
    r = resolve(evidence)
    assert r.winning_evidence is None
    assert r.should_escalate


def test_two_current_sources_conflicting_escalates():
    evidence = [
        Evidence(source="Policy v3", source_type="policy", status="CURRENT", content="Refunds within 30 days."),
        Evidence(source="SOP-Refunds", source_type="sop", content="Refunds within 14 days."),
    ]
    r = resolve(evidence)
    assert r.should_escalate
    assert r.conflict_detected


def test_no_evidence_escalates():
    r = resolve([])
    assert r.should_escalate
