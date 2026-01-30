# Language Parsers

> **Files:** `modules/ingest/parsers/*.py`
> **Purpose:** AST-based parsing of Rust, TypeScript, Solidity, and Markdown files for code chunk extraction
> **Last Updated:** 2025-10-01

## Overview

The language parsers extract syntactically coherent code chunks from multi-language codebases using tree-sitter AST parsing. Each parser handles a specific language, extracting functions, structs, classes, contracts, and other semantic units with metadata for vector search.

## Architecture

```
Multi-Language Parsing System
    ↓
┌────────────────────────────────────────┐
│         Language Parsers               │
├────────────────────────────────────────┤
│  RustASTParser                         │
│    ├─ tree-sitter-rust                 │
│    ├─ Extract: fn, struct, impl, trait │
│    └─ Fallback: Regex parsing          │
│                                         │
│  TypeScriptASTParser                   │
│    ├─ tree-sitter-typescript           │
│    ├─ Extract: function, class, type,  │
│    │           interface, component    │
│    └─ Fallback: Regex parsing          │
│                                         │
│  SolidityASTParser                     │
│    ├─ tree-sitter-solidity             │
│    ├─ Extract: contract, interface,    │
│    │           library, function       │
│    └─ No fallback (fail fast)          │
│                                         │
│  DocumentationParser                   │
│    ├─ Python markdown                  │
│    ├─ Extract: sections by heading     │
│    └─ Classify: architecture, API, etc │
└────────────────────────────────────────┘
    ↓
Code Chunks (with metadata)
    ├─ file_path: str
    ├─ content: str (code text)
    ├─ start_line: int
    ├─ end_line: int
    ├─ item_name: str
    ├─ item_type: str
    ├─ imports/use_statements: List[str]
    ├─ doc_comments: List[str]
    └─ metadata: Dict[str, Any]
        ├─ language: str
        ├─ business_domain: str
        ├─ complexity_score: float
        ├─ repo_id: str
        └─ repo_component: str
```

## Parsers

### 1. RustASTParser

**File:** `modules/ingest/parsers/rust_parser.py`

**Purpose:** Parse Rust source files using tree-sitter to extract functions, structs, enums, implementations, traits, modules, and constants.

#### Class Signature

```python
class RustASTParser:
    def __init__(self):
        """Initialize the Rust AST parser with tree-sitter or fallback."""
        self.tree_sitter_available = self._check_tree_sitter()

    def parse_file(
        self,
        file_path: str,
        content: str,
        repo_id: str
    ) -> ParseResult:
        """
        Parse a Rust file and extract code chunks.

        Returns ParseResult with chunks or error information.
        """
```

#### Extracted Items

| Item Type | Description | Example |
|-----------|-------------|---------|
| `fn` | Function declarations | `pub fn approve_loan(...)` |
| `struct` | Struct definitions | `pub struct LoanService { ... }` |
| `enum` | Enum definitions | `enum LoanStatus { ... }` |
| `impl` | Implementation blocks | `impl LoanService { ... }` |
| `trait` | Trait definitions | `trait Validator { ... }` |
| `mod` | Module declarations | `mod authentication { ... }` |
| `const` | Constants | `const MAX_AMOUNT: u64 = ...` |
| `static` | Static variables | `static GLOBAL_CONFIG: ...` |
| `type` | Type aliases | `type Result<T> = ...` |

#### RustCodeChunk Structure

```python
@dataclass
class RustCodeChunk:
    file_path: str              # "backend/loan_service.rs"
    content: str                # "pub fn approve_loan(...) { ... }"
    start_line: int             # 123
    end_line: int               # 168
    item_name: str              # "approve_loan"
    item_type: str              # "fn"
    use_statements: List[str]   # ["use crate::models::Loan;", ...]
    doc_comments: List[str]     # ["/// Approve a loan request", ...]
    metadata: Dict[str, Any]    # {language, business_domain, complexity_score, ...}
```

#### Example

```python
from modules.ingest.parsers.rust_parser import RustASTParser

parser = RustASTParser()

content = """
use crate::models::Loan;

/// Approve a loan request after validation
pub fn approve_loan(loan_id: LoanId) -> Result<Loan, LoanError> {
    // Implementation
}
"""

result = parser.parse_file("backend/loan_service.rs", content, "arda-credit")

if result.success:
    for chunk in result.chunks:
        print(f"{chunk.item_type}: {chunk.item_name} (lines {chunk.start_line}-{chunk.end_line})")
        print(f"  Use statements: {len(chunk.use_statements)}")
        print(f"  Doc comments: {len(chunk.doc_comments)}")
```

