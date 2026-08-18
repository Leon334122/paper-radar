# 文献雷达 · 个人文献更新网站

每天自动抓取 CNS、Nature/Science 系子刊与药剂学/纳米医学顶刊新发表的论文（当前 27 本期刊），按 8 个研究方向（药物递送系统、自组装多肽、纳米药物、肿瘤治疗、细胞搭便车、肺部靶向、细胞疗法、基因治疗）筛选相关文章，用 DeepSeek 生成中文总结（概述 / 创新点 / 意义），并发布为静态网页。

## 功能

- 每日 06:00（北京时间）自动更新，无需人工干预
- 期刊清单 27 本，分为 S / A / B / C 四个层级，可在 `config/journals.json` 随时增删
- 相关性筛选规则与关键词在 `config/keywords.yaml` 中配置
- 网站支持：方向/期刊层级/日期筛选、关键词搜索、收藏（浏览器本地）、单篇与列表导出 RIS / BibTeX、DOI / PubMed 外链
- 数据滚动保留 90 天，以 DOI 去重

## 目录结构

```
config/                期刊清单与关键词配置
pipeline/              抓取、筛选、总结、建站 Python 模块
site/                  静态网站（HTML/CSS/JS，数据自动生成）
data/papers.json       全部论文存储（含未入选的抓取结果，供调阈值）
.github/workflows/     GitHub Actions 每日自动更新工作流
tests/                 单元测试
```

## 本地运行

需要 Python 3.10+：

```bash
pip install -r requirements.txt

# 只抓取统计，不落盘（联调用）
python -m pipeline run --days 7 --dry-run --skip-summary

# 完整运行（抓取→筛选→DeepSeek 总结→生成网站）
python -m pipeline run --days 7

# 仅根据已有数据重建网站
python -m pipeline build

# 调整 config/keywords.yaml 后，无需重抓，只重新评分与建站
python -m pipeline rescore
```

本地运行前把 `.env.example` 复制为 `.env`，填入 `DEEPSEEK_API_KEY`（不填也能运行，总结会标记为“待补充”）。生成后直接双击打开 `site/index.html` 或在 `site/` 目录起一个静态服务器（如 `python -m http.server 8000`）预览。

## 配置说明

### config/journals.json

每本期刊一条记录：`name` 期刊名、`issn`（OpenAlex/Crossref 过滤用 ISSN-L）、`tier` 层级、`enabled` 是否启用、`rss` 期刊 RSS 地址（可为空数组，Elsevier/ACS/Wiley 期刊由 OpenAlex 覆盖）。

### config/keywords.yaml

`min_score` 入选阈值（默认 2：标题命中 1 个关键词，或摘要同方向命中 ≥2 个关键词即入选）。`directions` 下每个方向一组关键词，可自行增删调优。

### 环境变量 / GitHub Secrets

| 变量 | 必填 | 说明 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | 部署后必填 | DeepSeek 开放平台创建的 API Key |
| `DEEPSEEK_BASE_URL` | 否 | 默认 `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | 否 | 默认 `deepseek-v4-flash`，可换 `deepseek-v4-pro` |
| `OPENALEX_MAILTO` | 建议 | 你的邮箱，OpenAlex 礼貌池配额用 |

## 部署到 GitHub（一次配置，之后全自动）

详细图文指引见 [docs/上手指引.md](docs/上手指引.md)。要点：

1. 注册 GitHub 账号（免费），创建一个**私有仓库**（如 `paper-radar`）。
2. 把本项目推送到该仓库（需要 Personal Access Token，指引中有说明）。
3. 在仓库 Settings → Secrets and variables → Actions 中添加 `DEEPSEEK_API_KEY`（DeepSeek 平台申请）。
4. 在仓库 Settings → Pages 中把 Source 设为 **GitHub Actions**。
5. 手动触发一次 Actions 工作流（Actions → 每日更新文献雷达 → Run workflow）验证，之后每天自动运行。

## 成本估算

- DeepSeek（`deepseek-v4-flash`）：每天入选约 30–50 篇，每篇约 0.5–1K 输入 + 0.2K 输出 token，按 2026-08 官方价格估算约 ¥0.03–0.15/天（以官方最新报价为准）。
- GitHub Actions：每月 2000 分钟免费额度，本工作流每天约 3–5 分钟，远在免费范围内。

## 常见问题

- **总结一直显示“待补充”**：未配置 `DEEPSEEK_API_KEY`，或当次调用失败；配置密钥后重跑 `python -m pipeline run` 会重试。
- **某期刊一直没有文章**：检查 `journals.json` 中 `enabled` 与 `issn`；或该刊近期确实没有符合日期范围的论文。
- **相关文章太多/太少**：调整 `keywords.yaml` 中关键词或 `min_score`。
- **收藏丢失**：收藏保存在浏览器 localStorage，清缓存或换浏览器会丢失（属预期行为）。
