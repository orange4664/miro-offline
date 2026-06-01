# MiroFish-Offline 部署与配置说明（中文）

本分支基于 [nikmcfly/MiroFish-Offline](https://github.com/nikmcfly/MiroFish-Offline)，做了以下改动：

- 用 **Neo4j** 替代 Zep Cloud 存图谱（本地，不依赖云服务）
- LLM / Embedding 改为走**任意 OpenAI 兼容接口**（中转站 / 自建 / 官方都行），不依赖 Ollama
- 修复了 OASIS 采访 / 问卷在中转站下被拦截导致全部失败的问题
- 报告生成改中文、修复空响应崩溃、前端去掉无效重试

---

## 一、前置要求

| 工具 | 版本 | 说明 |
|------|------|------|
| Node.js | 18+ | 前端 |
| Python | 3.11 或 3.12 | 后端（**不支持 3.13**，tiktoken 装不上）|
| uv | 最新版 | Python 包管理器 |
| Docker Desktop | 最新版 | 仅用于跑 Neo4j |

如果系统 Python 是 3.13，不用卸载，`uv` 会自动下载 3.11 来用。

---

## 二、配置 .env

```bash
cp .env.example .env
```

然后编辑 `.env`，主要填三组值（详见 `.env.example` 内注释）：

1. **主 LLM**：`LLM_API_KEY` / `LLM_BASE_URL` / `LLM_MODEL_NAME`
   - 必须支持 chat completions 和 function calling（工具调用）
   - `LLM_BASE_URL` 通常以 `/v1` 结尾
2. **Embedding**：`EMBEDDING_PROVIDER=openai` + `EMBEDDING_API_KEY` / `EMBEDDING_BASE_URL` / `EMBEDDING_MODEL`
   - 没有可用 embedding 接口时可设 `EMBEDDING_PROVIDER=hash` 先跑通流程（质量低）
3. **OASIS**：`OPENAI_API_KEY` / `OPENAI_API_BASE_URL`，通常和主 LLM 填成同一套

> `.env` 已被 `.gitignore` 忽略，填真实密钥不会被提交上传。

---

## 三、启动 Neo4j（Docker）

```bash
docker compose up -d neo4j
```

- Neo4j Browser: http://localhost:7475 （账号 `neo4j` / 密码 `mirofish`）
- Bolt 端口: `7688`（已在 `.env` 配好）

确认健康：`docker ps` 看到 `mirofish-neo4j` 状态为 `healthy` 即可。

---

## 四、安装依赖

```bash
npm run setup:all
```

或分步：

```bash
npm run setup          # 根目录 + 前端 Node 依赖
npm run setup:backend  # 后端 Python 依赖（uv，自动建 venv）
```

---

## 五、启动

```bash
npm run dev
```

- 前端: http://localhost:3100
- 后端: http://localhost:5101

---

## 六、使用流程

在前端依次完成：上传材料 → 生成本体/图谱 → 准备模拟（生成人设+配置）→ 开始模拟 → 生成报告 → **发送问卷到世界 / 采访 Agent**。

> ⚠️ 采访/问卷功能要求模拟处于运行或已完成状态（OASIS 环境存活）。修改本仓库代码后，**必须新建一轮模拟**才会生效——旧模拟的进程是改动前启动的，不会自动更新。

---

## 七、常见问题

**Q: 采访/问卷一直转圈或报「No successful interviews」？**
A: 多半是 LLM 接口被中转站拦了默认请求头。本仓库已给 CAMEL/OpenAI 客户端加 `User-Agent: curl/8.5.0` 修复。若换了新中转站仍被拦，确认它支持 function calling。

**Q: 报告是英文？**
A: 上游 fork 把整个项目英语化了。本仓库已把后端报告 prompt 改中文，但**前端 UI 仍是英文**（1000+ 条文案未翻）。

**Q: Neo4j 连不上 / 维度报错？**
A: 确认 `docker compose up -d neo4j` 已起、`NEO4J_URI` 端口为 7688。改了 `EMBEDDING_DIMENSION` 需清空旧图谱重建。

**Q: 端口冲突？**
A: 本分支用 3100/5101/7688/7475，专门避开原版 MiroFish 的 3000/5001/7687/7474。