#### Fallback Behavior

**Tree-sitter Available:** Uses AST parsing for 100% accuracy
**Tree-sitter Unavailable:** Falls back to regex parsing (80-90% accuracy)

```python
if self.tree_sitter_available:
    return self._parse_with_tree_sitter(file_path, content, repo_id)
else:
    return self._parse_with_regex(file_path, content, repo_id)
```

### 2. TypeScriptASTParser

**File:** `modules/ingest/parsers/typescript_parser.py`

**Purpose:** Parse TypeScript/React source files to extract functions, classes, interfaces, types, React components, and hooks.

#### Class Signature

```python
class TypeScriptASTParser:
    def __init__(self):
        """Initialize TypeScript parser with tree-sitter."""
        self.tree_sitter_available = False
        self.parser = None
        # Try to initialize tree-sitter-typescript

    def parse_file(
        self,
        file_path: str,
        content: str,
        repo_id: str
    ) -> TypeScriptParseResult:
        """Parse a TypeScript file and extract code chunks."""
```

#### Extracted Items

| Item Type | Description | Example |
|-----------|-------------|---------|
| `function` | Function declarations | `function approveApplication(...)` |
| `arrow_function` | Arrow functions | `const validate = (...) => { ... }` |
| `class` | Class definitions | `class LoanService { ... }` |
| `interface` | TypeScript interfaces | `interface LoanData { ... }` |
| `type` | Type aliases | `type LoanStatus = ...` |
| `component` | React components | `const LoanForm = () => { ... }` |
| `hook` | React hooks | `const useLoan = () => { ... }` |
| `const` | Constants | `const API_URL = ...` |
| `export` | Export statements | `export { LoanService }` |

#### TypeScriptCodeChunk Structure

```python
@dataclass
class TypeScriptCodeChunk:
    file_path: str              # "frontend/src/LoanApproval.tsx"
    content: str                # "const LoanApproval = () => { ... }"
    start_line: int             # 45
    end_line: int               # 89
    item_name: str              # "LoanApproval"
    item_type: str              # "component"
    imports: List[str]          # ["import React from 'react';", ...]
    exports: List[str]          # ["export { LoanApproval }"]
    metadata: Dict[str, Any]    # {language, business_domain, is_react_component, ...}
```

#### React Component Detection

**Pattern Matching:**
- Function names starting with capital letter: `LoanForm`, `Button`
- Hook usage: `useState`, `useEffect`, `useCallback`
- JSX syntax: `<div>`, `<Component />`

```python
def _is_react_component(self, content: str, item_name: str) -> bool:
    # Capital letter start + JSX or hooks
    return (
        item_name[0].isupper() and
        (
            re.search(r'<[A-Z][^>]*>', content) or  # JSX
            re.search(r'use[A-Z]\w+\(', content)    # Hooks
        )
    )
```

#### Example

```python
from modules.ingest.parsers.typescript_parser import TypeScriptASTParser

parser = TypeScriptASTParser()

content = """
import React, { useState } from 'react';

interface LoanFormProps {
    onSubmit: (data: LoanData) => void;
}

const LoanForm: React.FC<LoanFormProps> = ({ onSubmit }) => {
    const [amount, setAmount] = useState(0);

    return (
        <form onSubmit={() => onSubmit({ amount })}>
            <input value={amount} onChange={e => setAmount(e.target.value)} />
        </form>
    );
};

export { LoanForm };
"""

result = parser.parse_file("frontend/src/LoanForm.tsx", content, "arda-platform")

for chunk in result.chunks:
    print(f"{chunk.item_type}: {chunk.item_name}")
    print(f"  Imports: {len(chunk.imports)}")
    print(f"  Is React component: {chunk.metadata.get('is_react_component', False)}")
```

### 3. SolidityASTParser

**File:** `modules/ingest/parsers/solidity_parser.py`

**Purpose:** Parse Solidity smart contract files to extract contracts, interfaces, libraries, functions, events, and state variables.

#### Class Signature

