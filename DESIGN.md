# Scoring design: strict F1 in evaluator 0.3.0

Status: implemented locally. This document explains the scoring behavior before
0.3.0, the changes introduced in 0.3.0, and the reasons for those changes.

## Goal

The headline score should reward correctly describing visual differences and
penalize missed differences, incorrect details, and extra predictions. A reader
should be able to interpret a high score as strong performance on complete
structured answers.

The evaluator operates on prediction JSON and gold annotations. Its judgments
depend on deterministic text matching; it does not inspect image pixels.

## Before: partial detection dominated the score

The previous headline score was a weighted sum:

```text
overall_score = 0.60 * recall
              + 0.25 * precision
              + 0.15 * attribute_accuracy
```

Recall and precision counted eligible subject/type matches even when the
predicted attribute, before/after values, or count was wrong. Attribute accuracy
averaged the correctness of those details over matched predictions. Fully
correct coverage was reported separately.

This allowed a prediction to earn most of its credit by naming the right
subject and change type. For example:

```text
Gold:       shirt, color, red -> blue
Prediction: shirt, color, green -> yellow
```

On a single-difference item, the old scorer gave this prediction 100% recall,
100% precision, and one-third attribute accuracy because the property `color`
was correct. Its overall score was 90%, despite both color values being wrong.

The formula also gave surprisingly high scores to sparse answers and duplicate
predictions. Precision and attribute accuracy could each remain high when only
a small fraction of the gold differences was found. With complete recall and
attribute accuracy, a prediction set could retain 75% of the available score
even as its precision approached zero.

## What changed and why

| Area | Before | In 0.3.0 | Reason |
| --- | --- | --- | --- |
| Headline metric | Weighted recall, precision, and attribute accuracy | Strict F1 over complete structured matches | Wrong details should reduce the main score directly. |
| Correctness counts | A partial detection counted as correct | Only a complete match counts as correct | Counts and headline metrics should describe the same outcome. |
| Partial credit | Contributed to the headline score | Reported as diagnostic metrics | Preserve useful error analysis without inflating the main score. |
| Required text details | Fuzzy token overlap at a threshold of 0.80 | Ordered normalized token equality | Overlapping words can hide wrong numbers, negation, or reversed relations. |
| Subject location | `left` and `right` were discarded during normalization | Retain location words and reject explicit opposite locations | Changes to different objects must remain distinguishable. |
| One-to-one assignment | Greedy selection by candidate score | Maximum-cardinality assignment using augmenting paths | One locally preferred pair should not block two eligible matches. |
| No-difference images | Correct abstention scored 85%; a hallucination scored 60% | Correct abstention scores 100%; a hallucination scores 0% | The result should reflect whether the model correctly reported no change. |
| Version reporting | Package and report versions disagreed | Package and report identify evaluator 0.3.0 | Results need an unambiguous evaluator identity. |

## Complete structured matches

Candidate generation still requires the same change kind and sufficient
subject/description similarity under the deterministic matcher. Explicit
opposite subject locations, such as `left` versus `right`, reject a candidate.

For a candidate to contribute to strict F1:

- An `attribute_change` or `count_change` must agree with every supplied gold
  `attribute`, `from`, and `to` field, plus the gold `count` when present.
- An `object_added` or `object_removed` must have the correct gold `count` when
  one is supplied. Otherwise its eligible subject/type match is sufficient.
- Each gold difference and each prediction can participate in at most one
  match.

Missing required details fail the complete-match check. A failed prediction
remains an extra prediction, and a gold difference without another complete
match remains missed. Fields absent from the gold annotation do not introduce
additional requirements.

Required text fields are normalized for case, punctuation, articles,
conjunctions, and simple plurals. Their token order must then agree. Numbers,
negation, and spatial relations remain significant. This preserves basic
formatting flexibility while preventing partial word overlap from certifying
incorrect details.

Complete matches are assigned independently from diagnostic detections.
Incomplete candidates are filtered out before strict assignment, so a partial
prediction cannot consume the gold difference needed by a complete prediction.
The assignment maximizes eligible match count, which is the objective used by
F1; it does not maximize total lexical similarity.

## New metric definitions

Let `TP` be complete one-to-one matches, `P` all predictions, and `G` all gold
differences:

```text
FP = P - TP
FN = G - TP

precision = TP / P
recall = TP / G
overall_score = f1 = 2 * TP / (G + P)
```

