"""The catalog the resolver uses comes from the database (2026-10-28): the infrastructure hands the domain the
instruments and their names; the JSON file is only the seed and the catalog of the tests without a database. The
catalog version follows its content, so a name added or removed makes the works be analysed again."""
import json

from backend.domain.instrument_catalog import (CATALOG_PATH, catalog_entries, catalog_version, match_instrument_name,
                                               seed_instruments, use_catalog)


def _seed_items():
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["instruments"]


def test_the_seed_catalog_keeps_the_version_of_the_file():
    assert catalog_version() == json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["version"]
    assert [item["id"] for item in seed_instruments()] == [item["id"] for item in _seed_items()]


def test_a_catalog_handed_by_the_infrastructure_replaces_the_seed():
    items = _seed_items()
    flugelhorn = next(item for item in items if item["id"] == "flugelhorn.bb")
    flugelhorn["aliases"].append("fiscornio")
    try:
        use_catalog(items)
        assert match_instrument_name("Fiscornio 2").identity.canonical_id == "flugelhorn.bb"
        assert catalog_version() != json.loads(CATALOG_PATH.read_text(encoding="utf-8"))["version"]
        assert catalog_version().startswith("instrument-catalog-v5+")
    finally:
        use_catalog(None)
    assert match_instrument_name("Fiscornio 2").identity is None, "back to the seed"


def test_the_same_content_in_another_spelling_keeps_the_version():
    """Names are compared normalized and without order: the database gives them back in another order and case."""
    items = _seed_items()
    for item in items:
        item["aliases"] = sorted((alias.upper() for alias in item["aliases"]), reverse=True)
    try:
        use_catalog(items)
        assert catalog_version() == "instrument-catalog-v5"
        assert len(catalog_entries()) == len(_seed_items())
    finally:
        use_catalog(None)