```python
class SolidityASTParser:
    def __init__(self):
        """Initialize Solidity parser (requires tree-sitter-solidity)."""
        import tree_sitter_solidity as ts_sol
        self.sol_language = tree_sitter.Language(ts_sol.language())
        self.parser = tree_sitter.Parser(self.sol_language)

    def parse_file(
        self,
        file_path: str,
        content: str,
        repo_id: str
    ) -> SolidityParseResult:
        """Parse Solidity file using tree-sitter AST (no fallback)."""
```

#### Extracted Items

| Item Type | Description | Example |
|-----------|-------------|---------|
| `contract` | Contract declarations | `contract Verifier { ... }` |
| `interface` | Interface declarations | `interface IVerifier { ... }` |
| `library` | Library declarations | `library SafeMath { ... }` |
| `function` | Function definitions | `function verifyProof(...) public` |
| `modifier` | Function modifiers | `modifier onlyOwner() { ... }` |
| `event` | Event definitions | `event ProofVerified(...)` |
| `struct` | Struct definitions | `struct Proof { ... }` |
| `enum` | Enum definitions | `enum Status { ... }` |
| `error` | Custom error definitions | `error InvalidProof()` |
| `state_variable` | State variables | `uint256 public count;` |
| `constructor` | Constructor functions | `constructor() { ... }` |

#### SolidityCodeChunk Structure

```python
@dataclass
class SolidityCodeChunk:
    file_path: str              # "contracts/verifier.sol"
    content: str                # "function verifyProof(...) { ... }"
    start_line: int             # 45
    end_line: int               # 89
    item_name: str              # "verifyProof"
    item_type: str              # "function"
    imports: List[str]          # ["import './Groth16.sol';", ...]
    metadata: Dict[str, Any]    # {language, visibility, state_mutability, ...}
```

#### No Fallback Policy

**Rationale:** Solidity syntax is complex and sensitive. Regex parsing would be unreliable and dangerous.

```python
def __init__(self):
    try:
        import tree_sitter_solidity as ts_sol
        # Initialize tree-sitter
    except Exception as e:
        raise RuntimeError(f"Tree-sitter Solidity required but failed: {e}")
```

#### Example

```python
from modules.ingest.parsers.solidity_parser import SolidityASTParser

parser = SolidityASTParser()

content = """
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "./IVerifier.sol";

contract Groth16Verifier is IVerifier {
    event ProofVerified(address indexed verifier, bool success);

    function verifyProof(
        uint256[2] memory a,
        uint256[2][2] memory b,
        uint256[2] memory c,
        uint256[1] memory input
    ) public override returns (bool) {
        // Verification logic
        emit ProofVerified(msg.sender, true);
        return true;
    }
}
"""

result = parser.parse_file("contracts/verifier.sol", content, "arda-credit")

for chunk in result.chunks:
    print(f"{chunk.item_type}: {chunk.item_name}")
    print(f"  Visibility: {chunk.metadata.get('visibility', 'internal')}")
```

### 4. DocumentationParser

**File:** `modules/ingest/parsers/documentation_parser.py`

**Purpose:** Parse Markdown documentation files to extract architectural knowledge, API documentation, and implementation guidance.

#### Class Signature

```python
class DocumentationParser:
    def __init__(self):
        """Initialize markdown parser with extensions."""
        self.md = markdown.Markdown(extensions=[
            'toc', 'tables', 'fenced_code', 'codehilite'
        ])

    def parse_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Parse markdown file into structured chunks."""
```

#### Document Type Classification

| Type | Patterns | Priority |
|------|----------|----------|
| `architecture` | architecture, overview, design, system | 0.9 |
| `api` | api, endpoint, swagger, integration | 0.8 |
| `authentication` | auth, login, magic-link, session, jwt | 0.8 |
| `deployment` | deploy, setup, install, config | 0.6 |
| `development` | dev, contributing, coding, guidelines | 0.7 |
| `integration` | integration, guide, example, tutorial | 0.7 |

#### DocumentationChunk Structure

```python
@dataclass
class DocumentationChunk:
    file_path: str              # "docs/ARCHITECTURE.md"
    content: str                # "## Authentication System\n..."
    start_line: int             # 45
    end_line: int               # 89
    item_name: str              # "Authentication System"
    item_type: str              # "architecture"
    use_statements: list        # [] (not applicable)
    doc_comments: list          # [] (not applicable)
    metadata: Dict[str, Any]    # {doc_type, section_level, importance_weight, ...}
```

