from tools.data_lookup import lookup_operational_data


def test_own_account_access():
    result = lookup_operational_data(
        query_type="get_account",
        current_account_id="ACCT-001"
    )

    assert "result" in result
    assert result["result"]["account_id"] == "ACCT-001"


def test_own_order_access():
    result = lookup_operational_data(
        query_type="get_order",
        current_account_id="ACCT-001",
        order_id="ORD-1001"
    )

    assert "result" in result
    assert result["result"]["order_id"] == "ORD-1001"
    assert result["result"]["account_id"] == "ACCT-001"


def test_cross_account_access_denied():
    result = lookup_operational_data(
        query_type="get_order",
        current_account_id="ACCT-001",
        order_id="ORD-2001"
    )

    assert "error" in result
    assert "access denied" in result["error"].lower()


def test_orders_are_scoped_to_current_account():
    result = lookup_operational_data(
        query_type="get_orders_for_account",
        current_account_id="ACCT-001"
    )

    assert "result" in result

    for order in result["result"]:
        assert order["account_id"] == "ACCT-001"