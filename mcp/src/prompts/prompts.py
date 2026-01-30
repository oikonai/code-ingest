"""MCP prompts - Arda Credit domain-specific search patterns."""

from fastmcp import FastMCP


# Define all prompt functions at module level for importability

def search_deal_operations(operation_type: str = "all") -> str:
    """Search for deal management operations in Arda Credit platform.

    Args:
        operation_type: Type of deal operation (origination, payment, transfer, marketplace, all)
    """
    if operation_type == "origination":
        focus = "Deal origination, creation, KYC validation, investor-originator matching"
    elif operation_type == "payment":
        focus = "Deal payment processing, balance updates, transaction tracking"
    elif operation_type == "transfer":
        focus = "Deal ownership transfers, investor changes, transfer validation"
    elif operation_type == "marketplace":
        focus = "Deal listing, marketplace browsing, sale price calculation"
    else:
        focus = "All deal operations including origination, payments, transfers, and marketplace"

    return f"""Find deal management code in Arda Credit platform focusing on: {focus}

Search in arda_code_rust collection for:
- API handlers in api/src/deal_handlers.rs
- Database operations in db/src/
- Transaction types in lib/src/transactions.rs
- Status workflow and validation logic

Search parameters:
- collection: arda_code_rust
- limit: 15
- score_threshold: 0.6

Focus on production-ready implementations with error handling and KYC validation."""


def search_zkproof_implementation() -> str:
    """Search for zero-knowledge proof implementation in Arda Credit."""
    return """Find zero-knowledge proof implementation for privacy-preserving deal operations:

Search Strategy:
1. arda_code_rust collection (limit=20, threshold=0.6):
   - SP1 zkVM program in program/src/main.rs
   - Proof generation in api/src/proof_generation.rs
   - Merkle tree state management in db/src/
   - Batch processing and transaction privacy

2. arda_code_solidity collection (limit=10, threshold=0.7):
   - ARDA.sol contract proof verification
   - State root validation
   - Groth16 proof handling

3. arda_documentation collection (limit=5, threshold=0.5):
   - ZK architecture documentation
   - Privacy guarantees and trust model

Focus on: Sindri integration, batch processing, privacy guarantees."""


def search_authentication_system(auth_type: str = "all") -> str:
    """Search for authentication and KYC system in Arda Credit.
    
    Args:
        auth_type: Type of authentication (magic_link, jwt, sessions, all)
    """
    return """Find authentication, KYC, and user management code:

Search in arda_code_rust collection:
- Magic link authentication in api/src/auth/
- KYC validation and status management
- User registration (investors, originators)
- Session management and JWT tokens
- Email service integration (AWS SES)

Search in arda_code_typescript collection:
- React authentication components
- Auth context and state management
- Magic link verification flow
- KYC status UI components

Parameters: limit=15, threshold=0.6
Focus on: Security patterns, validation, and user flows."""


def search_usdc_integration() -> str:
    """Search for USDC deposit and withdrawal system in Arda Credit."""
    return """Find USDC smart contract integration for deposits and withdrawals:

Search Strategy:
1. arda_code_solidity collection (limit=10, threshold=0.7):
   - MockUSDC contract for testing
   - USDC deposit handling in ARDA contract
   - Withdrawal validation and execution
   - Balance tracking and updates

2. arda_code_rust collection (limit=15, threshold=0.6):
   - Deposit monitoring service
   - Withdrawal processing API
   - Database triggers for balance updates
   - Ethereum client integration

3. arda_code_typescript collection (limit=10, threshold=0.6):
   - MetaMask integration
   - Deposit/withdrawal UI components
   - Transaction confirmation tracking

Focus on: Smart contract interaction, balance validation, transaction monitoring."""


def search_frontend_feature(feature_name: str) -> str:
    """Search for frontend React components and features in Arda Credit App.

    Args:
        feature_name: Feature to search for (dashboard, deals, portfolio, profile, etc.)
    """
    return f"""Find React frontend implementation for: {feature_name}

Search in arda_code_typescript collection:
- Component structure in src/components/{feature_name}/
- Page components in src/pages/
- State management with React Query
- Form handling with React Hook Form + Zod
- shadcn/ui components integration
- Routing with React Router v6

Search parameters:
- limit: 15
- threshold: 0.6

Focus on: Component architecture, type safety, error handling, and UX patterns."""


