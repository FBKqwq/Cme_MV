<script setup lang="ts">
import {
  computed,
  onMounted,
  ref,
} from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import type { DiagnosisLabel } from '../api/diagnosis'
import { useDiagnosisStore } from '../stores/diagnosis'

type TagType =
    | 'primary'
    | 'success'
    | 'warning'
    | 'danger'
    | 'info'

const router = useRouter()
const diagnosisStore = useDiagnosisStore()

// 浏览器刷新页面后，从 localStorage 恢复当前预测结果。
diagnosisStore.restore()

const doctorName = ref('')
const doctorLabel = ref<DiagnosisLabel | ''>('')
const doctorRemark = ref('')

const annotationSubmitted = computed(
    () => diagnosisStore.currentAnnotation !== null,
)

const result = computed(
    () => diagnosisStore.currentResult,
)

const currentCase = computed(
    () => result.value?.case ?? null,
)

const prediction = computed(
    () => result.value?.prediction ?? null,
)

const probabilityItems = computed<
    Array<[DiagnosisLabel, number]>
>(() => {
  if (!prediction.value) {
    return []
  }

  const preferredOrder: DiagnosisLabel[] = [
    '其他',
    '炎症',
    '感染',
    '肿瘤',
  ]

  return preferredOrder.map((label) => [
    label,
    prediction.value?.probabilities[label] ?? 0,
  ])
})

const toPercent = (value: number): number => {
  return Number((value * 100).toFixed(1))
}

const getTagType = (
    label: DiagnosisLabel,
): TagType => {
  const tagTypes: Record<DiagnosisLabel, TagType> = {
    其他: 'info',
    炎症: 'warning',
    感染: 'danger',
    肿瘤: 'primary',
  }

  return tagTypes[label]
}

const getProgressStatus = (
    label: DiagnosisLabel,
): '' | 'success' | 'warning' | 'exception' => {
  const statusMap: Record<
      DiagnosisLabel,
      '' | 'success' | 'warning' | 'exception'
  > = {
    其他: '',
    炎症: 'warning',
    感染: 'exception',
    肿瘤: 'success',
  }

  return statusMap[label]
}

const formatDateTime = (
    dateTime: string,
): string => {
  const date = new Date(dateTime)

  if (Number.isNaN(date.getTime())) {
    return dateTime
  }

  return date.toLocaleString('zh-CN', {
    hour12: false,
  })
}

const submitAnnotation = async (): Promise<void> => {
  const normalizedDoctorName = doctorName.value.trim()
  const normalizedRemark = doctorRemark.value.trim()

  if (!normalizedDoctorName) {
    ElMessage.warning('请输入医生姓名')
    return
  }

  if (!doctorLabel.value) {
    ElMessage.warning('请选择医生确认的真实诊断')
    return
  }

  try {
    await diagnosisStore.submitAnnotation({
      true_label: doctorLabel.value,
      doctor_name: normalizedDoctorName,
      remark: normalizedRemark || null,
    })

    ElMessage.success(
        '医生标注已保存到本地结果目录',
    )
  } catch (error: unknown) {
    if (axios.isAxiosError(error)) {
      const detail = error.response?.data?.detail

      if (typeof detail === 'string') {
        ElMessage.error(detail)
        return
      }

      if (!error.response) {
        ElMessage.error(
            '无法连接后端，请确认 FastAPI 正在运行',
        )
        return
      }

      ElMessage.error('医生标注提交失败')
      return
    }

    console.error('医生标注提交失败：', error)
    ElMessage.error('医生标注提交失败')
  }
}

const createNextCase = async (): Promise<void> => {
  diagnosisStore.clear()
  await router.push('/cases/new')
}

const returnToEdit = async (): Promise<void> => {
  await router.push('/cases/new')
}

onMounted(() => {
  if (!result.value) {
    ElMessage.warning('没有可以显示的预测结果')

    void router.replace('/cases/new')
  }
})
</script>

