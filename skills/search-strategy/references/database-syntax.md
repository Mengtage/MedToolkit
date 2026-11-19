# Database-Specific Search Syntax Guide

Detailed syntax rules and examples for each supported database.

---

## PubMed

### Syntax Rules

| Element | Syntax | Example |
|---|---|---|
| MeSH term | `"term"[MeSH]` | `"Diabetes Mellitus, Type 2"[MeSH]` |
| MeSH with subheading | `"term/subheading"[MeSH]` | `"Spine/surgery"[MeSH]` |
| Free-text (single word) | `term[Title/Abstract]` | `metformin[Title/Abstract]` |
| Free-text (phrase) | `"phrase"[Title/Abstract]` | `"type 2 diabetes"[Title/Abstract]` |
| Truncation | `term*[Title/Abstract]` | `diabet*[Title/Abstract]` |
| Boolean AND | `expr1 AND expr2` | Concept groups combined |
| Boolean OR | `expr1 OR expr2` | Within a concept group |
| Boolean NOT | `expr1 NOT expr2` | Exclude terms |

### Structure

```
(Concept_P_terms) AND (Concept_I_terms) AND (Concept_C_terms) AND (Concept_O_terms)
```

### Example

```pubmed
("Diabetes Mellitus, Type 2"[MeSH] OR "type 2 diabetes"[Title/Abstract] OR "T2DM"[Title/Abstract])
AND
("Glucagon-Like Peptide-1"[MeSH] OR "GLP-1"[Title/Abstract] OR "liraglutide"[Title/Abstract] OR "semaglutide"[Title/Abstract])
AND
("Metformin"[MeSH] OR "metformin"[Title/Abstract])
AND
("Hemoglobin A1C"[MeSH] OR "HbA1c"[Title/Abstract] OR "glycemic control"[Title/Abstract])
```

### Tips

- MeSH terms with `/` (subheadings) should NOT be wrapped in quotes
- Use `[MeSH Terms]` or `[MeSH Subheading]` for exploded searches
- Add `AND "humans"[MeSH]` to exclude animal studies
- Add `AND (clinical trial[pt] OR randomized controlled trial[pt])` to filter by study type

---

## Embase

### Syntax Rules

| Element | Syntax | Example |
|---|---|---|
| Emtree term (exploded) | `'term'/exp` | `'diabetes mellitus'/exp` |
| Emtree term (single) | `'term'` | `'metformin'` |
| Free-text title/abstract | `'term':ti,ab` | `'metformin':ti,ab` |
| Truncation | `term*:ti,ab` | `diabet*:ti,ab` |
| Boolean AND | `expr1 AND expr2` | Between concept groups |
| Boolean OR | `expr1 OR expr2` | Within a concept group |

### Structure

Embase uses line numbers for complex queries:

```
#1 P: ('term'/exp OR 'term':ti,ab)
#2 I: ('term'/exp OR 'term':ti,ab)
#Final: #1 AND #2
```

### Example

```embase
#1 P: ('diabetes mellitus, type 2'/exp OR 'type 2 diabetes':ti,ab OR 't2dm':ti,ab)
#2 I: ('glp-1 receptor agonist'/exp OR 'glp-1':ti,ab OR 'liraglutide':ti,ab OR 'semaglutide':ti,ab)
#3 C: ('metformin'/exp OR 'metformin':ti,ab)
#4 O: ('hba1c':ti,ab OR 'glycemic control':ti,ab OR 'glycosylated hemoglobin':ti,ab)
#Final: #1 AND #2 AND #3 AND #4
```

### Tips

- Embase uses **Emtree** (not MeSH) — some terms differ from PubMed
- Embase covers more international journals and drug literature than PubMed
- Use `:ti,ab` to restrict to title and abstract fields
- Use `/exp` to include all narrower Emtree terms (explosion)

---

## Cochrane Library

### Syntax Rules

