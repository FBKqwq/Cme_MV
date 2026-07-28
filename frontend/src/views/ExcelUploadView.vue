<script setup lang="ts">
import axios from 'axios'
import {
  computed,
  onMounted,
  ref,
} from 'vue'
import {
  ElMessage,
} from 'element-plus'
import type {
  UploadFile,
  UploadInstance,
  UploadProps,
} from 'element-plus'
import * as XLSX from 'xlsx'

import {
  batchPredictCases,
  getModelInfo,
  type BatchPredictionResponse,
  type ModelInfo,
} from '../api/diagnosis'
type ExcelCellValue =
    | string
    | number
    | boolean
    | Date
    | null

type ExcelDataRow = Record<
    string,
    ExcelCellValue
>

type PreviewRow = ExcelDataRow & {
  __excelRow: number
}

const MAX_FILE_SIZE =
    10 * 1024 * 1024

const REQUIRED_COLUMNS = [
  '病例编号',
  '年龄',
  '性别',
  '发烧时长',
  '最高体温',
]

const uploadRef =
    ref<UploadInstance>()

const modelInfo =
    ref<ModelInfo | null>(null)

const modelLoading = ref(false)
const parsing = ref(false)

const batchSubmitting = ref(false)

const batchResult =
    ref<BatchPredictionResponse | null>(null)

const selectedFileName = ref('')
const selectedSheetName = ref('')

const headers = ref<string[]>([])
const rows = ref<ExcelDataRow[]>([])

const validationErrors = ref<string[]>([])
const validationWarnings = ref<string[]>([])
const invalidExcelRows = ref<number[]>([])

const expectedColumns = computed<string[]>(
    () => {
      const modelColumns =
          modelInfo.value?.feature_schema.map(
              (feature) => feature.name,
          ) ?? []

      return Array.from(
          new Set([
            '病例编号',
            ...modelColumns,
          ]),
      )
    },
)

const previewRows = computed<PreviewRow[]>(
    () => {
      return rows.value
          .slice(0, 20)
          .map((row, index) => ({
            ...row,
            __excelRow: index + 2,
          }))
    },
)

const invalidRowSet = computed(
    () => new Set(invalidExcelRows.value),
)

const validRowCount = computed(() => {
  return Math.max(
      rows.value.length
      - invalidExcelRows.value.length,
      0,
  )
})

const canContinue = computed(() => {
  return (
      rows.value.length > 0
      && validationErrors.value.length === 0
      && invalidExcelRows.value.length === 0
      && validRowCount.value === rows.value.length
  )
})

const normalizeHeader = (
    value: unknown,
): string => {
  return String(value ?? '').trim()
}

const isEmptyValue = (
    value: unknown,
): boolean => {
  return (
      value === null
      || value === undefined
      || String(value).trim() === ''
  )
}

const formatCellValue = (
    value: ExcelCellValue | undefined,
): string => {
  if (
      value === null
      || value === undefined
      || value === ''
  ) {
    return '-'
  }

  if (value instanceof Date) {
    return value.toLocaleDateString()
  }

  if (typeof value === 'boolean') {
    return value ? '是' : '否'
  }

  return String(value)
}

const formatProbability = (
    value: number | undefined,
): string => {
  if (
      value === undefined
      || Number.isNaN(value)
  ) {
    return '-'
  }

  return `${(value * 100).toFixed(1)}%`
}

const clearParsedData = (): void => {
  selectedFileName.value = ''
  selectedSheetName.value = ''

  headers.value = []
  rows.value = []

  validationErrors.value = []
  validationWarnings.value = []
  invalidExcelRows.value = []
  batchResult.value = null
}

const resetUpload = (): void => {
  uploadRef.value?.clearFiles()
  clearParsedData()

  ElMessage.info('已清空 Excel 文件')
}

const loadModelInfo = async (): Promise<void> => {
  modelLoading.value = true

  try {
    const result = await getModelInfo()

    if (!result.loaded) {
      throw new Error('真实模型尚未加载')
    }

    if (
        result.feature_schema.length === 0
    ) {
      throw new Error(
          '模型没有提供字段结构',
      )
    }

    modelInfo.value = result
  } catch (error: unknown) {
    console.error(
        '读取模型字段失败：',
        error,
    )

    ElMessage.error(
        error instanceof Error
            ? error.message
            : '读取模型字段失败',
    )
  } finally {
    modelLoading.value = false
  }
}

