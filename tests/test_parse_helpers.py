from additional_asset.utils.helpers import to_int_or_none


def test_form_id_parsing_like_function_app():
    assert to_int_or_none("1001") == 1001
    assert to_int_or_none("1001.0") == 1001
