<script setup lang="ts">
import {
  computed,
  onMounted,
  ref,
} from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'

import {
  getCaseHistory,
  getModelInfo,
  type CaseHistoryItem,
  type DiagnosisLabel,
  type ModelFeatureSchema,
  type ModelInfo,
} from '../api/diagnosis'

interface PredictionCount {
  label: DiagnosisLabel
  count: number
}

const loading = ref(false)
const errorMessage = ref('')

const modelInfo =
    ref<ModelInfo | null>(null)

const historyItems =
    ref<CaseHistoryItem[]>([])

const diagnosisLabels: DiagnosisLabel[] = [
  '其他',
  '炎症',
  '感染',
  '肿瘤',
]

const totalCases = computed(
    () => historyItems.value.length,
)

const predictedCases = computed(
    () =>
        historyItems.value.filter(
            (item) => item.prediction !== null,
        ).length,
)

const annotatedCases = computed(
    () =>
        historyItems.value.filter(
            (item) => item.annotation !== null,
        ).length,
)

const agreementCases = computed(
    () =>
        historyItems.value.filter(
            (item) =>
                item.prediction !== null
                && item.annotation !== null
                && item.prediction.predicted_label
                === item.annotation.true_label,
        ).length,
)

const agreementRate = computed(() => {
  if (annotatedCases.value === 0) {
    return 0
  }

  return Number(
      (
          (
              agreementCases.value
              / annotatedCases.value
          )
          * 100
      ).toFixed(1),
  )
})

const predictionCounts = computed<
    PredictionCount[]
>(() => {
  return diagnosisLabels.map((label) => ({
    label,
    count: historyItems.value.filter(
        (item) =>
            item.prediction?.predicted_label
            === label,
    ).length,
  }))
})

const loadPageData =
    async (): Promise<void> => {
      loading.value = true
      errorMessage.value = ''

      try {
        const [
          modelResult,
          historyResult,
        ] = await Promise.all([
          getModelInfo(),
          getCaseHistory(),
        ])

        if (!modelResult.loaded) {
          throw new Error(
              '真实模型尚未加载。',
          )
        }

        modelInfo.value = modelResult
        historyItems.value = historyResult
      } catch (error: unknown) {
        console.error(
            '模型管理数据读取失败：',
            error,
        )

        if (axios.isAxiosError(error)) {
          const detail =
              error.response?.data?.detail

          if (typeof detail === 'string') {
            errorMessage.value = detail
          } else if (!error.response) {
            errorMessage.value =
                '无法连接后端，请确认 FastAPI 正在运行。'
          } else {
            errorMessage.value =
                '模型管理数据读取失败。'
          }
        } else if (error instanceof Error) {
          errorMessage.value =
              error.message
        } else {
          errorMessage.value =
              '模型管理数据读取失败。'
        }

        ElMessage.error(
            errorMessage.value,
        )
      } finally {
        loading.value = false
      }
    }

const formatDateTime = (
    value: string | null,
): string => {
  if (!value) {
    return '未知'
  }

  const date = new Date(value)

  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString(
      'zh-CN',
      {
        hour12: false,
      },
  )
}

const formatFileSize = (
    byteSize: number,
): string => {
  if (!Number.isFinite(byteSize)) {
    return '未知'
  }

  if (byteSize < 1024) {
    return `${byteSize} B`
  }

  if (byteSize < 1024 * 1024) {
    return (
        `${(byteSize / 1024).toFixed(1)} KB`
    )
  }

  return (
      `${(
          byteSize
          / 1024
          / 1024
      ).toFixed(2)} MB`
  )
}

const formatPercentMetric = (
    value: number | null | undefined,
): string => {
  if (
      value === null
      || value === undefined
      || Number.isNaN(value)
  ) {
    return '不可用'
  }

  return `${(value * 100).toFixed(1)}%`
}

const formatNumberMetric = (
    value: number | null | undefined,
): string => {
  if (
      value === null
      || value === undefined
      || Number.isNaN(value)
  ) {
    return '不可用'
  }

  return value.toFixed(3)
}

const getFeatureType = (
    feature: ModelFeatureSchema,
): string => {
  return feature.type === 'numeric'
      ? '数值型'
      : '类别型'
}

const getFeatureDescription = (
    feature: ModelFeatureSchema,
): string => {
  if (feature.type === 'categorical') {
    return (
        feature.allowed_values.join('、')
        || '没有可选值说明'
    )
  }

  if (
      feature.min !== null
      && feature.max !== null
  ) {
    return (
        `${feature.min} ～ ${feature.max}`
    )
  }

  return '没有参考范围'
}

