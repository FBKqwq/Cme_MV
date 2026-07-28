<script setup lang="ts">
import {
  computed,
  onMounted,
  reactive,
  ref,
} from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import {
  getModelInfo,
  type CategoricalModelFeature,
  type ModelFeatureSchema,
  type ModelInfo,
  type NumericModelFeature,
} from '../api/diagnosis'
import { useDiagnosisStore } from '../stores/diagnosis'

type GenderValue = '' | '男' | '女'

type DynamicFeatureValue =
    | string
    | number
    | null

interface CaseForm {
  caseCode: string
  age: number | null
  gender: GenderValue
  feverDuration: number | null
  maxTemperature: number | null
}

const BASE_MODEL_FEATURE_NAMES = new Set([
  '年龄',
  '性别',
  '发烧时长',
  '最高体温',
])

const router = useRouter()
const diagnosisStore = useDiagnosisStore()

const modelInfoLoading = ref(false)
const modelInfo = ref<ModelInfo | null>(null)
const modelInfoError = ref('')

const dynamicValues = reactive<
    Record<string, DynamicFeatureValue>
>({})

const createInitialForm = (): CaseForm => ({
  caseCode: '',
  age: null,
  gender: '',
  feverDuration: null,
  maxTemperature: null,
})

const form = reactive<CaseForm>(
    createInitialForm(),
)

const dynamicFeatures = computed<
    ModelFeatureSchema[]
>(() => {
  if (!modelInfo.value) {
    return []
  }

  return modelInfo.value.feature_schema.filter(
      (feature) =>
          !BASE_MODEL_FEATURE_NAMES.has(
              feature.name,
          ),
  )
})

const numericFeatures = computed<
    NumericModelFeature[]
>(() => {
  return dynamicFeatures.value.filter(
      (
          feature,
      ): feature is NumericModelFeature =>
          feature.type === 'numeric',
  )
})

const categoricalFeatures = computed<
    CategoricalModelFeature[]
>(() => {
  return dynamicFeatures.value.filter(
      (
          feature,
      ): feature is CategoricalModelFeature =>
          feature.type === 'categorical',
  )
})

const totalDisplayedFeatures = computed(
    () => {
      return (
          dynamicFeatures.value.length + 4
      )
    },
)

const modelDisplayName = computed(() => {
  if (!modelInfo.value) {
    return '模型信息加载中'
  }

  const modelName =
      modelInfo.value.best_model_name
      || '诊断分类模型'

  const version =
      modelInfo.value.package_version
      || '未知版本'

  return `${modelName} v${version}`
})

const initializeDynamicValues = (): void => {
  for (
      const key of Object.keys(dynamicValues)
      ) {
    delete dynamicValues[key]
  }

  for (
      const feature of dynamicFeatures.value
      ) {
    dynamicValues[feature.name] =
        feature.type === 'numeric'
            ? null
            : ''
  }
}

const loadModelInfo = async (): Promise<void> => {
  modelInfoLoading.value = true
  modelInfoError.value = ''

  try {
    modelInfo.value = await getModelInfo()

    if (!modelInfo.value.loaded) {
      throw new Error('真实模型尚未加载')
    }

    if (
        modelInfo.value.feature_schema.length
        === 0
    ) {
      throw new Error(
          '模型没有提供 feature_schema',
      )
    }

    initializeDynamicValues()
  } catch (error: unknown) {
    console.error(
        '模型信息加载失败：',
        error,
    )

    if (axios.isAxiosError(error)) {
      const detail =
          error.response?.data?.detail

      modelInfoError.value =
          typeof detail === 'string'
              ? detail
              : '无法读取真实模型信息'
    } else if (error instanceof Error) {
      modelInfoError.value =
          error.message
    } else {
      modelInfoError.value =
          '无法读取真实模型信息'
    }

    ElMessage.error(modelInfoError.value)
  } finally {
    modelInfoLoading.value = false
  }
}

const getNumericPlaceholder = (
    feature: NumericModelFeature,
): string => {
  if (
      feature.min !== null
      && feature.max !== null
  ) {
    return (
        `训练数据参考范围：`
        + `${feature.min} ～ ${feature.max}`
    )
  }

  return '未知时可以留空'
}

