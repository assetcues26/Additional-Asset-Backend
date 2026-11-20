from additional_asset.prompts.builders import (
    build_unified_phase1_prompt,
    build_unified_phase1_content_route_prompt,
    build_pinecone_selection_prompt,
)


def test_unified_prompt_builds():
    prompt = build_unified_phase1_prompt()
    assert "imageAnalysis" in prompt or "detectedAsset" in prompt or "JSON" in prompt
    assert "cost_lower_bound" not in prompt
    assert "currency MUST" not in prompt
    assert "CONTENT-BASED DUAL IMAGE ROUTING" not in prompt


def test_content_route_prompt_builds():
    prompt = build_unified_phase1_content_route_prompt()
    assert "CONTENT-BASED DUAL IMAGE ROUTING" in prompt
    assert "detectedAsset" in prompt or "imageAnalysis" in prompt
    assert "UNTRUSTED" in prompt or "Do not trust upload field names" in prompt
    assert "cost_lower_bound" not in prompt
    assert "SLOT NOTE AFTER BLIND VIEW" not in prompt
    assert "blind_view" not in prompt.lower()
    # barcode rules injected
    assert "zero_run_count" in prompt or "Virtual" in prompt or "asset_tag" in prompt


def test_selection_prompt_builds():
    prompt = build_pinecone_selection_prompt(
        detected_asset="Laptop",
        detected_description="Grey Dell laptop on desk",
        candidate_summary='[{"category":"IT","subcategory":"Laptop","makemodel":"Dell","score":0.9}]',
    )
    assert "Laptop" in prompt
    assert "Candidates" in prompt or "candidate" in prompt.lower()
