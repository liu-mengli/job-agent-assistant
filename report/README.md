# KB RAG 评估报告

## 目录结构

| 文件夹 | 轮次 | 改动内容 | 关键指标 |
|--------|:---:|------|------|
| `r6_final/` | R6 | 术语表注入 + 阈值0.01 + jieba BM25 + opencc简繁 + LLM相关性二次过滤 | Precision 1.00, Recall 1.00, 零幻觉 |
| `r7_colloquial/` | R7 | R6管线 + 口语化提问测试(10题) | 发现Q5完全失败, BM25下降30% |
| `r1_baseline/` | R1 | 基线(纯Dense, 阈值0.0) | — (原始结果未保留) |
| `r2_threshold_terminology/` | R2 | +阈值0.01 + 术语表注入 | — (原始结果未保留) |

## R6 最终方案

全链路:
```
用户提问 → opencc简繁转换 → jieba分词(BM25中文) + bge-m3(Dense)
         → RRF融合 → Cross-Encoder精排 → 阈值0.01过滤
         → LLM相关性二次过滤 → LLM生成回答
```

## R7 口语化测试发现

口语化提问的鲁棒性问题:
- Q5 "定时器那一堆参数都是啥意思" → passed=0(已修复:阈值fallback)
- Q0 丢失关键术语"Run Page"上下文
- BM25命中从10降到7
