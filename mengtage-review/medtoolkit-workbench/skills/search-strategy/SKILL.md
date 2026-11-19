---
name: medical-search-strategy-builder
description: >
  Build structured medical literature search strategies from natural language research questions
  using PICO/PEO frameworks with progressive clarification dialogue. Supports funnel-style questioning
  to transform vague user queries into precise research objectives before generating search strategies.
  Supports PubMed, Embase, Cochrane Library, Web of Science, and arXiv.
  Use when: the user asks to construct search strings, build search strategies for systematic reviews,
  convert research questions to database queries, mentions PICO/PEO, or needs PubMed/Embase/Cochrane
  search syntax. Handles vague, incomplete, or ambiguous queries through structured clarification.
  NOT for: performing actual database searches, downloading papers, or full systematic review execution.
metadata:
  openclaw:
    emoji: "🔍"
    version: "3.0.0"
    author: Mengtage
    license: "MIT"
    tags:
      - medical
      - systematic-review
      - search-strategy
      - pico
      - pubmed
      - evidence-based-medicine
      - clarification-dialogue
---

# Medical Search Strategy Builder

Build structured medical literature search strategies from natural language research questions using PICO/PEO frameworks with **progressive clarification dialogue**.

## Core Design: Funnel-Style Clarification

The skill operates in **three layers** to transform vague user input into precise research objectives:

```
┌─────────────────────────────────────────────────────────────┐
│  L1: Intent Recognition                                     │
│  → Assess query fuzziness, decide clarification depth       │
├─────────────────────────────────────────────────────────────┤
│  L2: Element Completion                                     │
│  → Dialogue to fill missing PICO/PEO components             │
├─────────────────────────────────────────────────────────────┤
│  L3: Terminology Alignment                                  │
│  → Map natural language to MeSH professional terms          │
├─────────────────────────────────────────────────────────────┤
│  Output: Professional search strategy                       │
└─────────────────────────────────────────────────────────────┘
```

---

## Stage 1: Intent Recognition & Fuzziness Assessment

**First, classify the user's input into one of three clarity levels:**

### Level 1: Vague Topic (High Fuzziness)

**Signals:**
- Single disease/condition without context: "糖尿病", "cancer"
- Broad topic areas: "心血管疾病研究", "mental health"
- No research question structure
- No identifiable PICO elements

**Action:** Initiate **Broad Clarification Dialogue**

> "您提到'糖尿病'，这是一个很广泛的研究领域。为了帮您构建精准的检索策略，我需要了解：
> 
> 1. **研究视角**：您关注的是糖尿病的哪个方面？
>    - 治疗/干预（如药物疗效）
>    - 病因/风险因素
>    - 并发症管理
>    - 预防策略
>    - 预后预测
>
> 2. **目标人群**：是否有特定的人群限制？
>    - 2型 vs 1型糖尿病
>    - 特定年龄段（儿童/老年人）
>    - 合并特定疾病的患者
>
> 请选择一个方向，或告诉我您的具体研究问题。"

### Level 2: Partial PICO (Medium Fuzziness)

**Signals:**
- Has Population + vague Intervention: "二甲双胍治疗糖尿病"
- Missing Comparison or Outcome
- Unclear study type (interventional vs observational)

**Action:** Initiate **Element Completion Dialogue**

> "我识别到您的研究问题涉及：
> - **人群(P)**：2型糖尿病患者
> - **干预(I)**：二甲双胍
>
> 为了构建完整的检索策略，还需要明确：
>
> 1. **对照(C)**：您希望与什么进行比较？
>    - 安慰剂/空白对照
>    - 其他降糖药（如磺脲类、DPP-4抑制剂）
>    - 生活方式干预
>    - 不同剂量的二甲双胍
>
> 2. **结局(O)**：您关注的治疗 outcomes 是什么？
>    - 血糖控制（HbA1c降低）
>    - 体重变化
>    - 心血管事件
>    - 不良反应/安全性
>    - 死亡率
>
> 3. **研究类型**：
>    - 随机对照试验（RCT）
>    - 队列研究
>    - 病例对照研究
>    - 不限定"

### Level 3: Structured Question (Low Fuzziness)

**Signals:**
- Clear PICO/PEO structure: "In adults with T2DM, does metformin vs sulfonylurea reduce cardiovascular mortality?"
- All elements identifiable
- Research type clear

**Action:** Proceed to **Terminology Alignment** (Stage 3)

---

## Stage 2: Progressive Element Completion

**For Level 2 inputs, use structured slot-filling dialogue:**

### Dialogue Pattern: Guided Slot Filling

**Principles:**
1. **One question at a time** — Don't overwhelm with multiple questions
2. **Provide options** — Make it easy for users to choose
3. **Accept partial answers** — Don't block on missing information
4. **Confirm understanding** — Restate what you've understood

### Example Dialogue Flow

**User:** "我想查二甲双胍治疗糖尿病的效果"

**AI:** 
> "收到。我理解您想研究**二甲双胍治疗2型糖尿病的效果**。
>
> 为了生成精准的检索式，我需要确认几个细节：
>
> **问题1/3：对照组是什么？**
> - A. 安慰剂/空白对照
> - B. 其他口服降糖药
> - C. 胰岛素
> - D. 生活方式干预
> - E. 不限制对照类型
> - F. 其他（请描述）"

**User:** "B"

**AI:**
> "好的，对照组为**其他口服降糖药**。
>
> **问题2/3：关注的结局指标？**（可多选）
> - A. 血糖控制（HbA1c、空腹血糖）
> - B. 体重变化
> - C. 心血管事件（心梗、卒中、死亡）
> - D. 不良反应/安全性
> - E. 长期并发症
> - F. 其他（请描述）"

