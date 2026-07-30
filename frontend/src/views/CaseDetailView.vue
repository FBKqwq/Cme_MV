<script setup lang="ts">
import {
  computed,
  ref,
  watch,
} from 'vue'
import axios from 'axios'
import {
  useRoute,
  useRouter,
} from 'vue-router'

import {
  getCaseDetail,
  type CaseDetailResponse,
  type DiagnosisLabel,
} from '../api/diagnosis'

type TagType =
    | 'primary'
    | 'success'
    | 'warning'
    | 'danger'
    | 'info'

interface FeatureEntry {
  name: string
  value: unknown
}

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const detail = ref<CaseDetailResponse | null>(null)
const errorMessage = ref('')

const featureEntries = computed<FeatureEntry[]>(
    () => {
      if (!detail.value) {
        return []
      }

      return Object.entries(
          detail.value.case.features ?? {},
      ).map(([name, value]) => ({
        name,
        value,
      }))
    },
)

const probabilityEntries = computed<
    Array<[DiagnosisLabel, number]>
>(() => {
  const prediction = detail.value?.prediction

  if (!prediction) {
    return []
  }

  const labels: DiagnosisLabel[] = [
    '其他',
    '炎症',
    '感染',
    '肿瘤',
  ]

  return labels.map((label) => [
    label,
    prediction.probabilities[label] ?? 0,
  ])
})

const consistency = computed<boolean | null>(
    () => {
      const prediction = detail.value?.prediction
      const annotation = detail.value?.annotation

      if (!prediction || !annotation) {
        return null
      }

      return (
          prediction.predicted_label
          === annotation.true_label
      )
    },
)

const getCaseId = (): number | null => {
  const rawValue = Array.isArray(
      route.params.caseId,
  )
      ? route.params.caseId[0]
      : route.params.caseId

  const caseId = Number(rawValue)

  if (
      !Number.isInteger(caseId)
      || caseId <= 0
  ) {
    return null
  }

  return caseId
}

const loadDetail = async (): Promise<void> => {
  const caseId = getCaseId()

  detail.value = null
  errorMessage.value = ''

  if (caseId === null) {
    errorMessage.value = '病例 ID 格式不正确。'
    return
  }

  loading.value = true

  try {
    detail.value = await getCaseDetail(caseId)
  } catch (error: unknown) {
    console.error('病例详情加载失败：', error)

    if (axios.isAxiosError(error)) {
      if (error.response?.status === 404) {
        errorMessage.value =
            '病例不存在或已被删除。'
        return
      }

      const responseDetail =
          error.response?.data?.detail

      if (typeof responseDetail === 'string') {
        errorMessage.value = responseDetail
        return
      }

      if (!error.response) {
        errorMessage.value =
            '无法连接后端，请确认 FastAPI 正在运行。'
        return
      }
    }

    errorMessage.value = '病例详情加载失败。'
  } finally {
    loading.value = false
  }
}

const goBack = async (): Promise<void> => {
  await router.push({
    name: 'case-create',
  })
}

const getTagType = (
    label: DiagnosisLabel,
): TagType => {
  const types: Record<DiagnosisLabel, TagType> = {
    其他: 'info',
    炎症: 'warning',
    感染: 'danger',
    肿瘤: 'primary',
  }

  return types[label]
}

const formatDateTime = (
    value: string,
): string => {
  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString('zh-CN', {
    hour12: false,
  })
}

const formatValue = (
    value: unknown,
): string => {
  if (
      value === null
      || value === undefined
      || value === ''
  ) {
    return '-'
  }

  if (typeof value === 'boolean') {
    return value ? '是' : '否'
  }

  if (typeof value === 'object') {
    try {
      return JSON.stringify(value)
    } catch {
      return String(value)
    }
  }

  return String(value)
}

const toPercentNumber = (
    value: number,
): number => {
  return Number((value * 100).toFixed(1))
}

watch(
    () => route.params.caseId,
    () => {
      void loadDetail()
    },
    {
      immediate: true,
    },
)
</script>

