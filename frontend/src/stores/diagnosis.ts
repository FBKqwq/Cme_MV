import { defineStore } from 'pinia'

import {
    createAnnotation,
    createCaseAndPrediction,
    type AnnotationCreatePayload,
    type AnnotationResponse,
    type CaseCreatePayload,
    type CasePredictionResponse,
} from '../api/diagnosis'

interface DiagnosisState {
    currentResult: CasePredictionResponse | null
    currentAnnotation: AnnotationResponse | null
    loading: boolean
}

const STORAGE_KEY = 'hospital-current-prediction'

export const useDiagnosisStore = defineStore('diagnosis', {
    state: (): DiagnosisState => ({
        currentResult: null,
        currentAnnotation: null,
        loading: false,
    }),

    actions: {
        async predictCase(
            payload: CaseCreatePayload,
        ): Promise<CasePredictionResponse> {
            this.loading = true

            try {
                const result = await createCaseAndPrediction(
                    payload,
                )

                this.currentResult = result
                this.currentAnnotation = null

                localStorage.setItem(
                    STORAGE_KEY,
                    JSON.stringify(result),
                )

                return result
            } finally {
                this.loading = false
            }
        },

        async submitAnnotation(
            payload: AnnotationCreatePayload,
        ): Promise<AnnotationResponse> {
            if (!this.currentResult) {
                throw new Error('当前没有预测病例')
            }

            this.loading = true

            try {
                const annotation = await createAnnotation(
                    this.currentResult.case.id,
                    payload,
                )

                this.currentAnnotation = annotation

                return annotation
            } finally {
                this.loading = false
            }
        },

        restore(): void {
            const saved = localStorage.getItem(STORAGE_KEY)

            if (!saved) {
                return
            }

            try {
                this.currentResult = JSON.parse(
                    saved,
                ) as CasePredictionResponse
            } catch {
                localStorage.removeItem(STORAGE_KEY)
            }
        },

        clear(): void {
            this.currentResult = null
            this.currentAnnotation = null
            localStorage.removeItem(STORAGE_KEY)
        },
    },
})