**User:** "A 和 C"

**AI:**
> "明白，关注**血糖控制**和**心血管事件**。
>
> **问题3/3：研究设计偏好？**
> - A. 仅随机对照试验（RCT）- 证据等级最高
> - B. 包括观察性研究（队列、病例对照）
> - C. 不限定，所有研究类型
>
> 请回复选项字母。"

**User:** "A"

**AI:**
> "完美！我已收集到完整的研究框架：
>
> | 维度 | 内容 |
> |------|------|
> | P (人群) | 2型糖尿病患者 |
> | I (干预) | 二甲双胍 |
> | C (对照) | 其他口服降糖药 |
> | O (结局) | 血糖控制 + 心血管事件 |
> | 研究类型 | RCT |
>
> 现在进入术语标准化阶段..."

---

## Stage 3: Terminology Alignment (MeSH Mapping)

**Map user's natural language to professional MeSH terms through real-time lookup:**

### Terminology Clarification Dialogue

**When user term is ambiguous or non-standard:**

> "您使用的术语'**血糖高**'，在医学文献中有多个专业对应：
>
> | 您的表述 | 可能的MeSH术语 | 适用场景 |
> |----------|----------------|----------|
> | 血糖高 | Hyperglycemia | 高血糖状态 |
> | | Diabetes Mellitus | 糖尿病（确诊疾病）|
> | | Blood Glucose | 血糖（实验室指标）|
> | | Prediabetic State | 糖尿病前期 |
>
> 请确认您想检索的是：
> - **A.** 已确诊的糖尿病患者（Diabetes Mellitus）
> - **B.** 高血糖状态/事件（Hyperglycemia）
> - **C.** 血糖指标本身（Blood Glucose）
> - **D.** 糖尿病前期（Prediabetic State）"

### Real-Time MeSH Lookup Guidance

**When term not in local reference:**

> "术语'**SGLT2抑制剂**'不在我的本地词库中。建议：
>
> 1. **快速确认**：您是否指以下药物类别？
>    - Sodium-Glucose Transporter 2 Inhibitors [MeSH]
>    - 包含：达格列净、恩格列净、卡格列净等
>
> 2. **自助查询**：访问 [NCBI MeSH Database](https://meshb.nlm.nih.gov/) 输入'SGLT2'获取官方术语
>
> 3. **继续构建**：我将使用您提供的术语，但建议在PubMed中验证是否映射正确"

---

## Stage 4: Search Strategy Generation

**Once all elements are clarified, generate database-specific strategies:**

### Multi-Database Syntax Generation

See [references/database-syntax.md](references/database-syntax.md) for detailed syntax guides.

### Filter Application

See [references/filters.md](references/filters.md) for study design and scope filters.

---

## Output Format

```markdown
## 输入质量评估
**澄清轮次**: 3轮对话
**初始模糊度**: 中（缺少对照组和结局指标）
**最终清晰度**: 高 ✅

## 研究问题分析
**原始问题**: 我想查二甲双胍治疗糖尿病的效果
**澄清后问题**: 在2型糖尿病患者中，二甲双胍与其他口服降糖药相比，对血糖控制和心血管事件的影响（RCT）
**研究类型**: 干预性研究
**框架**: PICO

## PICO 拆解
| 维度 | 自然语言 | MeSH术语 | 同义词/自由词 |
|------|----------|----------|---------------|
| P | 2型糖尿病 | Diabetes Mellitus, Type 2 | T2DM, type 2 diabetes |
| I | 二甲双胍 | Metformin | Glucophage |
| C | 其他口服降糖药 | Hypoglycemic Agents | sulfonylureas, DPP-4 inhibitors |
| O | 血糖控制 | Blood Glucose | HbA1c, glycemic control |
| O | 心血管事件 | Cardiovascular Diseases | MI, stroke, CV death |

## 检索策略

### PubMed
```pubmed
("Diabetes Mellitus, Type 2"[MeSH] OR "type 2 diabetes"[Title/Abstract] OR "T2DM"[Title/Abstract])
AND
("Metformin"[MeSH] OR "metformin"[Title/Abstract])
AND
("Hypoglycemic Agents"[MeSH] OR "sulfonylurea*"[Title/Abstract] OR "DPP-4 inhibitor*"[Title/Abstract] OR "glipizide"[Title/Abstract] OR "glibenclamide"[Title/Abstract])
AND
("Blood Glucose"[MeSH] OR "HbA1c"[Title/Abstract] OR "glycemic control"[Title/Abstract] OR "Cardiovascular Diseases"[MeSH] OR "myocardial infarction"[Title/Abstract] OR "stroke"[Title/Abstract])
AND
(randomized controlled trial[pt] OR randomized[Title/Abstract])
```

[Embase, Cochrane, WoS strategies follow...]
```

---

## Important Notes

- **Always clarify first** — Never generate strategy from vague input without clarification
- **Document the clarification process** — Show users how their vague input was refined
- **MeSH terms improve precision**; free-text terms improve recall. Always use both.
- **Phrase searching**: Multi-word terms should be quoted (e.g., `"type 2 diabetes"`)
- **This skill is a starting point** — For professional systematic reviews, supplement with database-specific tools and librarian consultation

---

## Reference Files

- [references/clarification-patterns.md](references/clarification-patterns.md) — Dialogue templates for common clarification scenarios
- [references/common-mesh-terms.md](references/common-mesh-terms.md) — Categorized MeSH lookup table
- [references/database-syntax.md](references/database-syntax.md) — Database-specific syntax guides
- [references/filters.md](references/filters.md) — Study design and scope filters
- [references/validation-checklist.md](references/validation-checklist.md) — Strategy validation checklist
