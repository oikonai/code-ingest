"""MCP resources - Arda Credit documentation and catalogs."""

import logging
from datetime import datetime
from fastmcp import FastMCP

logger = logging.getLogger(__name__)

# These will be set by the server module
_list_collections_impl = None
_semantic_search_impl = None
_get_deployed_services_impl = None
_query_cache = None


def set_resource_dependencies(list_collections_fn, semantic_search_fn, deployed_services_fn, query_cache):
    """
    Set function dependencies needed by resources.
    
    Args:
        list_collections_fn: Function to list collections
        semantic_search_fn: Function to perform semantic search
        deployed_services_fn: Function to get deployed services
        query_cache: Query cache instance
    """
    global _list_collections_impl, _semantic_search_impl, _get_deployed_services_impl, _query_cache
    _list_collections_impl = list_collections_fn
    _semantic_search_impl = semantic_search_fn
    _get_deployed_services_impl = deployed_services_fn
    _query_cache = query_cache


# Define all resource functions at module level for importability
async def arda_collections_info() -> str:
    """Information about Arda Credit specific vector collections (dynamically fetched from GitHub)."""
    from src.utils.github import get_cached_repo_structures, analyze_directory_structure
    
    repos = await get_cached_repo_structures()

    if not repos:
        # Fallback to static content if GitHub fetch fails
        return """# Arda Credit Vector Collections

⚠️ Unable to fetch live repository data. Using fallback information.

## arda_code_rust
Rust backend for Arda Credit privacy-preserving deal platform

## arda_code_typescript
React frontend for Arda Credit platform

## arda_code_solidity
Solidity smart contracts for Arda Credit

## arda_documentation
Architecture docs, API specs, deployment guides
"""

    arda_credit = repos.get('arda_credit', {})
    arda_platform = repos.get('arda_platform', {})

    # Generate dynamic content
    output = "# Arda Credit Vector Collections\n\n"
    output += f"_Last updated: {arda_credit.get('updated_at', 'Unknown')}_\n\n"

    # arda_code_rust section
    output += "## arda_code_rust\n"
    output += f"{arda_credit.get('description', 'Rust backend for Arda Credit')}\n\n"

    if arda_credit.get('tree'):
        structure = analyze_directory_structure(arda_credit['tree'])
        output += "**Key Components:**\n"
        if structure['api']:
            output += f"- `api/` - REST API ({len(structure['api'])} files)\n"
        if structure['database']:
            output += f"- `db/` - Database layer ({len(structure['database'])} files)\n"
        if structure['utils']:
            output += f"- `lib/` - Shared utilities ({len(structure['utils'])} files)\n"
        if structure['tests']:
            output += f"- `test/` - Test suite ({len(structure['tests'])} files)\n"

    output += f"\n**Technology:** {arda_credit.get('language', 'Rust')}\n"
    output += f"**Repository:** github.com/{arda_credit.get('owner', 'ardaglobal')}/{arda_credit.get('name', 'arda-credit')}\n\n"

    # arda_code_typescript section (from arda-platform repo)
    output += "## arda_code_typescript\n"
    output += f"{arda_platform.get('description', 'Arda Platform - Full-stack application')}\n\n"

    if arda_platform.get('tree'):
        structure = analyze_directory_structure(arda_platform['tree'])
        output += "**Key Components:**\n"
        if structure['components']:
            output += f"- `src/components/` - React components ({len(structure['components'])} files)\n"
        if structure['frontend']:
            output += f"- `src/pages/` - Page components ({len(structure['frontend'])} files)\n"
        if structure['utils']:
            output += f"- `src/utils/` - Utilities ({len(structure['utils'])} files)\n"

    output += f"\n**Technology:** {arda_platform.get('language', 'TypeScript')}\n"
    output += f"**Repository:** github.com/{arda_platform.get('owner', 'ardaglobal')}/{arda_platform.get('name', 'arda-platform')}\n\n"

    # Static sections for Solidity and docs
    output += """## arda_code_solidity
Solidity smart contracts for Arda Credit

**Key Components:**
- `src/ARDA.sol` - Main contract for proof verification
- `test/mocks/MockUSDC.sol` - USDC mock for local testing

**Technology:** Solidity 0.8.28, Foundry, SP1 Groth16 verifier

## arda_documentation
Architecture docs, API specs, deployment guides

**Key Topics:**
- Three-component architecture (contracts, zkVM, web server)
- Deal system design and workflows
- Privacy guarantees and ZK properties
"""

    return output


