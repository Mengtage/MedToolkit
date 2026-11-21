# 桌面浏览器验收

在项目根目录运行，Node + 已有 Python `.venv`；开发依赖独立于应用运行环境：

```bash
npm install --prefix .browser-tools --no-audit --no-fund playwright-core@1.65.1
CHROMIUM_PATH=/path/to/chrome node scripts/browser/acceptance.cjs
```

本机使用 `/home/labhub/.cache/ms-playwright/chromium-1255/chrome-linux64/chrome`。缺失的系统库通过 `apt-get download` 与 `dpkg-deb -x` 解包到 `.browser-tools/sysroot`，未安装到系统；本机复现：

```bash
LD_LIBRARY_PATH="$PWD/.browser-tools/sysroot/usr/lib/x86_64-linux-gnu" node scripts/browser/acceptance.cjs
```

依赖包为 libatk1.0-0t64、libatk-bridge2.0-0t64、libcups2t64、libasound2t64、libgbm1、libxcomposite1、libxdamage1、libxfixes3、libxrandr2、libatspi2.0-0t64、libavahi-common3、libavahi-client3、libxi6、libxres1；其他系统按实际缺库处理，不执行全局安装。程序默认端口 18765，可通过 `BROWSER_TEST_PORT` 指定空闲端口。

脚本启动真实 HTTP 服务与 SQLite Store，使用随机临时访问令牌，结束后关闭服务/浏览器并删除临时数据库。Gemini 两项环境变量在子进程强制为空，不读取配置文件。Chromium 以无头模式、1440×1000 桌面视口运行；服务器环境使用 `--no-sandbox`，仅访问本地合成测试页面。

统计走实际适配器；PubMed 仅替换出站传输为合成 JSON/XML，仍经过原 XML 解析、任务保存、浏览器产物查看和实际 RIS 下载。不代表在线 PubMed、Zotero、Gemini、用户桌面环境或其他浏览器验收。

结果在 `reports/browser/summary.json`；截图包括桌面全页与 TableOne/回归表格，截图前清空令牌。报告记录浏览器版本、时间、逐项结果、页面异常及网页/脚本哈希。退出非零即失败。

其他桌面流程使用相同依赖与CHROMIUM_PATH：`node scripts/browser/writer.cjs`、`node scripts/browser/writer_hunter.cjs`。分别使用18766、18767端口；主流程默认18765。三者均为合成隔离验收，不应对真实项目数据运行。