| Element | Syntax | Example |
|---|---|---|
| MeSH descriptor | `MeSH descriptor: [term] explode all trees` | `MeSH descriptor: [Diabetes Mellitus, Type 2] explode all trees` |
| Free-text | `"term":ti,ab,kw` | `"metformin":ti,ab,kw` |
| Truncation | `term*:ti,ab,kw` | `diabet*:ti,ab,kw` |
| Keyword | `"term":kw` | Searches controlled vocabulary keywords |

### Structure

Cochrane uses numbered lines (Search Manager format):

```
#1 MeSH descriptor: [term] explode all trees
#2 ("free text"):ti,ab,kw
#3 #1 OR #2
#4 MeSH descriptor: [term2] explode all trees
#5 #3 AND #4
```

### Example

```cochrane
#1 MeSH descriptor: [Diabetes Mellitus, Type 2] explode all trees
#2 ("type 2 diabetes" OR "T2DM"):ti,ab,kw
#3 #1 OR #2
#4 MeSH descriptor: [Metformin] explode all trees
#5 ("metformin"):ti,ab,kw
#6 #4 OR #5
#7 MeSH descriptor: [Glucagon-Like Peptide-1] explode all trees
#8 ("GLP-1" OR "liraglutide" OR "semaglutide"):ti,ab,kw
#9 #7 OR #8
#10 #3 AND #6 AND #9
```

### Tips

- Cochrane uses MeSH terms (same as PubMed)
- The `kw` field searches Cochrane's controlled keywords
- `explode all trees` includes all narrower MeSH terms
- Use Search Manager for complex strategies; results can be exported

---

## Web of Science

### Syntax Rules

| Element | Syntax | Example |
|---|---|---|
| Topic search | `TS=("term")` | `TS=("diabetes")` |
| Phrase search | `TS=("multi-word term")` | `TS=("type 2 diabetes")` |
| Truncation | `TS=(term*)` | `TS=(diabet*)` |
| Title only | `TI=("term")` | `TI=("metformin")` |
| Author | `AU=("surname initial")` | `AU=("Smith J")` |

### Structure

```
TS=(Concept_P_terms) AND TS=(Concept_I_terms) AND TS=(Concept_C_terms) AND TS=(Concept_O_terms)
```

### Example

```wos
TS=("Diabetes Mellitus, Type 2" OR "type 2 diabetes" OR "T2DM")
AND
TS=("Glucagon-Like Peptide-1" OR "GLP-1" OR "liraglutide" OR "semaglutide")
AND
TS=("Metformin")
AND
TS=("HbA1c" OR "glycemic control" OR "glycosylated hemoglobin")
```

### Tips

- WoS does not use MeSH — all terms are searched as free-text in the Topic field
- `TS=` searches title, abstract, author keywords, and Keywords Plus
- Use `PY=` to filter by publication year (e.g., `PY=(2020-2025)`)
- Use `DT=` to filter by document type (e.g., `DT=(Article OR Review)`)

---

## arXiv

### Syntax Rules

| Element | Syntax | Example |
|---|---|---|
| Title search | `ti:"term"` | `ti:"deep learning"` |
| Abstract search | `abs:"term"` | `abs:"neural network"` |
| All fields | `all:"term"` | `all:"machine learning"` |
| Truncation | `all:term*` | `all:learn*` |
| Boolean AND | `expr1 AND expr2` | Combine concepts |
| Boolean OR | `expr1 OR expr2` | Within concept |
| Boolean ANDNOT | `expr1 ANDNOT expr2` | Exclude terms |

### Structure

```
(ti:"term1" OR abs:"term1") AND (ti:"term2" OR abs:"term2")
```

### Example

```arxiv
(ti:"diabetes" OR abs:"diabetes") AND (ti:"machine learning" OR abs:"machine learning" OR all:deep* AND all:learn*)
```

### Tips

- arXiv does **NOT** support MeSH — all terms are free-text
- Use `ti:` for precise title matches, `abs:` for abstract matches
- Use `all:` with truncation for broad searches
- arXiv is primarily for preprints — useful for emerging/interdisciplinary topics
- Use `cat:` to filter by subject category (e.g., `cat:cs.AI`)
