"""
Code analysis utility functions for quality metrics.
Provides language-aware parsing, name extraction, and classification for code quality tools.
"""

import re
import networkx as nx
from typing import List, Dict, Set, Optional, Tuple
from enum import Enum


class Severity(Enum):
    """Severity levels for code quality issues."""
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"


# ============================================================================
# Language-Specific Patterns
# ============================================================================

# Function patterns for different languages
FUNCTION_PATTERNS = {
    "rust": [
        r'(?:pub\s+)?(?:async\s+)?fn\s+([a-z_]\w*)',  # fn foo(), pub fn foo(), async fn foo()
        r'impl\s+\w+\s*{\s*(?:pub\s+)?fn\s+([a-z_]\w*)',  # impl methods
    ],
    "typescript": [
        r'function\s+([a-z_]\w*)',  # function foo()
        r'const\s+([a-z_]\w*)\s*=\s*(?:async\s+)?\(',  # const foo = () =>
        r'(?:async\s+)?([a-z_]\w*)\s*\([^)]*\)\s*{',  # foo() {
        r'(?:export\s+)?(?:async\s+)?function\s+([a-z_]\w*)',  # export function foo()
    ],
    "javascript": [
        r'function\s+([a-z_]\w*)',
        r'const\s+([a-z_]\w*)\s*=\s*(?:async\s+)?\(',
        r'(?:async\s+)?([a-z_]\w*)\s*\([^)]*\)\s*{',
    ],
    "python": [
        r'def\s+([a-z_]\w*)',  # def foo():
        r'async\s+def\s+([a-z_]\w*)',  # async def foo():
    ],
    "solidity": [
        r'function\s+([a-z_]\w*)',  # function foo()
    ],
}

# Type reference patterns
TYPE_PATTERNS = {
    "rust": [
        r':\s*([A-Z]\w+)',  # Type annotations: foo: Bar
        r'<([A-Z]\w+)>',  # Generics: Vec<String>
        r'impl\s+([A-Z]\w+)',  # impl Foo
        r'struct\s+([A-Z]\w+)',  # struct Foo
        r'enum\s+([A-Z]\w+)',  # enum Foo
    ],
    "typescript": [
        r':\s*([A-Z]\w+)',  # Type annotations
        r'<([A-Z]\w+)>',  # Generics
        r'interface\s+([A-Z]\w+)',  # interface Foo
        r'class\s+([A-Z]\w+)',  # class Foo
        r'type\s+([A-Z]\w+)',  # type Foo
    ],
    "python": [
        r'->\s*([A-Z]\w+)',  # Return type
        r':\s*([A-Z]\w+)',  # Type annotations
        r'class\s+([A-Z]\w+)',  # class Foo
    ],
}

# Import patterns
IMPORT_PATTERNS = {
    "rust": [
        r'use\s+([a-z_]\w*(?:::[a-z_]\w*)*)',  # use foo::bar
        r'use\s+crate::([a-z_]\w*(?:::[a-z_]\w*)*)',  # use crate::foo::bar
    ],
    "typescript": [
        r'import\s+.*\s+from\s+[\'"]([^\'"]+)[\'"]',  # import foo from "bar"
        r'require\([\'"]([^\'"]+)[\'"]\)',  # require("foo")
    ],
    "javascript": [
        r'import\s+.*\s+from\s+[\'"]([^\'"]+)[\'"]',
        r'require\([\'"]([^\'"]+)[\'"]\)',
    ],
    "python": [
        r'import\s+([a-z_]\w*)',  # import foo
        r'from\s+([a-z_]\w*)\s+import',  # from foo import bar
    ],
}

# Test file patterns
TEST_FILE_PATTERNS = {
    "rust": [r'.*_test\.rs$', r'^test_.*\.rs$', r'.*/tests/.*\.rs$'],
    "typescript": [r'.*\.test\.ts$', r'.*\.spec\.ts$', r'.*/tests/.*\.ts$'],
    "javascript": [r'.*\.test\.js$', r'.*\.spec\.js$', r'.*/tests/.*\.js$'],
    "python": [r'test_.*\.py$', r'.*_test\.py$', r'.*/tests/.*\.py$'],
    "solidity": [r'.*\.t\.sol$', r'.*/test/.*\.sol$'],
}

