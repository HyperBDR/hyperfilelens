import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../lib/api'
import {
  createPlatformOpsUser,
  listPlatformOpsOrganizations,
  listPlatformOpsUsers,
} from './platformOpsUserApi'

vi.mock('../../lib/api', () => ({
  api: vi.fn(),
}))

afterEach(() => {
  vi.clearAllMocks()
})

describe('Admin Account Management API', () => {
  it('sends user filters to the platform operations endpoint', async () => {
    vi.mocked(api).mockResolvedValue({
      count: 0,
      page: 1,
      page_size: 20,
      results: [],
      stats: { total: 0, active: 0, inactive: 0, never_signed_in: 0 },
    })

    await listPlatformOpsUsers({
      page: 2,
      page_size: 50,
      search: 'acme owner',
      status: 'active',
      account_type: 'customer',
    })

    expect(api).toHaveBeenCalledWith(
      '/api/v1/platform-ops/users?page=2&page_size=50&search=acme+owner&status=active&account_type=customer',
    )
  })

  it('creates the customer and organization in one request', async () => {
    vi.mocked(api).mockResolvedValue({ id: 17, email: 'owner@example.com' })

    await createPlatformOpsUser({
      email: 'owner@example.com',
      password: 'Password123',
      organization_name: 'Example Customer',
      is_staff: false,
    })

    expect(api).toHaveBeenCalledWith('/api/v1/platform-ops/users', {
      method: 'POST',
      body: JSON.stringify({
        email: 'owner@example.com',
        password: 'Password123',
        organization_name: 'Example Customer',
        is_staff: false,
      }),
    })
  })

  it('sends organization health filters to the platform operations endpoint', async () => {
    vi.mocked(api).mockResolvedValue({
      count: 0,
      page: 1,
      page_size: 20,
      results: [],
      stats: { total: 0, active: 0, inactive: 0, with_incidents: 0 },
    })

    await listPlatformOpsOrganizations({
      search: 'owner@example.com',
      status: 'active',
      health: 'attention',
    })

    expect(api).toHaveBeenCalledWith(
      '/api/v1/platform-ops/orgs?search=owner%40example.com&status=active&health=attention',
    )
  })
})