Dataset metrics pool counts across images before computing ratios. This is
micro-averaging; the headline score is not the average of per-image F1 scores.
Duplicate predictions and predictions for unknown item IDs remain in `P` and
therefore reduce precision and F1.

When both gold and predictions are empty, F1 is defined as 1. When only one is
empty, F1 is 0. Recall is defined as 1 for empty gold. Precision is 1 when both
sets are empty and 0 when predictions are empty but gold is not. Correct empty
images add no true positives to the dataset totals.

`difference_coverage` is now an alias of strict recall. Partial matches remain
available through `detection_recall`, `detection_precision`, and
`attribute_accuracy`, which do not contribute to strict F1.

## Before-and-after examples

These examples exercise the scorer using fixtures or synthetic predictions;
they do not require new model generations. Percentages are rounded to one
decimal place.

| Case | Previous weighted score | Strict F1 |
| --- | ---: | ---: |
| Correct shirt and color property, both color values wrong | 90.0% | 0.0% |
| Two correct predictions out of 61 gold differences | 42.0% | 6.3% |
| Every perfect answer repeated 100 times: 1% precision | 75.3% | 2.0% |
| Perfect annotation fixture | 100.0% | 100.0% |
| No gold differences, empty prediction | 85.0% | 100.0% |
| No gold differences, one invented change | 60.0% | 0.0% |

The duplicate example has `TP = 61`, `G = 61`, and `P = 6100`, producing
`2 * 61 / (61 + 6100)`, or approximately 1.98% F1.

## Report and leaderboard migration

Prediction files continue to use schema `1.0`. Evaluator 0.3.0 emits report
schema `2.0` with `scoring_method: "strict_f1"`.

- `overall_score` equals the new `f1` metric.
- `precision`, `recall`, `correct_differences`, and `exact_correct_differences`
  refer to complete matches.
- `matched`, `missed`, and `extra` describe the strict assignment.
- `detected_differences` and `detection_matched` describe the independent
  diagnostic assignment.
- The old headline `weights` object is removed.
- CLI output puts Overall score first and distinguishes the supporting details.

The [leaderboard](LEADERBOARD.md) includes strict results calculated from saved
predictions and preserves the previous weighted results in an archive. Scores
from the two approaches are not directly comparable. The model outputs used
for those comparisons are the same saved generations.

## Plain-language score labels

The final result is displayed first as **Overall score [F1]**. The leaderboard
emphasizes that column and its values. This makes the final result easy to find
while keeping the metric name available for technical readers.

| Previous display label | Current display label |
| --- | --- |
| Overall score (strict F1) / Strict F1 | **Overall score [F1]** |
| Strict recall | Differences found [Recall] |
| Strict precision | Correct answers [Precision] |
| Detection recall (diagnostic) | Changes noticed [Detection recall] |
| Detection precision (diagnostic) | Relevant answers [Detection precision] |
| Attribute accuracy (diagnostic) | Detail accuracy [Attribute accuracy] |

The CLI groups recall and precision under the score breakdown, with partial
matches in a separate additional-details section. Duplicate coverage output is
omitted because it repeats recall. The JSON report retains `difference_coverage`
and its existing metric keys. This presentation change uses the same scoring
formula, values, evaluator version, and report schema.

## Validation

The scorer and CLI changes are covered by the test suite:

```bash
python3 -m unittest discover -s tests -v
```

At implementation time, all 35 tests passed. Regression coverage includes wrong
values, reversed changes with high word overlap, missing details, incorrect
counts, duplicate spam, unknown items, opposite locations, negation, relation
order, correct abstention, and matching conflicts. The perfect fixture remains
at 100%.

Implementation: [scorer](spotdiff_eval/scorer.py),
[CLI](spotdiff_eval/cli.py), [scorer tests](tests/test_scorer.py), and
[CLI test](tests/test_cli.py).

## Remaining limitations

Strict F1 fixes how accepted matches affect the score. The quality of an
accepted match still depends on the text matcher and the gold annotation.
Subject identity remains based on lexical similarity, and required fields use
conservative normalized equality. Valid paraphrases such as `pattern` versus
`shirt_design` can still be rejected. Descriptions do not override missing or
incorrect required structured fields.

Reviewed aliases and equivalent descriptions, human validation of matching
decisions, and gold regions or masks are useful next steps. Dataset scale,
annotation ambiguity, prompt hints, and a hidden test split also need separate
work. A lower score after this migration reflects a changed evaluation rule;
it does not establish that the underlying model became worse.