def debug_arda_issue(issue_description: str) -> str:
    """Debug-focused search across Arda Credit codebase.

    Args:
        issue_description: Description of the bug or issue to investigate
    """
    return f"""Debug search for Arda Credit issue: {issue_description}

Multi-collection search strategy:
1. arda_code_rust (limit=20, threshold=0.4): Backend error handling
2. arda_code_typescript (limit=15, threshold=0.4): Frontend error boundaries
3. arda_code_solidity (limit=10, threshold=0.5): Contract revert conditions
4. arda_documentation (limit=5, threshold=0.4): Known issues and troubleshooting

Look for:
- Similar error patterns and exception handling
- Related function implementations that might cause this
- Test cases covering this scenario
- Documentation about this feature area
- Recent changes that could be related

Use lower threshold to cast wide net for debugging."""


def explore_architecture_layer(layer: str = "all") -> str:
    """Explore architectural layer (presentation, business, data, blockchain).

    Args:
        layer: Architectural layer to explore (presentation, business, data, blockchain, all)
    """
    if layer == "presentation":
        return """Explore Arda Credit presentation layer (UI/UX):

Search in arda_code_typescript collection:
- React components in src/components/
- Page components in src/pages/
- UI state management (React Query, Context)
- Form handling (React Hook Form, Zod validation)
- shadcn/ui component usage
- Routing and navigation (React Router)

Parameters: limit=20, threshold=0.6
Focus on: Component architecture, user flows, accessibility, responsive design"""
    
    elif layer == "business":
        return """Explore Arda Credit business logic layer:

Search in arda_code_rust collection:
- API handlers in api/src/
- Business logic in lib/src/
- Deal lifecycle management
- KYC validation and rules
- Payment processing logic
- Transaction validation
- User role management

Parameters: limit=20, threshold=0.6
Focus on: Business rules, validation, workflows, state machines"""
    
    elif layer == "data":
        return """Explore Arda Credit data layer:

Search in arda_code_rust collection:
- Database schemas in db/src/
- Repository pattern implementations
- Query builders and ORMs
- Database migrations
- Data validation and constraints
- Indexing strategies

Parameters: limit=20, threshold=0.6
Focus on: Data models, persistence, consistency, transactions"""
    
    elif layer == "blockchain":
        return """Explore Arda Credit blockchain layer:

Search Strategy:
1. arda_code_solidity (limit=15, threshold=0.7):
   - Smart contracts (ARDA.sol, MockUSDC.sol)
   - State root management
   - Proof verification
   - USDC deposit/withdrawal

2. arda_code_rust (limit=15, threshold=0.6):
   - SP1 zkVM program (program/src/)
   - Proof generation
   - Ethereum client integration
   - Transaction monitoring

Parameters: Focus on privacy, security, gas optimization"""
    
    else:  # "all"
        return """Explore entire Arda Credit architecture:

Multi-layer search strategy:
1. Presentation Layer (arda_code_typescript, limit=10):
   - Components, pages, UI state

2. Business Layer (arda_code_rust, limit=15):
   - API handlers, business logic, workflows

3. Data Layer (arda_code_rust, limit=10):
   - Database schemas, repositories, queries

4. Blockchain Layer (arda_code_solidity + rust, limit=10):
   - Smart contracts, ZK proofs, Ethereum integration

Use this to understand how features flow through all layers."""


def find_api_endpoint(endpoint_pattern: str) -> str:
    """Find API endpoint implementation across the stack.

    Args:
        endpoint_pattern: API endpoint pattern (e.g., "/deals", "/auth", "/deposits")
    """
    return f"""Find API endpoint implementation: {endpoint_pattern}

Search Strategy:
1. Backend Implementation (arda_code_rust, limit=15, threshold=0.65):
   - Route handlers in api/src/
   - HTTP method implementations (GET, POST, PUT, DELETE)
   - Request/response types
   - Middleware and authentication
   - Error handling

2. Frontend API Calls (arda_code_typescript, limit=10, threshold=0.6):
   - API client functions
   - React Query hooks
   - Request/response handling
   - Error boundaries

3. API Documentation (arda_documentation, limit=5, threshold=0.6):
   - OpenAPI/Swagger specs
   - API contract documentation
   - Example requests/responses

Focus on: Complete request flow from frontend → backend → database"""


def trace_data_flow(entity: str) -> str:
    """Trace data flow for an entity through the stack.

    Args:
        entity: Entity name (User, Deal, Transaction, Balance, etc.)
    """
    return f"""Trace {entity} data flow through Arda Credit stack:

Multi-layer search strategy:

1. Database Schema (arda_code_rust, limit=10, threshold=0.65):
   - Table definition for {entity}
   - Columns, constraints, indexes
   - Foreign key relationships
   - Database migrations

2. Backend Handlers (arda_code_rust, limit=15, threshold=0.65):
   - API handlers for {entity} operations
   - CRUD operations (Create, Read, Update, Delete)
   - Business logic and validation
   - Repository pattern usage

3. Frontend Components (arda_code_typescript, limit=10, threshold=0.6):
   - {entity} display components
   - Forms for {entity} creation/editing
   - State management (queries, mutations)
   - Type definitions

4. Smart Contracts (arda_code_solidity, limit=5, threshold=0.6):
   - On-chain {entity} representation
   - Events related to {entity}

This gives you the complete lifecycle: Database → Backend → Frontend → Blockchain"""


