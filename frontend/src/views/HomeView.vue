<script setup lang="ts">
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  DocumentAdd,
  Files,
} from '@element-plus/icons-vue'

const router = useRouter()
const formatModelVersion = (): string => 'v1.0.0'

const handleCreateCase = (): void => {
  router.push('/cases/new')
}

const handleUpload = (): void => {
  ElMessage.info('Excel 上传功能将在下一阶段实现')
}
</script>

<template>
  <div class="home-page">
    <el-alert
        title="本系统预测结果仅用于临床辅助判断，不能替代医生最终诊断。"
        type="warning"
        :closable="false"
        show-icon
        class="warning-alert"
    />

    <div class="welcome-section">
      <div>
        <h2>欢迎使用病因预测系统</h2>
        <p>
          录入患者病例信息，获得其他、炎症、感染、肿瘤四分类预测结果。
        </p>
      </div>

      <div class="welcome-actions">
        <el-button
            type="primary"
            size="large"
            @click="handleCreateCase"
        >
          <el-icon>
            <DocumentAdd />
          </el-icon>
          新建病例
        </el-button>

        <el-button
            size="large"
            @click="handleUpload"
        >
          <el-icon>
            <Files />
          </el-icon>
          上传 Excel
        </el-button>
      </div>
    </div>

    <el-row :gutter="20" class="statistics-row">
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="hover" class="statistic-card">
          <el-statistic title="累计病例" :value="889" />
          <div class="statistic-note">原始训练病例</div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="hover" class="statistic-card">
          <el-statistic title="待医生标注" :value="0" />
          <div class="statistic-note">等待确认真实结果</div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="hover" class="statistic-card">
          <el-statistic
              title="当前模型版本"
              :value="1"
              :formatter="formatModelVersion"
          />
          <div class="statistic-note">随机森林四分类模型</div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="hover" class="statistic-card">
          <el-statistic
              title="模型 Macro-F1"
              :value="42.8"
              suffix="%"
              :precision="1"
          />
          <div class="statistic-note">当前测试集表现</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="process-card">
      <template #header>
        <div class="card-title">病例预测流程</div>
      </template>

      <el-steps :active="0" align-center>
        <el-step
            title="病例录入"
            description="填写或上传患者病例信息"
        />
        <el-step
            title="数据校验"
            description="检查缺失值和异常字段"
        />
        <el-step
            title="模型预测"
            description="输出四分类预测概率"
        />
        <el-step
            title="医生标注"
            description="医生确认患者真实诊断"
        />
        <el-step
            title="模型优化"
            description="已确认病例进入训练数据池"
        />
      </el-steps>
    </el-card>

    <el-card shadow="never" class="diagnosis-card">
      <template #header>
        <div class="card-title">预测类别</div>
      </template>

      <div class="diagnosis-list">
        <div class="diagnosis-item">
          <el-tag type="info" size="large">其他</el-tag>
          <span>不属于炎症、感染或肿瘤的其他诊断情况</span>
        </div>

        <div class="diagnosis-item">
          <el-tag type="warning" size="large">炎症</el-tag>
          <span>以炎症相关表现为主要特征的病例</span>
        </div>

        <div class="diagnosis-item">
          <el-tag type="danger" size="large">感染</el-tag>
          <span>由细菌、病毒或其他病原体引起的感染病例</span>
        </div>

        <div class="diagnosis-item">
          <el-tag effect="dark" size="large">肿瘤</el-tag>
          <span>与良性或恶性肿瘤相关的病例</span>
        </div>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.warning-alert {
  margin-bottom: 20px;
}

.welcome-section {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 26px 30px;
  background: linear-gradient(120deg, #ffffff, #ecf5ff);
  border: 1px solid #d9ecff;
  border-radius: 10px;
}

.welcome-section h2 {
  margin: 0;
  font-size: 24px;
}

.welcome-section p {
  margin: 10px 0 0;
  color: #606266;
}

.welcome-actions {
  display: flex;
  gap: 10px;
}

.statistics-row {
  margin-top: 20px;
}

.statistic-card {
  margin-bottom: 20px;
  border-radius: 9px;
}

.statistic-note {
  margin-top: 10px;
  font-size: 12px;
  color: #909399;
}

.process-card,
.diagnosis-card {
  margin-top: 20px;
  border-radius: 9px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.diagnosis-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.diagnosis-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 15px;
  color: #606266;
  background: #f8fafc;
  border-radius: 7px;
}

.diagnosis-item .el-tag {
  width: 64px;
  flex-shrink: 0;
  justify-content: center;
}

@media (max-width: 900px) {
  .welcome-section {
    align-items: flex-start;
    flex-direction: column;
    gap: 20px;
  }

  .diagnosis-list {
    grid-template-columns: 1fr;
  }
}
</style>
