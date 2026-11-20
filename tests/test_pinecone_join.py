from additional_asset.core.models import AdditionalAssetRequest, empty_response, to_external_response
from additional_asset.services.pinecone_service import ids_from_candidate, _scope_filter
from additional_asset.services.pipeline import _apply_masterdata_join


def test_ids_from_candidate_maps_pinecone_row():
    row = {
        "assetclass": "EI&E",
        "assetclassid": 1006,
        "category": "EI&E",
        "categoryname": "EI&E",
        "categoryid": 1018,
        "subcategory": "BATTERIES",
        "subcategoryid": 1063,
        "makemodel": "Exide",
        "makemodelid": 24525,
        "customerid": 1063,
    }
    ids = ids_from_candidate(row)
    assert ids["assetclassname"] == "EI&E"
    assert ids["assetclassid"] == 1006
    assert ids["categoryname"] == "EI&E"
    assert ids["categoryid"] == 1018
    assert ids["subcategoryname"] == "BATTERIES"
    assert ids["subcategoryid"] == 1063
    assert ids["makemodel"] == "Exide"
    assert ids["makemodelid"] == 24525


def test_ids_from_candidate_null_row():
    ids = ids_from_candidate(None)
    assert ids["assetclassid"] is None
    assert ids["categoryid"] is None
    assert ids["subcategoryid"] is None
    assert ids["makemodelid"] is None


def test_scope_filter_customer_only():
    f = _scope_filter(1063, None, None)
    assert f == {"customerid": {"$eq": 1063}}


def test_scope_filter_with_both_ids():
    f = _scope_filter(1063, 1006, 1018)
    assert f == {
        "$and": [
            {"customerid": {"$eq": 1063}},
            {"assetclassid": {"$eq": 1006}},
            {"categoryid": {"$eq": 1018}},
        ]
    }


def test_join_fills_from_row_when_ids_absent():
    req = AdditionalAssetRequest(
        asset_image_bytes=b"a",
        barcode_image_bytes=b"b",
        customerid=1063,
        categoryid=None,
        assetclassid=None,
    )
    response = empty_response("rid", customerid=1063)
    ids = ids_from_candidate(
        {
            "assetclass": "EI&E",
            "assetclassid": 1006,
            "category": "EI&E",
            "categoryid": 1018,
            "subcategory": "BATTERIES",
            "subcategoryid": 1063,
            "makemodel": "Exide",
            "makemodelid": 24525,
        }
    )
    _apply_masterdata_join(response, req, ids)
    assert response["assetclassid"] == 1006
    assert response["assetclassname"] == "EI&E"
    assert response["categoryid"] == 1018
    assert response["categoryname"] == "EI&E"
    assert response["subcategoryid"] == 1063
    assert response["makemodel"] == "Exide"


def test_join_echoes_user_ids_and_null_pick():
    req = AdditionalAssetRequest(
        asset_image_bytes=b"a",
        barcode_image_bytes=b"b",
        customerid=1063,
        categoryid=1012,
        assetclassid=1006,
    )
    response = empty_response("rid", customerid=1063, categoryid=1012, assetclassid=1006)
    _apply_masterdata_join(response, req, ids_from_candidate(None))
    assert response["categoryid"] == 1012
    assert response["assetclassid"] == 1006
    assert response["categoryname"] is None
    assert response["assetclassname"] is None
    assert response["subcategoryid"] is None
    assert response["makemodel"] is None


def test_external_response_pascal_case():
    internal = empty_response("rid", customerid=1063, categoryid=1018, assetclassid=1006)
    internal["imageAnalysis"] = "analysis"
    internal["detectedAsset"] = "Exide battery"
    internal["detected_description"] = "Lead-acid battery"
    internal["condition"] = {"grade": "Good"}
    internal["decodedtagnumber"] = "1000001442"
    internal["detectedtagnumber"] = "1000001442"
    internal["tagnumbersource"] = "decoded"
    internal["assetclassname"] = "EI&E"
    internal["categoryname"] = "EI&E"
    internal["subcategoryname"] = "BATTERIES"
    internal["subcategoryid"] = 1063
    internal["makemodel"] = "Exide"
    internal["makemodelid"] = 24525

    external = to_external_response(internal)
    assert external["ImageAnalysis"] == "analysis"
    assert external["AssetName"] == "Exide battery"
    assert external["Description"] == "Lead-acid battery"
    assert external["AssetClassName"] == "EI&E"
    assert external["AssetClassId"] == 1006
    assert external["CategoryName"] == "EI&E"
    assert external["CategoryId"] == 1018
    assert external["SubCategoryName"] == "BATTERIES"
    assert external["SubCategoryId"] == 1063
    assert external["MakeModel"] == "Exide"
    assert external["MakeModelId"] == 24525
    assert external["CustomerId"] == 1063
    assert external["AssetCondition"] == {"grade": "Good"}
    assert external["TagNumber"] == {
        "decodedtagnumber": "1000001442",
        "detectedtagnumber": "1000001442",
        "tagnumbersource": "decoded",
    }
    assert "cost_lower_bound" not in external
    assert "currency" not in external
