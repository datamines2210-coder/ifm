from app.logistics.dispatch import DispatchService, HEAD_OFFICE_GODOWN


def test_dispatch_falls_back_to_office_courier_without_partner_configured():
    service = DispatchService()
    result = service.assign("ord_test_1", "560001")
    assert result["dispatch_source"] == "office_direct"
    assert result["courier_partner"] == "indian_family_courier"
    assert result["tracking_number"].startswith("ifm_courier_")
    assert result["status"] == "assigned"


def test_dispatch_unknown_pincode_uses_head_office_godown():
    service = DispatchService()
    result = service.assign("ord_test_2", "999999")
    assert result["hub_name"] == HEAD_OFFICE_GODOWN


def test_dispatch_status_update_and_get():
    service = DispatchService()
    service.assign("ord_test_3", "110001")
    assert service.update_status("ord_test_3", "delivered") is True
    status = service.get_status("ord_test_3")
    assert status["status"] == "delivered"
    assert service.update_status("does_not_exist", "delivered") is False
