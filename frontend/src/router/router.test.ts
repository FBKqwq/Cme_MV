// @vitest-environment jsdom

import { describe, expect, it } from 'vitest'

import router from './index'

describe('application routes', () => {
    it('keeps the required diagnosis routes and removes unused pages', () => {
        const paths = router.getRoutes().map((route) => route.path)

        expect(paths).toContain('/')
        expect(paths).toContain('/cases/new')
        expect(paths).toContain('/prediction')
        expect(paths).toContain('/cases/:caseId')
        expect(paths).toContain('/excel-upload')
        expect(paths).toContain('/model-management')
        expect(paths).toContain('/knowledge-review')

        expect(paths).not.toContain('/cases/history')
    })

    it('resolves the default diagnosis page and review page', () => {
        expect(router.resolve('/cases/new').name).toBe('case-create')
        expect(router.resolve('/knowledge-review').name).toBe(
            'knowledge-review',
        )

        const rootRoute = router
            .getRoutes()
            .find((route) => route.path === '/')

        expect(rootRoute?.redirect).toEqual({
            name: 'case-create',
        })
    })
})