const getBaseFeatureValue = (
    featureName: string,
): DynamicFeatureValue => {
  const baseFeatureMap:
      Record<string, DynamicFeatureValue> = {
    年龄: form.age,
    性别: form.gender || null,
    发烧时长: form.feverDuration,
    最高体温: form.maxTemperature,
  }

  return baseFeatureMap[featureName] ?? null
}

const buildModelFeatures =
    (): Record<string, unknown> => {
      const features: Record<
          string,
          unknown
      > = {}

      if (!modelInfo.value) {
        return features
      }

      for (
          const feature
          of modelInfo.value.feature_schema
          ) {
        let value: DynamicFeatureValue

        if (
            BASE_MODEL_FEATURE_NAMES.has(
                feature.name,
            )
        ) {
          value = getBaseFeatureValue(
              feature.name,
          )
        } else {
          value =
              dynamicValues[feature.name]
              ?? null
        }

        if (
            value === null
            || value === ''
            || value === undefined
        ) {
          continue
        }

        features[feature.name] = value
      }

      return features
    }

const validateBaseForm = (): boolean => {
  if (!form.caseCode.trim()) {
    ElMessage.warning('请输入病例编号')
    return false
  }

  if (form.age === null) {
    ElMessage.warning('请输入患者年龄')
    return false
  }

  if (
      form.age < 0
      || form.age > 120
  ) {
    ElMessage.warning(
        '患者年龄应在 0 至 120 岁之间',
    )
    return false
  }

  if (
      form.gender !== '男'
      && form.gender !== '女'
  ) {
    ElMessage.warning('请选择患者性别')
    return false
  }

  if (form.feverDuration === null) {
    ElMessage.warning('请输入发烧时长')
    return false
  }

  if (form.feverDuration < 0) {
    ElMessage.warning(
        '发烧时长不能小于 0',
    )
    return false
  }

  if (form.maxTemperature === null) {
    ElMessage.warning('请输入最高体温')
    return false
  }

  if (
      form.maxTemperature < 34
      || form.maxTemperature > 43
  ) {
    ElMessage.warning(
        '最高体温应在 34℃ 至 43℃之间',
    )
    return false
  }

  return true
}

const submitForm = async (): Promise<void> => {
  if (!validateBaseForm()) {
    return
  }

  if (!modelInfo.value) {
    ElMessage.error(
        '真实模型信息尚未加载，请刷新模型信息',
    )
    return
  }

  const features = buildModelFeatures()

  try {
    await diagnosisStore.predictCase({
      case_code: form.caseCode.trim(),
      age: form.age as number,
      gender: form.gender as '男' | '女',
      fever_duration:
          form.feverDuration as number,
      max_temperature:
          form.maxTemperature as number,
      features,
    })

    ElMessage.success(
        '病例已保存，真实模型预测完成',
    )

    await router.push('/prediction')
  } catch (error: unknown) {
    if (axios.isAxiosError(error)) {
      if (error.response?.status === 409) {
        ElMessage.error(
            '病例编号已经存在，请更换编号',
        )
        return
      }

      if (error.response?.status === 422) {
        const detail =
            error.response?.data?.detail

        ElMessage.error(
            typeof detail === 'string'
                ? detail
                : '模型字段格式不正确',
        )

        console.error(
            '模型预测校验错误：',
            error.response.data,
        )
        return
      }

      if (!error.response) {
        ElMessage.error(
            '无法连接 FastAPI 后端',
        )
        return
      }

      const detail =
          error.response.data?.detail

      ElMessage.error(
          typeof detail === 'string'
              ? detail
              : '病例提交失败',
      )
      return
    }

    console.error(
        '病例提交失败：',
        error,
    )

    ElMessage.error('病例提交失败')
  }
}

const resetForm = (): void => {
  Object.assign(
      form,
      createInitialForm(),
  )

  initializeDynamicValues()
  diagnosisStore.clear()

  ElMessage.info('表单已重置')
}

onMounted(() => {
  void loadModelInfo()
})
</script>

