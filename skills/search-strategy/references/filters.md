# Search Filters Reference

Ready-to-use filter templates for PubMed, Embase, Cochrane, and Web of Science. Append these to the main search strategy to narrow results.

---

## Table of Contents

- [Study Design Filters](#study-design-filters)
- [Time Range Filters](#time-range-filters)
- [Species Filters](#species-filters)
- [Language Filters](#language-filters)
- [Age Group Filters](#age-group-filters)
- [Combined Filter Examples](#combined-filter-examples)

---

## Study Design Filters

### PubMed

| Study Design | Filter String |
|---|---|
| Randomized Controlled Trial | `AND (randomized controlled trial[pt] OR controlled clinical trial[pt] OR randomized[tiab] OR placebo[tiab] OR drug therapy[sh] OR randomly[tiab] OR trial[tiab] OR groups[tiab]) NOT (animals[mh] NOT humans[mh])` |
| Cohort Study | `AND (cohort[tiab] OR cohorts[tiab] OR cohort studies[mh] OR follow-up[tiab] OR longitudinal[tiab] OR prospective[tiab])` |
| Case-Control Study | `AND (case-control[tiab] OR case control[tiab] OR retrospective[tiab])` |
| Systematic Review | `AND (systematic review[pt] OR meta-analysis[pt])` |
| Meta-Analysis | `AND meta-analysis[pt]` |
| Clinical Trial | `AND clinical trial[pt]` |
| Observational Study | `AND (observational[tiab] OR cohort[tiab] OR cross-sectional[tiab] OR case-control[tiab] OR longitudinal[tiab])` |
| Practice Guideline | `AND practice guideline[pt]` |

### Embase

| Study Design | Filter String |
|---|---|
| Randomized Controlled Trial | `AND (random*:ti,ab OR rct:ti,ab OR placebo:ti,ab OR trial*:ti,ab) AND (human:de AND NOT (animal:de AND NOT human:de))` |
| Cohort Study | `AND (cohort*:ti,ab OR follow-up:ti,ab OR longitudinal:ti,ab OR prospective:ti,ab)` |
| Case-Control Study | `AND (case-control:ti,ab OR retrospective:ti,ab)` |
| Systematic Review | `AND (systematic review:ti,ab OR meta-analysis:ti,ab)` |

### Cochrane

| Study Design | Filter String |
|---|---|
| RCT (Cochrane standard) | `#MeSH descriptor: [Randomized Controlled Trial as Topic] explode all trees`<br>`OR (#1 "randomized":ti,ab,kw OR #1 "randomised":ti,ab,kw OR #1 "placebo":ti,ab,kw OR #1 "trial":ti,ab,kw)` |

### Web of Science

| Study Design | Filter String |
|---|---|
| Clinical Trial | `AND DT=(Clinical Trial)` |
| Review | `AND DT=(Review)` |
| Meta-Analysis | `AND TS=(meta-analysis)` |

---

## Time Range Filters

### PubMed

| Range | Filter String |
|---|---|
| Last 5 years | `AND ("last 5 years"[dp])` |
| Last 10 years | `AND ("last 10 years"[dp])` |
| Custom range | `AND (2020/01/01:2025/12/31[dp])` |
| Specific year | `AND 2024[dp]` |

**Date field tags:**
- `[dp]` — Publication Date
- `[epdat]` — Electronic Publication Date
- `[edat]` — Entrez Date (added to PubMed)

### Embase

| Range | Filter String |
|---|---|
| Last 5 years | `AND (2019:2025:yr)` |
| Custom range | `AND (2020:2025:yr)` |

### Web of Science

| Range | Filter String |
|---|---|
| Last 5 years | `AND PY=(2021-2025)` |
| Custom range | `AND PY=(2020-2025)` |

---

## Species Filters

### PubMed

| Species | Filter String |
|---|---|
| Humans only | `AND "humans"[MeSH]` |
| Exclude animals | `NOT (animals[mh] NOT humans[mh])` |
| Animals only | `AND "animals"[MeSH] NOT humans[mh]` |

### Embase

| Species | Filter String |
|---|---|
| Humans only | `AND (human:de AND NOT (animal:de AND NOT human:de))` |
| Animals only | `AND (animal:de NOT human:de)` |

---

## Language Filters

### PubMed

| Language | Filter String |
|---|---|
| English only | `AND English[Language]` |
| Chinese | `AND Chinese[Language]` |
| Exclude non-English | `NOT (non-english[Language])` |

### Embase

| Language | Filter String |
|---|---|
| English only | `AND (english:la)` |

### Web of Science

| Language | Filter String |
|---|---|
| English only | `AND LA=(English)` |

---

## Age Group Filters

### PubMed

| Age Group | Filter String |
|---|---|
| Infants (0-23 months) | `AND ("infant"[MeSH] OR "infant, newborn"[MeSH])` |
| Children (0-18) | `AND "child"[MeSH]` |
| Adults (19+) | `AND "adult"[MeSH]` |
| Middle Aged + Aged (45+) | `AND ("middle aged"[MeSH] OR "aged"[MeSH])` |
| Elderly (65+) | `AND "aged"[MeSH] AND "aged, 80 and over"[MeSH]` |

---

## Combined Filter Examples

### Example 1: RCTs in humans, English, last 10 years (PubMed)

```pubmed
AND (randomized controlled trial[pt] OR randomized[tiab] OR placebo[tiab])
AND "humans"[MeSH]
AND English[Language]
AND ("last 10 years"[dp])
```

### Example 2: Observational studies, adults only (PubMed)

```pubmed
AND (cohort[tiab] OR case-control[tiab] OR cross-sectional[tiab] OR longitudinal[tiab])
AND "adult"[MeSH]
AND "humans"[MeSH]
```

### Example 3: Systematic reviews, last 5 years (Embase)

```embase
AND (systematic review:ti,ab OR meta-analysis:ti,ab)
AND (2019:2025:yr)
AND (english:la)
```

### Example 4: Clinical trials, 2020-2025 (Web of Science)

```wos
AND DT=(Clinical Trial)
AND PY=(2020-2025)
AND LA=(English)
```

---

## Notes

- **Filter order matters**: Apply study design filters first, then scope filters (time, language, species)
- **Cochrane Handbook** recommends using validated methodological filters (e.g., Cochrane RCT filter, SIGN filters) for systematic reviews
- **Over-filtering risk**: Each additional filter reduces result count. Monitor for over-narrowing
- **Document all filters** in the final search strategy report for reproducibility
