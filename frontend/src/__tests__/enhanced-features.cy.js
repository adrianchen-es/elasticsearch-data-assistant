/*
Frontend Testing Suite for Enhanced Features
Tests mobile responsiveness, conversation management, and mapping display
*/

describe('Mobile Layout and Responsiveness', () => {
  beforeEach(() => {
    cy.viewport('iphone-x')
    cy.visit('/')
  })

  it('should display mobile navigation correctly', () => {
    // Check mobile header is visible
    cy.get('[data-testid="mobile-header"]').should('be.visible')
    
    // Check hamburger menu button
    cy.get('[data-testid="mobile-menu-toggle"]').should('be.visible')
    
    // Test menu toggle functionality
    cy.get('[data-testid="mobile-menu-toggle"]').click()
    cy.get('[data-testid="mobile-menu"]').should('be.visible')
    
    // Test navigation items
    cy.get('[data-testid="nav-chat"]').should('be.visible').click()
    cy.get('[data-testid="nav-query"]').should('be.visible')
    cy.get('[data-testid="nav-health"]').should('be.visible')
  })

  it('should handle provider selection in mobile view', () => {
    cy.get('[data-testid="mobile-menu-toggle"]').click()
    cy.get('[data-testid="mobile-provider-selector"]').should('be.visible')
    
    // Test provider selection
    cy.get('[data-testid="mobile-provider-selector"]').select('azure')
    cy.get('[data-testid="mobile-provider-selector"]').should('have.value', 'azure')
  })

  it('should display compact health indicators', () => {
    cy.get('[data-testid="mobile-health-indicators"]').should('be.visible')
    cy.get('[data-testid="compact-health-status"]').should('contain.text', 'Healthy')
  })
})

describe('Conversation Management', () => {
  beforeEach(() => {
    cy.visit('/')
    // Setup test data in localStorage
    cy.window().then((win) => {
      const testConversations = [
        {
          id: 'test-1',
          title: 'Test Conversation 1',
          timestamp: Date.now() - 3600000, // 1 hour ago
          messages: [
            { role: 'user', content: 'Test message 1' },
            { role: 'assistant', content: 'Test response 1' }
          ],
          isFavorite: false
        },
        {
          id: 'test-2', 
          title: 'Favorite Conversation',
          timestamp: Date.now() - 7200000, // 2 hours ago
          messages: [
            { role: 'user', content: 'Test message 2' },
            { role: 'assistant', content: 'Test response 2' }
          ],
          isFavorite: true
        }
      ]
      win.localStorage.setItem('es_assistant_conversations', JSON.stringify(testConversations))
    })
  })

  it('should display conversation list correctly', () => {
    cy.get('[data-testid="conversation-manager-toggle"]').click()
    cy.get('[data-testid="conversation-list"]').should('be.visible')
    
    // Check conversations are displayed
    cy.get('[data-testid="conversation-item"]').should('have.length', 2)
    cy.get('[data-testid="conversation-item"]').first().should('contain.text', 'Test Conversation 1')
  })

  it('should handle conversation favorites', () => {
    cy.get('[data-testid="conversation-manager-toggle"]').click()
    
    // Toggle favorite on first conversation
    cy.get('[data-testid="conversation-item"]').first()
      .find('[data-testid="favorite-toggle"]').click()
    
    // Check favorite status changed
    cy.get('[data-testid="conversation-item"]').first()
      .find('[data-testid="favorite-toggle"]')
      .should('have.class', 'text-yellow-500')
  })

  it('should delete conversations with confirmation', () => {
    cy.get('[data-testid="conversation-manager-toggle"]').click()
    
    // Click delete on first conversation
    cy.get('[data-testid="conversation-item"]').first()
      .find('[data-testid="delete-conversation"]').click()
    
    // Confirm deletion
    cy.get('[data-testid="delete-confirm"]').click()
    
    // Check conversation was removed
    cy.get('[data-testid="conversation-item"]').should('have.length', 1)
  })

  it('should sort conversations correctly', () => {
    cy.get('[data-testid="conversation-manager-toggle"]').click()
    
    // Test sort by date
    cy.get('[data-testid="sort-select"]').select('date')
    cy.get('[data-testid="conversation-item"]').first()
      .should('contain.text', 'Test Conversation 1') // Most recent first
    
    // Test sort by favorites
    cy.get('[data-testid="sort-select"]').select('favorites')
    cy.get('[data-testid="conversation-item"]').first()
      .should('contain.text', 'Favorite Conversation') // Favorites first
  })
})

