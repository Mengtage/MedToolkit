# Search Strategy Validation Checklist

Use this checklist to validate and optimize search strategies before finalizing them.

---

## Table of Contents

- [Input Quality Check](#input-quality-check)
- [Concept Validation](#concept-validation)
- [Syntax Validation](#syntax-validation)
- [Database-Specific Checks](#database-specific-checks)
- [Filter Validation](#filter-validation)
- [Recall vs. Precision Balance](#recall-vs-precision-balance)
- [Optimization Tips](#optimization-tips)

---

## Input Quality Check

- [ ] Research question is specific and answerable (not a vague topic)
- [ ] All PICO/PEO dimensions are identifiable (P, I, C/E, O)
- [ ] Each concept has a clear, descriptive name
- [ ] The research question has a defined outcome
- [ ] The question scope is appropriate (not too broad or too narrow)
- [ ] User has been informed of any input quality issues and suggestions provided

## Concept Validation

- [ ] Each PICO/PEO dimension has at least one concept defined
- [ ] Each concept has 3+ search terms (MeSH + free-text + truncated)
- [ ] MeSH terms are verified against the [NCBI MeSH Database](https://meshb.nlm.nih.gov/)
- [ ] Free-text terms cover common synonyms and abbreviations
- [ ] Truncated variants capture word stems (e.g., `diabet*` → diabetes, diabetic, diabetology)
- [ ] No duplicate terms within a concept
- [ ] Both MeSH and free-text terms are included (balance precision and recall)

## Syntax Validation

- [ ] Boolean operators (AND, OR, NOT) are UPPERCASE
- [ ] Phrase terms are properly quoted
- [ ] Field tags are correct for the target database
- [ ] Parentheses properly group terms within each concept
- [ ] No orphaned operators or unbalanced parentheses
- [ ] Truncation symbols (`*`) are placed correctly

## Database-Specific Checks

### PubMed
- [ ] MeSH terms use `[MeSH]` field tag
- [ ] MeSH terms with subheadings use correct format (`term/subheading`)
- [ ] Free-text terms use `[Title/Abstract]` field tag
- [ ] Consider adding species filter: `AND "humans"[MeSH]`
- [ ] Consider adding language filter: `AND English[Language]`

### Embase
- [ ] Emtree terms use `/exp` for explosion
- [ ] Free-text terms use `:ti,ab` field restriction
- [ ] Verify Emtree terms differ from MeSH where applicable

### Cochrane
- [ ] MeSH descriptors use `explode all trees`
- [ ] Free-text includes `:kw` (keyword) field
- [ ] Line numbers are sequential and correctly referenced

### Web of Science
- [ ] All terms use `TS=` topic search field
- [ ] Consider adding year filter: `PY=(2020-2025)`
- [ ] Consider adding document type: `DT=(Article OR Review)`

### arXiv
- [ ] No MeSH terms used (arXiv doesn't support them)
- [ ] Terms searched in both `ti:` and `abs:` fields
- [ ] Consider category filter: `cat:cs.AI` (if applicable)

## Filter Validation

- [ ] Study design filter is appropriate for the review type
- [ ] Time range filter is documented with specific dates
- [ ] Language filter is justified (not excluding relevant non-English studies without reason)
- [ ] Species filter is applied correctly
- [ ] Age group filter matches the target population
- [ ] Filters are applied AFTER the main concept search (not mixed in)
- [ ] Total filter combination does not over-narrow results (< 50 results may indicate over-filtering)

## Recall vs. Precision Balance

| Check | High Recall | High Precision |
|---|---|---|
| MeSH explosion | ✅ Use `/exp` | ❌ Use single term |
| Free-text synonyms | ✅ Include many | ❌ Use few, specific |
| Truncation | ✅ Broad (`*`) | ❌ Specific terms only |
| Field restriction | ❌ Search all fields | ✅ Restrict to title/abstract |
| Language filter | ❌ No filter | ✅ English only |
| Study type filter | ❌ No filter | ✅ RCT/Review only |

## Optimization Tips

1. **Start broad, then narrow**: Run a broad search first, check result counts, then add filters
2. **Check result relevance**: Scan the first 20-50 results for relevance
3. **Iterate**: Refine terms based on what you find (and don't find)
4. **Document changes**: Keep track of each iteration for reporting (PRISMA flow diagram)
5. **Peer review**: Have a librarian or colleague review the strategy
6. **Report**: Document the final strategy, date searched, database version, and all filters applied
7. **Cross-database**: Translate the strategy to all relevant databases for comprehensive coverage
8. **Verify with known studies**: Test the strategy against 3-5 known relevant articles to ensure they are retrieved
