# 前端开发提示词 - 风格延续指南

## 项目风格参考

请基于以下设计规范开发新的前端项目，保持与MedPaperHunter一致的视觉风格：

---

## 设计系统

### 颜色规范

```css
/* 医学专业风格 - 蓝色系主调 */
:root {
  /* 主色系 */
  --primary-color: #0066CC;      /* 主色调 - 科技蓝 */
  --primary-hover: #0052A3;     /* 主色悬停 */
  --primary-light: #E3F2FD;    /* 主色浅色背景 */
  
  /* 深色系 - 用于标题/页眉 */
  --secondary-color: #1B2A4A;   /* 深蓝 - 专业感 */
  --secondary-light: #2C3E50;
  
  /* 功能色 */
  --success-color: #4CAF50;    /* 成功/纳入 */
  --warning-color: #FF9800;     /* 警告 */
  --danger-color: #F44336;      /* 错误/排除 */
  --info-color: #2196F3;       /* 信息提示 */
  
  /* 中性色 */
  --background-light: #F5F7FA;  /* 页面背景 */
  --background-white: #FFFFFF;  /* 卡片背景 */
  --border-color: #E0E0E0;     /* 边框线 */
  --text-primary: #333333;     /* 主文本 */
  --text-secondary: #666666;    /* 次要文本 */
  --text-muted: #999999;        /* 辅助文本 */
}
```

### 字体规范

```css
/* 字体族 */
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;

/* 字号体系 */
--font-size-xs: 11px;     /* 辅助说明 */
--font-size-sm: 12px;    /* 标签/小字 */
--font-size-base: 14px; /* 正文 */
--font-size-lg: 16px;    /* 强调文本 */
--font-size-xl: 18px;    /* 小标题 */
--font-size-2xl: 20px;   /* 区块标题 */
--font-size-3xl: 24px;   /* 页面标题 */

/* 字重 */
--font-weight-normal: 400;
--font-weight-medium: 500;
--font-weight-semibold: 600;
--font-weight-bold: 700;
```

### 间距体系

```css
:root {
  --spacing-xs: 4px;
  --spacing-sm: 8px;
  --spacing-md: 12px;
  --spacing-lg: 16px;
  --spacing-xl: 20px;
  --spacing-2xl: 24px;
  --spacing-3xl: 32px;
  --spacing-4xl: 40px;
}
```

---

## 组件样式

### 按钮

```css
/* 主要按钮 */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 10px 24px;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
}

.btn-primary {
  background: var(--primary-color);
  color: white;
}

.btn-primary:hover {
  background: var(--primary-hover);
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(0, 102, 204, 0.3);
}

.btn-primary:disabled {
  background: #CCCCCC;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

/* 次要按钮 */
.btn-secondary {
  background: var(--background-white);
  color: var(--text-primary);
  border: 1px solid var(--border-color);
}

.btn-secondary:hover {
  background: var(--background-light);
  border-color: var(--primary-color);
}

/* 文字按钮 */
.btn-text {
  background: transparent;
  color: var(--primary-color);
  padding: 8px 12px;
}

.btn-text:hover {
  background: var(--primary-light);
}
```

### 卡片/面板

```css
/* 工作流程面板 */
.workflow-step {
  background: var(--background-white);
  border-radius: 8px;
  padding: var(--spacing-xl);
  margin-bottom: var(--spacing-lg);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  transition: box-shadow 0.2s;
}

.workflow-step:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

/* 流程网格 */
.process-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--spacing-xl);
}

/* 统计数字 */
.process-stats {
  background: var(--background-light);
  padding: var(--spacing-md);
  border-radius: 4px;
  margin-bottom: var(--spacing-md);
  font-size: 13px;
  line-height: 1.8;
}

.process-stats strong {
  color: var(--primary-color);
  font-size: 18px;
}
```

### 表单元素

```css
/* 大文本框 */
textarea.input-large {
  width: 100%;
  min-height: 100px;
  padding: var(--spacing-lg);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  font-size: 14px;
  font-family: inherit;
  resize: vertical;
  transition: border-color 0.2s;
}

textarea.input-large:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px var(--primary-light);
}

/* 输入框 */
input[type="text"],
input[type="email"],
input[type="password"] {
  width: 100%;
  padding: var(--spacing-sm) var(--spacing-md);
  border: 1px solid var(--border-color);
  border-radius: 4px;
  font-size: 14px;
  transition: border-color 0.2s;
}

input:focus {
  outline: none;
  border-color: var(--primary-color);
  box-shadow: 0 0 0 3px var(--primary-light);
}
```

### 进度条

```css
/* 进度条容器 */
.progress-bar-container {
  height: 8px;
  background: var(--border-color);
  border-radius: 4px;
  overflow: hidden;
  margin: var(--spacing-md) 0;
}

.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, var(--primary-color), #42A5F5);
  border-radius: 4px;
  transition: width 0.3s ease;
  position: relative;
}

/* 进度条动画 */
.progress-bar::after {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(255, 255, 255, 0.3),
    transparent
  );
  animation: shimmer 2s infinite;
}

@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

/* 进度文字 */
.progress-text {
  font-size: 12px;
  color: var(--text-secondary);
  text-align: center;
  margin-top: var(--spacing-xs);
}
```

### 标签/徽章

