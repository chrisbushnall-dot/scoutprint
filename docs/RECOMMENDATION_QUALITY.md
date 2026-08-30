# Recommendation quality

Scoutprint separates similarity from recommendation confidence. It does not replace missing
values with zero and it does not describe a sparse comparison as equivalent to a complete one.

## Discovery stages

1. Apply recent-season, competition, age, minutes and data-tier filters.
2. Exclude every player-season belonging to the reference's reconciled canonical person.
3. Infer overlapping functional-role confidences from provider position plus the available
   goal threat, creation, passing, progression/carrying, defensive and spatial-zone evidence.
4. Remove candidates below 42% broad role compatibility. Opposite-side wide roles remain valid.
5. Calculate raw profile similarity with the existing statistical and exact spatial methods.
6. Calculate evidence quality, then rank by the evidence-adjusted recommendation score.
7. Collapse multiple candidate seasons to the highest-ranked season for each canonical person.

The broad role families are attacking wide / inside forward, creative attacker / #10, centre
forward, central / progressive midfielder, deep / defensive midfielder, fullback / wingback and
centre back. They are overlapping compatibility groups, not rigid player labels.

## Raw similarity and recommendation score

Raw Profile Match remains the similarity over the dimensions that can legitimately be compared.
Comparison Coverage remains the weighted share of requested evidence that was actually present.

Evidence quality is:

```text
60% comparison coverage
20% share of meaningful comparison categories
15% minutes reliability (square-root scale, fully reliable at 1,800 minutes)
 5% data-tier reliability (A 100%, B 92%, C 86%)
```

The confidence factor is `0.55 + 0.45 × evidence quality`. Recommendation Score is Raw Profile
Match multiplied by that factor. Raw similarity is therefore preserved and visible, while a
sparse match cannot outrank a similarly strong, well-supported comparison without a penalty.
Confidence is HIGH at 80+ evidence quality, MEDIUM at 62–79.9 and LOW below 62. The production
coverage filter defaults to 40%; it can be lowered deliberately to inspect weaker evidence.

## Explanations

Every result returns its three highest calculated category similarities and its two lowest.
Only available categories are included. Tier C results never receive or display a spatial score
when no legitimate spatial profile exists.

## Identity safeguards

The API uses reconciled canonical-person IDs for reference search, self-exclusion and result
collapse. Conservative cross-provider alias reconciliation requires either matching DOB plus
compatible names, or compatible first/surname evidence plus an overlapping normalized
team-season. Discovery never excludes or merges players using a query-time name-string match.
