<script setup lang="ts">
const resumeImages = [
  { src: '/static/resume/resume1.png', alt: '简历图片 1' },
  { src: '/static/resume/resume2.png', alt: '简历图片 2' },
  { src: '/static/resume/resume3.png', alt: '简历图片 3' },
]

const pdfUrl = '/api/v1/resume/pdf'
const previewSrcList = resumeImages.map((img) => img.src)
</script>

<template>
  <div class="resume-viewer">
    <div class="resume-header">
      <h2 class="page-title">我的简历</h2>
      <a :href="pdfUrl" download class="download-btn">
        下载 PDF
      </a>
    </div>

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
              <span class="placeholder-hint">
                将 {{ img.src.split('/').pop() }} 放置于 uploads/resume/ 目录<br />
                Docker: /app/uploads/resume/
              </span>
            </div>
          </template>
        </el-image>
      </div>
    </div>
  </div>
</template>

<style scoped>
.resume-viewer {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 24px 32px;
}

.resume-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  flex-shrink: 0;
}

.page-title {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: #1d1d1f;
}

.download-btn {
  padding: 8px 20px;
  border-radius: 8px;
  background: #2563eb;
  color: #fff;
  font-size: 14px;
  font-weight: 500;
  text-decoration: none;
  transition: background 0.15s;
}

.download-btn:hover {
  background: #1d4ed8;
}

.image-grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
  min-height: 0;
}

.image-card {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.resume-image {
  width: 100%;
  height: 100%;
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
  cursor: pointer;
}

.resume-image :deep(img) {
  object-fit: contain;
}

.image-placeholder {
  width: 100%;
  height: 100%;
  min-height: 400px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: #9ca3af;
  font-size: 14px;
}

.placeholder-icon {
  font-size: 48px;
}

.placeholder-hint {
  font-size: 12px;
  color: #d1d5db;
  text-align: center;
  line-height: 1.6;
}
</style>