<template>
  <div
      v-if="result && currentCase && prediction"
      class="prediction-page"
  >
    <div class="page-heading">
      <div>
        <h2>模型预测结果</h2>

        <p>
          病例编号：{{ currentCase.case_code }}
        </p>
      </div>

      <div class="heading-tags">
        <el-tag type="warning" effect="plain">
          {{ prediction.model_version }}
        </el-tag>

        <el-tag
            v-if="annotationSubmitted"
            type="success"
            effect="plain"
        >
          已完成医生标注
        </el-tag>

        <el-tag
            v-else
            type="info"
            effect="plain"
        >
          待医生标注
        </el-tag>
      </div>
    </div>

    <el-alert
        title="当前结果由真实机器学习模型根据已填写的病例特征生成。未填写的字段会由训练管道按训练规则处理。该结果仅用于科研和临床辅助验证，不能替代医生诊断。"
        type="warning"
        :closable="false"
        show-icon
        class="page-alert"
    />

    <el-row :gutter="20">
      <el-col :xs="24" :lg="10">
        <el-card
            shadow="never"
            class="result-card"
        >
          <template #header>
            <div class="card-title">
              综合预测
            </div>
          </template>

          <el-result
              icon="warning"
              :title="`预测类别：${prediction.predicted_label}`"
              sub-title="该结果仅用于临床辅助判断，不能替代医生最终诊断"
          >
            <template #extra>
              <el-tag
                  :type="getTagType(
                  prediction.predicted_label
                )"
                  size="large"
                  effect="dark"
                  class="prediction-label"
              >
                {{ prediction.predicted_label }}
              </el-tag>
            </template>
          </el-result>

          <el-descriptions
              :column="1"
              border
          >
            <el-descriptions-item label="病例编号">
              {{ currentCase.case_code }}
            </el-descriptions-item>

            <el-descriptions-item label="模型版本">
              {{ prediction.model_version }}
            </el-descriptions-item>

            <el-descriptions-item label="患者年龄">
              {{ currentCase.age }} 岁
            </el-descriptions-item>

            <el-descriptions-item label="患者性别">
              {{ currentCase.gender }}
            </el-descriptions-item>

            <el-descriptions-item label="发烧时长">
              {{ currentCase.fever_duration }} 天
            </el-descriptions-item>

            <el-descriptions-item label="最高体温">
              {{ currentCase.max_temperature }} ℃
            </el-descriptions-item>

            <el-descriptions-item label="预测时间">
              {{
                formatDateTime(
                    prediction.created_at
                )
              }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <el-col :xs="24" :lg="14">
        <el-card
            shadow="never"
            class="result-card probability-card"
        >
          <template #header>
            <div class="card-title">
              四分类预测概率
            </div>
          </template>

          <div
              v-for="[label, probability] in probabilityItems"
              :key="label"
              class="probability-item"
          >
            <div class="probability-header">
              <el-tag
                  :type="getTagType(label)"
                  effect="plain"
              >
                {{ label }}
              </el-tag>

              <strong>
                {{ toPercent(probability) }}%
              </strong>
            </div>

            <el-progress
                :percentage="toPercent(probability)"
                :stroke-width="14"
                :show-text="false"
                :status="getProgressStatus(label)"
            />
          </div>

          <el-divider />

          <el-alert
              title="概率最高的类别不一定是真实诊断，请结合患者检查结果和临床经验进行确认。"
              type="info"
              :closable="false"
              show-icon
          />
        </el-card>
      </el-col>
    </el-row>

    <el-card
        shadow="never"
        class="annotation-card"
    >
      <template #header>
        <div class="annotation-header">
          <div class="card-title">
            医生确认诊断
          </div>

          <el-tag
              v-if="annotationSubmitted"
              type="success"
          >
            标注已保存
          </el-tag>
        </div>
      </template>

      <el-alert
          title="医生标注不会立即修改当前模型。经过审核的标注病例才能进入后续训练数据集。"
          type="info"
          :closable="false"
          show-icon
          class="annotation-alert"
      />

      <el-form label-position="top">
        <el-row :gutter="20">
          <el-col :xs="24" :md="12">
            <el-form-item label="医生姓名">
              <el-input
                  v-model="doctorName"
                  placeholder="请输入医生姓名"
                  maxlength="100"
                  clearable
                  :disabled="annotationSubmitted"
              />
            </el-form-item>
          </el-col>

          <el-col :xs="24" :md="12">
            <el-form-item label="模型预测结果">
              <el-input
                  :model-value="
                  prediction.predicted_label
                "
                  disabled
              />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="医生确认的真实诊断">
          <el-radio-group
              v-model="doctorLabel"
              :disabled="annotationSubmitted"
          >
            <el-radio-button value="其他">
              其他
            </el-radio-button>

            <el-radio-button value="炎症">
              炎症
            </el-radio-button>

            <el-radio-button value="感染">
              感染
            </el-radio-button>

            <el-radio-button value="肿瘤">
              肿瘤
            </el-radio-button>
          </el-radio-group>
        </el-form-item>

        <el-form-item label="标注说明">
          <el-input
              v-model="doctorRemark"
              type="textarea"
              :rows="4"
              maxlength="500"
              show-word-limit
              placeholder="可填写医生判断依据、检查结果或需要复核的情况"
              :disabled="annotationSubmitted"
          />
        </el-form-item>

        <el-alert
            v-if="annotationSubmitted &&
            diagnosisStore.currentAnnotation"
            :title="`标注保存成功：真实诊断为「${diagnosisStore.currentAnnotation.true_label}」`"
            type="success"
            :closable="false"
            show-icon
            class="saved-alert"
        />

        <div class="form-actions">
          <el-button
              :disabled="diagnosisStore.loading"
              @click="returnToEdit"
          >
            返回病例录入
          </el-button>

          <el-button
              :disabled="diagnosisStore.loading"
              @click="createNextCase"
          >
            录入下一病例
          </el-button>

          <el-button
              type="primary"
              :loading="diagnosisStore.loading"
              :disabled="annotationSubmitted"
              @click="submitAnnotation"
          >
            {{
              annotationSubmitted
                  ? '标注已提交'
                  : '提交医生标注'
            }}
          </el-button>
        </div>
      </el-form>
    </el-card>
  </div>

  <div
      v-else
      class="empty-wrapper"
  >
    <el-empty description="暂无预测结果">
      <el-button
          type="primary"
          @click="router.push('/cases/new')"
      >
        前往病例录入
      </el-button>
    </el-empty>
  </div>
</template>

<style scoped>
.prediction-page {
  max-width: 1280px;
  margin: 0 auto;
}

.page-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 18px;
}