<template>
  <div class="case-detail-page">
    <div class="page-heading">
      <div>
        <h2>病例详情</h2>
        <p>
          查看病例输入、模型预测和医生标注。
        </p>
      </div>

      <div class="heading-actions">
        <el-button @click="goBack">
          返回病例录入
        </el-button>

        <el-button
            type="primary"
            :loading="loading"
            @click="loadDetail"
        >
          刷新详情
        </el-button>
      </div>
    </div>

    <el-alert
        title="该页面展示模型预测记录，仅用于科研和临床辅助验证，不能替代医生诊断。"
        type="warning"
        :closable="false"
        show-icon
        class="page-alert"
    />

    <el-card
        v-if="errorMessage"
        shadow="never"
        class="error-card"
    >
      <el-result
          icon="error"
          title="无法读取病例详情"
          :sub-title="errorMessage"
      >
        <template #extra>
          <el-button @click="goBack">
            返回病例录入
          </el-button>

          <el-button
              type="primary"
              @click="loadDetail"
          >
            重新读取
          </el-button>
        </template>
      </el-result>
    </el-card>

    <div
        v-else
        v-loading="loading"
        class="detail-content"
    >
      <template v-if="detail">
        <el-card
            shadow="never"
            class="detail-card"
        >
          <template #header>
            <div class="card-header">
              <span>基础病例信息</span>

              <el-tag
                  type="info"
                  effect="plain"
              >
                ID：{{ detail.case.id }}
              </el-tag>
            </div>
          </template>

          <el-descriptions
              :column="3"
              border
          >
            <el-descriptions-item label="病例编号">
              {{ detail.case.case_code }}
            </el-descriptions-item>

            <el-descriptions-item label="年龄">
              {{ detail.case.age }} 岁
            </el-descriptions-item>

            <el-descriptions-item label="性别">
              {{ detail.case.gender }}
            </el-descriptions-item>

            <el-descriptions-item label="发烧时长">
              {{ detail.case.fever_duration }} 天
            </el-descriptions-item>

            <el-descriptions-item label="最高体温">
              {{ detail.case.max_temperature }} ℃
            </el-descriptions-item>

            <el-descriptions-item label="创建时间">
              {{ formatDateTime(detail.case.created_at) }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card
            shadow="never"
            class="detail-card"
        >
          <template #header>
            <div class="card-header">
              <span>模型预测结果</span>

              <el-tag
                  v-if="detail.prediction"
                  :type="getTagType(
                  detail.prediction.predicted_label
                )"
              >
                {{ detail.prediction.predicted_label }}
              </el-tag>
            </div>
          </template>

          <template v-if="detail.prediction">
            <el-descriptions
                :column="3"
                border
            >
              <el-descriptions-item label="预测类别">
                <el-tag
                    :type="getTagType(
                    detail.prediction.predicted_label
                  )"
                >
                  {{ detail.prediction.predicted_label }}
                </el-tag>
              </el-descriptions-item>

              <el-descriptions-item label="模型版本">
                {{ detail.prediction.model_version }}
              </el-descriptions-item>

              <el-descriptions-item label="预测时间">
                {{ formatDateTime(
                  detail.prediction.created_at
              ) }}
              </el-descriptions-item>
            </el-descriptions>

            <div class="probability-list">
              <div
                  v-for="[
                  label,
                  probability,
                ] in probabilityEntries"
                  :key="label"
                  class="probability-item"
              >
                <div class="probability-heading">
                  <el-tag
                      :type="getTagType(label)"
                      effect="plain"
                  >
                    {{ label }}
                  </el-tag>

                  <strong>
                    {{ toPercentNumber(probability) }}%
                  </strong>
                </div>

                <el-progress
                    :percentage="toPercentNumber(probability)"
                    :stroke-width="14"
                />
              </div>
            </div>
          </template>

          <el-empty
              v-else
              description="该病例没有模型预测记录"
              :image-size="90"
          />
        </el-card>

        <el-card
            shadow="never"
            class="detail-card"
        >
          <template #header>
            <div class="card-header">
              <span>模型输入快照</span>

              <el-tag
                  type="info"
                  effect="plain"
              >
                {{ featureEntries.length }} 个已保存字段
              </el-tag>
            </div>
          </template>

          <el-table
              v-if="featureEntries.length > 0"
              :data="featureEntries"
              border
              stripe
              max-height="520"
          >
            <el-table-column
                prop="name"
                label="字段名称"
                min-width="220"
            />

            <el-table-column
                label="提交值"
                min-width="260"
            >
              <template #default="{ row }">
                {{ formatValue(row.value) }}
              </template>
            </el-table-column>
          </el-table>

          <el-empty
              v-else
              description="没有保存模型输入字段"
              :image-size="90"
          />
        </el-card>

        <el-card
            shadow="never"
            class="detail-card"
        >
          <template #header>
            <div class="card-header">
              <span>医生标注</span>

              <template v-if="detail.annotation">
                <el-tag
                    v-if="consistency === true"
                    type="success"
                >
                  与模型一致
                </el-tag>

                <el-tag
                    v-else-if="consistency === false"
                    type="danger"
                >
                  与模型不一致
                </el-tag>

                <el-tag
                    v-else
                    type="info"
                    effect="plain"
                >
                  无法比较
                </el-tag>
              </template>
            </div>
          </template>

          <el-descriptions
              v-if="detail.annotation"
              :column="2"
              border
          >
            <el-descriptions-item label="医生最终诊断">
              <el-tag
                  :type="getTagType(
                  detail.annotation.true_label
                )"
              >
                {{ detail.annotation.true_label }}
              </el-tag>
            </el-descriptions-item>

            <el-descriptions-item label="医生姓名">
              {{ detail.annotation.doctor_name }}
            </el-descriptions-item>

            <el-descriptions-item label="标注状态">
              {{ detail.annotation.status }}
            </el-descriptions-item>

            <el-descriptions-item label="标注时间">
              {{ formatDateTime(
                detail.annotation.created_at
            ) }}
            </el-descriptions-item>

            <el-descriptions-item
                label="备注"
                :span="2"
            >
              {{ detail.annotation.remark || '无备注' }}
            </el-descriptions-item>
          </el-descriptions>

          <el-empty
              v-else
              description="该病例尚未完成医生标注"
              :image-size="90"
          />
        </el-card>
      </template>
    </div>
  </div>
</template>

<style scoped>
.case-detail-page {
  max-width: 1280px;
  margin: 0 auto;
}

.page-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
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

.heading-actions {
  display: flex;
  gap: 12px;
}

.page-alert,
.error-card,
.detail-card {
  margin-bottom: 20px;
}

.detail-content {
  min-height: 260px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-weight: 600;
}

.probability-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  margin-top: 22px;
}

.probability-item {
  padding: 16px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
}

.probability-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

@media (max-width: 768px) {
  .page-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .heading-actions {
    width: 100%;
    flex-direction: column-reverse;
  }

  .heading-actions .el-button {
    width: 100%;
    margin-left: 0;
  }

  .probability-list {
    grid-template-columns: 1fr;
  }
}
</style>
