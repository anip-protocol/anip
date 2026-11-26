import { describe, it, expect, vi } from 'vitest'
import { createTokenResolver, isDelegationToken } from '../credentials'

const JWT = 'eyJhbGciOiJFUzI1NiJ9.eyJzdWIiOiJhZ2VudCJ9.c2lnbmF0dXJl'

function setup(opts: { expires?: string; now?: () => number } = {}) {
  const issueCapabilityToken = vi.fn(async (_key: string, capability: string, _scope: string[]) => ({
    issued: true,
    tokenId: `tok-${capability}`,
    token: `${JWT}-${capability}-${issueCapabilityToken.mock.calls.length}`,
    expires: opts.expires ?? '2099-01-01T00:00:00Z',
  }))
  const scopes: Record<string, string[]> = {
    search_flights: ['travel.search'],
    book_flight: ['travel.book'],
  }
  const resolver = createTokenResolver(
    { issueCapabilityToken },
    async (capability) => scopes[capability],
    opts.now,
  )
  return { resolver, issueCapabilityToken }
}

describe('isDelegationToken', () => {
  it('recognises a JWT', () => {
    expect(isDelegationToken(JWT)).toBe(true)
    expect(isDelegationToken(`  ${JWT}  `)).toBe(true)
  })

  it('does not take an API key for a token', () => {
    expect(isDelegationToken('demo-human-key')).toBe(false)
    expect(isDelegationToken('a.b')).toBe(false)
    expect(isDelegationToken('a..c')).toBe(false)
    expect(isDelegationToken('')).toBe(false)
  })
})

describe('createTokenResolver', () => {
  it('uses a pasted delegation token as it is, without issuing one', async () => {
    const { resolver, issueCapabilityToken } = setup()

    const resolved = await resolver.resolve(JWT, 'search_flights')

    expect(resolved).toEqual({ token: JWT })
    expect(issueCapabilityToken).not.toHaveBeenCalled()
  })

  it('exchanges an API key for a token bound to the capability, with its minimum scope', async () => {
    const { resolver, issueCapabilityToken } = setup()

    const resolved = await resolver.resolve('demo-human-key', 'book_flight')

    expect(issueCapabilityToken).toHaveBeenCalledWith('demo-human-key', 'book_flight', ['travel.book'])
    expect(resolved.token).toContain('book_flight')
    expect(resolved.issuedFor).toEqual({ capability: 'book_flight', scope: ['travel.book'] })
  })

  it('reuses an issued token for the same key and capability until it is about to expire', async () => {
    let now = Date.parse('2026-01-01T00:00:00Z')
    const { resolver, issueCapabilityToken } = setup({
      expires: '2026-01-01T00:10:00Z',
      now: () => now,
    })

    const first = await resolver.resolve('demo-human-key', 'search_flights')
    const second = await resolver.resolve('demo-human-key', 'search_flights')
    expect(second.token).toBe(first.token)
    expect(issueCapabilityToken).toHaveBeenCalledTimes(1)

    now = Date.parse('2026-01-01T00:09:30Z') // inside the refresh margin
    const third = await resolver.resolve('demo-human-key', 'search_flights')
    expect(third.token).not.toBe(first.token)
    expect(issueCapabilityToken).toHaveBeenCalledTimes(2)
  })

  it('issues a separate token per capability, because a token is bound to one', async () => {
    const { resolver, issueCapabilityToken } = setup()

    const search = await resolver.resolve('demo-human-key', 'search_flights')
    const book = await resolver.resolve('demo-human-key', 'book_flight')

    expect(search.token).not.toBe(book.token)
    expect(issueCapabilityToken).toHaveBeenCalledTimes(2)
  })

  it('issues a new token after clear()', async () => {
    const { resolver, issueCapabilityToken } = setup()

    await resolver.resolve('demo-human-key', 'search_flights')
    resolver.clear()
    await resolver.resolve('demo-human-key', 'search_flights')

    expect(issueCapabilityToken).toHaveBeenCalledTimes(2)
  })

  it('needs a capability to exchange an API key', async () => {
    const { resolver, issueCapabilityToken } = setup()

    await expect(resolver.resolve('demo-human-key', null)).rejects.toThrow(/Choose a capability/)
    expect(issueCapabilityToken).not.toHaveBeenCalled()
  })

  it('refuses a capability the service does not declare', async () => {
    const { resolver, issueCapabilityToken } = setup()

    await expect(resolver.resolve('demo-human-key', 'cancel_flight')).rejects.toThrow(/cancel_flight/)
    expect(issueCapabilityToken).not.toHaveBeenCalled()
  })

  it('passes on the service refusing the key', async () => {
    const { resolver, issueCapabilityToken } = setup()
    issueCapabilityToken.mockRejectedValueOnce(new Error('authentication_required'))

    await expect(resolver.resolve('wrong-key', 'search_flights')).rejects.toThrow('authentication_required')
  })
})