async def arda_search_best_practices() -> str:
    """Best practices for searching Arda Credit codebase (with live repository insights)."""
    from src.utils.github import get_cached_repo_structures, analyze_directory_structure
    
    repos = await get_cached_repo_structures()

    output = """# Arda Credit Search Best Practices

_Tips are enhanced with live repository structure from GitHub_
"""

    # Add repository-specific tips if available
    if repos:
        arda_credit = repos.get('arda_credit', {})
        arda_platform = repos.get('arda_platform', {})

        if arda_credit.get('tree'):
            structure = analyze_directory_structure(arda_credit['tree'])
            output += f"\n## Live Repository Stats (arda-credit)\n"
            output += f"- API files: {len(structure['api'])}\n"
            output += f"- Database files: {len(structure['database'])}\n"
            output += f"- Test files: {len(structure['tests'])}\n"
            output += f"- Last updated: {arda_credit.get('updated_at', 'Unknown')}\n"

        if arda_platform.get('tree'):
            structure = analyze_directory_structure(arda_platform['tree'])
            output += f"\n## Live Repository Stats (arda-platform)\n"
            output += f"- Component files: {len(structure['components'])}\n"
            output += f"- Page files: {len(structure['frontend'])}\n"
            output += f"- Utility files: {len(structure['utils'])}\n"
            output += f"- Last updated: {arda_platform.get('updated_at', 'Unknown')}\n"

    output += """

## Collection Selection Guide

### arda_code_rust (Backend)
**Use when searching for:**
- API endpoints and handlers
- Database operations and migrations
- Deal lifecycle management
- ZK proof generation
- Authentication and KYC logic
- Ethereum client integration

**Key directories:**
- `api/src/` - REST API handlers
- `db/src/` - Database layer
- `program/src/` - SP1 zkVM program
- `lib/src/` - Shared business logic

### arda_code_typescript (Frontend)
**Use when searching for:**
- React components and pages
- UI/UX implementations
- State management (React Query)
- Form handling and validation
- MetaMask integration
- Frontend utilities

**Key directories:**
- `src/components/` - React components
- `src/pages/` - Route components
- `src/utils/` - Helper functions
- `src/types/` - TypeScript types

### arda_code_solidity (Smart Contracts)
**Use when searching for:**
- Contract implementations
- Proof verification logic
- USDC deposit/withdrawal
- State root management
- Event definitions

**Key files:**
- `src/ARDA.sol` - Main contract
- `test/mocks/MockUSDC.sol` - USDC mock
- `script/Deploy.s.sol` - Deployment

### arda_documentation
**Use when searching for:**
- Architecture decisions
- API specifications
- Deployment guides
- Security best practices
- Development workflows

## Query Formulation Tips

### For Backend Features
Good: "deal origination API handler with KYC validation and balance checking"
Bad: "deal api"

### For Frontend Components
Good: "React component for displaying investor portfolio with deal status cards"
Bad: "portfolio component"

### For Smart Contracts
Good: "USDC deposit event handling and balance update in ARDA contract"
Bad: "deposit function"

## Parameter Tuning

### High Precision (Exact Match)
- limit: 5-10
- threshold: 0.7-0.8
- Use for: Finding specific functions or components

### Broad Exploration
- limit: 20-30
- threshold: 0.4-0.5
- Use for: Understanding feature implementation, debugging

### Balanced (Recommended)
- limit: 10-15
- threshold: 0.6
- Use for: General code exploration

## Multi-Collection Search Strategy

For full-stack features, search in order:
1. **Backend first** (arda_code_rust): Understand API and business logic
2. **Frontend** (arda_code_typescript): Find UI implementation
3. **Smart Contracts** (arda_code_solidity): Check on-chain integration
4. **Documentation** (arda_documentation): Verify design intent
"""

    return output


async def collection_health_dashboard() -> str:
    """Real-time collection health metrics and status overview."""
    try:
        # Get all collections
        collections_data = _list_collections_impl()
        
        output = f"""# Arda Collections Health Dashboard

_Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}_

## Status Overview
"""
        
        # Count collections by type
        by_type = collections_data.get('by_type', {})
        total = collections_data.get('total_collections', 0)
        
        output += f"- **Total Collections**: {total}\n"
        output += f"- **Language Collections**: {len(by_type.get('language', []))}\n"
        output += f"- **Service Collections**: {len(by_type.get('service', []))}\n"
        output += f"- **Repository Collections**: {len(by_type.get('repo', []))}\n"
        output += f"- **Concern Collections**: {len(by_type.get('concern', []))}\n"
        
        # Identify empty collections
        empty_collections = []
        all_collections = []
        for type_name, collections in by_type.items():
            for coll in collections:
                all_collections.append(coll)
                if coll.get('points_count', 0) == 0:
                    empty_collections.append(coll['name'])
        
        output += f"\n## Health Metrics\n"
        output += f"- **Empty Collections**: {len(empty_collections)}\n"
        output += f"- **Populated Collections**: {total - len(empty_collections)}\n"
        
        if empty_collections:
            output += f"\n### ⚠️ Empty Collections (Need Ingestion)\n"
            for coll_name in empty_collections:
                output += f"- {coll_name}\n"
        
        # Show collection sizes
        output += f"\n## Collection Sizes\n"
        sorted_collections = sorted(all_collections, key=lambda x: x.get('points_count', 0), reverse=True)
        for coll in sorted_collections[:10]:  # Top 10
            name = coll['name']
            count = coll.get('points_count', 0)
            status = coll.get('status', 'unknown')
            output += f"- **{name}**: {count:,} vectors ({status})\n"
        
        # Action items
        output += f"\n## Action Items\n"
        if empty_collections:
            output += f"1. 🔴 **Critical**: Ingest data into {len(empty_collections)} empty collections\n"
        else:
            output += f"1. ✅ All collections populated\n"
        
        if total < 10:
            output += f"2. ⚠️ **Low collection count**: Consider adding more specialized collections\n"
        
        output += f"3. 💡 **Tip**: Run `refresh_repo_cache()` to update live repository stats\n"
        
        # Cache stats
        cache_stats = _query_cache.get_stats()
        output += f"\n## Query Cache Performance\n"
        output += f"- **Cache Size**: {cache_stats['size']}/{cache_stats['max_size']}\n"
        output += f"- **Hit Rate**: {cache_stats['hit_rate_percent']:.1f}%\n"
        output += f"- **Total Hits**: {cache_stats['hits']}\n"
        output += f"- **Total Misses**: {cache_stats['misses']}\n"
        
        return output
        
    except Exception as e:
        logger.error(f"Failed to generate dashboard: {e}")
        return f"""# Arda Collections Health Dashboard

⚠️ **Error generating dashboard**: {str(e)}

Please check:
- Qdrant connection is healthy
- Collections are accessible
- Server is properly initialized
"""


