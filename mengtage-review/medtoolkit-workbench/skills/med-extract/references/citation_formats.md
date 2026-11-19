# 引用格式参考

## Vancouver 格式

### 期刊文章（1-6位作者）
作者 AA, 作者 BB, 作者 CC. 文章标题. 期刊名缩写. 年份;卷(期):起止页码.

**示例：**
Smith J, Doe A, Wang L. Metformin and renal function in type 2 diabetes. J Diabetes Care. 2023;45(3):234-241.

### 期刊文章（7位及以上作者）
作者 AA, 作者 BB, 作者 CC, et al. 文章标题. 期刊名缩写. 年份;卷(期):起止页码.

### 书籍
作者 AA. 书名. 版次. 出版地: 出版社; 年份.

### 书籍章节
作者 AA. 章节标题. 编者 BB, 编者 CC, 编者 DD, eds. 书名. 版次. 出版地: 出版社; 年份:页码.

### 在线资源
作者 AA. 标题[文献类型]. 网站名. URL. 发布日期. 访问日期.

---

## AMA 格式

### 期刊文章
作者 AA, 作者 BB. 文章标题. 期刊名缩写. 年份;卷(期):起止页码. doi:xx.xxxx

**示例：**
Smith J, Doe A. Metformin and renal function in type 2 diabetes. J Diabetes Care. 2023;45(3):234-241. doi:10.1000/jdc.2023.001

### 书籍
作者 AA. 书名. 版次. 出版地: 出版社; 年份.

### 网站
作者 AA. 页面标题. 网站名. URL. 发布/更新日期. 访问日期.

---

## RIS 格式

RIS（Research Information Systems）是文献管理软件通用的导入格式。

### 常用标签

| 标签 | 含义 | 示例 |
|------|------|------|
| TY | 文献类型 | JOUR（期刊）, BOOK（书籍） |
| TI | 标题 | 文章标题 |
| AU | 作者 | Smith, John |
| T2 | 期刊名 | Journal of Medicine |
| PY | 出版年 | 2023 |
| VL | 卷号 | 45 |
| IS | 期号 | 3 |
| SP | 起始页 | 234 |
| EP | 结束页 | 241 |
| DO | DOI | 10.1000/example |
| AB | 摘要 | 文章摘要... |
| KW | 关键词 | diabetes, metformin |
| ER | 记录结束 | - |

### 示例

```
TY  - JOUR
TI  - Metformin and renal function in type 2 diabetes
AU  - Smith, John
AU  - Doe, Alice
T2  - Journal of Diabetes Care
PY  - 2023
VL  - 45
IS  - 3
SP  - 234
EP  - 241
DO  - 10.1000/jdc.2023.001
AB  - Background: ...
KW  - metformin
KW  - diabetes
KW  - renal function
ER  - 
```

---

## CSV 字段说明

| 字段名 | 说明 | 示例 |
|--------|------|------|
| id | 文献唯一标识 | MED001 |
| authors | 作者列表（逗号分隔） | Smith J, Doe A |
| title | 文章标题 | Metformin and renal function... |
| journal | 期刊名 | Journal of Diabetes Care |
| year | 发表年份 | 2023 |
| volume | 卷号 | 45 |
| issue | 期号 | 3 |
| pages | 页码 | 234-241 |
| doi | DOI | 10.1000/jdc.2023.001 |
| pmid | PubMed ID | 12345678 |
| abstract | 摘要 | Background: ... |
| keywords | 关键词（逗号分隔） | metformin, diabetes, renal |
| study_type | 研究类型 | Randomized controlled trial |
| inclusion_status | 纳入状态 | Included / Excluded |
