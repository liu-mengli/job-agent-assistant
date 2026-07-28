<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchResumes, downloadResume, type ResumeItem } from '../api/resumes'

const resumeImages = [
  { src: '/resume/resume1.png', alt: '简历图片 1' },
  { src: '/resume/resume2.png', alt: '简历图片 2' },
  { src: '/resume/resume3.png', alt: '简历图片 3' },
]

const previewSrcList = resumeImages.map((img) => img.src)

const readyResume = ref<ResumeItem | null>(null)
const downloading = ref(false)

onMounted(async () => {
  try {
    const data = await fetchResumes()
    readyResume.value =
      data.resumes.find((r) => r.status === 'ready') ?? null
  } catch {
    // 获取简历列表失败时不阻塞图片展示
  }
})

async function handleDownload() {
  if (!readyResume.value) return
  downloading.value = true
  try {
    await downloadResume(readyResume.value.id, readyResume.value.filename)
    ElMessage.success('简历下载成功')
  } catch {
    ElMessage.error('下载失败，请重试')
  } finally {
    downloading.value = false
  }
}
</script>

<template>
  <div class="resume-viewer">
    <div class="resume-header">
      <h2 class="page-title">我的简历</h2>
      <el-button
        type="primary"
        :disabled="!readyResume"
        :loading="downloading"
        @click="handleDownload"
      >
        {{ readyResume ? `下载 PDF（${readyResume.filename}）` : '暂无可下载的简历' }}
      </el-button>
    </div>
    <p v-if="!readyResume" class="download-hint">请先在「求职助手」页面上传简历 PDF 文件</p>

    <div class="image-grid">
      <div v-for="(img, idx) in resumeImages" :key="idx" class="image-card">
        <el-image
          :src="img.src"
          :alt="img.alt"
          :preview-src-list="previewSrcList"
          :initial-index="idx"
          fit="contain"
          class="resume-image"
        >
          <template #error>
            <div class="image-placeholder">
              <span class="placeholder-icon">📄</span>
              <span>{{ img.alt }}</span>
              <span class="placeholder-hint">将图片放置于 public/resume/ 目录</span>
            </div>
          </template>
        </el-image>
      </div>
    </div>
  </div>
</template>

<style scoped>
.resume-viewer {
  max-width: 960px;
  margin: 0 auto;
}

.resume-viewer {
  padding: 24px;
}

.resume-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.page-title {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: #1d1d1f;
}

.download-hint {
  margin: 0 0 16px;
  font-size: 13px;
  color: #9ca3af;
}

.image-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}

.image-card {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.resume-image {
  width: 100%;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
  cursor: pointer;
}

.image-placeholder {
  width: 100%;
  aspect-ratio: 1 / 1.414;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #9ca3af;
  font-size: 14px;
}

.placeholder-icon {
  font-size: 40px;
}

.placeholder-hint {
  font-size: 12px;
  color: #d1d5db;
}
</style>