#### Section Chunking Strategy

**Heading-Based Chunking:**
- Each H2 (`##`) becomes a separate chunk
- H3-H6 included in parent H2 chunk
- Code blocks preserved within chunks
- Tables preserved within chunks

**Example Structure:**
```markdown
# Document Title (H1 - metadata only)

## Authentication System (H2 - becomes chunk 1)
Content about auth...

### Magic Link Flow (H3 - included in chunk 1)
Details about magic links...

## API Endpoints (H2 - becomes chunk 2)
Content about API...
```

#### Example

```python
from modules.ingest.parsers.documentation_parser import DocumentationParser

parser = DocumentationParser()

chunks = parser.parse_file("docs/ARCHITECTURE.md")

for chunk in chunks:
    print(f"Section: {chunk['item_name']}")
    print(f"  Type: {chunk['metadata']['doc_type']}")
    print(f"  Importance: {chunk['metadata']['importance_weight']}")
    print(f"  Lines: {chunk['start_line']}-{chunk['end_line']}")
```

## Common Interfaces

### ParseResult Pattern

**All parsers return structured results:**

```python
@dataclass
class ParseResult:
    success: bool               # True if parsing succeeded
    chunks: List[CodeChunk]     # Extracted code chunks
    error_message: Optional[str]  # Error details if failed
    total_lines: int            # Total lines in file
    parsed_items: int           # Number of chunks extracted
```

**Usage:**
```python
result = parser.parse_file(file_path, content, repo_id)

if result.success:
    print(f"✅ Parsed {result.parsed_items} items from {result.total_lines} lines")
    for chunk in result.chunks:
        process_chunk(chunk)
else:
    print(f"❌ Parsing failed: {result.error_message}")
```

### Metadata Structure

**All chunks include rich metadata:**

```python
metadata = {
    # Common fields (all parsers)
    'language': str,            # rust, typescript, solidity, markdown
    'repo_id': str,             # arda-credit, arda-platform, arda-knowledge-hub, arda-chat-agent, ari-ui
    'repo_component': str,      # backend, frontend, contracts, docs
    'business_domain': str,     # finance, auth, ui, contracts, kyc
    'complexity_score': float,  # 0.0-1.0 (based on LOC, nesting)
    'line_count': int,          # Number of lines in chunk
    'chunk_hash': str,          # SHA256 hash for deduplication

    # Language-specific fields
    # Rust
    'is_public': bool,          # pub keyword present
    'is_async': bool,           # async keyword present
    'has_tests': bool,          # #[test] or #[cfg(test)]

    # TypeScript
    'is_react_component': bool, # React component detection
    'uses_hooks': bool,         # React hooks usage
    'is_typescript': bool,      # TypeScript vs JavaScript

    # Solidity
    'visibility': str,          # public, private, internal, external
    'state_mutability': str,    # view, pure, payable, nonpayable
    'is_interface': bool,       # Interface vs contract

    # Documentation
    'doc_type': str,            # architecture, api, authentication, etc.
    'section_level': int,       # 1-6 (H1-H6)
    'importance_weight': float  # 0.0-1.0 (based on section type)
}
```

## Business Domain Classification

**Pattern-Based Classification:**

```python
domain_patterns = {
    'finance': ['balance', 'transaction', 'payment', 'credit', 'loan', 'pool'],
    'auth': ['auth', 'login', 'session', 'magic_link', 'token', 'verification'],
    'ui': ['component', 'modal', 'form', 'button', 'layout', 'page', 'view'],
    'contracts': ['contract', 'solidity', 'ethereum', 'blockchain', 'verifier'],
    'trading': ['trading', 'marketplace', 'deal', 'investment', 'portfolio'],
    'kyc': ['kyc', 'identity', 'verification', 'compliance', 'investor'],
    'notifications': ['notification', 'email', 'alert', 'message']
}

def classify_business_domain(file_path: str, content: str) -> str:
    """Classify code chunk into business domain based on patterns."""
    content_lower = content.lower()

    for domain, patterns in domain_patterns.items():
        if any(pattern in content_lower for pattern in patterns):
            return domain

    return 'unknown'
```