# Mock patterns for test analysis
MOCK_PATTERNS = [
    r'jest\.mock\(',  # Jest
    r'MockBuilder',  # Rust mock_builder
    r'mock_',  # Generic mock prefix
    r'stub_',  # Generic stub prefix
    r'\.mockReturnValue',  # Jest mocks
    r'\.mockResolvedValue',  # Jest async mocks
    r'expect\(\w+\)\.toHaveBeenCalled',  # Jest spy assertions
]

# Specific assertion patterns (good)
SPECIFIC_ASSERTION_PATTERNS = [
    r'assert_eq!',  # Rust specific equality
    r'assert_ne!',  # Rust specific inequality
    r'\.toBe\(',  # Jest specific equality
    r'\.toEqual\(',  # Jest deep equality
    r'\.toStrictEqual\(',  # Jest strict equality
    r'\.toContain\(',  # Jest contains
    r'\.toMatch\(',  # Jest regex match
    r'assertEqual\(',  # Python
    r'expect\(',  # Solidity Foundry
]

# Generic assertion patterns (less valuable)
GENERIC_ASSERTION_PATTERNS = [
    r'assert!',  # Rust generic assertion
    r'\.toBeTruthy\(',  # Jest truthy
    r'\.toBeFalsy\(',  # Jest falsy
    r'assertTrue\(',  # Python
    r'assertFalse\(',  # Python
]


# ============================================================================
# Generic Name Detection
# ============================================================================

# Generic function names that indicate poor naming
GENERIC_FUNCTION_NAMES = {
    "process", "handle", "do", "execute", "run", "perform",
    "process_data", "handle_request", "handle_response",
    "do_something", "do_work", "execute_task",
    "run_task", "perform_action", "perform_operation",
    "get_data", "set_data", "update_data",
    "handler", "processor", "manager", "helper",
    "util", "utils", "common", "main",
}

# Generic variable names
GENERIC_VARIABLE_NAMES = {
    "data", "info", "obj", "item", "tmp", "temp",
    "result", "response", "value", "val", "x", "y",
}

# Allowed short names by language (common idioms)
ALLOWED_SHORT_NAMES = {
    "rust": {"i", "j", "k", "n", "ok", "err", "tx", "rx"},
    "typescript": {"i", "j", "k", "id", "el", "e", "x", "y"},
    "javascript": {"i", "j", "k", "id", "el", "e", "x", "y"},
    "python": {"i", "j", "k", "n", "x", "y", "e"},
    "solidity": {"i", "j", "k", "n"},
}


def is_generic_name(name: str) -> bool:
    """
    Check if a name is generic/non-descriptive.

    Args:
        name: Function or variable name to check

    Returns:
        True if name is generic, False otherwise
    """
    name_lower = name.lower()
    return name_lower in GENERIC_FUNCTION_NAMES or name_lower in GENERIC_VARIABLE_NAMES


def is_single_letter(name: str, language: str = "rust") -> bool:
    """
    Check if name is a single letter (excluding allowed idioms).

    Args:
        name: Variable name to check
        language: Programming language for context

    Returns:
        True if single letter and not allowed, False otherwise
    """
    if len(name) > 1:
        return False

    allowed = ALLOWED_SHORT_NAMES.get(language, set())
    return name.lower() not in allowed


def classify_name_quality(name: str, is_public: bool = False) -> Severity:
    """
    Classify the severity of a poor name.

    Args:
        name: Function or variable name
        is_public: Whether this is a public API function

    Returns:
        Severity level (CRITICAL, MAJOR, or MINOR)
    """
    if is_generic_name(name):
        return Severity.CRITICAL if is_public else Severity.MAJOR

    if is_single_letter(name):
        return Severity.MINOR

    return Severity.MINOR  # Default for other issues


# ============================================================================
# Code Parsing Functions
# ============================================================================