async def api_endpoint_catalog() -> str:
    """Complete catalog of all API endpoints across Arda services."""
    try:
        output = """# Arda API Endpoint Catalog

_Automatically extracted from codebase_

"""
        
        # Search for API endpoints in backend code
        try:
            api_results = await _semantic_search_impl(
                query="API endpoint route handler HTTP method",
                collection_name="arda_code_rust",
                limit=50,
                score_threshold=0.6
            )
            
            # Group endpoints by category
            endpoints_by_category = {
                "Authentication": [],
                "Deals": [],
                "Users": [],
                "Deposits & Withdrawals": [],
                "Transactions": [],
                "Other": []
            }
            
            for result in api_results.get('results', []):
                payload = result.get('payload', {})
                item_name = payload.get('item_name', '')
                file_path = payload.get('file_path', '')
                preview = payload.get('content_preview', '')[:200]
                
                # Categorize endpoint
                if 'auth' in item_name.lower() or 'auth' in file_path.lower():
                    category = "Authentication"
                elif 'deal' in item_name.lower() or 'deal' in file_path.lower():
                    category = "Deals"
                elif 'user' in item_name.lower() or 'user' in file_path.lower():
                    category = "Users"
                elif 'deposit' in item_name.lower() or 'withdraw' in item_name.lower():
                    category = "Deposits & Withdrawals"
                elif 'transaction' in item_name.lower() or 'tx' in item_name.lower():
                    category = "Transactions"
                else:
                    category = "Other"
                
                endpoint_info = {
                    "name": item_name,
                    "file": file_path,
                    "preview": preview
                }
                endpoints_by_category[category].append(endpoint_info)
            
            # Format output
            for category, endpoints in endpoints_by_category.items():
                if endpoints:
                    output += f"\n## {category} Endpoints\n\n"
                    for ep in endpoints[:10]:  # Limit to 10 per category
                        output += f"### `{ep['name']}`\n"
                        output += f"- **File**: `{ep['file']}`\n"
                        output += f"- **Preview**: {ep['preview']}...\n\n"
        
        except Exception as e:
            logger.warning(f"Failed to extract API endpoints from arda_code_rust: {e}")
            output += "\n⚠️ Could not automatically extract endpoints from backend code.\n"
        
        # Add static known endpoints from documentation
        output += """

## Known Core Endpoints (from documentation)

### Authentication
- `POST /auth/magic-link` - Request magic link
- `GET /auth/verify` - Verify magic link token
- `POST /auth/logout` - End user session

### Deals
- `GET /deals` - List all deals
- `POST /deals` - Create new deal
- `GET /deals/:id` - Get deal details
- `PUT /deals/:id` - Update deal
- `POST /deals/:id/transfer` - Transfer deal ownership

### Users
- `GET /users/me` - Get current user profile
- `PUT /users/me` - Update user profile
- `GET /users/:id/kyc` - Get KYC status

### Deposits & Withdrawals
- `POST /deposits` - Create deposit
- `GET /deposits/:id` - Get deposit status
- `POST /withdrawals` - Request withdrawal
- `GET /withdrawals/:id` - Get withdrawal status

### Transactions
- `GET /transactions` - List transactions
- `GET /transactions/:id` - Get transaction details

---

**Note**: This catalog is dynamically generated from code search. For complete API documentation, refer to OpenAPI specs in the `arda_documentation` collection.
"""
        
        return output
        
    except Exception as e:
        logger.error(f"Failed to generate API catalog: {e}")
        return f"# Arda API Endpoint Catalog\n\n⚠️ **Error**: {str(e)}"