def find_test_coverage(feature: str) -> str:
    """Find test coverage for a feature.

    Args:
        feature: Feature name or component to find tests for
    """
    return f"""Find test coverage for: {feature}

Search Strategy:
1. Unit Tests (arda_code_rust, limit=15, threshold=0.6):
   - Test files in test/ directories
   - Function-level tests with #[test] annotations
   - Mock implementations
   - Edge case coverage

2. Integration Tests (arda_code_typescript, limit=10, threshold=0.6):
   - .test.ts or .spec.ts files
   - Component testing (React Testing Library)
   - API integration tests
   - E2E test scenarios

3. Smart Contract Tests (arda_code_solidity, limit=10, threshold=0.65):
   - Foundry tests (test/)
   - Contract interaction tests
   - Gas optimization tests
   - Security tests (attack vectors)

Focus on: Test coverage percentage, missing test cases, test quality"""


def explore_deployment_config(service: str = "all") -> str:
    """Explore deployment configuration for a service.

    Args:
        service: Service name (arda-credit, arda-platform, etc.) or "all"
    """
    return f"""Explore deployment configuration for: {service}

Search in arda_deployment collection:
- Kubernetes manifests (Deployment, Service, ConfigMap)
- Helm charts and values files
- Environment configurations (dev, staging, production)
- Resource limits (CPU, memory)
- Replica counts and scaling policies
- Service networking and ingress rules
- Secrets and config management
- Health checks and probes

Parameters: limit=20, threshold=0.6
Focus on: Infrastructure as Code, environment parity, scaling strategy"""


def audit_security_patterns(concern: str = "all") -> str:
    """Audit security implementations across the codebase.

    Args:
        concern: Security concern (authentication, authorization, encryption, validation, all)
    """
    if concern == "authentication":
        focus = """Authentication security:
- Password/credential handling
- Magic link token security
- Session management
- JWT token validation
- Multi-factor authentication"""
    
    elif concern == "authorization":
        focus = """Authorization security:
- Role-based access control (RBAC)
- Permission checks
- Resource ownership validation
- API endpoint protection
- Admin privilege escalation prevention"""
    
    elif concern == "encryption":
        focus = """Encryption security:
- Data encryption at rest
- TLS/SSL for data in transit
- Key management
- Secure random number generation
- Cryptographic libraries usage"""
    
    elif concern == "validation":
        focus = """Input validation security:
- SQL injection prevention
- XSS protection
- CSRF tokens
- Input sanitization
- Type checking and schema validation"""
    
    else:  # "all"
        focus = """All security patterns:
- Authentication mechanisms
- Authorization controls
- Encryption implementation
- Input validation
- Error handling (no info leakage)
- Security headers
- Rate limiting
- Audit logging"""
    
    return f"""Security audit for Arda Credit: {concern}

{focus}

Search Strategy:
1. Backend Security (arda_code_rust, limit=20, threshold=0.65):
   - Security middleware
   - Authentication/authorization logic
   - Input validation functions
   - Cryptographic operations

2. Frontend Security (arda_code_typescript, limit=15, threshold=0.6):
   - Client-side validation
   - Secure storage (tokens, sensitive data)
   - XSS prevention
   - CSRF protection

3. Smart Contract Security (arda_code_solidity, limit=10, threshold=0.7):
   - Access control modifiers
   - Reentrancy guards
   - Integer overflow checks
   - Front-running protection

Focus on: OWASP Top 10, industry best practices, compliance requirements"""


def register_prompts(mcp: FastMCP):
    """Register all prompt functions with the MCP server."""
    mcp.prompt()(search_deal_operations)
    mcp.prompt()(search_zkproof_implementation)
    mcp.prompt()(search_authentication_system)
    mcp.prompt()(search_usdc_integration)
    mcp.prompt()(search_frontend_feature)
    mcp.prompt()(debug_arda_issue)
    mcp.prompt()(explore_architecture_layer)
    mcp.prompt()(find_api_endpoint)
    mcp.prompt()(trace_data_flow)
    mcp.prompt()(find_test_coverage)
    mcp.prompt()(explore_deployment_config)
    mcp.prompt()(audit_security_patterns)