def extract_function_names(content: str, language: str) -> List[Tuple[str, bool]]:
    """
    Extract function names from code content.

    Args:
        content: Code content to parse
        language: Programming language

    Returns:
        List of tuples (function_name, is_public)
    """
    patterns = FUNCTION_PATTERNS.get(language, [])
    functions = []

    for pattern in patterns:
        matches = re.findall(pattern, content, re.MULTILINE)
        for match in matches:
            # Check if function is public (has 'pub' keyword for Rust, 'export' for TS)
            is_public = bool(re.search(r'(?:pub|export)\s+(?:async\s+)?fn\s+' + re.escape(match), content))
            functions.append((match, is_public))

    return functions


def extract_type_references(content: str, language: str) -> List[str]:
    """
    Extract type references from code content.

    Args:
        content: Code content to parse
        language: Programming language

    Returns:
        List of type names referenced in the code
    """
    patterns = TYPE_PATTERNS.get(language, [])
    types = []

    for pattern in patterns:
        matches = re.findall(pattern, content)
        types.extend(matches)

    # Deduplicate and filter out common built-in types
    builtin_types = {
        "String", "Vec", "Option", "Result", "Box",  # Rust
        "Promise", "Array", "Map", "Set",  # TypeScript
        "List", "Dict", "Tuple",  # Python
    }

    return [t for t in set(types) if t not in builtin_types]


def extract_imports(content: str, language: str) -> List[str]:
    """
    Extract import statements from code content.

    Args:
        content: Code content to parse
        language: Programming language

    Returns:
        List of imported module paths
    """
    patterns = IMPORT_PATTERNS.get(language, [])
    imports = []

    for pattern in patterns:
        matches = re.findall(pattern, content)
        imports.extend(matches)

    return list(set(imports))


def extract_function_calls(content: str, language: str) -> List[str]:
    """
    Extract function call names from code content.

    Args:
        content: Code content to parse
        language: Programming language

    Returns:
        List of function names called in the code
    """
    # Simple pattern to match function calls
    pattern = r'([a-z_]\w*)\s*\('
    calls = re.findall(pattern, content)

    # Filter out common keywords
    keywords = {"if", "while", "for", "match", "return", "assert"}
    return [c for c in set(calls) if c not in keywords]


# ============================================================================
# Test Analysis Functions
# ============================================================================

def is_test_file(file_path: str, language: str) -> bool:
    """
    Check if a file is a test file based on naming patterns.

    Args:
        file_path: Path to the file
        language: Programming language

    Returns:
        True if file is a test file, False otherwise
    """
    patterns = TEST_FILE_PATTERNS.get(language, [])
    return any(re.search(pattern, file_path) for pattern in patterns)


def find_test_file_for(impl_file: str, language: str) -> Optional[str]:
    """
    Find the corresponding test file for an implementation file.

    Args:
        impl_file: Implementation file path
        language: Programming language

    Returns:
        Expected test file path, or None
    """
    if language == "rust":
        # foo.rs -> foo_test.rs or tests/foo_test.rs
        base = impl_file.replace(".rs", "")
        return f"{base}_test.rs"

    elif language in ["typescript", "javascript"]:
        # foo.ts -> foo.test.ts
        ext = ".ts" if language == "typescript" else ".js"
        base = impl_file.replace(ext, "")
        return f"{base}.test{ext}"

    elif language == "python":
        # foo.py -> test_foo.py
        filename = impl_file.split("/")[-1].replace(".py", "")
        return f"test_{filename}.py"

    elif language == "solidity":
        # Foo.sol -> Foo.t.sol
        base = impl_file.replace(".sol", "")
        return f"{base}.t.sol"

    return None


def analyze_mock_density(test_content: str) -> Dict:
    """
    Analyze mock usage density in test code.

    Args:
        test_content: Test file content

    Returns:
        Dictionary with mock analysis metrics
    """
    # Count mocks
    mock_count = sum(len(re.findall(pattern, test_content)) for pattern in MOCK_PATTERNS)

    # Count assertions
    specific_assertion_count = sum(len(re.findall(pattern, test_content)) for pattern in SPECIFIC_ASSERTION_PATTERNS)
    generic_assertion_count = sum(len(re.findall(pattern, test_content)) for pattern in GENERIC_ASSERTION_PATTERNS)
    total_assertions = specific_assertion_count + generic_assertion_count

    # Calculate ratios
    mock_ratio = mock_count / max(total_assertions, 1)  # Avoid division by zero
    specificity_ratio = specific_assertion_count / max(total_assertions, 1)

    # Classify quality
    if mock_ratio > 2.0:
        quality = "over_mocked"
    elif mock_ratio > 1.0:
        quality = "moderately_mocked"
    else:
        quality = "behavior_focused"

    return {
        "mock_count": mock_count,
        "assertion_count": total_assertions,
        "specific_assertions": specific_assertion_count,
        "generic_assertions": generic_assertion_count,
        "mock_ratio": round(mock_ratio, 2),
        "specificity_ratio": round(specificity_ratio, 2),
        "quality": quality
    }