async def code_patterns_library() -> str:
    """Library of common code patterns used in Arda Credit."""
    return """# Arda Code Patterns Library

_Common patterns and best practices across the Arda codebase_

## Error Handling Patterns

### Rust (Backend)
```rust
// anyhow::Result pattern for error propagation
use anyhow::{Context, Result};

pub async fn process_deal(deal_id: i64) -> Result<Deal> {
    let deal = db.get_deal(deal_id)
    .await
    .context("Failed to fetch deal from database")?;
    
    validate_deal(&deal)
    .context("Deal validation failed")?;
    
    Ok(deal)
}
```

### TypeScript (Frontend)
```typescript
// Error boundaries for React components
class ErrorBoundary extends React.Component {
  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    logErrorToService(error, errorInfo);
  }
  
  render() {
    if (this.state.hasError) {
      return <ErrorFallback />;
    }
    return this.props.children;
  }
}

// Try-catch with toast notifications
try {
  await createDeal(dealData);
  toast.success("Deal created successfully");
} catch (error) {
  toast.error(`Failed to create deal: ${error.message}`);
}
```

## Authentication Patterns

### Magic Link Flow
1. **Request Magic Link** (Backend)
   ```rust
   // Generate secure token
   let token = generate_magic_link_token(&user.email);
   
   // Store token with expiration
   cache.set_with_ttl(token, user.id, Duration::minutes(15));
   
   // Send email via AWS SES
   email_service.send_magic_link(user.email, token).await?;
   ```

2. **Verify Token** (Backend)
   ```rust
   // Validate token and create session
   let user_id = cache.get(token).context("Token expired or invalid")?;
   let session = create_session(user_id).await?;
   Ok(session.to_jwt())
   ```

3. **Frontend Integration** (TypeScript)
   ```typescript
   // Request magic link
   await api.post('/auth/magic-link', { email });
   
   // Verify from email link
   const { token } = parseQueryParams();
   const { jwt } = await api.get(`/auth/verify?token=${token}`);
   localStorage.setItem('auth_token', jwt);
   ```

## Database Access Patterns

### Repository Pattern (Rust)
```rust
pub struct DealRepository {
    pool: PgPool,
}

impl DealRepository {
    pub async fn find_by_id(&self, id: i64) -> Result<Option<Deal>> {
    sqlx::query_as!(
        Deal,
        "SELECT * FROM deals WHERE id = $1",
        id
    )
    .fetch_optional(&self.pool)
    .await
    .context("Database query failed")
    }
    
    pub async fn create(&self, deal: NewDeal) -> Result<Deal> {
    sqlx::query_as!(
        Deal,
        "INSERT INTO deals (originator_id, amount, status) 
         VALUES ($1, $2, $3) 
         RETURNING *",
        deal.originator_id,
        deal.amount,
        deal.status
    )
    .fetch_one(&self.pool)
    .await
    .context("Failed to create deal")
    }
}
```

## State Management Patterns

### React Query (Frontend)
```typescript
// Query hook for fetching data
function useDeals() {
  return useQuery({
    queryKey: ['deals'],
    queryFn: () => api.get('/deals'),
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

// Mutation hook for updates
function useCreateDeal() {
  const queryClient = useQueryClient();
  
  return useMutation({
    mutationFn: (newDeal: NewDeal) => api.post('/deals', newDeal),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['deals'] });
    },
  });
}

// Usage in component
function DealsList() {
  const { data: deals, isLoading } = useDeals();
  const createDeal = useCreateDeal();
  
  if (isLoading) return <Spinner />;
  
  return (
    <div>
      {deals.map(deal => <DealCard key={deal.id} deal={deal} />)}
      <Button onClick={() => createDeal.mutate(newDealData)}>
    Create Deal
      </Button>
    </div>
  );
}
```

## Form Validation Patterns

### Zod + React Hook Form (Frontend)
```typescript
import { z } from 'zod';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';

// Define schema
const dealSchema = z.object({
  amount: z.number().positive().min(1000),
  description: z.string().min(10).max(500),
  originatorId: z.string().uuid(),
});

type DealFormData = z.infer<typeof dealSchema>;

// Use in form
function DealForm() {
  const { register, handleSubmit, formState: { errors } } = useForm<DealFormData>({
    resolver: zodResolver(dealSchema),
  });
  
  const onSubmit = (data: DealFormData) => {
    // Data is guaranteed to be valid
    createDeal(data);
  };
  
  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      <input {...register('amount')} type="number" />
      {errors.amount && <span>{errors.amount.message}</span>}
      
      <textarea {...register('description')} />
      {errors.description && <span>{errors.description.message}</span>}
      
      <button type="submit">Create Deal</button>
    </form>
  );
}
```

## Smart Contract Patterns

### Access Control (Solidity)
```solidity
// Ownable pattern for admin functions
contract ARDA is Ownable {
    mapping(address => bool) public verifiers;
    
    modifier onlyVerifier() {
    require(verifiers[msg.sender], "Not authorized");
    _;
    }
    
    function addVerifier(address verifier) external onlyOwner {
    verifiers[verifier] = true;
    }
    
    function verifyProof(bytes calldata proof) external onlyVerifier {
    // Only authorized verifiers can call this
    }
}
```

### Reentrancy Guard (Solidity)
```solidity
contract ARDA {
    bool private locked;
    
    modifier nonReentrant() {
    require(!locked, "Reentrant call");
    locked = true;
    _;
    locked = false;
    }
    
    function withdraw(uint256 amount) external nonReentrant {
    // Safe from reentrancy attacks
    require(balances[msg.sender] >= amount);
    balances[msg.sender] -= amount;
    payable(msg.sender).transfer(amount);
    }
}
```

## Testing Patterns

### Rust Unit Tests
```rust
#[cfg(test)]
mod tests {
    use super::*;
    
    #[tokio::test]
    async fn test_deal_creation() {
    // Arrange
    let repo = DealRepository::new_test();
    let new_deal = NewDeal { /* ... */ };
    
    // Act
    let result = repo.create(new_deal).await;
    
    // Assert
    assert!(result.is_ok());
    let deal = result.unwrap();
    assert_eq!(deal.status, DealStatus::Pending);
    }
}
```

### React Component Tests (TypeScript)
```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { DealCard } from './DealCard';

describe('DealCard', () => {
  it('renders deal information', () => {
    const deal = { id: 1, amount: 10000, status: 'active' };
    render(<DealCard deal={deal} />);
    
    expect(screen.getByText('$10,000')).toBeInTheDocument();
    expect(screen.getByText('active')).toBeInTheDocument();
  });
  
  it('calls onTransfer when transfer button clicked', () => {
    const onTransfer = jest.fn();
    const deal = { id: 1, amount: 10000, status: 'active' };
    render(<DealCard deal={deal} onTransfer={onTransfer} />);
    
    fireEvent.click(screen.getByText('Transfer'));
    expect(onTransfer).toHaveBeenCalledWith(deal.id);
  });
});
```

---

**Usage**: Reference these patterns when implementing new features to maintain consistency across the codebase.
"""


