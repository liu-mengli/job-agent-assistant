<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { ElMessage } from 'element-plus'

const router = useRouter()
const authStore = useAuthStore()

const formRef = ref()
const loading = ref(false)

const form = reactive({
  username: '',
  password: '',
})

const rules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

function handleLogin() {
  formRef.value?.validate(async (valid: boolean) => {
    if (!valid) return
    loading.value = true
    const ok = await authStore.login(form.username, form.password)
    loading.value = false
    if (ok) {
      router.push('/')
    } else {
      ElMessage.error('账号或密码错误')
    }
  })
}
</script>

<template>
  <div class="login-wrapper">
    <div class="login-card">
      <div class="login-header">
        <div class="logo">&#9906;</div>
        <h2>AI 找工作助手</h2>
        <p>请登录您的账号</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @keyup.enter="handleLogin"
      >
        <el-form-item label="账号" prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入账号"
            size="large"
          />
        </el-form-item>

        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            show-password
            size="large"
          />
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          :loading="loading"
          class="login-btn"
          @click="handleLogin"
        >
          登 录
        </el-button>
      </el-form>
    </div>
  </div>
</template>

<style scoped>
.login-wrapper {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f5f5f7;
}

.login-card {
  width: 400px;
  padding: 48px 40px 36px;
  background: #fff;
  border-radius: 18px;
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
}

.login-header {
  text-align: center;
  margin-bottom: 36px;
}

.logo {
  font-size: 42px;
  color: #2563eb;
  margin-bottom: 12px;
}

.login-header h2 {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 600;
  color: #1d1d1f;
}

.login-header p {
  margin: 0;
  font-size: 14px;
  color: #86868b;
}

.login-btn {
  width: 100%;
  margin-top: 8px;
  border-radius: 10px;
  font-size: 15px;
}

:deep(.el-form-item__label) {
  font-weight: 500;
  color: #1d1d1f;
}

:deep(.el-input__wrapper) {
  border-radius: 10px;
  box-shadow: 0 0 0 1px #d2d2d7 inset;
}

:deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px #a1a1a6 inset;
}

:deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 2px #2563eb inset;
}
</style>