# ============================================================================
# Dependency Graph Functions
# ============================================================================

def build_dependency_graph(chunks: List[Dict]) -> nx.DiGraph:
    """
    Build a dependency graph from code chunks.

    Args:
        chunks: List of code chunk dictionaries with payload data

    Returns:
        NetworkX directed graph of file dependencies
    """
    graph = nx.DiGraph()

    for chunk in chunks:
        payload = chunk.get("payload", {})
        file_path = payload.get("file_path", "")
        content = payload.get("content_preview", "")
        language = payload.get("language", "rust")

        if not file_path or not content:
            continue

        # Add node
        graph.add_node(file_path)

        # Extract imports and add edges
        imports = extract_imports(content, language)
        for imp in imports:
            # Resolve import to file path (simplified)
            dep_path = resolve_import_to_file(imp, file_path, language)
            if dep_path and dep_path != file_path:
                graph.add_edge(file_path, dep_path)

    return graph


def resolve_import_to_file(import_path: str, source_file: str, language: str) -> Optional[str]:
    """
    Resolve an import statement to a file path.

    Args:
        import_path: Import path (e.g., "crate::foo::bar" or "../foo")
        source_file: File containing the import
        language: Programming language

    Returns:
        Resolved file path, or None if cannot resolve
    """
    # Simplified resolution - in production, this would need proper path resolution
    if language == "rust":
        # crate::foo::bar -> src/foo/bar.rs
        if import_path.startswith("crate::"):
            parts = import_path.replace("crate::", "").split("::")
            return f"src/{'/'.join(parts)}.rs"
        else:
            parts = import_path.split("::")
            return f"src/{'/'.join(parts)}.rs"

    elif language in ["typescript", "javascript"]:
        # Relative imports: ../foo -> resolve relative to source_file
        if import_path.startswith("."):
            # Simplified - just return the import path
            return import_path.replace("./", "").replace("../", "")
        else:
            # Package import - skip external packages
            return None

    return None


def detect_cycles(graph: nx.DiGraph) -> List[List[str]]:
    """
    Detect circular dependencies in the dependency graph.

    Args:
        graph: Dependency graph

    Returns:
        List of cycles (each cycle is a list of file paths)
    """
    try:
        cycles = list(nx.simple_cycles(graph))
        return cycles
    except Exception:
        return []


def find_god_modules(graph: nx.DiGraph, threshold: int = 10) -> List[Dict]:
    """
    Find "god modules" that are depended upon by many other modules.

    Args:
        graph: Dependency graph
        threshold: Minimum number of dependents to be considered a god module

    Returns:
        List of god module dictionaries with file path and dependent count
    """
    god_modules = []

    for node in graph.nodes():
        in_degree = graph.in_degree(node)
        if in_degree >= threshold:
            god_modules.append({
                "module": node,
                "dependent_count": in_degree,
                "dependents": list(graph.predecessors(node))[:5]  # Sample of dependents
            })

    # Sort by dependent count descending
    god_modules.sort(key=lambda x: x["dependent_count"], reverse=True)
    return god_modules


def calculate_coupling_metrics(graph: nx.DiGraph) -> Dict:
    """
    Calculate coupling metrics from dependency graph.

    Args:
        graph: Dependency graph

    Returns:
        Dictionary with coupling metrics
    """
    node_count = graph.number_of_nodes()
    edge_count = graph.number_of_edges()

    if node_count == 0:
        return {
            "coupling_ratio": 0.0,
            "avg_in_degree": 0.0,
            "avg_out_degree": 0.0,
            "total_modules": 0,
            "total_dependencies": 0
        }

    # Coupling ratio: edges / nodes (lower is better)
    coupling_ratio = edge_count / node_count

    # Average degrees
    avg_in_degree = sum(dict(graph.in_degree()).values()) / node_count
    avg_out_degree = sum(dict(graph.out_degree()).values()) / node_count

    return {
        "coupling_ratio": round(coupling_ratio, 2),
        "avg_in_degree": round(avg_in_degree, 2),
        "avg_out_degree": round(avg_out_degree, 2),
        "total_modules": node_count,
        "total_dependencies": edge_count
    }


