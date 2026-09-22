from supportpilot.tools.crm import check_service_status, lookup_invoice, lookup_order
from supportpilot.tools.errors import get_error_code_doc


def test_check_service_status_known_service():
    result = check_service_status.invoke({"service": "api"})
    assert result["service"] == "api"
    assert "status" in result


def test_check_service_status_unknown_service():
    result = check_service_status.invoke({"service": "not-a-real-service"})
    assert "error" in result


def test_lookup_order_known():
    result = lookup_order.invoke({"order_id": "ord-5001"})
    assert result["order_id"] == "ORD-5001"
    assert result["plan"] == "pro"


def test_lookup_order_unknown():
    result = lookup_order.invoke({"order_id": "ORD-9999"})
    assert "error" in result


def test_lookup_invoice_known():
    result = lookup_invoice.invoke({"invoice_id": "inv-1001"})
    assert result["invoice_id"] == "INV-1001"
    assert result["amount"] == 49.0


def test_lookup_invoice_unknown():
    result = lookup_invoice.invoke({"invoice_id": "INV-0000"})
    assert "error" in result


def test_get_error_code_doc_known():
    result = get_error_code_doc.invoke({"code": "e105"})
    assert result["code"] == "E105"
    assert "meaning" in result and "fix" in result


def test_get_error_code_doc_unknown():
    result = get_error_code_doc.invoke({"code": "E999"})
    assert "error" in result