const validateWorkbookData = (): void => {
  validationErrors.value = []
  validationWarnings.value = []

  const invalidRows = new Set<number>()

  if (headers.value.length === 0) {
    validationErrors.value.push(
        '没有读取到 Excel 表头。',
    )

    invalidExcelRows.value = []
    return
  }

  if (rows.value.length === 0) {
    validationErrors.value.push(
        'Excel 中没有病例数据。',
    )

    invalidExcelRows.value = []
    return
  }

  const blankHeaderIndexes =
      headers.value
          .map((header, index) => ({
            header,
            index,
          }))
          .filter(
              (item) => item.header === '',
          )
          .map((item) => item.index + 1)

  if (blankHeaderIndexes.length > 0) {
    validationErrors.value.push(
        `第 ${blankHeaderIndexes.join('、')} 列表头为空。`,
    )
  }

  const headerCount =
      new Map<string, number>()

  for (const header of headers.value) {
    if (!header) {
      continue
    }

    headerCount.set(
        header,
        (headerCount.get(header) ?? 0) + 1,
    )
  }

  const duplicateHeaders =
      Array.from(headerCount.entries())
          .filter(([, count]) => count > 1)
          .map(([header]) => header)

  if (duplicateHeaders.length > 0) {
    validationErrors.value.push(
        `存在重复表头：${duplicateHeaders.join('、')}。`,
    )
  }

  const missingRequiredColumns =
      REQUIRED_COLUMNS.filter(
          (column) =>
              !headers.value.includes(column),
      )

  if (
      missingRequiredColumns.length > 0
  ) {
    validationErrors.value.push(
        `缺少必填列：${missingRequiredColumns.join('、')}。`,
    )
  }

  const missingModelColumns =
      expectedColumns.value.filter(
          (column) =>
              column !== '病例编号'
              && !headers.value.includes(column),
      )

  if (missingModelColumns.length > 0) {
    validationWarnings.value.push(
        `缺少 ${missingModelColumns.length} 个模型字段。`
        + '这些字段在后续预测时将按缺失值处理：'
        + missingModelColumns.join('、'),
    )
  }

  const extraColumns =
      headers.value.filter(
          (column) =>
              column
              && !expectedColumns.value.includes(
                  column,
              ),
      )

  if (extraColumns.length > 0) {
    validationWarnings.value.push(
        `发现模型之外的列：${extraColumns.join('、')}。`
        + '后续批量预测时将忽略这些列。',
    )
  }

  const caseCodeRows =
      new Map<string, number[]>()

  rows.value.forEach((row, index) => {
    const excelRow = index + 2

    for (
        const column of REQUIRED_COLUMNS
        ) {
      if (
          !headers.value.includes(column)
      ) {
        continue
      }

      if (isEmptyValue(row[column])) {
        invalidRows.add(excelRow)
      }
    }

    const caseCode =
        String(
            row['病例编号'] ?? '',
        ).trim()

    if (!caseCode) {
      return
    }

    const existing =
        caseCodeRows.get(caseCode) ?? []

    existing.push(excelRow)
    caseCodeRows.set(
        caseCode,
        existing,
    )
  })

  const duplicateCaseCodes: string[] = []

  for (
      const [
        caseCode,
        excelRows,
      ] of caseCodeRows.entries()
      ) {
    if (excelRows.length <= 1) {
      continue
    }

    duplicateCaseCodes.push(caseCode)

    for (const rowNumber of excelRows) {
      invalidRows.add(rowNumber)
    }
  }

  if (duplicateCaseCodes.length > 0) {
    validationErrors.value.push(
        `Excel 内存在重复病例编号：`
        + duplicateCaseCodes.join('、'),
    )
  }

  invalidExcelRows.value =
      Array.from(invalidRows).sort(
          (a, b) => a - b,
      )

  if (invalidExcelRows.value.length > 0) {
    validationWarnings.value.push(
        `有 ${invalidExcelRows.value.length} 行`
        + '缺少病例编号、年龄、性别、'
        + '发烧时长或最高体温。',
    )
  }
}

