# Clarification Dialogue Patterns

Ready-to-use dialogue templates for common clarification scenarios in medical search strategy building.

---

## Table of Contents

- [Pattern 1: Vague Disease Topic](#pattern-1-vague-disease-topic)
- [Pattern 2: Partial PICO Missing C/O](#pattern-2-partial-pico-missing-co)
- [Pattern 3: Ambiguous Terminology](#pattern-3-ambiguous-terminology)
- [Pattern 4: Multiple Research Questions](#pattern-4-multiple-research-questions)
- [Pattern 5: Unclear Study Type](#pattern-5-unclear-study-type)
- [Pattern 6: Outcome Specification](#pattern-6-outcome-specification)
- [Pattern 7: Population Refinement](#pattern-7-population-refinement)
- [Pattern 8: Intervention Details](#pattern-8-intervention-details)

---

## Pattern 1: Vague Disease Topic

**Trigger:** User provides only a disease name without research context

**Examples:**
- "糖尿病"
- "我想了解阿尔茨海默病"
- "cancer research"

**Dialogue Template:**

```
您提到'[DISEASE]'，这是一个很广泛的研究领域。为了帮您构建精准的检索策略，
我需要先了解您的研究视角：

**您关注的是哪个方面？**

🔬 **病因与风险因素**（观察性研究）
   - 疾病发生的原因
   - 危险因素识别
   - 预防策略

💊 **治疗与干预**（干预性研究）
   - 药物疗效比较
   - 手术vs保守治疗
   - 新型疗法

📊 **诊断与筛查**
   - 诊断准确性
   - 筛查工具评估
   - 生物标志物

🏥 **预后与并发症**
   - 疾病进展预测
   - 并发症管理
   - 生存分析

💰 **卫生经济学**
   - 成本效益分析
   - 医疗资源利用

请回复数字（1-5），或直接用一句话描述您的研究问题。
```

**Follow-up if user selects treatment:**

```
好的，您关注的是[DISEASE]的治疗/干预。

**目标人群是否有特定限制？**

- A. 不限定，所有[DISEASE]患者
- B. 特定亚型（如：2型糖尿病 vs 1型）
- C. 特定年龄段（儿童/成人/老年人）
- D. 合并特定疾病的患者
- E. 特定严重程度/分期

请回复字母，或描述您的人群特征。
```

---

## Pattern 2: Partial PICO Missing C/O

**Trigger:** User has P + I but missing Comparison and/or Outcome

**Examples:**
- "二甲双胍治疗糖尿病"
- "阿司匹林预防心血管事件"

**Dialogue Template:**

```
我识别到您的研究问题涉及：

✓ **人群(P)**：[POPULATION]
✓ **干预(I)**：[INTERVENTION]

为了构建完整的检索策略，还需要明确以下要素：

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**1. 对照组(C)是什么？**（单选）

A. 安慰剂/空白对照
B. 标准治疗/常规护理
C. 其他活性药物（请说明）
D. 不同剂量的同一种药物
E. 不限制对照类型

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**2. 关注的结局(O)是什么？**（可多选）

疗效指标：
□ 主要临床终点（如：死亡率、心梗发生率）
□ 替代指标（如：血压、血糖、血脂）
□ 症状改善
□ 生活质量

安全性指标：
□ 不良反应发生率
□ 严重不良事件
□ 停药率

其他：
□ 经济学指标（成本、QALY）
□ 依从性

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**3. 研究设计偏好？**（单选）

A. 仅随机对照试验（RCT）- 证据等级最高 ⭐推荐
B. 包括观察性研究（队列、病例对照）
C. 不限定，所有研究类型

请按顺序回复，例如："B, 疗效指标A, A"
```

---

## Pattern 3: Ambiguous Terminology

**Trigger:** User uses colloquial or ambiguous terms that map to multiple MeSH concepts

**Examples:**
- "血糖高" → Hyperglycemia? Diabetes? Prediabetic?
- "心脏病" → Heart Disease? Cardiovascular Diseases? Coronary Disease?
- "降压药" → Antihypertensive Agents? Specific drug classes?

**Dialogue Template:**

```
您使用的术语'[USER_TERM]'在医学文献中有多个专业对应。

为了精准检索，请确认您想表达的是：

┌────────────────────────────────────────────────────────┐
│ 选项A: [MeSH_TERM_1]                                    │
│ 定义: [SCOPE_NOTE_1]                                    │
│ 适用场景: [WHEN_TO_USE_1]                               │
├────────────────────────────────────────────────────────┤
│ 选项B: [MeSH_TERM_2]                                    │
│ 定义: [SCOPE_NOTE_2]                                    │
│ 适用场景: [WHEN_TO_USE_2]                               │
├────────────────────────────────────────────────────────┤
│ 选项C: [MeSH_TERM_3]                                    │
│ 定义: [SCOPE_NOTE_3]                                    │
│ 适用场景: [WHEN_TO_USE_3]                               │
└────────────────────────────────────────────────────────┘

💡 **建议**：
- 如果您研究的是[SCENARIO_1]，选择A
- 如果您研究的是[SCENARIO_2]，选择B
- 如果您研究的是[SCENARIO_3]，选择C

请回复 A/B/C，或进一步描述您的具体含义。
```

**Example for "血糖高":**

```
您使用的术语'血糖高'在医学文献中有多个专业对应：

┌────────────────────────────────────────────────────────┐
│ 选项A: Hyperglycemia（高血糖症）                         │
│ 定义: 血糖水平高于正常范围的病理状态                      │
│ 适用场景: 急性高血糖事件、血糖波动研究                    │
├────────────────────────────────────────────────────────┤
│ 选项B: Diabetes Mellitus（糖尿病）                       │
│ 定义: 以慢性高血糖为特征的代谢性疾病                      │
│ 适用场景: 确诊糖尿病的患者群体                            │
├────────────────────────────────────────────────────────┤
│ 选项C: Prediabetic State（糖尿病前期）                   │
│ 定义: 血糖高于正常但未达糖尿病诊断标准的状态              │
│ 适用场景: 糖尿病预防、风险人群筛查                        │
├────────────────────────────────────────────────────────┤
│ 选项D: Blood Glucose（血糖）                             │
│ 定义: 血液中的葡萄糖，作为实验室指标                      │
│ 适用场景: 血糖监测技术、检测方法研究                      │
└────────────────────────────────────────────────────────┘

💡 **建议**：
- 如果您研究的是已确诊的糖尿病患者，选择B
- 如果您研究的是血糖控制/监测技术，选择D
- 如果您研究的是糖尿病前期干预，选择C

请回复 A/B/C/D。
```

---

## Pattern 4: Multiple Research Questions

**Trigger:** User's query contains multiple distinct research questions

**Examples:**
- "我想了解糖尿病的病因、治疗和预后"
- "比较几种降压药的效果和安全性"

**Dialogue Template:**

```
我注意到您的需求包含**多个研究问题**：

1. [RESEARCH_QUESTION_1]
2. [RESEARCH_QUESTION_2]
3. [RESEARCH_QUESTION_3]

⚠️ **建议：拆分为独立检索**

系统评价标准要求每个检索策略针对**单一明确的研究问题**。
混合多个问题会导致：
- 检索式过于复杂
- 结果难以解释
- 文献筛选困难

**推荐方案：**

方案A：分步检索
   → 先完成问题1的检索
   → 再分别完成问题2、3

方案B：聚焦最优先的问题
   → 您当前最急需回答的是哪个问题？

方案C：提高抽象层级
   → 如果三个问题都关注[COMMON_THEME]，
   → 可以构建一个更宽泛的检索，然后在筛选阶段细分

请回复 A/B/C，或告诉我您的优先级排序。
```

---

## Pattern 5: Unclear Study Type

**Trigger:** Cannot determine if research is interventional or observational

**Examples:**
- "吸烟和肺癌的关系"
- "运动对抑郁症的影响"

**Dialogue Template:**

```
我需要确认您的**研究类型**，这将决定使用PICO还是PEO框架：

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔬 **干预性研究 (PICO框架)**
   
   适用场景：
   - 比较治疗效果（药物A vs 药物B）
   - 评估干预措施（手术 vs 保守治疗）
   - 随机对照试验(RCT)
   
   关键词：治疗、疗效、干预、随机、对照

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 **观察性研究 (PEO框架)**
   
   适用场景：
   - 风险因素研究（吸烟→肺癌）
   - 预后因素分析
   - 疾病自然史
   - 队列研究、病例对照研究
   
   关键词：风险、关联、预后、发病率、危险因素

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

根据您的描述"[USER_QUERY]"，我初步判断这是：

- **A.** 干预性研究 → 使用 PICO 框架
- **B.** 观察性研究 → 使用 PEO 框架
- **C.** 我不确定，请帮我判断

请回复 A/B/C。
```

---

## Pattern 6: Outcome Specification

**Trigger:** User says "effect" or "outcome" without specificity

**Examples:**
- "药物的效果"
- "治疗结果"

**Dialogue Template:**

```
您提到关注'效果/结局'，我需要了解**具体指标**以确保检索全面。

不同研究关注不同的结局层次：

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**临床硬终点**（最高证据等级）
☐ 全因死亡率
☐ 疾病特异性死亡率
☐ 主要心血管事件（MACE）
☐ 卒中/心梗发生率

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**替代指标**（常用于短期研究）
☐ 实验室指标（血糖、血脂、肝肾功能）
☐ 影像学指标（肿瘤大小、斑块体积）
☐ 生理指标（血压、心率、体重）

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**患者报告结局**（PROs）
☐ 生活质量量表（SF-36, EQ-5D）
☐ 症状评分
☐ 功能状态
☐ 患者满意度

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**安全性结局**
☐ 不良反应发生率
☐ 严重不良事件（SAE）
☐ 停药/退出率
☐ 实验室异常

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**请选择您关注的主要结局**（最多选3个）：

例如："主要结局1, 替代指标A, 安全性A"

如果您不确定，告诉我您的研究目的是什么，我来推荐合适的结局指标。
```

---

## Pattern 7: Population Refinement

**Trigger:** Population is too broad or has undefined subgroups

**Examples:**
- "高血压患者"（所有高血压？特定分级？）
- "老年人"（多大算老年？）

**Dialogue Template:**

```
您定义的人群是'[POPULATION]'，为了精准检索，建议进一步限定：

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**疾病特征**（如适用）

疾病分期/严重程度：
☐ 不限定
☐ 早期/轻度
☐ 中期/中度
☐ 晚期/重度
☐ 特定分期：[请描述]

合并症要求：
☐ 不限定
☐ 无合并症（单纯疾病）
☐ 合并特定疾病：[请描述]
☐ 多重合并症

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**人口学特征**

年龄范围：
☐ 不限定
☐ 儿童（0-18岁）
☐ 成人（18-65岁）
☐ 老年人（≥65岁）
☐ 特定范围：[ ]-[ ]岁

性别：
☐ 不限定
☐ 仅男性
☐ 仅女性

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**治疗史**（如适用）

既往治疗：
☐ 不限定
☐ 初治/未治疗
☐ 经治/难治性
☐ 特定治疗史：[请描述]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

请回复您的选择，或确认"不限定，包含所有亚组"。
```

---

## Pattern 8: Intervention Details

**Trigger:** Intervention is vague or has multiple components

**Examples:**
- "中医治疗"（中药？针灸？推拿？）
- "综合管理"（包括什么？）

**Dialogue Template:**

```
您提到的干预措施是'[INTERVENTION]'，这包含多种具体形式。

**请明确您想检索的具体干预类型：**

┌────────────────────────────────────────────────────────┐
│ [INTERVENTION] 的可能形式：                             │
├────────────────────────────────────────────────────────┤
│                                                        │
│  A. [SUBTYPE_1]                                        │
│     例如：[EXAMPLE_1]                                  │
│                                                        │
│  B. [SUBTYPE_2]                                        │
│     例如：[EXAMPLE_2]                                  │
│                                                        │
│  C. [SUBTYPE_3]                                        │
│     例如：[EXAMPLE_3]                                  │
│                                                        │
│  D. 以上全部（宽泛检索）                                │
│                                                        │
│  E. 其他：[请描述]                                      │
│                                                        │
└────────────────────────────────────────────────────────┘

💡 **检索建议**：
- 如果您想研究[SUBTYPE_1]的特定机制，选择A
- 如果您想比较不同形式的效果，选择D
- 如果文献有限，建议选择D以获取更多研究

请回复 A/B/C/D/E。
```

**Example for "中医治疗":**

```
您提到的干预措施是'中医治疗'，这包含多种具体形式。

**请明确您想检索的具体干预类型：**

┌────────────────────────────────────────────────────────┐
│ 中医治疗的可能形式：                                    │
├────────────────────────────────────────────────────────┤
│                                                        │
│  A. 中药/中成药                                        │
│     例如：汤剂、颗粒剂、复方制剂                        │
│                                                        │
│  B. 针灸                                               │
│     包括：体针、耳针、电针                              │
│                                                        │
│  C. 推拿/按摩                                          │
│     包括：经络推拿、穴位按压                            │
│                                                        │
│  D. 综合疗法                                           │
│     中药 + 针灸 + 推拿联合使用                          │
│                                                        │
│  E. 其他中医技术                                        │
│     例如：拔罐、刮痧、艾灸                              │
│                                                        │
│  F. 以上全部（宽泛检索）                                │
│                                                        │
└────────────────────────────────────────────────────────┘

💡 **检索建议**：
- 如果您想研究中药的化学成分，选择A
- 如果您想比较中西医治疗差异，选择F
- 如果文献有限，建议选择F以获取更多研究

请回复 A/B/C/D/E/F。
```

---

## General Principles for All Patterns

### 1. Progressive Disclosure
- Start with the most critical missing information
- Don't ask for everything at once
- Adapt follow-up questions based on user responses

### 2. Provide Options
- Always offer multiple-choice options when possible
- Include "Other" or free-text option
- Use visual separators (ASCII boxes, emojis) to improve readability

### 3. Confirm Understanding
- Restate what you've understood before proceeding
- Show the emerging PICO/PEO framework
- Allow users to correct misinterpretations

### 4. Graceful Degradation
- If user cannot provide detail, accept partial information
- Generate best-effort strategy with warnings
- Never block on missing non-critical information

### 5. Educational Value
- Briefly explain why each piece of information matters
- Connect choices to search strategy implications
- Guide users toward evidence-based practice