<template>
  <div class="case-create-page">
    <div class="page-heading">
      <div>
        <h2>病例录入</h2>

        <p>
          根据真实模型的字段结构填写患者已获得的信息。
          未检查的项目可以留空。
        </p>
      </div>

      <div class="heading-tags">
        <el-tag
            v-if="modelInfo"
            type="success"
            effect="plain"
        >
          模型已加载
        </el-tag>

        <el-tag
            v-if="modelInfo"
            type="info"
            effect="plain"
        >
          {{ modelInfo.feature_count }} 个模型特征
        </el-tag>
      </div>
    </div>

    <el-alert
        title="请勿填写最终诊断结果、感染分类或医生最终标注，避免发生标签泄漏。"
        type="warning"
        :closable="false"
        show-icon
        class="page-alert"
    />

    <el-alert
        v-if="modelInfoError"
        :title="modelInfoError"
        type="error"
        :closable="false"
        show-icon
        class="page-alert"
    >
      <template #default>
        <el-button
            type="danger"
            link
            @click="loadModelInfo"
        >
          重新读取模型信息
        </el-button>
      </template>
    </el-alert>

    <el-card
        v-loading="modelInfoLoading"
        shadow="never"
        class="model-card"
    >
      <template #header>
        <div class="card-header">
          <span>当前模型</span>

          <el-button
              link
              type="primary"
              :loading="modelInfoLoading"
              @click="loadModelInfo"
          >
            刷新模型信息
          </el-button>
        </div>
      </template>

      <el-descriptions
          v-if="modelInfo"
          :column="3"
          border
      >
        <el-descriptions-item label="模型">
          {{ modelDisplayName }}
        </el-descriptions-item>

        <el-descriptions-item label="输入特征">
          {{ modelInfo.feature_count }} 个
        </el-descriptions-item>

        <el-descriptions-item label="页面展示字段">
          {{ totalDisplayedFeatures }} 个
        </el-descriptions-item>

        <el-descriptions-item label="训练时间">
          {{ modelInfo.created_at || '未知' }}
        </el-descriptions-item>

        <el-descriptions-item label="Macro-F1">
          {{
            modelInfo.test_metrics.macro_f1
            !== null
            && modelInfo.test_metrics.macro_f1
            !== undefined
                ? (
                modelInfo.test_metrics.macro_f1
                * 100
            ).toFixed(1) + '%'
                : '未知'
          }}
        </el-descriptions-item>

        <el-descriptions-item label="用途">
          科研原型与流程验证
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-form
        :model="form"
        label-position="top"
        class="case-form"
    >
      <el-card
          shadow="never"
          class="form-card"
      >
        <template #header>
          <div class="section-title">
            <span>基础病例信息</span>

            <el-tag
                type="danger"
                effect="plain"
                size="small"
            >
              必填
            </el-tag>
          </div>
        </template>

        <el-row :gutter="20">
          <el-col :xs="24" :md="12">
            <el-form-item label="病例编号">
              <el-input
                  v-model="form.caseCode"
                  placeholder="例如：REAL-2026-0001"
                  maxlength="64"
                  clearable
              />
            </el-form-item>
          </el-col>

          <el-col :xs="24" :md="12">
            <el-form-item label="年龄">
              <el-input-number
                  v-model="form.age"
                  :min="0"
                  :max="120"
                  :step="1"
                  controls-position="right"
                  class="full-width"
              />
            </el-form-item>
          </el-col>

          <el-col :xs="24" :md="12">
            <el-form-item label="性别">
              <el-select
                  v-model="form.gender"
                  placeholder="请选择性别"
                  class="full-width"
              >
                <el-option
                    label="男"
                    value="男"
                />

                <el-option
                    label="女"
                    value="女"
                />
              </el-select>
            </el-form-item>
          </el-col>

          <el-col :xs="24" :md="12">
            <el-form-item label="发烧时长（天）">
              <el-input-number
                  v-model="form.feverDuration"
                  :min="0"
                  :precision="1"
                  :step="1"
                  controls-position="right"
                  class="full-width"
              />
            </el-form-item>
          </el-col>

          <el-col :xs="24" :md="12">
            <el-form-item label="最高体温（℃）">
              <el-input-number
                  v-model="form.maxTemperature"
                  :min="34"
                  :max="43"
                  :precision="1"
                  :step="0.1"
                  controls-position="right"
                  class="full-width"
              />
            </el-form-item>
          </el-col>
        </el-row>
      </el-card>

      <el-card
          v-if="numericFeatures.length > 0"
          shadow="never"
          class="form-card"
      >
        <template #header>
          <div class="section-title">
            <span>数值型检查指标</span>

            <el-tag
                type="info"
                effect="plain"
                size="small"
            >
              未检查可留空
            </el-tag>
          </div>
        </template>

        <el-row :gutter="20">
          <el-col
              v-for="feature in numericFeatures"
              :key="feature.name"
              :xs="24"
              :md="12"
          >
            <el-form-item>
              <template #label>
                <div class="feature-label">
                  <span>{{ feature.name }}</span>

                  <el-tooltip
                      v-if="
                      feature.min !== null
                      && feature.max !== null
                    "
                      :content="getNumericPlaceholder(feature)"
                  >
                    <span class="help-icon">
                      ?
                    </span>
                  </el-tooltip>
                </div>
              </template>

              <el-input-number
                  v-model="dynamicValues[feature.name]"
                  :placeholder="
                  getNumericPlaceholder(feature)
                "
                  controls-position="right"
                  class="full-width"
              />

              <div class="field-help">
                <template
                    v-if="
                    feature.min !== null
                    && feature.max !== null
                  "
                >
                  训练数据参考范围：
                  {{ feature.min }} ～ {{ feature.max }}
                </template>

                <template v-else>
                  未检查时可以留空
                </template>
              </div>
            </el-form-item>
          </el-col>
        </el-row>
      </el-card>

      <el-card
          v-if="categoricalFeatures.length > 0"
          shadow="never"
          class="form-card"
      >
        <template #header>
          <div class="section-title">
            <span>类别型检查指标</span>

            <el-tag
                type="info"
                effect="plain"
                size="small"
            >
              使用训练数据中的取值
            </el-tag>
          </div>
        </template>

        <el-row :gutter="20">
          <el-col
              v-for="feature in categoricalFeatures"
              :key="feature.name"
              :xs="24"
              :md="12"
          >
            <el-form-item :label="feature.name">
              <el-select
                  v-model="dynamicValues[feature.name]"
                  placeholder="请选择；未知可留空"
                  clearable
                  filterable
                  class="full-width"
              >
                <el-option
                    v-for="option in feature.allowed_values"
                    :key="option"
                    :label="option"
                    :value="option"
                />
              </el-select>

              <div class="field-help">
                可选值：
                {{
                  feature.allowed_values
                      .slice(0, 6)
                      .join('、')
                }}
                <template
                    v-if="
                    feature.allowed_values.length > 6
                  "
                >
                  等 {{ feature.allowed_values.length }} 项
                </template>
              </div>
            </el-form-item>
          </el-col>
        </el-row>
      </el-card>

      <el-card
          shadow="never"
          class="submit-card"
      >
        <el-alert
            title="提交时会保存模型输入快照、预测类别、四分类概率和模型版本，便于后续审计与复现。"
            type="info"
            :closable="false"
            show-icon
            class="submit-alert"
        />

        <div class="form-actions">
          <el-button
              :disabled="
              diagnosisStore.loading
              || modelInfoLoading
            "
              @click="resetForm"
          >
            重置表单
          </el-button>

          <el-button
              type="primary"
              :loading="diagnosisStore.loading"
              :disabled="
              modelInfoLoading
              || !modelInfo
            "
              @click="submitForm"
          >
            保存病例并开始真实预测
          </el-button>
        </div>
      </el-card>
    </el-form>
  </div>
</template>

<style scoped>
.case-create-page {
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

.model-card,
.form-card,
.submit-card {
  margin-bottom: 20px;
  border-radius: 9px;
}

.card-header,
.section-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-weight: 600;
}

.case-form {
  margin-top: 20px;
}

.full-width {
  width: 100%;
}

.feature-label {
  display: flex;
  align-items: center;
  gap: 7px;
}

.help-icon {
  width: 17px;
  height: 17px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid #a8abb2;
  border-radius: 50%;
  color: #909399;
  font-size: 12px;
  cursor: help;
}

.field-help {
  width: 100%;
  margin-top: 6px;
  color: #909399;
  font-size: 12px;
  line-height: 1.5;
}

.submit-alert {
  margin-bottom: 20px;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 12px;
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