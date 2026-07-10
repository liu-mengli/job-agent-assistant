<script setup lang="ts">
import type { StructuredContent } from '../types/structured'

const props = defineProps<{ data: StructuredContent }>()

function matchIcon(level: string): string {
  if (level === 'match') return '✅'
  if (level === 'partial') return '⚠️'
  return '❌'
}

function matchLabel(level: string): string {
  if (level === 'match') return '匹配'
  if (level === 'partial') return '部分'
  return '缺失'
}

function matchScoreColor(score: number): string {
  if (score >= 70) return '#16a34a'
  if (score >= 40) return '#f59e0b'
  return '#ef4444'
}
</script>

<template>
  <div class="structured-msg">
    <!-- ====== browse / full_recommendation: 岗位表格 ====== -->
    <template v-if="data.response_type === 'browse' || data.response_type === 'full_recommendation'">
      <div v-if="data.summary" class="s-summary">{{ data.summary }}</div>

      <table v-if="data.jobs?.length" class="s-table job-table">
        <thead>
          <tr>
            <th class="col-rank">#</th>
            <th class="col-title">岗位</th>
            <th class="col-company">公司</th>
            <th class="col-salary">薪资</th>
            <th v-if="data.response_type === 'full_recommendation'" class="col-match">匹配度</th>
            <th class="col-reason">推荐理由</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="job in data.jobs" :key="job.rank">
            <td class="col-rank">{{ job.rank }}</td>
            <td class="col-title">{{ job.title }}</td>
            <td class="col-company">{{ job.company }}</td>
            <td class="col-salary">{{ job.salary }}</td>
            <td v-if="data.response_type === 'full_recommendation'" class="col-match">
              <span v-if="job.match_score != null" class="match-badge" :style="{ background: matchScoreColor(job.match_score) }">
                {{ job.match_score }}%
              </span>
              <span v-else class="match-na">—</span>
            </td>
            <td class="col-reason">{{ job.reason }}</td>
          </tr>
        </tbody>
      </table>

      <div v-if="data.assessment" class="s-assessment">{{ data.assessment }}</div>
      <div v-if="data.next_steps" class="s-next-steps">{{ data.next_steps }}</div>
    </template>

    <!-- ====== match_analysis: 匹配度分析 ====== -->
    <template v-else-if="data.response_type === 'match_analysis'">
      <div v-if="data.overall_match != null" class="match-score-hero">
        <div class="match-score-ring" :style="{ borderColor: matchScoreColor(data.overall_match) }">
          <span class="match-score-num" :style="{ color: matchScoreColor(data.overall_match) }">{{ data.overall_match }}%</span>
          <span class="match-score-label">综合匹配度</span>
        </div>
      </div>

      <div v-if="data.match_summary" class="s-summary">{{ data.match_summary }}</div>

      <table v-if="data.skill_comparisons?.length" class="s-table skill-table">
        <thead>
          <tr>
            <th>岗位要求</th>
            <th class="col-matchlevel">匹配度</th>
            <th>你的情况</th>
            <th>说明</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(sk, i) in data.skill_comparisons" :key="i" :class="'row-' + sk.match_level">
            <td>{{ sk.requirement }}</td>
            <td class="col-matchlevel">
              <span class="match-tag" :class="'tag-' + sk.match_level">
                {{ matchIcon(sk.match_level) }} {{ matchLabel(sk.match_level) }}
              </span>
            </td>
            <td>{{ sk.your_status }}</td>
            <td class="col-note">{{ sk.note }}</td>
          </tr>
        </tbody>
      </table>

      <div v-if="data.strengths?.length" class="s-section">
        <div class="s-section-title">✅ 优势亮点</div>
        <ul class="s-list">
          <li v-for="(s, i) in data.strengths" :key="i">{{ s }}</li>
        </ul>
      </div>

      <div v-if="data.weaknesses?.length" class="s-section">
        <div class="s-section-title">⚠️ 需加强的短板</div>
        <ul class="s-list weaknesses">
          <li v-for="(w, i) in data.weaknesses" :key="i">{{ w }}</li>
        </ul>
      </div>

      <div v-if="data.application_advice" class="s-advice">
        <div class="s-section-title">💡 投递建议</div>
        <p>{{ data.application_advice }}</p>
      </div>
    </template>

    <!-- ====== 其余类型：回退到纯文本（不渲染） ====== -->
  </div>
</template>

<style scoped>
.structured-msg {
  margin-bottom: 8px;
}

/* 表格 */
.s-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
  margin: 10px 0;
  border-radius: 8px;
  overflow: hidden;
}

.s-table th {
  background: #f5f5f7;
  color: #86868b;
  font-weight: 500;
  text-align: left;
  padding: 8px 10px;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.s-table td {
  padding: 10px 10px;
  border-bottom: 1px solid #f0f0f0;
  color: #1d1d1f;
  vertical-align: middle;
}

.s-table tr:last-child td {
  border-bottom: none;
}

.col-rank { width: 32px; color: #86868b; text-align: center; }
.col-match { width: 56px; text-align: center; }
.col-matchlevel { width: 64px; text-align: center; }
.col-salary { color: #2563eb; font-weight: 500; white-space: nowrap; }
.col-company { color: #86868b; }
.col-reason { color: #6b7280; font-size: 12px; }
.col-note { color: #6b7280; font-size: 12px; }

/* 匹配度徽章 */
.match-badge {
  display: inline-block;
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 10px;
  min-width: 36px;
  text-align: center;
}

.match-na {
  color: #86868b;
}

/* 匹配度英雄区 */
.match-score-hero {
  display: flex;
  justify-content: center;
  margin: 8px 0 12px;
}

.match-score-ring {
  width: 90px;
  height: 90px;
  border: 4px solid;
  border-radius: 50%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
}

.match-score-num {
  font-size: 24px;
  font-weight: 700;
}

.match-score-label {
  font-size: 10px;
  color: #86868b;
}

/* 文本块 */
.s-summary {
  font-size: 13px;
  color: #1d1d1f;
  margin-bottom: 8px;
  line-height: 1.6;
}

.s-assessment {
  font-size: 13px;
  color: #1d1d1f;
  margin-top: 10px;
  padding: 10px 12px;
  background: #f9fafb;
  border-radius: 8px;
  line-height: 1.6;
}

.s-next-steps {
  font-size: 13px;
  color: #2563eb;
  margin-top: 8px;
  padding: 8px 12px;
  background: #eff6ff;
  border-radius: 8px;
  line-height: 1.5;
}

.s-section {
  margin-top: 10px;
}

.s-section-title {
  font-size: 12px;
  font-weight: 600;
  color: #1d1d1f;
  margin-bottom: 4px;
}

.s-list {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  color: #374151;
  line-height: 1.7;
}

.s-list.weaknesses li {
  color: #9a3412;
}

.s-advice {
  margin-top: 10px;
  padding: 10px 12px;
  background: #eff6ff;
  border-radius: 8px;
  font-size: 13px;
  color: #1d1d1f;
  line-height: 1.6;
}

.s-advice .s-section-title {
  margin-bottom: 4px;
}

/* 技能标签 */
.match-tag {
  font-size: 11px;
  white-space: nowrap;
}

.tag-match { color: #16a34a; }
.tag-partial { color: #d97706; }
.tag-missing { color: #ef4444; }

/* 行高亮 */
.row-partial td { background: #fffbeb; }
.row-missing td { background: #fef2f2; }
</style>