const parseExcelFile = async (
    rawFile: File,
): Promise<void> => {
  parsing.value = true
  clearParsedData()

  try {
    const fileName =
        rawFile.name.toLowerCase()

    if (!fileName.endsWith('.xlsx')) {
      throw new Error(
          '目前只允许上传 .xlsx 文件。',
      )
    }

    if (rawFile.size > MAX_FILE_SIZE) {
      throw new Error(
          'Excel 文件不能超过 10MB。',
      )
    }

    selectedFileName.value =
        rawFile.name

    const arrayBuffer =
        await rawFile.arrayBuffer()

    const workbook = XLSX.read(
        arrayBuffer,
        {
          type: 'array',
          cellDates: true,
        },
    )

    if (
        workbook.SheetNames.length === 0
    ) {
      throw new Error(
          'Excel 文件中没有工作表。',
      )
    }

    const firstSheetName =
        workbook.SheetNames[0]

    selectedSheetName.value =
        firstSheetName

    const worksheet =
        workbook.Sheets[firstSheetName]

    if (!worksheet) {
      throw new Error(
          '无法读取第一个工作表。',
      )
    }

    const matrix =
        XLSX.utils.sheet_to_json<
            ExcelCellValue[]
        >(worksheet, {
          header: 1,
          defval: null,
          raw: true,
        })

    if (matrix.length === 0) {
      throw new Error(
          'Excel 工作表为空。',
      )
    }

    const rawHeaderRow =
        matrix[0] ?? []

    let lastHeaderIndex =
        rawHeaderRow.length - 1

    while (
        lastHeaderIndex >= 0
        && normalizeHeader(
            rawHeaderRow[lastHeaderIndex],
        ) === ''
        ) {
      lastHeaderIndex -= 1
    }

    const parsedHeaders =
        rawHeaderRow
            .slice(0, lastHeaderIndex + 1)
            .map(normalizeHeader)

    headers.value = parsedHeaders

    const parsedRows: ExcelDataRow[] =
        matrix
            .slice(1)
            .filter((rawRow) => {
              return rawRow.some(
                  (value) => !isEmptyValue(value),
              )
            })
            .map((rawRow) => {
              const result: ExcelDataRow = {}

              parsedHeaders.forEach(
                  (header, columnIndex) => {
                    if (!header) {
                      return
                    }

                    result[header] =
                        rawRow[columnIndex] ?? null
                  },
              )

              return result
            })

    rows.value = parsedRows

    validateWorkbookData()

    if (
        validationErrors.value.length > 0
    ) {
      ElMessage.warning(
          'Excel 已读取，但存在格式错误。',
      )
    } else {
      ElMessage.success(
          `成功读取 ${rows.value.length} 条病例数据。`,
      )
    }
  } catch (error: unknown) {
    clearParsedData()

    console.error(
        'Excel 解析失败：',
        error,
    )

    ElMessage.error(
        error instanceof Error
            ? error.message
            : 'Excel 解析失败',
    )
  } finally {
    parsing.value = false
  }
}

const handleFileChange:
    UploadProps['onChange'] = (
    uploadFile: UploadFile,
) => {
  if (!uploadFile.raw) {
    return
  }

  void parseExcelFile(
      uploadFile.raw,
  )
}

const handleFileRemove:
    UploadProps['onRemove'] = () => {
  clearParsedData()
}

const handleFileExceed:
    UploadProps['onExceed'] = () => {
  ElMessage.warning(
      '一次只能选择一个 Excel 文件，'
      + '请先移除当前文件。',
  )
}

