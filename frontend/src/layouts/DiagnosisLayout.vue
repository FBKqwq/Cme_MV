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

    <el-container class="content-container">
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
:global(html),
:global(body),
:global(#app) {
  width: 100%;
  height: 100%;
  margin: 0;
  overflow: hidden;
}

.app-container {
  width: 100%;
  height: 100vh;
  overflow: hidden;
}

.sidebar {
  height: 100vh;
  flex-shrink: 0;
  overflow-y: auto;
  background: #17365d;
}

.content-container {
  height: 100vh;
  min-width: 0;
  overflow: hidden;
}

.logo {
  height: 80px;
  padding: 18px 22px;
  box-sizing: border-box;
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
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 28px;
  box-sizing: border-box;
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
  flex: 1;
  min-height: 0;
  min-width: 0;
  padding: 24px;
  box-sizing: border-box;
  overflow-x: hidden;
  overflow-y: auto;
  background: #f4f6f9;
}
</style>