async def codebase_statistics() -> str:
    """Live codebase statistics aggregated from vector collections."""
    from src.utils.github import get_cached_repo_structures
    
    try:
        collections_data = _list_collections_impl()
        
        output = """# Arda Codebase Statistics

_Aggregated from vector database collections_

"""
        
        # Calculate total vectors across all collections
        total_vectors = 0
        language_breakdown = {}
        
        by_type = collections_data.get('by_type', {})
        
        # Aggregate by language
        for coll in by_type.get('language', []):
            name = coll['name']
            count = coll.get('points_count', 0)
            total_vectors += count
            
            # Extract language from collection name
            if 'rust' in name:
                language_breakdown['Rust'] = language_breakdown.get('Rust', 0) + count
            elif 'typescript' in name:
                language_breakdown['TypeScript'] = language_breakdown.get('TypeScript', 0) + count
            elif 'solidity' in name:
                language_breakdown['Solidity'] = language_breakdown.get('Solidity', 0) + count
            elif 'python' in name:
                language_breakdown['Python'] = language_breakdown.get('Python', 0) + count
        
        output += f"## Overall Statistics\n"
        output += f"- **Total Code Embeddings**: {total_vectors:,}\n"
        output += f"- **Total Collections**: {collections_data.get('total_collections', 0)}\n"
        
        output += f"\n## Code by Language\n"
        for lang, count in sorted(language_breakdown.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_vectors * 100) if total_vectors > 0 else 0
            output += f"- **{lang}**: {count:,} embeddings ({percentage:.1f}%)\n"
        
        # Repository breakdown
        output += f"\n## Code by Repository\n"
        for coll in by_type.get('repo', []):
            name = coll['name']
            count = coll.get('points_count', 0)
            output += f"- **{name}**: {count:,} embeddings\n"
        
        # Service breakdown
        output += f"\n## Code by Service\n"
        for coll in by_type.get('service', []):
            name = coll['name']
            count = coll.get('points_count', 0)
            output += f"- **{name}**: {count:,} embeddings\n"
        
        # Get repository metadata if available
        repos = await get_cached_repo_structures()
        if repos:
            output += f"\n## Repository Metadata\n"
            
            arda_credit = repos.get('arda_credit', {})
            if arda_credit:
                output += f"\n### arda-credit\n"
                output += f"- **Description**: {arda_credit.get('description', 'N/A')}\n"
                output += f"- **Primary Language**: {arda_credit.get('language', 'N/A')}\n"
                output += f"- **Last Updated**: {arda_credit.get('updated_at', 'N/A')}\n"
                output += f"- **Files**: {len(arda_credit.get('tree', []))}\n"
            
            arda_platform = repos.get('arda_platform', {})
            if arda_platform:
                output += f"\n### arda-platform\n"
                output += f"- **Description**: {arda_platform.get('description', 'N/A')}\n"
                output += f"- **Primary Language**: {arda_platform.get('language', 'N/A')}\n"
                output += f"- **Last Updated**: {arda_platform.get('updated_at', 'N/A')}\n"
                output += f"- **Files**: {len(arda_platform.get('tree', []))}\n"
        
        output += f"\n## Search Performance\n"
        cache_stats = _query_cache.get_stats()
        output += f"- **Query Cache Hit Rate**: {cache_stats['hit_rate_percent']:.1f}%\n"
        output += f"- **Cached Queries**: {cache_stats['size']}\n"
        output += f"- **Total Queries**: {cache_stats['hits'] + cache_stats['misses']}\n"
        
        output += f"\n---\n"
        output += f"*Statistics are updated in real-time from the vector database*\n"
        
        return output
        
    except Exception as e:
        logger.error(f"Failed to generate codebase statistics: {e}")
        return f"# Arda Codebase Statistics\n\n⚠️ **Error**: {str(e)}"


async def changelog_resource() -> str:
    """Recent code changes and updates from vector collections."""
    from src.utils.github import get_cached_repo_structures
    
    try:
        output = """# Arda Codebase Changelog

_Recent code changes and repository updates_

"""
        
        # Try to get repository metadata
        repos = await get_cached_repo_structures()
        
        if repos:
            output += "## Recent Repository Updates\n\n"
            
            for repo_key, repo_data in repos.items():
                if repo_data:
                    output += f"### {repo_data.get('name', repo_key)}\n"
                    output += f"- **Last Updated**: {repo_data.get('updated_at', 'Unknown')}\n"
                    output += f"- **Description**: {repo_data.get('description', 'N/A')}\n"
                    output += f"- **Language**: {repo_data.get('language', 'N/A')}\n"
                    
                    if repo_data.get('pushed_at'):
                        output += f"- **Last Push**: {repo_data.get('pushed_at')}\n"
                    
                    output += "\n"
        else:
            output += "⚠️ Unable to fetch live repository data.\n\n"
        
        # Try to search for recent changes in code
        try:
            # Search for recent migrations, version bumps, changelog entries
            recent_changes_query = "version update changelog migration recent changes"
            recent_results = await _semantic_search_impl(
                query=recent_changes_query,
                collection_name="arda_documentation",
                limit=10,
                score_threshold=0.5
            )
            
            if recent_results.get('results'):
                output += "## Recent Documentation Changes\n\n"
                for result in recent_results['results'][:5]:
                    payload = result.get('payload', {})
                    item_name = payload.get('item_name', 'Unknown')
                    file_path = payload.get('file_path', '')
                    score = result.get('score', 0)
                    
                    output += f"### {item_name}\n"
                    output += f"- **File**: `{file_path}`\n"
                    output += f"- **Relevance**: {score:.2f}\n\n"
        except Exception as e:
            logger.warning(f"Could not fetch recent changes from documentation: {e}")
            output += "\n_Note: Could not fetch recent changes from documentation collection._\n"
        
        output += """
## How to Track Changes

### For Database Migrations
Search `arda_database_schemas` collection for migration files:
```
semantic_search("database migration", "arda_database_schemas", limit=20)
```

### For API Changes
Search `arda_code_rust` collection for API route changes:
```
semantic_search("API endpoint route handler", "arda_code_rust", limit=20)
```

### For Frontend Changes
Search `arda_code_typescript` collection for component changes:
```
semantic_search("React component", "arda_code_typescript", limit=20)
```

### For Contract Changes
Search `arda_code_solidity` collection for smart contract changes:
```
semantic_search("contract function event", "arda_code_solidity", limit=20)
```

---

**Tip**: Use `refresh_repo_cache()` to update repository metadata with the latest information from GitHub.
"""
        
        return output
        
    except Exception as e:
        logger.error(f"Failed to generate changelog: {e}")
        return f"# Arda Codebase Changelog\n\n⚠️ **Error**: {str(e)}"


