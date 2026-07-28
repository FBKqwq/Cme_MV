<script setup lang="ts">
import {
  computed,
  onMounted,
  ref,
} from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import {
  getCaseHistory,
  type CaseHistoryItem,
  type DiagnosisLabel,
} from '../api/diagnosis'

type TagType =
    | 'primary'
    | 'success'
    | 'warning'
    | 'danger'
    | 'info'

const router = useRouter()

const loading = ref(false)
const historyItems = ref<CaseHistoryItem[]>([])

const keyword = ref('')
const predictedLabelFilter =
    ref<DiagnosisLabel | ''>('')
const annotationStatusFilter = ref('')

const filteredItems = computed(() => {
  const normalizedKeyword =
      keyword.value.trim().toLowerCase()

  return historyItems.value.filter((item) => {
    const matchesKeyword =
        !normalizedKeyword
        || item.case.case_code
            .toLowerCase()
            .includes(normalizedKeyword)

    const matchesPrediction =
        !predictedLabelFilter.value
        || item.prediction?.predicted_label
        === predictedLabelFilter.value

    let matchesAnnotation = true

    if (
        annotationStatusFilter.value === 'annotated'
    ) {
      matchesAnnotation =
          item.annotation !== null
    }

    if (
        annotationStatusFilter.value === 'unannotated'
    ) {
      matchesAnnotation =
          item.annotation === null
    }

    if (
        annotationStatusFilter.value === 'correct'
    ) {
      matchesAnnotation =
          item.annotation !== null
          && item.prediction !== null
          && item.annotation.true_label
          === item.prediction.predicted_label
    }

    if (
        annotationStatusFilter.value === 'incorrect'
    ) {
      matchesAnnotation =
          item.annotation !== null
          && item.prediction !== null
          && item.annotation.true_label
          !== item.prediction.predicted_label
    }

    return (
        matchesKeyword
        && matchesPrediction
        && matchesAnnotation
    )
  })
})

const totalCases = computed(
    () => historyItems.value.length,
)

const annotatedCases = computed(
    () =>
        historyItems.value.filter(
            (item) => item.annotation !== null,
        ).length,
)

const correctCases = computed(
    () =>
        historyItems.value.filter(
            (item) =>
                item.annotation !== null
                && item.prediction !== null
                && item.annotation.true_label
                === item.prediction.predicted_label,
        ).length,
)

const agreementRate = computed(() => {
  if (annotatedCases.value === 0) {
    return 0
  }

  return Number(
      (
          (
              correctCases.value
              / annotatedCases.value
          ) * 100
      ).toFixed(1),
  )
})

const loadHistory = async (): Promise<void> => {
  loading.value = true

  try {
    historyItems.value =
        await getCaseHistory()
  } catch (error: unknown) {
    if (axios.isAxiosError(error)) {
      const detail =
          error.response?.data?.detail

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
    }

    ElMessage.error('历史病例加载失败')
  } finally {
    loading.value = false
  }
}

const resetFilters = (): void => {
  keyword.value = ''
  predictedLabelFilter.value = ''
  annotationStatusFilter.value = ''
}

