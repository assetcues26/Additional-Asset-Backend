from additional_asset.services.view_classifier import pick_asset_and_tag_slots


def test_detects_swap():
    asset_slot, tag_slot, swapped = pick_asset_and_tag_slots(
        {"asset": "tag_closeup", "barcode": "full_asset"}
    )
    assert asset_slot == "barcode"
    assert tag_slot == "asset"
    assert swapped is True


def test_normal_slots():
    asset_slot, tag_slot, swapped = pick_asset_and_tag_slots(
        {"asset": "full_asset", "barcode": "tag_closeup"}
    )
    assert asset_slot == "asset"
    assert tag_slot == "barcode"
    assert swapped is False