# ============================================================================
# Scoring and Grading Functions
# ============================================================================

def score_to_grade(score: float) -> str:
    """
    Convert numeric score to letter grade.

    Args:
        score: Numeric score (0-100)

    Returns:
        Letter grade (A, B+, B, C+, C, D, F)
    """
    if score >= 97:
        return "A+"
    elif score >= 93:
        return "A"
    elif score >= 90:
        return "A-"
    elif score >= 87:
        return "B+"
    elif score >= 83:
        return "B"
    elif score >= 80:
        return "B-"
    elif score >= 77:
        return "C+"
    elif score >= 73:
        return "C"
    elif score >= 70:
        return "C-"
    elif score >= 67:
        return "D+"
    elif score >= 63:
        return "D"
    elif score >= 60:
        return "D-"
    else:
        return "F"


def calculate_weighted_score(scores: Dict[str, float], weights: Dict[str, float]) -> float:
    """
    Calculate weighted average score.

    Args:
        scores: Dictionary of metric names to scores
        weights: Dictionary of metric names to weights (should sum to 1.0)

    Returns:
        Weighted average score
    """
    total_score = 0.0
    total_weight = 0.0

    for metric, score in scores.items():
        weight = weights.get(metric, 0.0)
        if score is not None:
            total_score += score * weight
            total_weight += weight

    # Normalize by actual weights used (in case some metrics are missing)
    if total_weight > 0:
        return round(total_score / total_weight * sum(weights.values()), 2)

    return 0.0


# ============================================================================
# Architecture Coherence Analysis Functions
# ============================================================================

# Architectural layers (ordered from high to low)
ARCHITECTURE_LAYERS = {
    "ui": 4,  # Frontend/UI layer
    "api": 3,  # API/Controller layer
    "service": 2,  # Business logic/Service layer
    "database": 1,  # Data access layer
}


def detect_layer(file_path: str) -> str:
    """
    Detect architectural layer from file path.

    Args:
        file_path: Path to the file

    Returns:
        Layer name: "ui", "api", "service", "database", or "unknown"
    """
    path_lower = file_path.lower()

    # UI layer patterns
    if any(pattern in path_lower for pattern in [
        "frontend", "ui", "components", "pages", "views",
        "react", "vue", "svelte", "angular"
    ]):
        return "ui"

    # API layer patterns
    if any(pattern in path_lower for pattern in [
        "/api/", "/routes/", "/controllers/", "/handlers/",
        "/endpoints/", "router"
    ]):
        return "api"

    # Service layer patterns
    if any(pattern in path_lower for pattern in [
        "/services/", "/business/", "/logic/", "/domain/",
        "/use_cases/", "/usecases/"
    ]):
        return "service"

    # Database layer patterns
    if any(pattern in path_lower for pattern in [
        "/database/", "/db/", "/models/", "/repositories/",
        "/dao/", "/entities/", "schema", "migration"
    ]):
        return "database"

    return "unknown"


def find_layer_violations(graph: nx.DiGraph, chunks: List[Dict]) -> List[Dict]:
    """
    Find dependencies that violate layering rules.

    A layer violation occurs when a lower layer depends on a higher layer.
    For example, database layer importing UI code.

    Args:
        graph: Dependency graph
        chunks: List of code chunks with file paths

    Returns:
        List of violation dictionaries
    """
    violations = []

    # Build file to layer mapping
    file_layers = {}
    for chunk in chunks:
        file_path = chunk.get("payload", {}).get("file_path", "")
        if file_path:
            file_layers[file_path] = detect_layer(file_path)

    # Check each edge in the dependency graph
    for from_file, to_file in graph.edges():
        from_layer = file_layers.get(from_file, "unknown")
        to_layer = file_layers.get(to_file, "unknown")

        # Skip unknown layers
        if from_layer == "unknown" or to_layer == "unknown":
            continue

        from_level = ARCHITECTURE_LAYERS.get(from_layer, 0)
        to_level = ARCHITECTURE_LAYERS.get(to_layer, 0)

        # Violation: lower layer depending on higher layer
        if from_level < to_level:
            severity = "critical" if from_level == 1 else "major"  # Database violations are critical

            violations.append({
                "from_layer": from_layer,
                "to_layer": to_layer,
                "from_file": from_file,
                "to_file": to_file,
                "severity": severity,
                "description": f"{from_layer.capitalize()} layer should not depend on {to_layer} layer"
            })

    return violations