const getFeatureMedian = (
    feature: ModelFeatureSchema,
): string => {
  if (
      feature.type !== 'numeric'
      || feature.median === null
  ) {
    return '-'
  }

  return String(feature.median)
}

onMounted(() => {
  void loadPageData()
})
</script>

<template>
  <div class="model-management-page">
    <div class="page-heading">
      <div>
        <h2>模型管理</h2>

        <p>
          查看当前诊断模型的版本、指标、
          输入字段和实际运行统计。
        </p>
      </div>

      <el-button
          type="primary"
          :loading="loading"
          @click="loadPageData"
      >
        刷新模型信息
      </el-button>
    </div>

    <el-alert
        title="当前页面仅展示已加载模型的信息，不提供在线训练或自动替换模型功能。"
        type="warning"
        :closable="false"
        show-icon
        class="page-alert"
    />

    <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="error"
        :closable="false"
        show-icon
        class="page-alert"
    />

    <div v-loading="loading">
      <template v-if="modelInfo">
        <el-card
            shadow="never"
            class="page-card"
        >
          <template #header>
            <div class="card-header">
              <span>当前模型</span>

              <el-tag
                  type="success"
                  effect="plain"
              >
                已加载
              </el-tag>
            </div>
          </template>

          <el-descriptions
              :column="3"
              border
          >
            <el-descriptions-item
                label="模型名称"
            >
              {{
                modelInfo.best_model_name
                || '未知'
              }}
            </el-descriptions-item>

            <el-descriptions-item
                label="模型版本"
            >
              {{
                modelInfo.package_version
                || '未知'
              }}
            </el-descriptions-item>

            <el-descriptions-item
                label="模型文件"
            >
              {{ modelInfo.model_file }}
            </el-descriptions-item>

            <el-descriptions-item
                label="文件大小"
            >
              {{
                formatFileSize(
                    modelInfo.model_file_size,
                )
              }}
            </el-descriptions-item>

            <el-descriptions-item
                label="生成时间"
            >
              {{
                formatDateTime(
                    modelInfo.created_at,
                )
              }}
            </el-descriptions-item>

            <el-descriptions-item
                label="scikit-learn"
            >
              {{
                modelInfo.sklearn_version
                || '未知'
              }}
            </el-descriptions-item>

            <el-descriptions-item
                label="输入特征"
            >
              {{ modelInfo.feature_count }} 个
            </el-descriptions-item>

            <el-descriptions-item
                label="输出类别"
                :span="2"
            >
              <el-space wrap>
                <el-tag
                    v-for="label in modelInfo.class_labels"
                    :key="label"
                    effect="plain"
                >
                  {{ label }}
                </el-tag>
              </el-space>
            </el-descriptions-item>

            <el-descriptions-item
                label="预测假设"
                :span="3"
            >
              {{
                modelInfo
                    .prediction_time_assumption
                || '无'
              }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>

        <el-card
            shadow="never"
            class="page-card"
        >
          <template #header>
            <div class="card-header">
              <span>测试集评估指标</span>

              <el-tag
                  type="info"
                  effect="plain"
              >
                离线测试结果
              </el-tag>
            </div>
          </template>

          <el-row :gutter="18">
            <el-col
                :xs="24"
                :sm="12"
                :lg="8"
            >
              <div class="metric-box">
                <div class="metric-name">
                  Accuracy
                </div>

                <div class="metric-value">
                  {{
                    formatPercentMetric(
                        modelInfo
                            .test_metrics
                            .accuracy,
                    )
                  }}
                </div>
              </div>
            </el-col>

            <el-col
                :xs="24"
                :sm="12"
                :lg="8"
            >
              <div class="metric-box">
                <div class="metric-name">
                  Balanced Accuracy
                </div>

                <div class="metric-value">
                  {{
                    formatPercentMetric(
                        modelInfo
                            .test_metrics
                            .balanced_accuracy,
                    )
                  }}
                </div>
              </div>
            </el-col>

            <el-col
                :xs="24"
                :sm="12"
                :lg="8"
            >
              <div class="metric-box">
                <div class="metric-name">
                  Macro-F1
                </div>

                <div class="metric-value">
                  {{
                    formatPercentMetric(
                        modelInfo
                            .test_metrics
                            .macro_f1,
                    )
                  }}
                </div>
              </div>
            </el-col>

            <el-col
                :xs="24"
                :sm="12"
                :lg="8"
            >
              <div class="metric-box">
                <div class="metric-name">
                  Weighted-F1
                </div>

                <div class="metric-value">
                  {{
                    formatPercentMetric(
                        modelInfo
                            .test_metrics
                            .weighted_f1,
                    )
                  }}
                </div>
              </div>
            </el-col>

            <el-col
                :xs="24"
                :sm="12"
                :lg="8"
            >
              <div class="metric-box">
                <div class="metric-name">
                  ROC-AUC
                </div>

                <div class="metric-value">
                  {{
                    formatNumberMetric(
                        modelInfo
                            .test_metrics
                            .macro_roc_auc_ovr,
                    )
                  }}
                </div>
              </div>
            </el-col>

            <el-col
                :xs="24"
                :sm="12"
                :lg="8"
            >
              <div class="metric-box">
                <div class="metric-name">
                  Log Loss
                </div>

                <div class="metric-value">
                  {{
                    formatNumberMetric(
                        modelInfo
                            .test_metrics
                            .log_loss,
                    )
                  }}
                </div>
              </div>
            </el-col>
          </el-row>
        </el-card>

        <el-row
            :gutter="20"
            class="statistics-row"
        >
          <el-col
              :xs="24"
              :sm="12"
              :lg="6"
          >
            <el-card shadow="never">
              <el-statistic
                  title="累计病例"
                  :value="totalCases"
              />
            </el-card>
          </el-col>

          <el-col
              :xs="24"
              :sm="12"
              :lg="6"
          >
            <el-card shadow="never">
              <el-statistic
                  title="已有预测"
                  :value="predictedCases"
              />
            </el-card>
          </el-col>

          <el-col
              :xs="24"
              :sm="12"
              :lg="6"
          >
            <el-card shadow="never">
              <el-statistic
                  title="医生已标注"
                  :value="annotatedCases"
              />
            </el-card>
          </el-col>

          <el-col
              :xs="24"
              :sm="12"
              :lg="6"
          >
            <el-card shadow="never">
              <el-statistic
                  title="模型与医生一致率"
                  :value="agreementRate"
                  suffix="%"
                  :precision="1"
              />
            </el-card>
          </el-col>
        </el-row>

        <el-card
            shadow="never"
            class="page-card"
        >
          <template #header>
            <div class="card-header">
              <span>预测类别统计</span>

              <el-tag
                  type="info"
                  effect="plain"
              >
                实际运行数据
              </el-tag>
            </div>
          </template>

          <el-row :gutter="18">
            <el-col
                v-for="item in predictionCounts"
                :key="item.label"
                :xs="24"
                :sm="12"
                :lg="6"
            >
              <div class="category-box">
                <div class="category-label">
                  {{ item.label }}
                </div>

                <div class="category-count">
                  {{ item.count }}
                </div>
              </div>
            </el-col>
          </el-row>
        </el-card>

        <el-card
            shadow="never"
            class="page-card"
        >
          <template #header>
            <div class="card-header">
              <span>模型输入字段</span>

              <el-tag
                  type="info"
                  effect="plain"
              >
                {{
                  modelInfo.feature_schema.length
                }}
                个字段
              </el-tag>
            </div>
          </template>

          <el-table
              :data="modelInfo.feature_schema"
              border
              stripe
              max-height="620"
          >
            <el-table-column
                prop="name"
                label="字段名称"
                min-width="180"
                fixed="left"
            />

            <el-table-column
                label="字段类型"
                width="110"
            >
              <template #default="{ row }">
                {{ getFeatureType(row) }}
              </template>
            </el-table-column>

            <el-table-column
                label="是否必填"
                width="110"
            >
              <template #default="{ row }">
                <el-tag
                    :type="
                    row.required
                      ? 'danger'
                      : 'info'
                  "
                    effect="plain"
                    size="small"
                >
                  {{
                    row.required
                        ? '是'
                        : '否'
                  }}
                </el-tag>
              </template>
            </el-table-column>

            <el-table-column
                label="可选值或参考范围"
                min-width="300"
            >
              <template #default="{ row }">
                {{
                  getFeatureDescription(row)
                }}
              </template>
            </el-table-column>

            <el-table-column
                label="训练数据中位数"
                width="150"
            >
              <template #default="{ row }">
                {{ getFeatureMedian(row) }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </template>
    </div>
  </div>
</template>

<style scoped>
.model-management-page {
  max-width: 1400px;
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

.page-alert,
.page-card,
.statistics-row {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-weight: 600;
}

.metric-box,
.category-box {
  margin-bottom: 18px;
  padding: 20px;
  border: 1px solid #ebeef5;
  border-radius: 9px;
  background: #ffffff;
}

.metric-name,
.category-label {
  color: #606266;
  font-size: 14px;
}

.metric-value,
.category-count {
  margin-top: 10px;
  color: #303133;
  font-size: 28px;
  font-weight: 700;
}

.statistics-row .el-card {
  margin-bottom: 12px;
}

@media (max-width: 768px) {
  .page-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .page-heading .el-button {
    width: 100%;
  }
}
</style>