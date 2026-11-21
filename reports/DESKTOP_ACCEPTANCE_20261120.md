# 桌面浏览器验收 · 2026-11-20

2026-11-20 08:29:36 UTC，真实 Chromium 159.0.8154.6 无头浏览器、1440×1000 桌面视口：20 项流程检查全部通过，页面 JavaScript 异常为 0。脚本、原始结果与截图均已保存。

| 流程 | 验证内容 |
|---|---|
| 鉴权 | 空令牌/错误令牌拒绝，正确令牌连接 |
| 项目 | 创建、特殊字符作为文字呈现、切换隔离、重新加载后的持久化 |
| 输入错误 | 非法 JSON 与空数组显示错误，不创建任务 |
| 相关性 | Pearson、Spearman 各自提交、运行、刷新、查看实际产物 |
| 列联表 | auto、chi2、fisher、yates；核对 requested_method，保留实际检验名称 |
| 组间与 TableOne | 提交执行，核对结果；TableOne 表格无 undefined |
| 回归 | OLS、Logistic、Poisson、Gamma；完整系数表、右侧区间/OR 可滚动查看 |
| 评估与插补 | 独立提交执行及 JSON 产物；切换后清除旧表格 |
| 检索与 RIS | 合成 PubMed JSON/XML 经真实解析/任务服务，1/2 条标记不完整，浏览器实际下载并核对 RIS 内容 |
| 页面 | 令牌重载清空、无 localStorage/sessionStorage；Gemini 未配置提示；结果表不造成桌面整页横向溢出 |

截图发现原回归表长小数挤出内容区。修复仅在宽度 ≥900px 添加结果容器横向滚动、表格间距与分隔线，保留全精度与原字段。已复验左右两端截图，TableOne/回归表可读。未更改统计实现或旧默认策略，无需作方法选择决策。

证据：`browser/summary.json`、`browser/run.log`、`browser/desktop.png`、`browser/tableone.png`、四种回归左右端截图及 `browser/references.ris`。结果摘要记录网页与测试脚本 SHA256；复现见 [scripts/browser/README.md](../scripts/browser/README.md)。

原 121 项 Python/HTTP/统计检查未重复运行：与 `validation-summary.json` 的已测源码逐项比对，哈希全部一致。测试环境缺少的 Chromium 依赖仅解包至 `.browser-tools/sysroot`，未修改共享服务；临时测试项目与随机令牌随进程结束清理。

本轮仅合成数据，无 Gemini 请求，无用户文献库写入。PubMed 出站传输使用测试替身，未重新验证外网接口；Firefox/Safari、真实用户桌面、手机、旧 WebApp、临床及生产安全不在本轮验收范围。
