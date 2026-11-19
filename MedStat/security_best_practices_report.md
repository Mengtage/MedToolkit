# MedStat 项目安全检查报告

## 执行摘要

本报告对 MedStat 数据上传与自动化分析应用进行了全面安全检查。总体评估为**中等风险**，主要关注敏感数据处理和生产环境配置。

---

## 🔴 严重问题

### 1. 硬编码密钥（中等风险）

**位置**：[app.py:67](file:///workspace/app.py#L67)

**描述**：
```python
app.secret_key = 'your-secret-key-here-change-in-production'
```

**问题**：
- 密钥硬编码在源代码中，可能被意外提交到仓库
- 生产环境中使用默认密钥是不安全的

**影响**：
- 如果密钥泄露，会话劫持风险
- 无法安全轮换密钥

**修复建议**：
```python
# 使用环境变量
import os
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))
```

---

## 🟡 中等问题

### 2. 内存存储，缺少会话过期清理（中等风险）

**位置**：[app.py:81](file:///workspace/app.py#L81)

**描述**：
```python
user_data_store = {}
```

**问题**：
- 用户数据存储在内存字典中，没有清理机制
- 长时间运行会导致内存泄漏
- 没有数据过期策略
- 数据在进程重启后丢失

**影响**：
- 潜在内存溢出风险
- 敏感数据无限期保留
- 会话可能永久保留在内存中

**修复建议**：
- 添加定期清理旧会话机制
- 设置会话过期时间
- 考虑使用 Redis 等外部存储替代

```python
import time
from collections import defaultdict

user_data_store = {}
session_timestamps = {}

def cleanup_old_sessions(max_age=3600):  # 1小时
    current_time = time.time()
    expired_sessions = [
        sid for sid, ts in session_timestamps.items()
        if current_time - ts > max_age
    ]
    for sid in expired_sessions:
        if sid in user_data_store:
            del user_data_store[sid]
            del session_timestamps[sid]
```

---

### 3. 文件验证不完整（低风险）

**位置**：[app.py:84-86](file:///workspace/app.py#L84-L86)

**描述**：
```python
def allowed_file(filename):
    """检查文件扩展名是否允许"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
```

**问题**：
- 仅检查扩展名，未验证文件内容类型
- 可能被伪装的恶意文件绕过
- 缺少MIME类型验证

**影响**：
- 可能上传伪装成CSV的恶意文件
- 潜在的代码注入风险

**修复建议**：
```python
import magic

def allowed_file(file):
    # 检查扩展名
    filename = file.filename
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False
    
    # 验证MIME类型
    mime = magic.from_buffer(file.read(1024), mime=True)
    file.seek(0)
    allowed_mimes = {
        'csv': ['text/csv', 'text/plain'],
        'xlsx': ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'],
        'xls': ['application/vnd.ms-excel']
    }
    return mime in allowed_mimes.get(ext, [])
```

---

## 🟢 低风险问题

### 4. 缺少速率限制（低风险）

**问题**：
- 没有API请求速率限制
- 容易受到暴力攻击或资源耗尽攻击

**修复建议**：
使用 Flask-Limiter
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(get_remote_address, app=app)

@app.route('/upload', methods=['POST'])
@limiter.limit("10/minute")  # 每分钟10次
def upload_file():
    # ...
```

---

### 5. 敏感数据未加密（低风险）

**问题**：
- 用户上传的数据存储在内存中，未加密
- 如果内存被dump，可能泄露敏感信息

**修复建议**：
- 文档中说明不要用于真正的敏感医疗数据
- 对于生产版本考虑添加加密选项

---

### 6. 缺少输入验证（低风险）

**问题**：
- 部分API缺少严格的输入验证
- 潜在的注入风险（虽然通过Pandas相对安全）

**修复建议**：
添加更严格的参数验证
```python
from pydantic import BaseModel, ValidationError

class UpdateTypeRequest(BaseModel):
    session_id: str
    column: str
    new_type: str

@app.route('/update_type', methods=['POST'])
def update_column_type():
    try:
        data = UpdateTypeRequest(**request.json)
    except ValidationError as e:
        return jsonify({'error': 'Invalid input'}), 400
    # ...
```

---

### 7. 缺少请求日志记录（低风险）

**问题**：
- 没有API访问日志
- 难以追踪潜在攻击

**修复建议**：
```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.before_request
def log_request():
    logger.info(f"{request.method} {request.path} from {request.remote_addr}")
```

---

## ✅ 良好实践

### 以下安全措施已正确实现：

1. **文件扩展名白名单** - [app.py:71-72](file:///workspace/app.py#L71-L72)
   - 使用 `ALLOWED_EXTENSIONS` 限制文件类型

2. **安全文件名处理** - [app.py:376](file:///workspace/app.py#L376)
   - 使用 `werkzeug.utils.secure_filename` 处理文件名

3. **文件大小限制** - [app.py:72](file:///workspace/app.py#L72)
   - 设置了16MB的最大上传限制

4. **会话ID安全生成** - [app.py:373](file:///workspace/app.py#L373)
   - 使用 `uuid.uuid4()` 生成不可预测的会话ID

5. **异常处理**
   - 所有API端点都有try-except捕获异常
   - 不泄露详细的异常信息给用户

6. **不使用eval/exec**
   - 代码中未发现危险的执行函数

---

## 📋 总体评级

| 严重程度 | 数量 | 状态 |
|---------|-----|------|
| 🔴 严重 | 0 | ✅ 无 |
| 🟡 中等 | 3 | ⚠️ 需注意 |
| 🟢 低风险 | 4 | ℹ️ 建议优化 |

---

## 🚀 部署前建议清单

### 生产环境必须：
1. [ ] 更换强 Secret Key，使用环境变量
2. [ ] 添加会话清理机制
3. [ ] 配置HTTPS（生产环境）
4. [ ] 设置安全的Cookie标志
5. [ ] 添加API访问日志
6. [ ] 考虑添加速率限制

### 推荐但非必须：
1. [ ] 添加MIME类型验证
2. [ ] 定期安全审计
3. [ ] 添加请求ID追踪
4. [ ] 考虑使用CSRF保护
5. [ ] 完善错误处理和监控

---

## 📌 总结

项目安全状况**总体可控**，严重问题为0。主要需要关注会话管理和生产环境配置。建议根据上述优先级逐步修复。

**最关键的一步：务必在生产部署前修改硬编码的 `app.secret_key`！**

---

**报告生成时间**：2026-05-18  
**检查范围**：`app.py` 和整个项目结构
