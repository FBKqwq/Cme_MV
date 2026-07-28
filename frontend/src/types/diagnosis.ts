export type DiagnosisLabel =
    | '其他'
    | '炎症'
    | '感染'
    | '肿瘤'

export interface CaseInput {
    caseCode: string
    age: number
    gender: '男' | '女'
    feverDuration: number
    maxTemperature: number
}

export interface PredictionResult {
    predictedLabel: DiagnosisLabel

    probabilities: Record<DiagnosisLabel, number>

    modelVersion: string
    predictedAt: string
}