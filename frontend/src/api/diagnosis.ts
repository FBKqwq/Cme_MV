import http from './http'

export type DiagnosisLabel =
    | '其他'
    | '炎症'
    | '感染'
    | '肿瘤'

export interface NumericModelFeature {
    name: string
    type: 'numeric'
    required: boolean
    min: number | null
    max: number | null
    median: number | null
}

export interface CategoricalModelFeature {
    name: string
    type: 'categorical'
    required: boolean
    allowed_values: string[]
}

export type ModelFeatureSchema =
    | NumericModelFeature
    | CategoricalModelFeature

export interface ModelInfo {
    loaded: boolean
    model_file: string
    model_file_size: number
    package_version: string | null
    best_model_name: string | null
    created_at: string | null
    feature_count: number
    feature_columns: string[]
    feature_schema: ModelFeatureSchema[]
    class_labels: DiagnosisLabel[]
    test_metrics: {
        accuracy?: number | null
        balanced_accuracy?: number | null
        macro_f1?: number | null
        weighted_f1?: number | null
        macro_roc_auc_ovr?: number | null
        log_loss?: number | null
    }
    prediction_time_assumption: string | null
    sklearn_version: string | null
}

export interface CaseCreatePayload {
    case_code: string
    age: number
    gender: '男' | '女'
    fever_duration: number
    max_temperature: number
    features: Record<string, unknown>
}

export interface CaseResponse {
    id: number
    case_code: string
    age: number
    gender: string
    fever_duration: number
    max_temperature: number
    features: Record<string, unknown>
    created_at: string
}

export interface PredictionResponse {
    id: number
    case_id: number
    predicted_label: DiagnosisLabel
    probabilities: Record<DiagnosisLabel, number>
    model_version: string
    created_at: string
}

export interface CasePredictionResponse {
    case: CaseResponse
    prediction: PredictionResponse
}

export interface AnnotationCreatePayload {
    true_label: DiagnosisLabel
    doctor_name: string
    remark?: string | null
}

export interface AnnotationResponse {
    id: number
    case_id: number
    true_label: DiagnosisLabel
    doctor_name: string
    status: string
    remark: string | null
    created_at: string
}

export interface CaseHistoryItem {
    case: CaseResponse
    prediction: PredictionResponse | null
    annotation: AnnotationResponse | null
}

export interface CaseDetailResponse {
    case: CaseResponse
    prediction: PredictionResponse | null
    annotation: AnnotationResponse | null
}

export interface BatchCaseItem {
    excel_row: number
    case_code: string
    age: number
    gender: '男' | '女'
    fever_duration: number
    max_temperature: number
    features: Record<string, unknown>
}

export interface BatchPredictionRequest {
    rows: BatchCaseItem[]
}

export interface BatchPredictionResultItem {
    excel_row: number
    case_id: number
    case_code: string
    predicted_label: DiagnosisLabel
    probabilities: Record<DiagnosisLabel, number>
}

export interface BatchPredictionResponse {
    total: number
    success_count: number
    model_version: string
    results: BatchPredictionResultItem[]
}

export const createCaseAndPrediction = async (
    payload: CaseCreatePayload,
): Promise<CasePredictionResponse> => {
    const response = await http.post<CasePredictionResponse>(
        '/api/cases/predict',
        payload,
    )

    return response.data
}

export const createAnnotation = async (
    caseId: number,
    payload: AnnotationCreatePayload,
): Promise<AnnotationResponse> => {
    const response = await http.post<AnnotationResponse>(
        `/api/cases/${caseId}/annotations`,
        payload,
    )

    return response.data
}

export const getCases = async (): Promise<CaseResponse[]> => {
    const response = await http.get<CaseResponse[]>(
        '/api/cases',
    )

    return response.data
}

export const getCaseDetail = async (
    caseId: number,
): Promise<CaseDetailResponse> => {
    const response = await http.get<CaseDetailResponse>(
        `/api/cases/${caseId}`,
    )

    return response.data
}

export const getCaseHistory = async (): Promise<
    CaseHistoryItem[]
> => {
    const response = await http.get<CaseHistoryItem[]>(
        '/api/case-history',
    )

    return response.data
}

export const getModelInfo = async (): Promise<ModelInfo> => {
    const response = await http.get<ModelInfo>(
        '/api/model/info',
    )

    return response.data
}

export const batchPredictCases = async (
    payload: BatchPredictionRequest,
): Promise<BatchPredictionResponse> => {
    const response = await http.post<BatchPredictionResponse>(
        '/api/cases/batch-predict',
        payload,
    )

    return response.data
}
