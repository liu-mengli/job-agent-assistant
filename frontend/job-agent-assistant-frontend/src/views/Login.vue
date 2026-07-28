<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const formRef = ref()
const loading = ref(false)
const isRegister = ref(false)

const form = reactive({
  username: '',
  password: '',
  confirmPassword: '',
})

const rules = computed(() => {
  const base: any = {
    username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
    password: [
      { required: true, message: '请输入密码', trigger: 'blur' },
      { min: 6, message: '密码至少 6 位', trigger: 'blur' },
    ],
  }
  if (isRegister.value) {
    base.confirmPassword = [
      { required: true, message: '请再次输入密码', trigger: 'blur' },
      {
        validator: (_rule: any, value: string, callback: any) => {
          if (value !== form.password) {
            callback(new Error('两次输入的密码不一致'))
          } else {
            callback()
          }
        },
        trigger: 'blur',
      },
    ]
  }
  return base
})

function toggleMode() {
  isRegister.value = !isRegister.value
  form.username = ''
  form.password = ''
  form.confirmPassword = ''
  formRef.value?.resetFields()
}

async function handleSubmit() {
  formRef.value?.validate(async (valid: boolean) => {
    if (!valid) return
    loading.value = true

    if (isRegister.value) {
      const ok = await authStore.register(form.username, form.password)
      loading.value = false
      if (ok) {
        ElMessage.success('注册成功')
        const redirect = route.query.redirect as string
        router.push(redirect || '/')
      } else {
        ElMessage.error('注册失败，该账号可能已被注册')
      }
    } else {
      const ok = await authStore.login(form.username, form.password)
      loading.value = false
      if (ok) {
        const redirect = route.query.redirect as string
        router.push(redirect || '/')
      } else {
        ElMessage.error('账号或密码错误')
      }
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
        <p>{{ isRegister ? '创建一个新账号' : '请登录您的账号' }}</p>
      </div>

      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-position="top"
        @keyup.enter="handleSubmit"
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

        <el-form-item v-if="isRegister" label="确认密码" prop="confirmPassword">
          <el-input
            v-model="form.confirmPassword"
            type="password"
            placeholder="请再次输入密码"
            show-password
            size="large"
          />
        </el-form-item>

        <el-button
          type="primary"
          size="large"
          :loading="loading"
          class="login-btn"
          @click="handleSubmit"
        >
          {{ isRegister ? '注 册' : '登 录' }}
        </el-button>
      </el-form>

      <div class="toggle-row">
        <span>{{ isRegister ? '已有账号？' : '没有账号？' }}</span>
        <a class="toggle-link" @click="toggleMode">
          {{ isRegister ? '立即登录' : '立即注册' }}
        </a>
      </div>
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

.toggle-row {
  text-align: center;
  margin-top: 20px;
  font-size: 13px;
  color: #86868b;
}

.toggle-link {
  color: #2563eb;
  cursor: pointer;
  margin-left: 4px;
  font-weight: 500;
}

.toggle-link:hover {
  text-decoration: underline;
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