describe('Mapping Display Functionality', () => {
  const sampleMapping = {
    properties: {
      title: { type: 'text', analyzer: 'standard' },
      description: { type: 'text' },
      category: { type: 'keyword' },
      price: { type: 'double' },
      created_at: { type: 'date' },
      metadata: {
        properties: {
          tags: { type: 'keyword' },
          content: { type: 'text', analyzer: 'english' }
        }
      }
    }
  }

  beforeEach(() => {
    cy.visit('/')
    cy.intercept('GET', '/api/mapping/*', { fixture: 'sample-mapping.json' }).as('getMapping')
  })

  it('should display mapping fields correctly', () => {
    // Trigger mapping display
    cy.get('[data-testid="chat-input"]').type('Show me the mapping for test-index{enter}')
    
    cy.wait('@getMapping')
    cy.get('[data-testid="mapping-display"]').should('be.visible')
    
    // Check field display
    cy.get('[data-testid="mapping-field"]').should('have.length.greaterThan', 4)
    cy.get('[data-testid="mapping-field"]').first().should('contain.text', 'title')
  })

  it('should handle field search functionality', () => {
    cy.get('[data-testid="chat-input"]').type('Show me the mapping{enter}')
    
    cy.wait('@getMapping')
    cy.get('[data-testid="mapping-search"]').type('meta')
    
    // Should filter to metadata fields only
    cy.get('[data-testid="mapping-field"]:visible').should('have.length.lessThan', 3)
    cy.get('[data-testid="mapping-field"]:visible').should('contain.text', 'metadata')
  })

  it('should copy field paths to clipboard', () => {
    cy.get('[data-testid="chat-input"]').type('Show me the mapping{enter}')
    
    cy.wait('@getMapping')
    cy.get('[data-testid="mapping-field"]').first()
      .find('[data-testid="copy-field-path"]').click()
    
    // Check clipboard content (mocked in test environment)
    cy.window().its('navigator.clipboard.writeText').should('have.been.calledWith', 'title')
  })

  it('should expand and collapse nested fields', () => {
    cy.get('[data-testid="chat-input"]').type('Show me the mapping{enter}')
    
    cy.wait('@getMapping')
    cy.get('[data-testid="expandable-field"][data-field="metadata"]').click()
    
    // Check nested fields are visible
    cy.get('[data-testid="mapping-field"][data-field="metadata.tags"]').should('be.visible')
    cy.get('[data-testid="mapping-field"][data-field="metadata.content"]').should('be.visible')
    
    // Collapse again
    cy.get('[data-testid="expandable-field"][data-field="metadata"]').click()
    cy.get('[data-testid="mapping-field"][data-field="metadata.tags"]').should('not.be.visible')
  })
})

