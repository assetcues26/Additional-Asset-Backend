"""Azure Functions entry — Additional Asset generation API."""

from __future__ import annotations

import base64
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import azure.functions as func

from additional_asset.core import config
from additional_asset.core.models import AdditionalAssetRequest, to_external_response
from additional_asset.services.pipeline import run_additional_asset
from additional_asset.utils.helpers import to_int_or_none

app = func.FunctionApp()
logging.basicConfig(level=getattr(logging, config.log_level(), logging.INFO))


def _error(request_id: str, code: str, detail: str, status: int = 400) -> func.HttpResponse:
    body = {
        "request_id": request_id,
        "error": code,
        "detail": detail,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return func.HttpResponse(json.dumps(body), status_code=status, mimetype="application/json")


def _read_file_bytes(file_item) -> bytes:
    data = file_item.read()
    if isinstance(data, str):
        return data.encode("utf-8")
    return data or b""


def _parse_multipart(req: func.HttpRequest) -> AdditionalAssetRequest:
    if not config.accept_multipart():
        raise ValueError("Multipart transport is disabled")

    asset_file = req.files.get("assetimage") or req.files.get("AssetImage")
    barcode_file = req.files.get("barcodeimage") or req.files.get("BarcodeImage")
    if asset_file is None:
        raise ValueError("Missing required field: assetimage")
    if barcode_file is None:
        raise ValueError("Missing required field: barcodeimage")

    form = {k: v for k, v in (req.form or {}).items()}
    customerid = to_int_or_none(form.get("customerid") or form.get("CustomerId"))
    categoryid = to_int_or_none(form.get("categoryid") or form.get("CategoryId"))
    assetclassid = to_int_or_none(form.get("assetclassid") or form.get("AssetClassId"))

    if customerid is None:
        raise ValueError("Missing or invalid required field: customerid")

    return AdditionalAssetRequest(
        asset_image_bytes=_read_file_bytes(asset_file),
        barcode_image_bytes=_read_file_bytes(barcode_file),
        customerid=customerid,
        categoryid=categoryid,
        assetclassid=assetclassid,
        source="multipart",
    )


def _decode_b64_image(value: Any, field: str) -> bytes:
    if value is None:
        raise ValueError(f"Missing required field: {field}")
    if isinstance(value, bytes):
        return value
    text = str(value).strip()
    if "," in text and text.lower().startswith("data:"):
        text = text.split(",", 1)[1]
    try:
        return base64.b64decode(text, validate=False)
    except Exception as exc:
        raise ValueError(f"Invalid base64 for {field}") from exc


def _parse_json(req: func.HttpRequest) -> AdditionalAssetRequest:
    if not config.accept_json():
        raise ValueError("JSON transport is disabled")
    try:
        body = req.get_json()
    except Exception as exc:
        raise ValueError(f"Invalid JSON body: {exc}") from exc
    if not isinstance(body, dict):
        raise ValueError("JSON body must be an object")

    # Accept both camelCase and lowercase
    def pick(*keys):
        for k in keys:
            if k in body and body[k] is not None:
                return body[k]
        return None

    customerid = to_int_or_none(pick("customerid", "CustomerId"))
    categoryid = to_int_or_none(pick("categoryid", "CategoryId"))
    assetclassid = to_int_or_none(pick("assetclassid", "AssetClassId"))

    if customerid is None:
        raise ValueError("Missing or invalid required field: customerid")

    return AdditionalAssetRequest(
        asset_image_bytes=_decode_b64_image(pick("assetimage", "AssetImage"), "assetimage"),
        barcode_image_bytes=_decode_b64_image(pick("barcodeimage", "BarcodeImage"), "barcodeimage"),
        customerid=customerid,
        categoryid=categoryid,
        assetclassid=assetclassid,
        source="json",
    )


def _parse_request(req: func.HttpRequest) -> AdditionalAssetRequest:
    content_type = (req.headers.get("Content-Type") or req.headers.get("content-type") or "").lower()
    has_files = bool(getattr(req, "files", None)) and len(req.files) > 0

    if "multipart/form-data" in content_type or has_files:
        return _parse_multipart(req)
    if "application/json" in content_type:
        return _parse_json(req)

    # Fallback: try JSON then multipart
    try:
        return _parse_json(req)
    except Exception:
        return _parse_multipart(req)


@app.function_name("additional_asset")
@app.route(route="additional_asset", methods=["POST"], auth_level=func.AuthLevel.ANONYMOUS)
def additional_asset(req: func.HttpRequest) -> func.HttpResponse:
    request_id = str(uuid.uuid4())
    try:
        parsed = _parse_request(req)
    except ValueError as exc:
        return _error(request_id, "PAYLOAD_VALIDATION_FAILED", str(exc), 400)
    except Exception as exc:
        logging.exception("[%s] parse failed", request_id)
        return _error(request_id, "PAYLOAD_VALIDATION_FAILED", str(exc), 400)

    try:
        result = run_additional_asset(parsed, request_id)
        # Soft failures still return 200 with field-level nulls when phase1 worked;
        # only hard preprocess / phase1 total failure uses 502 via error set early.
        if result.get("error") and str(result["error"]).startswith("IMAGE_"):
            status = 400
        elif result.get("error") and str(result["error"]).startswith("PHASE1_"):
            status = 502
        else:
            status = 200
        external = to_external_response(result)
        return func.HttpResponse(
            json.dumps(external, default=str),
            status_code=status,
            mimetype="application/json",
        )
    except Exception as exc:
        logging.exception("[%s] unhandled", request_id)
        return _error(request_id, "INTERNAL_SERVER_ERROR", str(exc), 500)


@app.function_name("health")
@app.route(route="health", methods=["GET"], auth_level=func.AuthLevel.ANONYMOUS)
def health(req: func.HttpRequest) -> func.HttpResponse:
    body = {
        "status": "healthy",
        "service": "additional-asset",
        "model_active": config.gemini_model_name(),
        "text_model": config.gemini_text_model_name(),
        "pinecone_lookup": config.include_pinecone_lookup(),
        "pixel_gate": config.blank_image_gate_enabled(),
        "phase1_content_route": config.phase1_content_route_enabled(),
        "blind_view": config.blind_view_enabled(),
        "accept_multipart": config.accept_multipart(),
        "accept_json": config.accept_json(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return func.HttpResponse(json.dumps(body), status_code=200, mimetype="application/json")