const downloadTemplate = (): void => {
  if (!modelInfo.value) {
    ElMessage.error(
        '模型字段尚未加载。',
    )
    return
  }

  const templateHeaders =
      expectedColumns.value

  const templateSheet =
      XLSX.utils.aoa_to_sheet([
        templateHeaders,
      ])

  templateSheet['!cols'] =
      templateHeaders.map(
          (header) => ({
            wch: Math.max(
                header.length * 2 + 4,
                14,
            ),
          }),
      )

  const instructionData: unknown[][] = [
    [
      '字段名称',
      '字段类型',
      '是否必填',
      '取值说明',
    ],
    [
      '病例编号',
      '文本',
      '是',
      '每个病例编号必须唯一',
    ],
  ]

  for (
      const feature
      of modelInfo.value.feature_schema
      ) {
    let valueDescription = ''

    if (
        feature.type === 'categorical'
    ) {
      valueDescription =
          feature.allowed_values.join('、')
    } else if (
        feature.min !== null
        && feature.max !== null
    ) {
      valueDescription =
          `训练数据参考范围：`
          + `${feature.min} ～ ${feature.max}`
    } else {
      valueDescription =
          '填写数值；未知可留空'
    }

    instructionData.push([
      feature.name,
      feature.type === 'numeric'
          ? '数值'
          : '类别',
      REQUIRED_COLUMNS.includes(
          feature.name,
      )
          ? '是'
          : '否',
      valueDescription,
    ])
  }

  const instructionSheet =
      XLSX.utils.aoa_to_sheet(
          instructionData,
      )

  instructionSheet['!cols'] = [
    { wch: 24 },
    { wch: 12 },
    { wch: 12 },
    { wch: 60 },
  ]

  const workbook =
      XLSX.utils.book_new()

  XLSX.utils.book_append_sheet(
      workbook,
      templateSheet,
      '病例导入模板',
  )

  XLSX.utils.book_append_sheet(
      workbook,
      instructionSheet,
      '填写说明',
  )

  XLSX.writeFile(
      workbook,
      '医院诊断批量导入模板.xlsx',
  )

  ElMessage.success(
      'Excel 模板已生成。',
  )
}

const isInvalidRow = (
    excelRow: number,
): boolean => {
  return invalidRowSet.value.has(
      excelRow,
  )
}

const submitBatchPrediction =
    async (): Promise<void> => {
      if (!canContinue.value) {
        ElMessage.warning(
            '请先修正 Excel 中的异常数据。',
        )
        return
      }

      batchSubmitting.value = true
      batchResult.value = null

      try {
        const requestRows = rows.value.map(
            (row, index) => {
              const features:
                  Record<string, unknown> = {}

              for (
                  const column
                  of expectedColumns.value
                  ) {
                if (column === '病例编号') {
                  continue
                }

                const value = row[column]

                if (
                    value === null
                    || value === undefined
                    || value === ''
                ) {
                  continue
                }

                features[column] = value
              }

              return {
                excel_row: index + 2,
                case_code: String(
                    row['病例编号'] ?? '',
                ).trim(),
                age: Number(row['年龄']),
                gender: String(
                    row['性别'] ?? '',
                ).trim() as '男' | '女',
                fever_duration: Number(
                    row['发烧时长'],
                ),
                max_temperature: Number(
                    row['最高体温'],
                ),
                features,
              }
            },
        )

        batchResult.value =
            await batchPredictCases({
              rows: requestRows,
            })

        ElMessage.success(
            `成功导入并预测 ${batchResult.value.success_count} 条病例。`,
        )
      } catch (error: unknown) {
        console.error(
            '批量预测失败：',
            error,
        )

        if (axios.isAxiosError(error)) {
          const detail =
              error.response?.data?.detail

          ElMessage.error(
              typeof detail === 'string'
                  ? detail
                  : '批量预测失败',
          )
        } else {
          ElMessage.error(
              error instanceof Error
                  ? error.message
                  : '批量预测失败',
          )
        }
      } finally {
        batchSubmitting.value = false
      }
    }

onMounted(() => {
  void loadModelInfo()
})
</script>

