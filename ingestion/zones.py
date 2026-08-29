from __future__ import annotations


def tactical_zone(x: float, y: float) -> dict[str, bool | str]:
    channel = (
        "left_channel"
        if y < 20
        else "left_half_space"
        if y < 40
        else "centre"
        if y <= 60
        else "right_half_space"
        if y <= 80
        else "right_channel"
    )
    third = "defensive_third" if x < 33.333 else "middle_third" if x < 66.667 else "attacking_third"
    penalty_area = x >= 85.83 and 21.1 <= y <= 78.9
    six_yard_box = x >= 95 and 36.8 <= y <= 63.2
    zone_14 = 66.667 <= x < 83.333 and 36.667 <= y <= 63.333
    return {
        "third": third,
        "channel": channel,
        "penalty_area": penalty_area,
        "six_yard_box": six_yard_box,
        "zone_14": zone_14,
        "wide": y < 20 or y > 80,
        "central": 40 <= y <= 60,
    }
