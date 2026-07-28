<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchUsers, deleteUser, type AdminUser } from '../api/admin'

const users = ref<AdminUser[]>([])
const loading = ref(false)

async function loadUsers() {
  loading.value = true
  try {
    const data = await fetchUsers()
    users.value = data.users
  } catch {
    ElMessage.error('获取用户列表失败')
  } finally {
    loading.value = false
  }
}

async function handleDelete(user: AdminUser) {
  try {
    await ElMessageBox.confirm(
      `确定要删除用户「${user.username}」吗？该操作将同时清除该用户的所有对话记录和上传文件，不可恢复。`,
      '删除确认',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }

  try {
    await deleteUser(user.id)
    ElMessage.success(`已删除用户「${user.username}」`)
    await loadUsers()
  } catch {
    ElMessage.error('删除失败')
  }
}

onMounted(loadUsers)
</script>

<template>
  <div class="user-management">
    <div class="page-header">
      <h2>人员管理</h2>
      <span class="user-count">共 {{ users.length }} 个普通用户</span>
    </div>

    <el-table :data="users" v-loading="loading" stripe style="width: 100%">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="username" label="账号" min-width="150" />
      <el-table-column prop="password" label="密码" min-width="200">
        <template #default="{ row }">
          <code class="password-cell">{{ row.password }}</code>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120" fixed="right">
        <template #default="{ row }">
          <el-button type="danger" size="small" @click="handleDelete(row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && users.length === 0" description="暂无普通用户" />
  </div>
</template>

<style scoped>
.user-management {
  max-width: 960px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  align-items: baseline;
  gap: 16px;
  margin-bottom: 24px;
}

.page-header h2 {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: #1d1d1f;
}

.user-count {
  font-size: 13px;
  color: #86868b;
}

.password-cell {
  font-size: 13px;
  background: #f5f5f7;
  padding: 2px 8px;
  border-radius: 4px;
  font-family: 'SF Mono', 'Menlo', monospace;
}
</style>