def identify_services(file_paths: List[str]) -> Dict[str, List[str]]:
    """
    Identify services from file paths.

    Args:
        file_paths: List of file paths

    Returns:
        Dictionary mapping service names to their file paths
    """
    services = {}

    for file_path in file_paths:
        # Look for service directories
        # Pattern: services/auth/, services/payment/, src/auth/, src/payment/
        parts = file_path.split("/")

        for i, part in enumerate(parts):
            if part in ["services", "src", "modules", "apps"]:
                if i + 1 < len(parts):
                    service_name = parts[i + 1]
                    if service_name not in services:
                        services[service_name] = []
                    services[service_name].append(file_path)
                    break

    return services


def analyze_service_boundaries(graph: nx.DiGraph, chunks: List[Dict]) -> Dict:
    """
    Analyze service coupling and boundary clarity.

    Args:
        graph: Dependency graph
        chunks: List of code chunks with file paths

    Returns:
        Dictionary with service boundary analysis
    """
    # Get all file paths
    file_paths = [chunk.get("payload", {}).get("file_path", "") for chunk in chunks if chunk.get("payload", {}).get("file_path")]

    # Identify services
    services = identify_services(file_paths)

    if not services:
        return {
            "score": 100.0,
            "services_identified": [],
            "cross_service_dependencies": [],
            "avg_boundary_clarity": 1.0
        }

    # Build file to service mapping
    file_to_service = {}
    for service_name, files in services.items():
        for file_path in files:
            file_to_service[file_path] = service_name

    # Analyze cross-service dependencies
    cross_service_deps = []
    service_boundary_clarity = {}

    for service_name in services:
        internal_deps = 0
        external_deps = 0

        service_files = set(services[service_name])

        for from_file in service_files:
            if from_file not in graph:
                continue

            for to_file in graph.successors(from_file):
                if to_file in service_files:
                    internal_deps += 1
                else:
                    external_deps += 1
                    to_service = file_to_service.get(to_file, "unknown")

                    if to_service != "unknown":
                        # Record cross-service dependency
                        dep_key = (service_name, to_service)
                        existing = next((d for d in cross_service_deps if d["from_service"] == service_name and d["to_service"] == to_service), None)

                        if existing:
                            existing["dependency_count"] += 1
                        else:
                            cross_service_deps.append({
                                "from_service": service_name,
                                "to_service": to_service,
                                "dependency_count": 1,
                                "coupling_strength": 0.0  # Will calculate below
                            })

        # Calculate boundary clarity for this service
        total_deps = internal_deps + external_deps
        if total_deps > 0:
            clarity = internal_deps / total_deps
            service_boundary_clarity[service_name] = clarity

    # Calculate coupling strength for cross-service deps
    for dep in cross_service_deps:
        from_service = dep["from_service"]
        to_service = dep["to_service"]
        from_size = len(services.get(from_service, []))
        to_size = len(services.get(to_service, []))

        if from_size > 0:
            # Normalize by service size
            dep["coupling_strength"] = round(dep["dependency_count"] / from_size, 3)

    # Calculate average boundary clarity
    avg_clarity = sum(service_boundary_clarity.values()) / len(service_boundary_clarity) if service_boundary_clarity else 1.0

    # Calculate score (higher clarity = higher score)
    score = round(avg_clarity * 100, 1)

    return {
        "score": score,
        "services_identified": list(services.keys()),
        "cross_service_dependencies": sorted(cross_service_deps, key=lambda x: x["coupling_strength"], reverse=True)[:20],  # Top 20
        "avg_boundary_clarity": round(avg_clarity, 3)
    }