```css
/* 术语标签 */
.term-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
  margin: var(--spacing-md) 0;
}

.term-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 12px;
  background: var(--primary-light);
  color: var(--primary-color);
  border-radius: 16px;
  font-size: 12px;
  transition: all 0.2s;
}

.term-tag:hover {
  background: var(--primary-color);
  color: white;
}

.term-tag .remove-tag {
  cursor: pointer;
  opacity: 0.7;
}

.term-tag .remove-tag:hover {
  opacity: 1;
}

/* 状态徽章 */
.badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}

.badge-success {
  background: #E8F5E9;
  color: #4CAF50;
}

.badge-warning {
  background: #FFF3E0;
  color: #FF9800;
}

.badge-danger {
  background: #FFEBEE;
  color: #F44336;
}
```

### 表格

```css
/* 数据表格 */
.data-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--background-white);
  border-radius: 4px;
  overflow: hidden;
}

.data-table th {
  background: var(--secondary-color);
  color: white;
  padding: var(--spacing-md);
  text-align: left;
  font-weight: 500;
}

.data-table td {
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--border-color);
}

.data-table tr:hover {
  background: var(--background-light);
}

/* 表头固定 */
.data-table thead {
  position: sticky;
  top: 0;
  z-index: 10;
}
```

### 错误和消息

```css
/* 错误提示 */
.error-msg {
  display: none;
  padding: var(--spacing-md);
  background: #FFEBEE;
  color: #C62828;
  border-left: 3px solid #F44336;
  border-radius: 4px;
  font-size: 13px;
  margin-top: var(--spacing-md);
}

/* 成功提示 */
.success-msg {
  padding: var(--spacing-md);
  background: #E8F5E9;
  color: #2E7D32;
  border-left: 3px solid #4CAF50;
  border-radius: 4px;
  font-size: 13px;
}

/* 加载动画 */
.loading-spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid var(--border-color);
  border-top-color: var(--primary-color);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
```

---

## 布局规范

### 页面结构

```html
<div class="container">
  <!-- 页面标题区 -->
  <header class="page-header">
    <h1 class="page-title">页面标题</h1>
    <p class="page-subtitle">页面副标题/说明</p>
  </header>
  
  <!-- 主内容区 -->
  <main class="main-content">
    <!-- 工作流程区块 -->
    <section class="workflow-section">
      <!-- 步骤1 -->
      <div class="workflow-step">
        <h3>步骤标题</h3>
        <!-- 内容 -->
      </div>
    </section>
  </main>
  
  <!-- 页脚 -->
  <footer class="page-footer">
    <p>页脚信息</p>
  </footer>
</div>
```

```css
/* 容器 */
.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: var(--spacing-xl);
}

/* 页面头部 */
.page-header {
  margin-bottom: var(--spacing-3xl);
  padding-bottom: var(--spacing-xl);
  border-bottom: 1px solid var(--border-color);
}

.page-title {
  font-size: var(--font-size-3xl);
  color: var(--secondary-color);
  margin-bottom: var(--spacing-sm);
}

.page-subtitle {
  font-size: var(--font-size-lg);
  color: var(--text-secondary);
}
```

### 响应式断点

```css
/* 移动端优先 */
@media (max-width: 576px) {
  /* 超小屏幕 */
  .container { padding: var(--spacing-md); }
  .process-grid { grid-template-columns: 1fr; }
}

@media (min-width: 577px) and (max-width: 768px) {
  /* 小屏幕 */
  .process-grid { grid-template-columns: 1fr; }
}

@media (min-width: 769px) and (max-width: 992px) {
  /* 中等屏幕 */
  .process-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (min-width: 993px) {
  /* 大屏幕 */
  .process-grid { grid-template-columns: repeat(3, 1fr); }
}
```

---

## 交互规范

### 加载状态

```javascript
function showLoading(buttonId) {
  const btn = document.getElementById(buttonId);
  btn.disabled = true;
  btn.dataset.originalText = btn.textContent;
  btn.innerHTML = '<span class="loading-spinner"></span> 加载中...';
}

function hideLoading(buttonId) {
  const btn = document.getElementById(buttonId);
  btn.disabled = false;
  btn.textContent = btn.dataset.originalText || '提交';
}
```

### 错误处理

```javascript
function showError(elementId, message) {
  const errorEl = document.getElementById(elementId);
  errorEl.textContent = message;
  errorEl.style.display = 'block';
}

function hideError(elementId) {
  document.getElementById(elementId).style.display = 'none';
}
```

### API调用模式

```javascript
async function fetchData(url, options = {}) {
  try {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      },
      ...options
    });
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('请求失败:', error);
    throw error;
  }
}
```

---

## 视觉特征总结

### 设计关键词

- **专业感**：医学/科研领域，深蓝色调传递专业信任
- **简洁清晰**：大量留白，信息层次分明
- **功能导向**：每个元素都有明确目的
- **微交互**：hover效果、过渡动画提升体验

### 关键视觉元素

1. **主色调**：`#0066CC` 科技蓝
2. **深色强调**：`#1B2A4A` 用于标题和重要信息
3. **圆角**：统一使用 `4px` 小圆角
4. **阴影**：轻柔阴影 `0 1px 3px rgba(0,0,0,0.1)`
5. **间距**：基于 `4px` 倍数的间距体系

### 无障碍考虑

- 足够的颜色对比度
- 焦点状态清晰可见
- 支持键盘操作
- ARIA标签

---

请严格遵循以上设计规范，确保新项目与MedPaperHunter在视觉上保持一致。