<template>
  <div class="excel-upload-page">
    <div class="page-heading">
      <div>
        <h2>Excel 批量导入</h2>

        <p>
          下载标准模板，填写病例信息后上传并检查数据。
        </p>
      </div>

      <el-button
          type="primary"
          plain
          :loading="modelLoading"
          :disabled="!modelInfo"
          @click="downloadTemplate"
      >
        下载 Excel 模板
      </el-button>
    </div>

    <el-alert
        title="请勿在测试文件中填写患者姓名、身份证号、手机号、住址等直接身份信息。"
        type="warning"
        :closable="false"
        show-icon
        class="page-alert"
    />

    <el-card
        v-loading="modelLoading"
        shadow="never"
        class="upload-card"
    >
      <template #header>
        <div class="card-header">
          <span>第一步：选择 Excel 文件</span>

          <el-tag
              v-if="modelInfo"
              type="success"
              effect="plain"
          >
            {{ modelInfo.feature_count }} 个模型特征
          </el-tag>
        </div>
      </template>

      <el-upload
          ref="uploadRef"
          class="excel-uploader"
          drag
          action="#"
          accept=".xlsx"
          :auto-upload="false"
          :limit="1"
          :on-change="handleFileChange"
          :on-remove="handleFileRemove"
          :on-exceed="handleFileExceed"
      >
        <div class="upload-content">
          <div class="upload-icon">
            XLSX
          </div>

          <div class="upload-title">
            将 Excel 文件拖到此处
          </div>

          <div class="upload-description">
            或点击选择文件
          </div>
        </div>

        <template #tip>
          <div class="upload-tip">
            仅支持 .xlsx，文件最大 10MB，
            默认读取第一个工作表。
          </div>
        </template>
      </el-upload>

      <div
          v-if="selectedFileName"
          class="file-actions"
      >
        <span>
          已选择：{{ selectedFileName }}
        </span>

        <el-button
            type="danger"
            link
            @click="resetUpload"
        >
          清空文件
        </el-button>
      </div>
    </el-card>

    <el-card
        v-if="rows.length > 0"
        v-loading="parsing"
        shadow="never"
        class="summary-card"
    >
      <template #header>
        <div class="card-header">
          <span>第二步：检查导入结果</span>

          <el-tag
              :type="
              validationErrors.length === 0
                ? 'success'
                : 'danger'
            "
          >
            {{
              validationErrors.length === 0
                  ? '格式检查通过'
                  : '存在格式错误'
            }}
          </el-tag>
        </div>
      </template>

      <el-descriptions
          :column="4"
          border
      >
        <el-descriptions-item
            label="工作表"
        >
          {{ selectedSheetName }}
        </el-descriptions-item>

        <el-descriptions-item
            label="总数据行"
        >
          {{ rows.length }}
        </el-descriptions-item>

        <el-descriptions-item
            label="有效数据"
        >
          {{ validRowCount }}
        </el-descriptions-item>

        <el-descriptions-item
            label="异常数据"
        >
          {{ invalidExcelRows.length }}
        </el-descriptions-item>
      </el-descriptions>

      <div
          v-if="validationErrors.length > 0"
          class="message-section"
      >
        <el-alert
            v-for="message in validationErrors"
            :key="message"
            :title="message"
            type="error"
            :closable="false"
            show-icon
            class="message-alert"
        />
      </div>

      <div
          v-if="validationWarnings.length > 0"
          class="message-section"
      >
        <el-alert
            v-for="message in validationWarnings"
            :key="message"
            :title="message"
            type="warning"
            :closable="false"
            show-icon
            class="message-alert"
        />
      </div>
    </el-card>

    <el-card
        v-if="rows.length > 0"
        shadow="never"
        class="preview-card"
    >
      <template #header>
        <div class="card-header">
          <span>第三步：数据预览</span>

          <span class="preview-tip">
            仅显示前 20 行
          </span>
        </div>
      </template>

      <el-table
          :data="previewRows"
          border
          stripe
          max-height="560"
      >
        <el-table-column
            label="Excel 行"
            fixed
            width="90"
        >
          <template #default="{ row }">
            {{ row.__excelRow }}
          </template>
        </el-table-column>

        <el-table-column
            label="状态"
            fixed
            width="90"
        >
          <template #default="{ row }">
            <el-tag
                :type="
                isInvalidRow(row.__excelRow)
                  ? 'danger'
                  : 'success'
              "
                size="small"
            >
              {{
                isInvalidRow(row.__excelRow)
                    ? '异常'
                    : '有效'
              }}
            </el-tag>
          </template>
        </el-table-column>

        <el-table-column
            v-for="column in headers"
            :key="column"
            :label="column || '空表头'"
            min-width="150"
        >
          <template #default="{ row }">
            {{
              formatCellValue(
                  row[column],
              )
            }}
          </template>
        </el-table-column>
      </el-table>

      <div class="bottom-actions">
        <el-button @click="resetUpload">
          重新选择文件
        </el-button>

        <el-button
            type="primary"
            :loading="batchSubmitting"
            :disabled="
            !canContinue
            || batchSubmitting
            || batchResult !== null
          "
            @click="submitBatchPrediction"
        >
          批量保存并开始预测
        </el-button>
      </div>
    </el-card>

    <el-card
        v-if="batchResult"
        shadow="never"
        class="result-card"
    >
      <template #header>
        <div class="card-header">
          <span>第四步：批量导入结果</span>

          <el-tag type="success">
            全部成功
          </el-tag>
        </div>
      </template>

      <el-descriptions
          :column="3"
          border
      >
        <el-descriptions-item label="导入总数">
          {{ batchResult.total }}
        </el-descriptions-item>

        <el-descriptions-item label="成功数量">
          {{ batchResult.success_count }}
        </el-descriptions-item>

        <el-descriptions-item label="模型版本">
          {{ batchResult.model_version }}
        </el-descriptions-item>
      </el-descriptions>

      <el-table
          :data="batchResult.results"
          border
          stripe
          class="result-table"
      >
        <el-table-column
            prop="excel_row"
            label="Excel 行"
            width="100"
        />

        <el-table-column
            prop="case_code"
            label="病例编号"
            min-width="210"
        />

        <el-table-column
            prop="predicted_label"
            label="预测结果"
            width="130"
        />

        <el-table-column label="其他" width="110">
          <template #default="{ row }">
            {{
              formatProbability(
                  row.probabilities['其他'],
              )
            }}
          </template>
        </el-table-column>

        <el-table-column label="炎症" width="110">
          <template #default="{ row }">
            {{
              formatProbability(
                  row.probabilities['炎症'],
              )
            }}
          </template>
        </el-table-column>

        <el-table-column label="感染" width="110">
          <template #default="{ row }">
            {{
              formatProbability(
                  row.probabilities['感染'],
              )
            }}
          </template>
        </el-table-column>

        <el-table-column label="肿瘤" width="110">
          <template #default="{ row }">
            {{
              formatProbability(
                  row.probabilities['肿瘤'],
              )
            }}
          </template>
        </el-table-column>
      </el-table>

      <div class="bottom-actions">
        <el-button @click="resetUpload">
          继续导入其他文件
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.excel-upload-page {
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
.upload-card,
.summary-card,
.preview-card,
.result-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-weight: 600;
}

.excel-uploader {
  width: 100%;
}

.excel-uploader :deep(.el-upload) {
  width: 100%;
}

.excel-uploader :deep(
  .el-upload-dragger
) {
  width: 100%;
  padding: 42px 20px;
}

.upload-content {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.upload-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 74px;
  height: 52px;
  margin-bottom: 16px;
  border-radius: 8px;
  background: #ecf5ff;
  color: #409eff;
  font-weight: 700;
  letter-spacing: 1px;
}

.upload-title {
  font-size: 17px;
  font-weight: 600;
}

.upload-description {
  margin-top: 8px;
  color: #909399;
}

.upload-tip,
.preview-tip {
  color: #909399;
  font-size: 13px;
}

.file-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 16px;
  padding: 12px 16px;
  border-radius: 6px;
  background: #f5f7fa;
}

.message-section {
  margin-top: 18px;
}

.message-alert {
  margin-top: 10px;
}

.result-table {
  margin-top: 20px;
}

.bottom-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 20px;
}

@media (max-width: 768px) {
  .page-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .page-heading .el-button {
    width: 100%;
  }

  .bottom-actions {
    flex-direction: column-reverse;
  }

  .bottom-actions .el-button {
    width: 100%;
    margin-left: 0;
  }
}
</style>