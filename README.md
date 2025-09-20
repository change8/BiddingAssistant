# 投标助手（MVP）

面向销售人员的轻量投标标书要点梳理与风险提示工具。核心目标：上传或粘贴招标文本后，基于内置/可配置检查项与大模型分析，输出以下分类要点：

- 关键/核心条款：必须满足或影响报价/资质/进度的条款
- 疑问/需澄清：需向甲方澄清的模糊、不完整、矛盾条款
- 不利条款：对我方商务、技术、交付不利的要求（可尝试沟通调整）
- 拦标项：明显限制性、唯一性、与资格/参数设置相关的拦标要求
- 可能控标信号：供应商指向性、过细参数组合、非通用验收方式等
- 关键词提取：由用户配置或系统内置的关键字提取

本仓库包含：
- backend：分析引擎、规则模板、（可对接大模型的）接口骨架
- frontend/miniprogram：微信小程序骨架（页面与交互占位）
- sample_data：示例标书片段与 CLI 演示脚本

注意：本仓库为原型脚手架，不包含依赖安装与可运行构建流程；便于后续按需落地。

## 快速开始（原型）

- 规则模板：`backend/rules/checklist.zh-CN.yaml`
- CLI 演示：`backend/cli_demo.py`（基于关键词/正则启发式，LLM 为占位）
- 小程序壳：`frontend/miniprogram`（上传入口与结果展示占位）

## 后端 API（MVP）

### 环境准备

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn[standard] pydantic python-docx pdfminer.six PyPDF2 pillow pytesseract sentence-transformers
```

> 注：`python-docx`/`pdfminer.six`/`PyPDF2`/`pytesseract` 等依赖按需安装；未安装时相应功能会自动降级。

### 启动服务

```bash
uvicorn backend.app:create_app --factory --host 0.0.0.0 --port 8000
```

主要接口：

- `GET /rules`：返回当前加载的规则模板
- `POST /analyze/text`：传入 `text` 字段，立即触发分析（默认同步返回）
- `POST /analyze/file`：上传文件，后台完成抽取后分析，可选轮询 `/jobs/{job_id}`
- `GET /jobs/{job_id}` / `GET /jobs` / `DELETE /jobs/{job_id}`：任务状态管理
- `GET /config`：查看当前 LLM / 检索配置（API Key 已自动隐藏）

### 配置说明

配置按以下优先级读取：环境变量 → 指定配置文件 → 默认值。

- 环境变量：
  - `BIDDING_ASSISTANT_LLM_PROVIDER`（如 `stub` / `openai` / `azure_openai`）
  - `BIDDING_ASSISTANT_LLM_API_KEY`
  - `BIDDING_ASSISTANT_LLM_MODEL`
  - `BIDDING_ASSISTANT_LLM_BASE_URL`
- 配置文件：
  - 支持 `export BIDDING_ASSISTANT_CONFIG=/path/to/app.yaml`
  - 默认读取 `backend/config.yaml` 或 `config/app.yaml`

示例 `config/app.yaml`：

```yaml
llm:
  provider: stub
  model: gpt-4o-mini
retrieval:
  enable_heuristic: true
  enable_embedding: false
  embedding_model: shibing624/text2vec-base-chinese
  limit: 6
```

## 小程序前端

- API 基础地址：`frontend/miniprogram/utils/config.js`
- 页面逻辑：`frontend/miniprogram/pages/home/home.*`，已改为调后台接口、轮询任务状态并展示分类汇总
- 如需体验，请在微信开发者工具中导入 `frontend/miniprogram` 目录，并确保后台服务可通过 HTTP 访问

## 文档抽取与预处理

- 文本归一化：`backend/analyzer/preprocess.py`
- 抽取调度：`backend/extractors/dispatcher.py`（自动识别 txt/docx/pdf，并在必要时触发 OCR）
- OCR（可选）：集成 `pytesseract`/`pdf2image`，缺省时自动跳过
- 分段检索：`backend/analyzer/retrieval.py` 提供启发式与向量检索两种能力，可与 LLM 协同

## 分析流程（MVP）

1) 文档获取：上传文件（txt/pdf/docx）或直接粘贴文本
2) 文本抽取：优先使用原生文本，必要时 OCR（占位接口）
3) 规则匹配：关键词/正则/（可选）语义匹配（LLM）
4) 分类整理：按类别聚合、标注证据片段、给出建议/澄清点
5) 输出结果：JSON 结构供前端展示；支持导出 markdown

## 关键设计

- 规则可配置：YAML 定义类别、严重度、匹配模式（keyword/regex/semantic）
- LLM 可插拔：`backend/analyzer/llm.py` 提供统一接口，便于切换供应商
- 审计可追溯：每条命中保留文本证据与命中的规则 id

## 下一步建议

- 接入真实解析库（pdfminer/docx/ocr），完善抽取质量
- 引入向量召回/术语库，提升“控标信号”的召回率
- 对接企业登录与数据隔离，加密与脱敏
- 增加行业模板（政采、央企、运营商、医疗、教育等）
- 建立自动化测试（规则覆盖率 / 接口契约）与持续集成流程
- 完成小程序端 API 域名配置、鉴权与部署脚本