async def metrics_resource() -> str:
    """Performance metrics and operational insights."""
    try:
        output = """# Arda Performance Metrics

_Operational metrics and performance insights_

"""
        
        # Get collection metrics
        collections_data = _list_collections_impl()
        cache_stats = _query_cache.get_stats()
        
        output += f"## Vector Database Metrics\n\n"
        
        total_vectors = 0
        all_collections = []
        by_type = collections_data.get('by_type', {})
        for type_name, collections in by_type.items():
            for coll in collections:
                all_collections.append(coll)
                total_vectors += coll.get('points_count', 0)
        
        output += f"- **Total Vector Embeddings**: {total_vectors:,}\n"
        output += f"- **Total Collections**: {collections_data.get('total_collections', 0)}\n"
        output += f"- **Average Vectors per Collection**: {total_vectors // max(collections_data.get('total_collections', 1), 1):,}\n"
        
        # Largest collections
        sorted_collections = sorted(all_collections, key=lambda x: x.get('points_count', 0), reverse=True)
        output += f"\n### Largest Collections\n"
        for coll in sorted_collections[:5]:
            name = coll['name']
            count = coll.get('points_count', 0)
            output += f"- **{name}**: {count:,} vectors\n"
        
        # Cache performance metrics
        output += f"\n## Query Cache Performance\n\n"
        output += f"- **Cache Hit Rate**: {cache_stats['hit_rate_percent']:.1f}%\n"
        output += f"- **Total Requests**: {cache_stats['total_requests']:,}\n"
        output += f"- **Cache Hits**: {cache_stats['hits']:,}\n"
        output += f"- **Cache Misses**: {cache_stats['misses']:,}\n"
        output += f"- **Current Cache Size**: {cache_stats['size']:,} / {cache_stats['max_size']:,}\n"
        output += f"- **Cache TTL**: {cache_stats['ttl_minutes']:.0f} minutes\n"
        
        # Calculate estimated time savings
        if cache_stats['hits'] > 0:
            avg_search_time = 1.5  # seconds (uncached)
            cached_search_time = 0.3  # seconds (cached)
            time_saved = cache_stats['hits'] * (avg_search_time - cached_search_time)
            output += f"\n**Estimated Time Saved by Cache**: ~{time_saved:.1f} seconds ({time_saved/60:.1f} minutes)\n"
        
        # Search performance breakdown
        output += f"\n## Search Performance Insights\n\n"
        
        if cache_stats['hit_rate_percent'] >= 60:
            output += "✅ **Excellent cache performance** - Most queries are being cached effectively.\n\n"
        elif cache_stats['hit_rate_percent'] >= 40:
            output += "⚠️ **Moderate cache performance** - Consider increasing cache TTL or size.\n\n"
        else:
            output += "🔴 **Low cache performance** - Queries may be too diverse or cache TTL too short.\n\n"
        
        output += """### Performance Tips

1. **Use Specific Collections**: Searching a specific collection (e.g., `arda_code_rust`) is 3-5x faster than cross-collection search
2. **Optimize Threshold**: Higher thresholds (0.7+) return fewer results faster
3. **Batch Queries**: Use `batch_semantic_search` for multiple related queries (reuses embeddings)
4. **Cache Warm-up**: First query to a new pattern takes ~2s, subsequent queries <500ms
5. **Collection Selection**: Language-specific collections are faster than concern-based collections

### Recommended Limits by Use Case

| Use Case | Limit | Threshold | Expected Time |
|----------|-------|-----------|---------------|
| Quick lookup | 5-10 | 0.7-0.8 | <1s |
| Feature exploration | 15-20 | 0.6-0.7 | 1-2s |
| Debugging/investigation | 25-30 | 0.5-0.6 | 2-3s |
| Comprehensive audit | 40-50 | 0.4-0.5 | 3-5s |

---

**Note**: Metrics are collected in real-time from the vector database and query cache.
"""
        
        return output
        
    except Exception as e:
        logger.error(f"Failed to generate metrics: {e}")
        return f"# Arda Performance Metrics\n\n⚠️ **Error**: {str(e)}"