# Pattern detection regexes
ERROR_HANDLING_PATTERNS = {
    "rust": {
        "Result<T,E>": r'Result<[\w,\s<>]+>',
        "Option<T>": r'Option<[\w\s<>]+>',
        "panic!": r'panic!\(',
        "unwrap": r'\.unwrap\(',
    },
    "typescript": {
        "try/catch": r'try\s*{[\s\S]*?}\s*catch',
        "Promise": r'Promise<[\w\s<>]+>',
        "throw": r'throw\s+',
        ".catch()": r'\.catch\(',
    },
    "python": {
        "try/except": r'try:[\s\S]*?except',
        "raise": r'raise\s+\w+',
        "assert": r'assert\s+',
    }
}

API_STYLE_PATTERNS = {
    "REST": r'@(Get|Post|Put|Delete|Patch)\(',
    "GraphQL": r'(@Query|@Mutation|type Query|type Mutation)',
    "RPC": r'(\.rpc\(|@rpc|def rpc_)',
}


def extract_patterns(content: str, language: str) -> Dict[str, str]:
    """
    Extract code patterns from content.

    Args:
        content: Code content to analyze
        language: Programming language

    Returns:
        Dictionary mapping pattern categories to detected patterns
    """
    patterns_found = {}

    # Error handling patterns
    error_patterns = ERROR_HANDLING_PATTERNS.get(language, {})
    for pattern_name, regex in error_patterns.items():
        if re.search(regex, content):
            patterns_found.setdefault("error_handling", []).append(pattern_name)

    # API style patterns (language-agnostic)
    for style_name, regex in API_STYLE_PATTERNS.items():
        if re.search(regex, content):
            patterns_found.setdefault("api_style", []).append(style_name)

    return patterns_found


def analyze_pattern_consistency(chunks: List[Dict]) -> Dict:
    """
    Measure pattern usage consistency across codebase.

    Args:
        chunks: List of code chunks with content

    Returns:
        Dictionary with pattern consistency analysis
    """
    # Count pattern usage
    pattern_counts = {
        "error_handling": {},
        "api_style": {}
    }

    language_map = {
        "rust": "rust",
        "typescript": "typescript",
        "javascript": "typescript",  # Use TS patterns for JS
        "python": "python"
    }

    for chunk in chunks:
        payload = chunk.get("payload", {})
        content = payload.get("content_preview", "")
        language = language_map.get(payload.get("language", "").lower(), "typescript")

        patterns = extract_patterns(content, language)

        for category, pattern_list in patterns.items():
            for pattern in pattern_list:
                pattern_counts[category][pattern] = pattern_counts[category].get(pattern, 0) + 1

    # Calculate consistency score
    # High consistency = one dominant pattern in each category
    consistency_scores = []

    for category, counts in pattern_counts.items():
        if not counts:
            continue

        total = sum(counts.values())
        max_count = max(counts.values())
        dominant_ratio = max_count / total if total > 0 else 0
        consistency_scores.append(dominant_ratio)

    overall_score = (sum(consistency_scores) / len(consistency_scores) * 100) if consistency_scores else 100

    # Identify inconsistencies (patterns with <20% usage)
    inconsistencies = []
    for category, counts in pattern_counts.items():
        total = sum(counts.values())
        if total == 0:
            continue

        for pattern, count in counts.items():
            ratio = count / total
            if ratio < 0.2 and total > 10:  # Only flag if we have enough samples
                inconsistencies.append({
                    "category": category,
                    "pattern": pattern,
                    "usage_count": count,
                    "usage_ratio": round(ratio, 2),
                    "description": f"Rarely used {category} pattern: {pattern} ({count}/{total})"
                })

    return {
        "score": round(overall_score, 1),
        "patterns_found": pattern_counts,
        "inconsistencies": inconsistencies[:10]  # Top 10
    }


