import {
    createRouter,
    createWebHistory,
    type RouteRecordRaw,
} from 'vue-router'

const diagnosisRoutes: RouteRecordRaw[] = [
    {
        path: '/cases/new',
        name: 'case-create',
        component: () => import('../views/CaseCreateView.vue'),
    },
    {
        path: '/prediction',
        name: 'prediction',
        component: () => import('../views/PredictionView.vue'),
    },
    {
        path: '/cases/:caseId',
        name: 'case-detail',
        component: () => import('../views/CaseDetailView.vue'),
        props: true,
    },
    {
        path: '/excel-upload',
        name: 'excel-upload',
        component: () => import('../views/ExcelUploadView.vue'),
    },
    {
        path: '/model-management',
        name: 'model-management',
        component: () => import('../views/ModelManagementView.vue'),
    },
]

const routes: RouteRecordRaw[] = [
    {
        path: '/',
        component: () => import('../layouts/DiagnosisLayout.vue'),
        redirect: {
            name: 'case-create',
        },
        children: diagnosisRoutes,
    },
    {
        path: '/knowledge-review',
        name: 'knowledge-review',
        component: () => import('../views/KnowledgeReviewView.vue'),
    },
    {
        path: '/:pathMatch(.*)*',
        redirect: {
            name: 'case-create',
        },
    },
]

const router = createRouter({
    history: createWebHistory(import.meta.env.BASE_URL),
    routes,
})

export default router