**Example:**
```python
# File: backend/loan_service.rs
# Content: "pub fn approve_loan(loan_id: LoanId) -> ..."
# Domain: "finance" (matches 'loan' pattern)

# File: frontend/LoginForm.tsx
# Content: "const LoginForm = () => { ... useAuth() ... }"
# Domain: "auth" (matches 'auth' pattern)
```

## Complexity Scoring

**Factors:**
- **Line count**: More lines = higher complexity
- **Nesting depth**: Deeper nesting = higher complexity
- **Cyclomatic complexity**: More branches = higher complexity

```python
def calculate_complexity_score(content: str) -> float:
    """Calculate complexity score (0.0-1.0)."""
    lines = content.split('\n')
    line_count = len(lines)

    # Nesting depth (indent levels)
    max_indent = 0
    for line in lines:
        indent = len(line) - len(line.lstrip())
        max_indent = max(max_indent, indent // 4)

    # Branch keywords
    branch_keywords = ['if', 'else', 'match', 'case', 'for', 'while', 'loop']
    branch_count = sum(content.count(kw) for kw in branch_keywords)

    # Normalize scores (0.0-1.0)
    line_score = min(1.0, line_count / 200)
    nest_score = min(1.0, max_indent / 5)
    branch_score = min(1.0, branch_count / 10)

    # Weighted average
    return (line_score * 0.4) + (nest_score * 0.3) + (branch_score * 0.3)
```

**Usage:**
```python
complexity = calculate_complexity_score(chunk.content)

if complexity > 0.7:
    print("⚠️ High complexity chunk - may need refactoring")
elif complexity > 0.4:
    print("📊 Medium complexity chunk")
else:
    print("✅ Low complexity chunk")
```

## Performance Characteristics

| Parser | Typical Speed | Notes |
|--------|--------------|-------|
| **RustASTParser** | 50-100 files/sec | Tree-sitter: fast, Regex: slower |
| **TypeScriptASTParser** | 100-200 files/sec | Lightweight AST parsing |
| **SolidityASTParser** | 200-500 files/sec | Small files, fast parsing |
| **DocumentationParser** | 500-1000 files/sec | Markdown parsing very fast |

**Optimization Tips:**
- Use tree-sitter for accuracy (100% AST parsing)
- Batch file processing for higher throughput
- Skip large files (>500KB) to avoid memory issues

## Error Handling

### Parse Failures

**Common Causes:**
1. **Syntax errors** in source code
2. **Encoding issues** (non-UTF-8)
3. **Tree-sitter unavailable** (missing dependency)
4. **File too large** (>500KB)

**Handling:**
```python
result = parser.parse_file(file_path, content, repo_id)

if not result.success:
    logger.error(f"❌ Failed to parse {file_path}: {result.error_message}")

    # Check specific error types
    if "Syntax errors" in result.error_message:
        # File has compilation errors
        pass
    elif "Tree-sitter unavailable" in result.error_message:
        # Install tree-sitter dependencies
        pass
```

### Graceful Degradation

**Rust & TypeScript:** Fall back to regex parsing if tree-sitter unavailable
**Solidity:** Fail fast (no fallback due to complexity)
**Documentation:** Always succeeds (Python markdown is robust)

## Testing

### Unit Tests

```python
def test_rust_parser():
    parser = RustASTParser()
    content = "pub fn test_function() { println!(\"test\"); }"
    result = parser.parse_file("test.rs", content, "test-repo")

    assert result.success
    assert len(result.chunks) == 1
    assert result.chunks[0].item_type == "fn"
    assert result.chunks[0].item_name == "test_function"

def test_typescript_component():
    parser = TypeScriptASTParser()
    content = "const Button = () => <button>Click</button>;"
    result = parser.parse_file("Button.tsx", content, "test-repo")

    assert result.success
    assert result.chunks[0].metadata['is_react_component'] == True
```

## Related Documentation

- [Ingestion Pipeline](./PIPELINE.md) - Pipeline orchestration
- [Embedding Service](./EMBEDDING.md) - Embedding generation *(Coming soon)*
- [Vector Client](./VECTOR_CLIENT.md) - Vector storage *(Coming soon)*
- [Vector Search Architecture](../../architecture/VECTOR_SEARCH.md) - Search system

---

**Note:** This document is auto-synced with code. Update when modifying parser files in `modules/ingest/parsers/`.
