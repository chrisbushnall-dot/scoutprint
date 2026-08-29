from ingestion.statsbomb import canonical_id
from ingestion.zones import tactical_zone


def test_canonical_ids_are_stable_and_provider_scoped():
    assert canonical_id("player", "a", 1) == canonical_id("player", "a", 1)
    assert canonical_id("player", "a", 1) != canonical_id("player", "b", 1)


def test_tactical_zones():
    box = tactical_zone(90, 50)
    assert box["penalty_area"] and box["central"] and box["third"] == "attacking_third"
    assert tactical_zone(75, 30)["channel"] == "left_half_space"
