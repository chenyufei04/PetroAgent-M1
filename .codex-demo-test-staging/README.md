# 石油工程术语质控

基于 Vue 3、TypeScript、Vite 和 FastAPI 的石油工程术语与数据质量控制项目。

## 项目结构

```text
demo-test/
├─ .venv/                     # Python 3.10 虚拟环境
├─ backend/
│  ├─ __init__.py
│  └─ main.py                 # FastAPI接口、文件保存及Excel解析
├─ dist/                      # 前端生产构建产物
├─ node_modules/              # Node.js依赖
├─ src/
│  ├─ data/
│  │  └─ seed.ts              # 初始术语、规则和基础数据
│  ├─ services/
│  │  └─ qualityEngine.ts     # 质控规则匹配与文本标注引擎
│  ├─ stores/
│  │  └─ data.ts              # Pinia全局数据状态
│  ├─ views/
│  │  ├─ QualityPage.vue      # 数据上传、质控结果和问题标注
│  │  ├─ RulesPage.vue        # 规则库与模糊查询
│  │  ├─ TermsPage.vue        # 术语库与模糊查询
│  │  ├─ BaseDataPage.vue     # 基础字典与模糊查询
│  │  ├─ ImportPage.vue       # 术语/规则分离导入
│  │  └─ BlankPage.vue        # 未实现功能的占位页
│  ├─ App.vue                 # 应用整体布局与顶部导航
│  ├─ main.ts                 # Vue应用入口
│  ├─ router.ts               # 页面路由
│  ├─ styles.css              # 全局样式
│  └─ types.ts                # 公共TypeScript类型
├─ uploads/                   # 质控页上传文件的本地保存目录
├─ index.html                 # Vite HTML入口
├─ package.json               # 前端依赖与脚本
├─ requirements.txt           # Python后端依赖
├─ tsconfig.json              # TypeScript配置
└─ vite.config.ts             # Vite配置及API代理
```

## 环境准备

```powershell
npm install
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 启动项目

终端一启动后端：

```powershell
.venv\Scripts\Activate.ps1
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

终端二启动前端：

```powershell
npm run dev
```

访问 `http://127.0.0.1:5173`。质控页上传的原始文件会自动保存到 `uploads` 目录。

## 已实现模块

- 质控：上传并解析XLSX、CSV、DOCX、TXT、JSON、XML等文件，按严重级别标注问题。
- 规则库：典型石油工程规则、分类筛选和模糊查询。
- 术语库：中英文术语、缩写、定义、来源和模糊查询。
- 基础数据：专业分类、计量单位、常用缩写和数据来源。
- 数据导入：术语与规则分别导入并分别保存。
- 规则自检：当前保留为空白功能页。
