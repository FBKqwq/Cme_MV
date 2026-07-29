<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const activeMenu = computed(() => route.path)
</script>

<template>
  <el-container class="app-container">
    <el-aside
        width="220px"
        class="sidebar"
    >
      <div class="logo">
        <div class="logo-title">
          病因预测系统
        </div>

        <div class="logo-version">
          Clinical AI v1.0
        </div>
      </div>

      <el-menu
          router
          :default-active="activeMenu"
          background-color="#17365d"
          text-color="#dbeafe"
          active-text-color="#ffffff"
          class="sidebar-menu"
      >
        <el-menu-item index="/cases/new">
          病例录入
        </el-menu-item>

        <el-menu-item index="/excel-upload">
          Excel 上传
        </el-menu-item>

        <el-menu-item index="/model-management">
          模型管理
        </el-menu-item>

        <el-menu-item index="/knowledge-review">
          知识复验
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div>
          <div class="header-title">
            医院病人诊断辅助预测系统
          </div>

          <div class="header-description">
            病例管理、机器学习预测与医生标注
          </div>
        </div>

        <div class="doctor-info">
          当前医生
        </div>
      </el-header>

      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.app-container {
  min-height: 100vh;
}

.sidebar {
  min-height: 100vh;
  background: #17365d;
}

.logo {
  height: 80px;
  padding: 18px 22px;
  color: #ffffff;
  border-bottom: 1px solid rgb(255 255 255 / 12%);
}

.logo-title {
  font-size: 18px;
  font-weight: 600;
}

.logo-version {
  margin-top: 5px;
  font-size: 12px;
  color: #a8c7e8;
}

.sidebar-menu {
  border-right: none;
}

.sidebar-menu .el-menu-item {
  margin: 6px 10px;
  border-radius: 6px;
}

.sidebar-menu .el-menu-item.is-active {
  background: #337ecc;
}

.header {
  height: 80px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 28px;
  background: #ffffff;
  border-bottom: 1px solid #e4e7ed;
}

.header-title {
  font-size: 21px;
  font-weight: 600;
}

.header-description {
  margin-top: 6px;
  font-size: 13px;
  color: #909399;
}

.doctor-info {
  font-size: 14px;
  font-weight: 600;
}

.main-content {
  padding: 24px;
  background: #f4f6f9;
}
</style>