.page-heading h2 {
  margin: 0;
  font-size: 24px;
}

.page-heading p {
  margin: 8px 0 0;
  color: #909399;
}

.heading-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.page-alert {
  margin-bottom: 20px;
}

.result-card {
  height: 100%;
  border-radius: 9px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.prediction-label {
  min-width: 100px;
  justify-content: center;
  font-size: 18px;
}

.probability-card {
  min-height: 100%;
}

.probability-item {
  margin-bottom: 28px;
}

.probability-item:last-of-type {
  margin-bottom: 0;
}

.probability-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 9px;
}

.probability-header strong {
  font-size: 16px;
  color: #303133;
}

.annotation-card {
  margin-top: 20px;
  border-radius: 9px;
}

.annotation-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.annotation-alert {
  margin-bottom: 20px;
}

.saved-alert {
  margin-bottom: 20px;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 12px;
}

.empty-wrapper {
  min-height: 500px;
  display: flex;
  align-items: center;
  justify-content: center;
}

@media (max-width: 991px) {
  .result-card {
    height: auto;
    margin-bottom: 18px;
  }
}

@media (max-width: 768px) {
  .page-heading {
    align-items: flex-start;
    flex-direction: column;
    gap: 12px;
  }

  .form-actions {
    flex-direction: column-reverse;
  }

  .form-actions .el-button {
    width: 100%;
    margin-left: 0;
  }
}
</style>