async def architecture_resource() -> str:
    """Architecture diagrams and system design documentation."""
    return """# Arda Architecture Overview

_System architecture with Mermaid diagrams_

## High-Level Architecture

```mermaid
graph TB
    subgraph "Frontend Layer"
        UI[arda-platform<br/>React + TypeScript]
    end
    
    subgraph "Application Layer"
        API[arda-credit API<br/>Rust + Axum]
        ZK[SP1 zkVM Program<br/>Rust]
    end
    
    subgraph "Data Layer"
        DB[(PostgreSQL<br/>Deal & User Data)]
        Vector[(Qdrant<br/>Vector Search)]
    end
    
    subgraph "Blockchain Layer"
        Contract[ARDA Contract<br/>Solidity]
        USDC[USDC Contract<br/>ERC-20]
    end
    
    subgraph "External Services"
        Modal[Modal<br/>ZK Proof Generation]
        Ethereum[Ethereum<br/>L1/L2 Network]
        Email[AWS SES<br/>Email Service]
    end
    
    UI --> API
    UI --> Contract
    API --> DB
    API --> Vector
    API --> Email
    API --> Modal
    API --> Ethereum
    Modal --> ZK
    ZK --> Contract
    Contract --> USDC
    Contract --> Ethereum
```

## Authentication Flow

```mermaid
sequenceDiagram
    participant User
    participant Frontend
    participant API
    participant Cache
    participant Email
    
    User->>Frontend: Enter email
    Frontend->>API: POST /auth/magic-link
    API->>Cache: Store token (15min TTL)
    API->>Email: Send magic link
    Email->>User: Email with link
    User->>Frontend: Click link
    Frontend->>API: GET /auth/verify?token=xxx
    API->>Cache: Validate token
    Cache-->>API: User ID
    API->>API: Create session
    API-->>Frontend: JWT token
    Frontend->>Frontend: Store JWT
    Frontend-->>User: Authenticated
```

## Deal Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Pending: Originator creates deal
    Pending --> Active: Admin approves
    Pending --> Rejected: Admin rejects
    
    Active --> InvestmentOpen: Deal goes live
    InvestmentOpen --> InvestmentOpen: Investors commit
    InvestmentOpen --> Funded: Minimum reached
    InvestmentOpen --> Cancelled: Deadline missed
    
    Funded --> ProofGenerated: Generate ZK proof
    ProofGenerated --> OnChain: Submit to contract
    OnChain --> Settled: USDC transferred
    
    Settled --> [*]
    Rejected --> [*]
    Cancelled --> [*]
```

## ZK Proof Generation

```mermaid
sequenceDiagram
    participant API as arda-credit API
    participant Modal as Modal Service
    participant zkVM as SP1 zkVM
    participant Contract as ARDA Contract
    participant Verifier as SP1 Verifier
    
    API->>Modal: Request proof generation
    Note over API,Modal: Batch of transactions
    Modal->>zkVM: Execute program
    zkVM->>zkVM: Compute new state
    zkVM->>Modal: Generate proof
    Modal-->>API: Proof + public inputs
    API->>Contract: Submit proof
    Contract->>Verifier: Verify proof
    Verifier-->>Contract: Valid ✓
    Contract->>Contract: Update state root
    Contract-->>API: Success
```

## Data Flow for Deal Creation

```mermaid
graph LR
    subgraph Frontend
        Form[Deal Form]
        Validation[Client Validation]
    end
    
    subgraph Backend
        Handler[POST /deals]
        Auth[Auth Middleware]
        BizLogic[Business Logic]
        KYC[KYC Check]
    end
    
    subgraph Database
        DealsTable[(deals table)]
        UsersTable[(users table)]
    end
    
    subgraph Vector DB
        EmbedGen[Generate Embedding]
        VectorStore[(Qdrant Collection)]
    end
    
    Form --> Validation
    Validation --> Handler
    Handler --> Auth
    Auth --> BizLogic
    BizLogic --> KYC
    KYC --> UsersTable
    BizLogic --> DealsTable
    DealsTable --> EmbedGen
    EmbedGen --> VectorStore
    BizLogic -.Success.-> Form
```

## Service Dependencies

```mermaid
graph TD
    Platform[arda-platform]
    Credit[arda-credit]
    
    Platform --> Credit
    Platform --> MetaMask
    Platform --> ARDA_Contract
    
    Credit --> PostgreSQL
    Credit --> Modal
    Credit --> Ethereum_Node
    Credit --> AWS_SES
    Credit --> Qdrant
    
    Modal --> SP1_zkVM
    SP1_zkVM --> ARDA_Contract
    
    ARDA_Contract --> SP1_Verifier
    ARDA_Contract --> USDC_Contract
    
    style Platform fill:#e1f5ff
    style Credit fill:#fff4e1
    style ARDA_Contract fill:#f0f0f0
```

## Collection Organization

```mermaid
graph TD
    Root[Qdrant Vector DB]
    
    Root --> Lang[By Language]
    Root --> Repo[By Repository]
    Root --> Service[By Service]
    Root --> Concern[By Concern]
    
    Lang --> Rust[arda_code_rust]
    Lang --> TS[arda_code_typescript]
    Lang --> Sol[arda_code_solidity]
    Lang --> Python[arda_code_python]
    
    Repo --> RepoCredit[arda_repo_credit]
    Repo --> RepoPlatform[arda_repo_platform]
    
    Service --> Frontend[arda_frontend]
    Service --> Backend[arda_backend]
    Service --> Middleware[arda_middleware]
    
    Concern --> API[arda_api_contracts]
    Concern --> DB[arda_database_schemas]
    Concern --> Deploy[arda_deployment]
    Concern --> Docs[arda_documentation]
    
    style Root fill:#ffcccc
    style Lang fill:#ccffcc
    style Repo fill:#ccccff
    style Service fill:#ffffcc
    style Concern fill:#ffccff
```

## Deployment Architecture

```mermaid
graph TB
    subgraph "Production Environment"
        LB[Load Balancer]
        
        subgraph "Application Tier"
            API1[arda-credit API<br/>Instance 1]
            API2[arda-credit API<br/>Instance 2]
        end
        
        subgraph "Frontend Tier"
            CDN[CDN / Vercel]
            Static[Static Assets]
        end
        
        subgraph "Data Tier"
            PrimaryDB[(Primary PostgreSQL)]
            ReplicaDB[(Read Replica)]
            VectorDB[(Qdrant Cloud)]
        end
        
        subgraph "External"
            Modal_Prod[Modal<br/>GPU Inference]
            ETH_Prod[Ethereum<br/>Mainnet/L2]
        end
    end
    
    Users --> CDN
    Users --> LB
    CDN --> Static
    LB --> API1
    LB --> API2
    API1 --> PrimaryDB
    API2 --> PrimaryDB
    API1 --> ReplicaDB
    API2 --> ReplicaDB
    API1 --> VectorDB
    API2 --> VectorDB
    API1 --> Modal_Prod
    API2 --> Modal_Prod
    API1 --> ETH_Prod
    API2 --> ETH_Prod
    PrimaryDB -.Replication.-> ReplicaDB
```

## Security Layers

```mermaid
graph TD
    Input[User Input]
    
    Input --> Frontend_Val[Frontend Validation<br/>Zod Schema]
    Frontend_Val --> API_Val[API Validation<br/>Rust Types]
    API_Val --> Auth_Check[Authentication<br/>JWT Validation]
    Auth_Check --> Authz_Check[Authorization<br/>Role & Permissions]
    Authz_Check --> Biz_Rules[Business Rules<br/>KYC, Balance, Limits]
    Biz_Rules --> DB_Constraints[Database Constraints<br/>FK, Unique, Check]
    DB_Constraints --> Contract_Val[Contract Validation<br/>Solidity Modifiers]
    Contract_Val --> Success[✓ Validated]
    
    style Frontend_Val fill:#e1f5ff
    style API_Val fill:#ffe1f5
    style Auth_Check fill:#f5ffe1
    style Authz_Check fill:#fff5e1
    style Biz_Rules fill:#e1ffe1
    style DB_Constraints fill:#ffe1e1
    style Contract_Val fill:#f0f0f0
    style Success fill:#ccffcc
```

---

## Key Architectural Decisions

### 1. Three-Tier Architecture
- **Frontend** (arda-platform): React SPA for user interaction
- **Backend** (arda-credit): Rust API for business logic
- **Blockchain** (ARDA contract): Solidity for on-chain state

### 2. Zero-Knowledge Privacy
- SP1 zkVM for proof generation
- Batch transactions for privacy
- On-chain verification for trust

### 3. Hybrid Data Storage
- **PostgreSQL**: Structured deal/user data
- **Qdrant**: Semantic code search
- **Ethereum**: Immutable state commitments

### 4. Serverless ZK Computation
- Modal for GPU-based proof generation
- On-demand scaling
- Cost-effective for sporadic workloads

### 5. Magic Link Authentication
- Email-based passwordless auth
- Short-lived tokens (15min)
- Session management with JWT

---

**Note**: These diagrams represent the current architecture. For implementation details, search the relevant collections using semantic search.
"""


