# MedHunter：去重、人工 checkpoint 与背对背筛选留痕

## 每条文献保留哪些记录

| 层级 | 保存内容 | 用途 |
|---|---|---|
| 检索来源 | 数据库、检索式、时间、批次、原始响应、PMID/DOI、记录快照及哈希 | 回到最初检索来源；更新检索生成新批次 |
| 去重 | 原始记录、规范化标题与标识、匹配字段、候选冲突、合并组、保留条目、规则版本 | 任一合并可以追溯到被合并记录，不物理删除来源 |
| 筛选方案 | 研究问题、阶段、纳排标准、评审人与裁决者、方案版本/哈希 | 防止中途变更标准后沿用旧判断 |
| 人工 checkpoint | 批准者、时间、批准的方案哈希与文献集哈希 | 未批准不能领取正式筛选材料或提交判断 |
| 独立判断 | review_id、record_id、评审者、include/exclude/uncertain、理由、证据位置、时间 | 人类与LLM分别保存，提交后锁定 |
| LLM运行 | 模型版本、参数、实际提示、原始响应、运行ID、方案哈希 | 可审阅当时模型看到什么、返回什么；不记录隐藏思维链 |
| 揭盲与裁决 | 双方提交事件、揭盲时间、逐条最终结论、裁决理由、后续修订事件 | 原始意见不被最终结论覆盖；分歧可统计 |

主键须为内部 record_id，PMID/DOI 是可缺失、可能冲突的属性，不能代替内部主键。多篇论文可能属于同一研究：记录级去重不等于 study-level 合并；全文阶段应另建 study_id—report_id 关系。

## 执行顺序

1. 完成无 LLM 去重，人工处理疑似冲突；固定文献集与纳排标准。先在独立试筛批次校准标准，正式批次重新冻结方案。
2. 人类作者明确批准 checkpoint：纳排标准、阶段、资料范围、评审人和裁决者。批准不等于允许把非公开全文发送给外部模型，后者需要单独确认。
3. 人类和 LLM 获得相同资料范围，各自筛选，不看到对方结论、理由、置信度或排序提示。现有原型的 ballot 仅允许题名、摘要、作者、期刊、日期和 PMID/DOI，剔除旧 screening 字段。
4. 双方逐条提交并锁定后才揭盲。缺项、解析失败或模型中断停留未完成，不默认为排除；uncertain 必须进入人工复核。
5. 人类裁决者确认最终结果。原型要求每条都有最终确认，包括一致项；修订追加事件，不修改早先记录。最终纳入/排除计数由最终确认推导，重复记录与未完成项分开统计。
6. 全文筛选应作为新阶段/新批次，绑定全文文件哈希、页码/段落与明确排除原因；复用题名摘要阶段的来源关系，不覆盖它。当前全文工作流未实现。

## 已实现的本地原型

- `workbench/deduplication.py`：标题、PMID、DOI 规范化与精确匹配，无模糊匹配、无 LLM；保存所有原始记录与合并证据，空标题不丢弃。选择完整字段较多的记录展示，不擅自混合有冲突的元数据。最多1000条/20000候选对，超限明确拒绝。
- 默认策略已于2026-11-20获用户确认：`review` 保留冲突待人工核对；API和CLI均默认采用此策略。`title_wins` 仅作为显式覆盖选项保留，记录override。已接入统一桌面检索任务的“去重并复核”按钮；旧Hunter独立应用不在本轮迁移范围。
- `workbench/screening.py`：本地 SQLite 追加事件，prepare→approve→ballot/submit→reveal→adjudicate/export；快照与哈希链验证，提交不可覆盖，最终修订追加。仅支持题名摘要阶段。
- `workbench/screening_cli.py`：通过 JSON 请求调用原型；模型输出可导入但不自动调用模型，Gemini 配置保持空白。

去重调用（选择策略后）：

```bash
.venv/bin/python -m workbench.deduplication_cli --data runtime --conflict-policy review PROJECT_ID SEARCH_ARTIFACT.json
```

新产物包含原文献、去重后的 records、组成员、合并原因与待复核候选；检索原产物不覆盖。

筛选调用：

```bash
.venv/bin/python -m workbench.screening_cli --data runtime request.json
```

请求示例（将ID与研究方案替换为实际值）：

```json
{
  "operation": "prepare",
  "arguments": {
    "project": "PROJECT_ID",
    "source_artifact": "DEDUP_ARTIFACT.json",
    "actor": "author",
    "protocol": {
      "question": "实际研究问题",
      "stage": "title_abstract",
      "inclusion": "实际纳入标准",
      "exclusion": "实际排除标准",
      "human_reviewer": "author",
      "llm_reviewer": "model-reviewer",
      "adjudicator": "author"
    }
  }
}
```

后续 approve 需要 review、actor、confirmed:true；submit 需要 review、actor、decisions、provenance。每条 decision 的字段固定为 record_id、decision、reason、locator。人工 provenance 为 `{"type":"human_manual"}`；模型 provenance 为 model、parameters、prompt、raw_response、run_id。其他方法的准确参数见源码。最终 export 包含完整事件链、最终决定及待最终确认数量。

## 当前权限与产品接入状态

题名摘要已接入独立评审页面与HTTP角色/批次权限，服务端身份由独立令牌确定；审批、独立提交、揭盲、人工裁决和JSON/CSV导出已实现。完整界面和验收见 [桌面筛选报告](SCREENING_DESKTOP_20261120.md)。CLI仍属于受信任管理员入口，不能把CLI声明actor当作受限评审认证。

管理员和磁盘访问者仍受信任；哈希链无外部锚定。真实模型运行器、全文快照、规范化排除代码与两类CSV已完成；全文、PRISMA与生产部署仍待接入。Gemini保持空白。旧Hunter llm_screen不能直接承担此审计流程：它只返回纳入项，且解析失败可能映射为NO，当前未启用。
