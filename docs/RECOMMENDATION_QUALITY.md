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
6. Calculate evidence quality and functional-role fit, then rank by the evidence-and-role-
   adjusted recommendation score.
7. Collapse multiple candidate seasons to the highest-ranked season for each canonical person.

Attacking roles distinguish centre forward / box 9, scoring wide forward / inside forward,
creative wide forward, second striker, creative #10 / attacking midfielder and hybrid
creator-scorer. Central/deep midfield, fullback/wingback and centre-back families remain. These
are overlapping profiles rather than rigid labels. Provider position is only a prior; scoring,
creation, involvement, progression, box occupation, half-space use and width determine the
functional mixture. A soft dominant-archetype mismatch penalty stops a pure box 9 from being
treated as interchangeable with a wide scorer or hybrid creator while preserving secondary-role
memberships and mirror-flank matches.

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

The confidence factor is `0.55 + 0.45 × evidence quality`. The role factor is
`0.35 + 0.65 × functional-role compatibility`. Recommendation Score is Raw Profile Match
multiplied by both factors. Raw similarity is therefore preserved and visible, while sparse or
functionally mismatched comparisons cannot outrank similarly strong, well-supported role fits.
Confidence is HIGH at 80+ evidence quality, MEDIUM at 62–79.9 and LOW below 62. The production
coverage filter remains 40% because the measured distribution has natural source-specific bands;
the number itself was not raised arbitrarily. LOW-confidence rows are excluded from the primary
list by default and can be restored with **Include LOW-confidence discoveries**.

## Final quality audit

The pre-change top-25 decomposition showed that Messi's provider label `Center Forward` created
near-max broad compatibility with Undav and Guirassy despite Messi's elite creation, involvement
and progression. Salah's generic `Forward` label similarly allowed Kane and Boniface to benefit
from matching goal and shooting output without enough penalty for central occupation.

The final method uses behaviour-led attacking subroles and makes role compatibility an explicit
recommendation factor. In the default 900-minute recent-window searches, Messi now begins with
Florian Wirtz and Jamal Musiala; Salah promotes wide/inside-forward profiles and no longer has
Kane or Boniface in the leading group. LOW-confidence discovery rows remain available only via
the explicit toggle.

## Explanations

Every result returns its three highest calculated category similarities and its two lowest.
Only available categories are included. Tier C results never receive or display a spatial score
when no legitimate spatial profile exists.

## Identity safeguards

The API uses reconciled canonical-person IDs for reference search, self-exclusion and result
collapse. Conservative cross-provider alias reconciliation requires either matching DOB plus
compatible names, or compatible first/surname evidence plus an overlapping normalized
team-season. Discovery never excludes or merges players using a query-time name-string match.