const openDetail = async (
    item: CaseHistoryItem,
): Promise<void> => {
  await router.push({
    name: 'case-detail',
    params: {
      caseId: item.case.id,
    },
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

const getConsistency = (
    item: CaseHistoryItem,
): boolean | null => {
  if (!item.prediction || !item.annotation) {
    return null
  }

  return (
      item.prediction.predicted_label
      === item.annotation.true_label
  )
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

onMounted(() => {
  void loadHistory()
})
</script>

<template>
  <div class="history-page">
    <div class="page-heading">
      <div>
        <h2>历史病例</h2>
        <p>
          查看病例、模型预测和医生真实标注。
        </p>
      </div>

      <el-button
          type="primary"
          :loading="loading"
          @click="loadHistory"
      >
        刷新数据
      </el-button>
    </div>

    <el-row
        :gutter="20"
        class="statistics-row"
    >
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never">
          <el-statistic
              title="累计病例"
              :value="totalCases"
          />
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never">
          <el-statistic
              title="已标注病例"
              :value="annotatedCases"
          />
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never">
          <el-statistic
              title="预测一致病例"
              :value="correctCases"
          />
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never">
          <el-statistic
              title="预测一致率"
              :value="agreementRate"
              suffix="%"
              :precision="1"
          />
        </el-card>
      </el-col>
    </el-row>

    <el-card
        shadow="never"
        class="filter-card"
    >
      <el-form inline>
        <el-form-item label="病例编号">
          <el-input
              v-model="keyword"
              placeholder="搜索病例编号"
              clearable
          />
        </el-form-item>

        <el-form-item label="预测类别">
          <el-select
              v-model="predictedLabelFilter"
              placeholder="全部类别"
              clearable
              class="filter-select"
          >
            <el-option label="其他" value="其他" />
            <el-option label="炎症" value="炎症" />
            <el-option label="感染" value="感染" />
            <el-option label="肿瘤" value="肿瘤" />
          </el-select>
        </el-form-item>

        <el-form-item label="标注情况">
          <el-select
              v-model="annotationStatusFilter"
              placeholder="全部状态"
              clearable
              class="filter-select"
          >
            <el-option
                label="已标注"
                value="annotated"
            />
            <el-option
                label="待标注"
                value="unannotated"
            />
            <el-option
                label="预测一致"
                value="correct"
            />
            <el-option
                label="预测不一致"
                value="incorrect"
            />
          </el-select>
        </el-form-item>

        <el-form-item>
          <el-button @click="resetFilters">
            重置筛选
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card
        v-loading="loading"
        shadow="never"
        class="table-card"
    >
      <el-table
          :data="filteredItems"
          stripe
          empty-text="暂无病例数据"
      >
        <el-table-column
            prop="case.case_code"
            label="病例编号"
            min-width="160"
            fixed="left"
        />

        <el-table-column
            prop="case.age"
            label="年龄"
            width="80"
        />

        <el-table-column
            prop="case.gender"
            label="性别"
            width="80"
        />

        <el-table-column
            label="模型预测"
            width="110"
        >
          <template #default="{ row }">
            <el-tag
                v-if="row.prediction"
                :type="getTagType(
                row.prediction.predicted_label
              )"
            >
              {{ row.prediction.predicted_label }}
            </el-tag>

            <el-tag
                v-else
                type="info"
                effect="plain"
            >
              无预测
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column
            label="医生标注"
            width="110"
        >
          <template #default="{ row }">
            <el-tag
                v-if="row.annotation"
                :type="getTagType(
                row.annotation.true_label
              )"
                effect="plain"
            >
              {{ row.annotation.true_label }}
            </el-tag>

            <el-tag
                v-else
                type="info"
                effect="plain"
            >
              待标注
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column
            label="是否一致"
            width="110"
        >
          <template #default="{ row }">
            <el-tag
                v-if="getConsistency(row) === true"
                type="success"
            >
              一致
            </el-tag>

            <el-tag
                v-else-if="getConsistency(row) === false"
                type="danger"
            >
              不一致
            </el-tag>

            <el-tag
                v-else
                type="info"
                effect="plain"
            >
              未判断
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column
            label="模型版本"
            min-width="160"
        >
          <template #default="{ row }">
            {{ row.prediction?.model_version ?? '-' }}
          </template>
        </el-table-column>

        <el-table-column
            label="创建时间"
            min-width="180"
        >
          <template #default="{ row }">
            {{ formatDateTime(row.case.created_at) }}
          </template>
        </el-table-column>

        <el-table-column
            label="操作"
            width="110"
            fixed="right"
        >
          <template #default="{ row }">
            <el-button
                link
                type="primary"
                @click="openDetail(row)"
            >
              查看详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.history-page {
  max-width: 1400px;
  margin: 0 auto;
}

.page-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.page-heading h2 {
  margin: 0;
  font-size: 24px;
}

.page-heading p {
  margin: 8px 0 0;
  color: #909399;
}

.statistics-row {
  margin-bottom: 20px;
}

.statistics-row .el-card {
  margin-bottom: 12px;
  border-radius: 9px;
}

.filter-card,
.table-card {
  margin-bottom: 20px;
  border-radius: 9px;
}

.filter-select {
  width: 150px;
}

@media (max-width: 768px) {
  .page-heading {
    align-items: flex-start;
    flex-direction: column;
    gap: 14px;
  }
}
</style>
