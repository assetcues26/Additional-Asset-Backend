from additional_asset.services.tag_merge import merge_tag_fields, order_decoded_prefer_tag_like


def test_zxing_wins():
    out = merge_tag_fields(
        {"detectedtagnumber": "OCR123"},
        [{"text": "ZXING999", "format": "QRCode"}],
    )
    assert out["decodedtagnumber"] == "ZXING999"
    assert out["tagnumbersource"] == "decoded"
    assert out["detectedtagnumber"] in ("OCR123", "ZXING999")


def test_prefer_tag_like_over_datamatrix_serial():
    codes = [
        {
            "value": "5CD2479STB,6F9U0PA#ACJ,15-fb0052AX",
            "format": "DATAMATRIX",
            "type": "barcode",
            "image": "barcode",
        },
        {
            "value": "10000058",
            "format": "QRCODE",
            "type": "asset_tag",
            "image": "barcode",
        },
    ]
    ordered = order_decoded_prefer_tag_like(codes)
    assert ordered[0]["value"] == "10000058"
    out = merge_tag_fields({}, codes)
    assert out["decodedtagnumber"] == "10000058"


def test_vision_when_no_zxing():
    out = merge_tag_fields({"detectedtagnumber": "TAG42"}, [])
    assert out["decodedtagnumber"] is None
    assert out["detectedtagnumber"] == "TAG42"
    assert out["tagnumbersource"] == "vision"


def test_na_when_empty():
    out = merge_tag_fields({}, [])
    assert out["tagnumbersource"] == "NA"