def extract_api_contracts(chunks: List[Dict]) -> List[Dict]:
    """
    Extract API definitions and analyze consistency.

    Args:
        chunks: List of code chunks

    Returns:
        List of API contract dictionaries
    """
    apis = []

    # API endpoint patterns
    api_patterns = [
        r'@(Get|Post|Put|Delete|Patch)\(["\']([^"\']+)["\']\)',  # Decorators
        r'\.route\(["\']([^"\']+)["\']\)',  # Express-style
        r'async\s+fn\s+(\w+)',  # Rust async handlers
    ]

    for chunk in chunks:
        payload = chunk.get("payload", {})
        content = payload.get("content_preview", "")
        file_path = payload.get("file_path", "")

        for pattern in api_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                if isinstance(match, tuple):
                    method, path = match[0], match[1] if len(match) > 1 else ""
                else:
                    method, path = "unknown", match

                apis.append({
                    "method": method,
                    "path": path,
                    "file": file_path,
                    "naming_convention": detect_naming_convention(path)
                })

    return apis


def detect_naming_convention(name: str) -> str:
    """Detect naming convention used in a string."""
    if re.match(r'^[a-z]+(_[a-z]+)*$', name):
        return "snake_case"
    elif re.match(r'^[a-z]+([A-Z][a-z]+)*$', name):
        return "camelCase"
    elif re.match(r'^[A-Z][a-z]+([A-Z][a-z]+)*$', name):
        return "PascalCase"
    elif re.match(r'^[a-z]+(-[a-z]+)*$', name):
        return "kebab-case"
    else:
        return "mixed"


# ============================================================================
# Documentation Analysis Functions
# ============================================================================

# Documentation patterns by language
DOC_PATTERNS = {
    "rust": [
        r'///[^\n]*',  # Line doc comments
        r'//![^\n]*',  # Inner line doc comments
        r'/\*\*[\s\S]*?\*/',  # Block doc comments
    ],
    "typescript": [
        r'/\*\*[\s\S]*?\*/',  # JSDoc comments
    ],
    "javascript": [
        r'/\*\*[\s\S]*?\*/',  # JSDoc comments
    ],
    "python": [
        r'"""[\s\S]*?"""',  # Triple-quoted docstrings
        r"'''[\s\S]*?'''",  # Single-quoted docstrings
    ],
    "solidity": [
        r'///[^\n]*',  # NatSpec single-line
        r'/\*\*[\s\S]*?\*/',  # NatSpec multi-line
    ]
}


def has_documentation(content: str, language: str, item_line: int) -> Tuple[bool, str]:
    """
    Check if an item has documentation within 3 lines.

    Args:
        content: Full file content
        language: Programming language
        item_line: Line number of the item

    Returns:
        Tuple of (has_docs: bool, doc_text: str)
    """
    patterns = DOC_PATTERNS.get(language, [])
    if not patterns:
        return False, ""

    lines = content.split("\n")
    start_line = max(0, item_line - 4)  # Check 3 lines before
    end_line = min(len(lines), item_line + 1)

    relevant_content = "\n".join(lines[start_line:end_line])

    for pattern in patterns:
        match = re.search(pattern, relevant_content)
        if match:
            return True, match.group(0)

    return False, ""


def assess_doc_quality(doc_text: str) -> Dict:
    """
    Assess documentation quality.

    Args:
        doc_text: Documentation text

    Returns:
        Dictionary with quality metrics
    """
    if not doc_text:
        return {
            "length": 0,
            "has_example": False,
            "has_params": False,
            "has_returns": False,
            "quality_score": 0
        }

    length = len(doc_text)

    # Check for common documentation elements
    has_example = bool(re.search(r'(example|Example|EXAMPLE|```)', doc_text, re.IGNORECASE))
    has_params = bool(re.search(r'(@param|@arg|Args:|Parameters:)', doc_text, re.IGNORECASE))
    has_returns = bool(re.search(r'(@return|@returns|Returns:)', doc_text, re.IGNORECASE))

    # Calculate quality score (0-100)
    quality_score = 0
    if length > 20:
        quality_score += 25  # Has reasonable length
    if length > 100:
        quality_score += 25  # Has detailed description
    if has_params:
        quality_score += 25  # Documents parameters
    if has_returns:
        quality_score += 15  # Documents return value
    if has_example:
        quality_score += 10  # Has example

    return {
        "length": length,
        "has_example": has_example,
        "has_params": has_params,
        "has_returns": has_returns,
        "quality_score": quality_score
    }
