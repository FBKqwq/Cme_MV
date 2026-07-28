// @vitest-environment jsdom

import { describe, expect, it } from 'vitest'

import router from './index'

describe('application routes', () => {
    it('keeps diagnosis routes and adds an independent review page', () => {
        const paths = router.getRoutes().map((route) => route.path)

        expect(paths).toContain('/')
        expect(paths).toContain('/cases/new')
        expect(paths).toContain('/prediction')
        expect(paths).toContain('/cases/history')
        expect(paths).toContain('/cases/:caseId')
        expect(paths).toContain('/excel-upload')
        expect(paths).toContain('/model-management')
        expect(paths).toContain('/knowledge-review')
    })

    it('resolves module switch targets', () => {
        expect(router.resolve('/').name).toBe('home')
        expect(router.resolve('/knowledge-review').name).toBe(
            'knowledge-review',
        )
    })
})