describe('Health Status and Caching', () => {
  beforeEach(() => {
    cy.visit('/')
    // Clear sessionStorage
    cy.window().then((win) => {
      win.sessionStorage.clear()
    })
  })

  it('should cache health status in sessionStorage', () => {
    cy.intercept('GET', '/api/health', { 
      body: { status: 'healthy', elasticsearch: 'connected', ai_service: 'ready' },
      delay: 100
    }).as('getHealth')

    // First load should make API call
    cy.get('[data-testid="health-status"]').should('be.visible')
    cy.wait('@getHealth')

    // Check sessionStorage was populated
    cy.window().then((win) => {
      const cached = win.sessionStorage.getItem('es_assistant_health_status')
      expect(cached).to.not.be.null
      const data = JSON.parse(cached)
      expect(data.status).to.equal('healthy')
      expect(data.timestamp).to.be.a('number')
    })
  })

  it('should use cached health status within TTL', () => {
    // Set up cached data
    cy.window().then((win) => {
      const cacheData = {
        status: 'healthy',
        elasticsearch: 'connected', 
        ai_service: 'ready',
        timestamp: Date.now(),
        ttl: 15 * 60 * 1000 // 15 minutes
      }
      win.sessionStorage.setItem('es_assistant_health_status', JSON.stringify(cacheData))
    })

    cy.intercept('GET', '/api/health', cy.spy().as('healthSpy'))

    // Should use cached data, not make API call
    cy.reload()
    cy.get('[data-testid="health-status"]').should('contain.text', 'Healthy')
    cy.get('@healthSpy').should('not.have.been.called')
  })

  it('should respect manual refresh throttling', () => {
    cy.intercept('GET', '/api/health', { 
      body: { status: 'healthy' },
      delay: 100
    }).as('getHealth')

    // First refresh
    cy.get('[data-testid="manual-refresh"]').click()
    cy.wait('@getHealth')

    // Immediate second refresh should be throttled
    cy.get('[data-testid="manual-refresh"]').click()
    cy.get('[data-testid="throttle-message"]').should('be.visible')
      .and('contain.text', 'Please wait')
  })
})

describe('Provider Management Integration', () => {
  beforeEach(() => {
    cy.visit('/')
    cy.intercept('GET', '/api/providers/status', {
      body: {
        providers: [
          {
            name: 'azure',
            configured: true,
            healthy: true,
            endpoint: 'https://******.openai.azure.com/',
            last_error: null
          },
          {
            name: 'openai', 
            configured: true,
            healthy: false,
            endpoint: 'https://api.openai.com/v1/',
            last_error: 'API key invalid'
          }
        ]
      }
    }).as('getProviders')
  })

  it('should display provider status correctly', () => {
    cy.wait('@getProviders')
    
    cy.get('[data-testid="provider-status"]').should('be.visible')
    cy.get('[data-testid="provider-azure"]').should('contain.text', 'Healthy')
    cy.get('[data-testid="provider-openai"]').should('contain.text', 'Error')
  })

  it('should handle provider selection and fallback', () => {
    cy.wait('@getProviders')
    
    // Select unavailable provider
    cy.get('[data-testid="provider-selector"]').select('openai')
    
    // Should show warning about provider health
    cy.get('[data-testid="provider-warning"]').should('be.visible')
      .and('contain.text', 'selected provider may not be available')
    
    // AI service should fallback to healthy provider
    cy.get('[data-testid="chat-input"]').type('Generate a simple query{enter}')
    cy.get('[data-testid="provider-used"]').should('contain.text', 'azure')
  })
})

describe('Token Management and Error Handling', () => {
  it('should handle token limit errors gracefully', () => {
    cy.intercept('POST', '/api/chat/stream', {
      statusCode: 413,
      body: {
        error: {
          code: 'token_limit_exceeded',
          message: 'Request too large',
          prompt_tokens: 50000,
          limit: 32000,
          model: 'gpt-4'
        }
      }
    }).as('tokenError')

    cy.get('[data-testid="chat-input"]').type('Very long query here...{enter}')
    cy.wait('@tokenError')

    // Should display user-friendly error message
    cy.get('[data-testid="token-error-message"]').should('be.visible')
      .and('contain.text', 'request is too large')
      .and('contain.text', 'try breaking it into smaller parts')

    // Should show token usage details
    cy.get('[data-testid="token-usage"]').should('contain.text', '50,000 tokens')
    cy.get('[data-testid="token-limit"]').should('contain.text', '32,000 limit')
  })

  it('should suggest chunking for large requests', () => {
    // Simulate large mapping or document
    const largeInput = 'Show me details about ' + 'field '.repeat(1000)
    
    cy.get('[data-testid="chat-input"]').type(largeInput)
    
    // Should show chunking suggestion before sending
    cy.get('[data-testid="chunking-suggestion"]').should('be.visible')
      .and('contain.text', 'This request is quite large')
  })
})
