# KB RAG 检索优化 — 面试问答

> 基于 3200 SOP 操作手册知识库的 RAG 检索质量优化实录，10 题评估，6 轮迭代。

---

## 1. 精排后无质量门槛

### Q: 为什么 Cross-Encoder 精排后还需要加门槛？怎么做的？

**问题背景**

Cross-Encoder（bge-reranker-v2-m3）给每个候选切片的 query-document 相关性打分。但无论分数多低，结果都会原样传给 LLM。评估发现大量噪声切片的 rerank 分数在 0.0001-0.001 量级，LLM 基于这些低质内容生成回答导致幻觉。

**解决方案**

在 `config.py` 新增 `KB_RERANK_THRESHOLD=0.01`，精排后逐条过滤：低于阈值的切片直接丢弃。为防止口语化等场景下全部被过滤导致零结果，加了一层 fallback：全部低于阈值时保留 top-1。

**实现位置**

- [config.py](config.py#L88)：`KB_RERANK_THRESHOLD: float = 0.01`
- [kb_graph.py:492-500](api/agent/kb_graph.py#L492-L500)：阈值过滤 + `if not passed: passed = reranked[:1]` fallback

**效果**

10 题评估实测，阈值从 0.0 调整到 0.01 后：
- 最优阈值通过分析所有问题中 relevant vs irrelevant 的 rerank 分数边界确定
- Precision@5 从 0.36 翻倍到 0.69
- 过滤掉了 ~40% 的噪声结果（平均通过数从 5.0 降到 3.0）
- Recall 无损（所有相关结果 rerank > 0.01）

---

## 2. 混合检索 Dense + BM25

### Q: 为什么需要混合检索？关键词从哪里来？

**问题背景**

bge-m3 做纯语义检索（Dense），对中文语义匹配效果好，但对精确术语匹配有盲区：型号编号"3200"被当作普通数字，英文缩写"SLT/UPH/TLC"的 embedding 语义信号弱。用户搜"3200 的 Offset 设置"时，Dense 可能返回 3100 相关的内容（语义相似），而不是精确的 3200 Offset 页面。

**关键词来源**

BM25 的关键词直接从 Query 改写后的搜索词中提取，不需要额外的关键词提取步骤：
1. 用户提问 → LLM Query 改写（含术语表注入）→ 2-3 个搜索词
2. 每个搜索词同时走两条路径：embedding(Dense) 和 tsquery(BM25)
3. BM25 的 `plainto_tsquery('simple', query)` 自动按空格/标点分词

术语表的作用是让 Query 改写产出更准确的关键词（如用户说"选良率的地方"→ 术语表映射 → 改写为"Yield Control"），从而间接提升 BM25 命中率。BM25 本身不直接查术语表。

**混合检索方案**

PG 内置 `tsvector`/`tsquery` 全文检索作为 BM25 实现：
- `fts` 列（英文）：`GENERATED ALWAYS AS (to_tsvector('simple', content))`，自动从 content 生成，按非字母数字字符分词，匹配英文术语/型号/缩写
- `fts_zh` 列（中文）：jieba `cut_for_search` 分词 + opencc 简繁转换 → 手动写入 `to_tsvector('simple', ...)`

Dense 和 BM25 结果通过 **RRF（Reciprocal Rank Fusion）** 融合：
```
RRF_score(chunk) = Σ 1/(k + rank_i)  // k=60
```
不依赖原始分数量纲（余弦距离 vs ts_rank），仅用排名信息融合。融合后取 top-20 送 Cross-Encoder 精排。

**实现位置**

- [kb_store.py](api/rag/kb_store.py)：`fts`/`fts_zh` 双列 + `kb_search()`(Dense) + `kb_bm25_search()`(BM25)
- [kb_graph.py:242-276](api/agent/kb_graph.py#L242-L276)：`_rrf_fusion()` RRF 算法
- [kb_graph.py:304-310](api/agent/kb_graph.py#L304-L310)：混合检索主循环

**效果**

| 轮次 | BM25 方案 | 总命中 | 覆盖题数 |
|:----:|------|:-----:|:-------:|
| R1 | 无 | 0 | 0/10 |
| R2 | 英文 fts 列 (AND) | 4 | 2/10 |
| R4 | +bigram+opencc | 9 | 6/10 |
| R5 | +jieba 替换 bigram | 8 | 6/10 |

---

## 3. 检索质量度量与评估

### Q: 怎么评估检索和回答质量？

**检索质量（4 个 IR 指标）**

在 `kb_retrieval_logs` 表中埋点记录每次检索的全链路数据。评估时人工标注 ground truth（每个问题哪些切片是相关的），然后计算：

| 指标 | 计算方法 | 衡量什么 |
|------|---------|---------|
| **Recall@5** | 命中的相关切片数 / 总相关切片数 | 有没有漏掉？ |
| **Precision@5** | top-5 中相关切片数 / 5 | 找出来的有没有垃圾？ |
| **Hit Rate** | 10 题中至少命中 1 条相关的题目占比 | 能不能找到？ |
| **MRR** | 第一个相关切片倒数排名的均值 | 最佳答案排第几？ |

**回答质量（3 个维度）**

| 维度 | 评分 | 标准 |
|------|:---:|------|
| **准确性** | 1-5 | 是否严格基于原文，有无编造/曲解 |
| **完整性** | 1-5 | 是否覆盖检索结果中的全部关键信息 |
| **幻觉** | Pass/Fail | 是否出现检索结果中没有的信息 |

**评估工具**

`eval_rag.py`：自动化评估脚本，支持自定义问题集 JSON → 逐题执行全链路检索管线 + LLM 回答生成 → 保存结果 JSON。`GET /api/v1/knowledge/logs` API 提供在线查询 + 汇总统计。

**实现位置**

- [kb_store.py:148-268](api/rag/kb_store.py#L148-L268)：`kb_retrieval_logs` 表 + 写入/查询函数
- [kb_graph.py:554-582](api/agent/kb_graph.py#L554-L582)：`_schedule_retrieval_log()` fire-and-forget 异步写入
- [knowledge.py:152-172](api/knowledge.py#L152-L172)：`GET /knowledge/logs` API
- [eval_rag.py](eval_rag.py)：评估脚本

---

## 4. 术语表注入 Query 改写

### Q: 为什么要从文档提取术语表？怎么注入到 Query 改写？

**问题背景**

Query 改写 LLM 是零-shot 的，不知道文档具体用了什么术语。用户说"选良率的地方"，LLM 改写为"良率选择 设置"，但文档里写的是"Yield Control (良率控制設定)"。改写词与文档术语不一致导致检索精度下降。

**解决方案**

1. **术语提取**：LLM 一次性扫描 41 个切片，按 6 类提取 231 个中英技术名词（页面/功能/硬件/操作/模式/缩写），保存到 `api/rag/kb_terminology.json`
2. **Prompt 注入**：术语表格式化后注入 `QUERY_REWRITE_PROMPT`，作为改写时的参考
3. **实体映射规则**：在 Prompt 中明确要求页面/角色映射（"工程师→Engineer Page"，"作业员→User Page"），禁止自行推测

**实现位置**

- [extract_terminology.py](extract_terminology.py)：一次性术语提取脚本
- [api/rag/kb_terminology.json](api/rag/kb_terminology.json)：231 个术语，6 类
- [kb_graph.py:209-270](api/agent/kb_graph.py#L209-L270)：`_build_terminology_ref()` + Prompt 注入

**效果**

- Query 改写更精准："温度控制"→"Cobra 溫度控制設定"（而非之前的泛化词）
- Q4 "工程师页面"改写从错误的"Setup Page"修正为"Engineer Page"
- BM25 首次激活：术语表中的英文术语出现在改写 query 中，触发了关键词匹配

---

## 5. jieba 中文分词 BM25 + opencc 简繁转换

### Q: 纯 Dense + 术语表后还有 69% Precision 和 31% 噪声，怎么解决的？

**问题背景**

R2 的 Precision 达 0.69，但 BM25 贡献只有 4 次，仅 2 题。中文查询 BM25 几乎没激活——PG 的 `tsvector('simple')` 对中文不分词（因为没有空格），每个中文字符被当作一个独立 token，`plainto_tsquery` 的 AND 语义要求所有单字符都匹配，几乎不可能命中。

回答质量方面，噪声结果混入导致 LLM 偶尔产生主观推测。

**解决方案**

**jieba 替换 bigram**：`jieba.cut_for_search` 分词（召回优先模式，长词同时拆分子词）。例如"执行模式"→"执行/模式"而非 bigram 的"执行/行模/模式"（"行模"是假词）。

**opencc 简繁转换**：文档是繁体中文，用户用简体提问。分词前统一用 opencc t2s 转简体，消除"温度≠溫度"的不匹配。

**fts_zh 列**：jieba 分词后的 token 串写入 `to_tsvector('simple', ...)`，与英文 `fts` 列独立。检索时查询也经过同样的 jieba+opencc 处理。

此时 Precision 0.69，但仍有 31% 噪声。噪声的共性是"同页面不同章节"的弱关联切片，Dense+Reranker 无法区分。

**效果**

- BM25 总命中：4 → 9（R4），覆盖 6/10 题
- 幻觉从 2 次降为 0 次（R5 jieba 轮次）
- 仍有噪声混入（如同属 Setup Page 的 Parament 切片被误判为与 Offset Setting 相关）

---

## 6. LLM 相关性二次过滤

### Q: Reranker 为什么无法解决剩余 31% 噪声？LLM 过滤怎么做？

**问题背景**

Reranker（Cross-Encoder）打分的依据是 query-document 语义相似度，但它不理解"这个切片能不能回答用户的问题"。所以 `Lot Done（清除总计）` 跟 `Run Page 执行模式` 语义相似（都属 Run Page 章节），Reranker 给 0.68 高分，但它实际上不能回答用户问的"运行模式有哪些"。

这是 Dense+Reranker 组合的精度天花板——语义相似 ≠ 能回答问题。

**解决方案**

在精排和阈值过滤之后、回答生成之前，插入一次轻量 LLM 调用做逐条判定：

```
passed(2-5条) + 用户问题 → LLM 逐条判 [1, 0, 1, 0, 0] → 仅保留标记为 1 的
```

**设计要点**：
- 每条切片取前 1200 字 + 章节标题送入判定 LLM
- 判定标准：包含能直接回答问题的具体操作步骤/参数值/功能说明 → 1
- **同章节多子切片规则**：一个章节被拆成多段时，每段包含不同参数/步骤，都应标记为 1（修复切片拆分后的误判）
- **两层 fallback**：全部被判 0 时保留 Reranker top-1
- 单条结果时跳过（无需判断）

**实现位置**

- [kb_graph.py:74-165](api/agent/kb_graph.py#L74-L165)：`RELEVANCE_FILTER_LLM` + `RELEVANCE_FILTER_PROMPT` + `_llm_relevance_filter()`
- [kb_graph.py:527-529](api/agent/kb_graph.py#L527-L529)：在 `kb_execute_tools` 中插入调用

**效果**

```
R5: Precision 0.69, 噪声 31%
R6: Precision 1.00, 噪声 0%
```

- 10 题全部零噪声、零幻觉
- 额外成本：每题 +1 次 LLM 调用（~2 秒）
- fallback 机制确保即使 LLM 判错也不会丢答案

---

## 7. 口语化提问鲁棒性

### Q: 口语化提问为什么 BM25 崩溃、出现幻觉？怎么修的？

**问题背景**

用 10 道口语化问题（"这机器有几种运行模式啊？""定时器那一堆参数都是啥意思？"）测试时发现：
- **Q5 零结果**："定时器那一堆参数都是啥意思"→ Reranker 全判低于阈值，用户得不到回答
- **Q4 改写错误**："工程师页面"被改写为"Setup Page"而非"Engineer Page"
- **BM25 崩溃**：从 10 降到 3（口语中去技术化的表达导致 tsquery AND 全部失败）
- **回答出现推测**：噪声混入导致 LLM 添加"可能为文件版本差异"等主观分析

**解决方案（4 个修复叠加）**

**修复 1 — 阈值 fallback**：全部被阈值过滤时保留 Reranker top-1，解决 Q5 零结果。

**修复 2 — BM25 OR 语义**：中文 `fts_zh` 列从 `plainto_tsquery`(AND) 改为 `to_tsquery`(OR)。口语化改写词 token 多（如"定时器 那一堆 参数 都是 啥意思"），AND 要求全部命中几乎不可能。OR 取任意 token 命中即可。用 `top_k/3 ≈ 3` 限制每路召回数，避免过度泛滥。

**修复 3 — Prompt 实体映射**：在 `QUERY_REWRITE_PROMPT` 中加硬规则——"工程师→Engineer Page""作业员→User Page"，禁止 LLM 自行推测。

**修复 4 — LLM 过滤 Prompt 优化**：新增同章节多子切片规则——"一个章节被拆成多段，每段包含不同参数或步骤，都应标记为 1"，解决切片拆分后 Q1 Offset Setting 全被误判为不相关的问题。

**实现位置**

- [kb_graph.py:508-514](api/agent/kb_graph.py#L508-L514)：阈值 fallback
- [kb_store.py:175-196](api/rag/kb_store.py#L175-L196)：`kb_bm25_search()` OR 语义 + `max(3, top_k//3)` 限制
- [kb_graph.py:225-228](api/agent/kb_graph.py#L225-L228)：实体映射规则
- [kb_graph.py:87-89](api/agent/kb_graph.py#L87-L89)：LLM 过滤 Prompt 同章节规则

**效果**

| 指标 | 修复前(v1) | 修复后(v4) |
|------|:--------:|:--------:|
| 零结果题 | 1 (Q5) | 0 |
| BM25 总命中 | 3 | 77 |
| Q4 改写 | Setup Page(错) | Engineer Page(对) |
| Q1 LLM过滤 | 5→0(全拒) | 5→5(全保留) |
| 回答准确性 | 4.5/5 | 4.9/5 |

---

## 补充：切片策略优化（P0）

### Q: 全文切片导致的安全问题 fallback 是怎么解决的？

**问题**

chunk #0 "全文" 是 2168 字的超大切片，混合了封面、保修声明、RoHS 表格、安全概要、版本记录、目录等内容。安全信息在 1500+ 字处。LLM 相关性过滤只读前 1200 字，看不到安全部分 → 判为不相关 → 全靠 fallback 兜底。

**解决方案**

修改 `kb_chunker.py` 的 `split_manual()`：
1. `MAX_CHUNK_SIZE` 从 4000 降到 800
2. 新增 `_split_oversized()` 函数：超长切片按 `\n\n` 段落边界二次拆分，目标 400-800 字/切片
3. 尾部短文本（<40 字）合并到前一个切片

**效果**

```
41 → 51 切片 | Max: 3433→855 | 平均: 547→408 | >1000字: 4→0
全文: 1×2168 → 4 段（安全概要独立为 794 字切片）
Q3 安全问题：fallback → 正常通过（LLM 过滤正确识别）
```

**实现位置**

- [kb_chunker.py:49-73](api/rag/kb_chunker.py#L49-L73)：`_split_oversized()` + `MAX_CHUNK_SIZE=800`

---

## 全链路迭代总览

```
R1: 纯 Dense + 阈值 0.0
    Precision 0.36  BM25 0  幻觉 2  噪声 50 条

R2: + 精排阈值 0.01 + 术语表注入
    Precision 0.69  BM25 4  幻觉 1  噪声 31 条

R3-R5: + bigram → jieba + opencc 中文 BM25
    Precision 0.65  BM25 8  幻觉 0  噪声 31 条

R6: + LLM 相关性二次过滤
    Precision 1.00  噪声 0  零幻觉  ← 正式提问达标

R7: + BM25 OR 语义 + Prompt 修复 + 阈值 fallback
    口语化 BM25 3→77  零结果 1→0  ← 口语化达标

P0: + 超长切片拆分
    Q3 安全 fallback 消除  51 切片平均 408 字
```

### 当前管线架构

```
用户提问
  │
  ├─ Query 改写 (LLM + 术语表(231词) + 实体映射规则)
  │
  ├─ Dense 检索 (bge-m3, 1024维, cosine <=> 0.55)
  │     └─ BM25 英文 (fts 列, plainto_tsquery, AND)
  │     └─ BM25 中文 (fts_zh 列, jieba+opencc, to_tsquery OR, top_k/3)
  │
  ├─ RRF 融合 (k=60, 多 query 去重)
  │
  ├─ Cross-Encoder 精排 (bge-reranker-v2-m3, top-20→top-5)
  │
  ├─ 精排阈值过滤 (0.01, fallback top-1)
  │
  ├─ LLM 相关性二次过滤 (逐条判 1/0, fallback top-1)
  │
  └─ LLM 生成回答 (System Prompt + 检索上下文)
```

### 关键性能指标（最终状态）

| 指标 | 正式提问 | 口语化提问 |
|------|:------:|:--------:|
| Precision | 1.00 | 1.00 |
| Recall | 1.00 | 1.00 |
| Hit Rate | 100% | 100% |
| MRR | 1.00 | 1.00 |
| 幻觉 | 0/10 | 0/10 |
| BM25 命中 | 10 | 77 |
| 额外延迟/题 | ~2s (LLM 过滤) | ~2s |