async def service_dependency_map() -> str:
    """Visual dependency map of all Arda services."""
    try:
        output = """# Arda Service Dependency Map

_Service relationships and dependencies_

"""
        
        # Try to get deployment information
        try:
            deployment_info = await _get_deployed_services_impl()
            services = deployment_info.get('services', {})
            
            if services:
                output += f"## Deployed Services ({len(services)})\n\n"
                
                for service_name, service_data in services.items():
                    output += f"### {service_name}\n"
                    output += f"- **Type**: {service_data.get('type', 'Unknown')}\n"
                    output += f"- **Repository**: {service_data.get('repo', 'Unknown')}\n"
                    
                    if service_data.get('exposed_ports'):
                        output += f"- **Exposed Ports**: {', '.join(map(str, service_data['exposed_ports']))}\n"
                    
                    if service_data.get('container_images'):
                        output += f"- **Container Images**: {len(service_data['container_images'])}\n"
                    
                    output += "\n"
            else:
                output += "⚠️ No deployed services found. The `arda_deployment` collection may be empty.\n\n"
        
        except Exception as e:
            logger.warning(f"Failed to get deployment info: {e}")
            output += f"⚠️ Could not fetch deployment information: {e}\n\n"
        
        # Add static known dependencies
        output += """## Known Service Dependencies

### arda-credit (Backend API)
**Depends on:**
- PostgreSQL database (deal data, user data)
- Modal (ZK proof generation)
- Ethereum node (smart contract interaction)
- AWS SES (email service)
- Qdrant (optional: for semantic search)

**Provides:**
- REST API for deal management
- Authentication services
- KYC validation
- Transaction processing

**Used by:**
- arda-platform (frontend)
- External clients

---

### arda-platform (Frontend)
**Depends on:**
- arda-credit API (backend services)
- MetaMask (wallet integration)

**Provides:**
- Web UI for investors and originators
- Deal browsing and management
- Portfolio tracking

**Used by:**
- End users (investors, originators)

---

### SP1 zkVM Program
**Depends on:**
- Deal transaction data (from arda-credit)
- Previous state roots

**Provides:**
- Zero-knowledge proofs
- Privacy-preserving transaction batches

**Used by:**
- arda-credit (proof generation)
- ARDA smart contract (proof verification)

---

### ARDA Smart Contract
**Depends on:**
- SP1 verifier (proof verification)
- USDC contract (deposits/withdrawals)

**Provides:**
- On-chain state verification
- USDC custody
- Deposit/withdrawal logic

**Used by:**
- arda-credit (monitoring)
- End users (wallet transactions)

---

## Dependency Graph

```
┌─────────────────┐
│  End Users      │
│  (Investors/    │
│   Originators)  │
└────────┬────────┘
     │
     ▼
┌─────────────────┐      ┌──────────────┐
│ arda-platform   │─────▶│  MetaMask    │
│  (Frontend)     │      └──────────────┘
└────────┬────────┘
     │
     ▼
┌─────────────────┐
│  arda-credit    │───────┐
│  (Backend API)  │       │
└────────┬────────┘       │
     │                │
    ┌────┴────┬───────────┼──────────┐
    ▼         ▼           ▼          ▼
┌─────────┐ ┌──────┐ ┌────────┐ ┌────────┐
│PostgreSQL│ │Modal │ │Ethereum│ │AWS SES│
└──────────┘ └───┬──┘ │  Node  │ └────────┘
             │    └────┬───┘
             │         │
             ▼         ▼
     ┌───────────┐ ┌──────────┐
     │SP1 zkVM   │ │  ARDA    │
     │  Program  │ │ Contract │
     └───────────┘ └─────┬────┘
                         │
                         ▼
                  ┌──────────────┐
                  │USDC Contract │
                  └──────────────┘
```

---

**Note**: This map shows logical dependencies. For real-time service health and network topology, query the `arda_deployment` collection or use `get_deployed_services()` tool.
"""
        
        return output
        
    except Exception as e:
        logger.error(f"Failed to generate dependency map: {e}")
        return f"# Arda Service Dependency Map\n\n⚠️ **Error**: {str(e)}"


def register_resources(mcp: FastMCP):
    """Register all resource functions with the MCP server."""
    # Decorate and register each resource
    mcp.resource("arda://collections")(arda_collections_info)
    mcp.resource("arda://search-tips")(arda_search_best_practices)
    mcp.resource("arda://dashboard")(collection_health_dashboard)
    mcp.resource("arda://api-catalog")(api_endpoint_catalog)
    mcp.resource("arda://patterns")(code_patterns_library)
    mcp.resource("arda://stats")(codebase_statistics)
    mcp.resource("arda://dependencies")(service_dependency_map)
    mcp.resource("arda://changelog")(changelog_resource)
    mcp.resource("arda://metrics")(metrics_resource)
    mcp.resource("arda://architecture")(architecture_resource)


