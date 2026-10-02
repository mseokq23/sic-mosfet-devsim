from sicsim.schema import selection_json_schema, validate_selection

ALLOWED = [f"C{i:04d}" for i in range(20)]


def sel(ids, **kw):
    d = {"selected_ids": ids, "reason_codes": ["HIGH_UNCERTAINTY"], "short_rationale": "test"}
    d.update(kw)
    return d


def test_accept():
    s, r = validate_selection(sel(ALLOWED[:5]), ALLOWED, 5)
    assert s is not None and r is None


def test_accept_json_string():
    import json
    s, r = validate_selection(json.dumps(sel(ALLOWED[:3])), ALLOWED, 3)
    assert s is not None


def test_out_of_list_rejects_whole_response():
    s, r = validate_selection(sel(ALLOWED[:4] + ["C9999"]), ALLOWED, 5)
    assert s is None and r.startswith("OUT_OF_LIST")


def test_duplicates():
    s, r = validate_selection(sel(ALLOWED[:4] + [ALLOWED[0]]), ALLOWED, 5)
    assert s is None and r == "DUPLICATE_IDS"


def test_batch_size():
    s, r = validate_selection(sel(ALLOWED[:4]), ALLOWED, 5)
    assert s is None and r.startswith("BATCH_SIZE")


def test_invalid_json():
    s, r = validate_selection("{not json", ALLOWED, 5)
    assert s is None and r.startswith("INVALID_JSON")


def test_extra_field_and_bad_reason():
    assert validate_selection(sel(ALLOWED[:2], extra=1), ALLOWED, 2)[1].startswith("SCHEMA")
    assert validate_selection(sel(ALLOWED[:2], reason_codes=["MAGIC"]), ALLOWED, 2)[1].startswith("SCHEMA")


def test_already_evaluated():
    s, r = validate_selection(sel(ALLOWED[:2]), ALLOWED, 2, already_evaluated=[ALLOWED[1]])
    assert s is None and r.startswith("ALREADY_EVALUATED")


def test_json_schema_shape():
    s = selection_json_schema(ALLOWED)
    assert s["properties"]["selected_ids"]["items"]["enum"] == ALLOWED
    assert s["additionalProperties"] is False
