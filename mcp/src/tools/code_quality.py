"""MCP tools for code quality analysis - "Oink Score" metrics."""

import logging
import asyncio
from typing import Dict, List, Optional, Set
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError, NotFoundError

# Import helper functions from code_analysis module
from src.utils.code_analysis import (
    extract_function_names,
    extract_type_references,
    extract_imports,
    extract_function_calls,
    is_generic_name,
    is_single_letter,
    classify_name_quality,
    is_test_file,
    find_test_file_for,
    analyze_mock_density,
    build_dependency_graph,
    detect_cycles,
    find_god_modules,
    calculate_coupling_metrics,
    score_to_grade,
    calculate_weighted_score,
    Severity,
)

logger = logging.getLogger(__name__)

# Global state - will be set by server module
_semantic_search_impl = None
_list_collections_impl = None
_query_cache = None
_github_token = None


def set_quality_globals(semantic_search_fn, list_collections_fn, query_cache, github_token):
    """
    Set global state references needed by code quality tools.

    Args:
        semantic_search_fn: Function to perform semantic search
        list_collections_fn: Function to list collections
        query_cache: Query cache instance
        github_token: GitHub API token for PR metrics
    """
    global _semantic_search_impl, _list_collections_impl, _query_cache, _github_token
    _semantic_search_impl = semantic_search_fn
    _list_collections_impl = list_collections_fn
    _query_cache = query_cache
    _github_token = github_token


# ============================================================================
# Tool 1: Semantic Coherence Analysis (Priority 1)
# ============================================================================

async def _analyze_semantic_coherence_impl(
    collection_name: str = "arda_code_rust",
    scope: str = "repository",
    file_path: Optional[str] = None
) -> dict:
    """
    Internal implementation of semantic coherence analysis.

    Args:
        collection_name: Target collection to analyze
        scope: Analysis scope (repository, file, pr)
        file_path: Optional specific file to analyze

    Returns:
        Dictionary with coherence score, issues, and recommendations
    """
    try:
        logger.info(f"🔍 Analyzing semantic coherence: {collection_name} (scope={scope})")

        # Check cache first
        cache_params = {"scope": scope, "file_path": file_path}
        cached_result = _query_cache.get("semantic_coherence", collection_name, cache_params)
        if cached_result:
            logger.info("   ⚡ Returned from cache")
            return cached_result

        # Search for function definitions
        search_query = "function definition method implementation"
        if file_path:
            search_query += f" {file_path}"

        results = await _semantic_search_impl(
            query=search_query,
            collection_name=collection_name,
            limit=50,
            score_threshold=0.4
        )

        # Analyze function names
        issues_found = []
        function_count = 0
        critical_count = 0
        major_count = 0
        minor_count = 0

        language_map = {
            "arda_code_rust": "rust",
            "arda_code_typescript": "typescript",
            "arda_code_javascript": "javascript",
            "arda_code_python": "python",
            "arda_code_solidity": "solidity",
        }
        language = language_map.get(collection_name, "rust")

        seen_functions = set()  # Deduplicate

        for result in results.get("results", []):
            payload = result.get("payload", {})
            content = payload.get("content_preview", "")
            file = payload.get("file_path", "unknown")
            start_line = payload.get("start_line", 0)

            # Extract function names
            functions = extract_function_names(content, language)

            for func_name, is_public in functions:
                # Skip duplicates
                if func_name in seen_functions:
                    continue
                seen_functions.add(func_name)

                function_count += 1

                # Check for generic names
                if is_generic_name(func_name):
                    severity = classify_name_quality(func_name, is_public)

                    # Suggest better name
                    suggestion = f"Rename to describe the specific action (e.g., 'validate_payment', 'calculate_fee')"

                    issue = {
                        "severity": severity.value,
                        "file_path": file,
                        "line": start_line,
                        "issue_type": "generic_function_name",
                        "name": func_name,
                        "is_public": is_public,
                        "suggestion": suggestion,
                        "context": content[:100]
                    }
                    issues_found.append(issue)

                    # Count by severity
                    if severity == Severity.CRITICAL:
                        critical_count += 1
                    elif severity == Severity.MAJOR:
                        major_count += 1
                    else:
                        minor_count += 1

                # Check for single-letter names (less severe)
                elif is_single_letter(func_name, language):
                    issue = {
                        "severity": "minor",
                        "file_path": file,
                        "line": start_line,
                        "issue_type": "single_letter_name",
                        "name": func_name,
                        "suggestion": "Use a descriptive name",
                        "context": content[:100]
                    }
                    issues_found.append(issue)
                    minor_count += 1

        # Calculate score
        # Base score of 100, deduct points for issues
        penalty = (critical_count * 10) + (major_count * 5) + (minor_count * 2)
        coherence_score = max(0, 100 - penalty)

        # Generate recommendations
        recommendations = []
        if critical_count > 0:
            recommendations.append(f"CRITICAL: Fix {critical_count} generic names in public APIs")
        if major_count > 5:
            recommendations.append(f"Review {major_count} generic private function names")
        if minor_count > 10:
            recommendations.append(f"Consider improving {minor_count} minor naming issues")

        # Identify hot spots (files with most issues)
        file_issue_counts = {}
        for issue in issues_found:
            file = issue["file_path"]
            file_issue_counts[file] = file_issue_counts.get(file, 0) + 1

        if file_issue_counts:
            worst_file = max(file_issue_counts.items(), key=lambda x: x[1])
            recommendations.append(f"Focus on {worst_file[0]} - {worst_file[1]} issues found")

        result = {
            "coherence_score": round(coherence_score, 1),
            "grade": score_to_grade(coherence_score),
            "functions_analyzed": function_count,
            "issues_found": issues_found[:20],  # Limit to top 20 for response size
            "total_issues": len(issues_found),
            "by_severity": {
                "critical": critical_count,
                "major": major_count,
                "minor": minor_count
            },
            "statistics": {
                "generic_function_names": critical_count + major_count,
                "single_letter_names": minor_count,
                "issue_rate": round(len(issues_found) / max(function_count, 1), 2)
            },
            "recommendations": recommendations
        }

        # Cache result
        _query_cache.put("semantic_coherence", collection_name, cache_params, result)

        return result

    except Exception as e:
        logger.exception(f"Semantic coherence analysis failed: {e}")
        raise ToolError(f"Analysis failed: {str(e)}") from e


# ============================================================================
# Tool 2: Test Elasticity Analysis (Priority 2)
# ============================================================================

async def _analyze_test_elasticity_impl(
    collection_name: str = "arda_code_rust",
    module_path: Optional[str] = None
) -> dict:
    """
    Internal implementation of test elasticity analysis.

    Args:
        collection_name: Target collection to analyze
        module_path: Optional specific module to analyze

    Returns:
        Dictionary with elasticity score, test coverage map, and brittle tests
    """
    try:
        logger.info(f"🧪 Analyzing test elasticity: {collection_name}")

        # Check cache
        cache_params = {"module_path": module_path}
        cached_result = _query_cache.get("test_elasticity", collection_name, cache_params)
        if cached_result:
            logger.info("   ⚡ Returned from cache")
            return cached_result

        # Determine language
        language_map = {
            "arda_code_rust": "rust",
            "arda_code_typescript": "typescript",
            "arda_code_javascript": "javascript",
            "arda_code_python": "python",
            "arda_code_solidity": "solidity",
        }
        language = language_map.get(collection_name, "rust")

        # Search for test files
        test_query = "test spec describe it should expect assert"
        test_results = await _semantic_search_impl(
            query=test_query,
            collection_name=collection_name,
            limit=50,
            score_threshold=0.5
        )

        # Search for implementation files
        impl_query = "function implementation module"
        impl_results = await _semantic_search_impl(
            query=impl_query,
            collection_name=collection_name,
            limit=50,
            score_threshold=0.5
        )

        # Build test coverage map
        test_coverage_map = {}
        brittle_tests = []
        test_file_count = 0
        impl_file_count = 0

        # Process test files
        for result in test_results.get("results", []):
            payload = result.get("payload", {})
            file_path = payload.get("file_path", "")
            content = payload.get("content_preview", "")

            if not is_test_file(file_path, language):
                continue

            test_file_count += 1

            # Analyze mock density
            mock_analysis = analyze_mock_density(content)

            test_coverage_map[file_path] = {
                "has_tests": True,
                "test_count": mock_analysis["assertion_count"],
                "mock_density": mock_analysis["mock_ratio"],
                "assertion_quality": "high" if mock_analysis["specificity_ratio"] > 0.6 else "low",
                "elasticity_rating": mock_analysis["quality"]
            }

            # Identify brittle tests (over-mocked)
            if mock_analysis["quality"] == "over_mocked":
                brittle_tests.append({
                    "file": file_path,
                    "reason": f"High mock density ({mock_analysis['mock_ratio']})",
                    "mock_count": mock_analysis["mock_count"],
                    "assertion_count": mock_analysis["assertion_count"],
                    "suggestion": "Reduce mocking, test actual behavior"
                })

        # Process implementation files
        impl_files = set()
        for result in impl_results.get("results", []):
            payload = result.get("payload", {})
            file_path = payload.get("file_path", "")

            if not is_test_file(file_path, language):
                impl_files.add(file_path)
                impl_file_count += 1

        # Calculate score components (each 0-25 points)
        # 1. Test existence: % of modules with tests
        test_existence_score = (test_file_count / max(impl_file_count, 1)) * 25
        test_existence_score = min(25, test_existence_score)  # Cap at 25

        # 2. Mock quality: Low mocking = high score
        avg_mock_density = sum(t["mock_density"] for t in test_coverage_map.values()) / max(len(test_coverage_map), 1)
        mock_quality_score = max(0, 25 - (avg_mock_density * 10))

        # 3. Assertion quality: Specific assertions = high score
        high_quality_tests = sum(1 for t in test_coverage_map.values() if t["assertion_quality"] == "high")
        assertion_quality_score = (high_quality_tests / max(len(test_coverage_map), 1)) * 25

        # 4. Integration coverage: Assume 15 points for now (would need deeper analysis)
        integration_coverage_score = 15

        # Total score
        elasticity_score = test_existence_score + mock_quality_score + assertion_quality_score + integration_coverage_score

        # Generate recommendations
        recommendations = []
        if test_file_count < impl_file_count * 0.5:
            recommendations.append(f"Add tests for {impl_file_count - test_file_count} modules without tests")
        if len(brittle_tests) > 0:
            recommendations.append(f"Refactor {len(brittle_tests)} over-mocked tests to focus on behavior")
        if avg_mock_density > 1.5:
            recommendations.append("Overall mock density is high - prefer integration tests")

        result = {
            "elasticity_score": round(elasticity_score, 1),
            "grade": score_to_grade(elasticity_score),
            "test_coverage_map": dict(list(test_coverage_map.items())[:10]),  # Limit for response size
            "statistics": {
                "test_files": test_file_count,
                "impl_files": impl_file_count,
                "coverage_ratio": round(test_file_count / max(impl_file_count, 1), 2),
                "avg_mock_density": round(avg_mock_density, 2)
            },
            "brittle_tests": brittle_tests[:10],  # Limit for response size
            "score_breakdown": {
                "test_existence": round(test_existence_score, 1),
                "mock_quality": round(mock_quality_score, 1),
                "assertion_quality": round(assertion_quality_score, 1),
                "integration_coverage": round(integration_coverage_score, 1)
            },
            "recommendations": recommendations
        }

        # Cache result
        _query_cache.put("test_elasticity", collection_name, cache_params, result)

        return result

    except Exception as e:
        logger.exception(f"Test elasticity analysis failed: {e}")
        raise ToolError(f"Analysis failed: {str(e)}") from e


# ============================================================================
# Tool 3: Contextual Density Analysis (Priority 3)
# ============================================================================

async def _analyze_contextual_density_impl(
    function_name: str,
    collection_name: str = "arda_code_rust",
    max_depth: int = 3
) -> dict:
    """
    Internal implementation of contextual density analysis.

    Args:
        function_name: Function to analyze
        collection_name: Target collection
        max_depth: Maximum dependency depth to trace

    Returns:
        Dictionary with density score, dependencies, and scattering analysis
    """
    try:
        logger.info(f"📊 Analyzing contextual density: {function_name} in {collection_name}")

        # Check cache
        cache_params = {"function_name": function_name, "max_depth": max_depth}
        cached_result = _query_cache.get("contextual_density", collection_name, cache_params)
        if cached_result:
            logger.info("   ⚡ Returned from cache")
            return cached_result

        # Determine language
        language_map = {
            "arda_code_rust": "rust",
            "arda_code_typescript": "typescript",
            "arda_code_python": "python",
        }
        language = language_map.get(collection_name, "rust")

        # Find the function
        func_results = await _semantic_search_impl(
            query=f"function {function_name} definition implementation",
            collection_name=collection_name,
            limit=5,
            score_threshold=0.6
        )

        if not func_results.get("results"):
            raise NotFoundError(f"Function '{function_name}' not found in {collection_name}")

        # Get the function's file and content
        func_payload = func_results["results"][0].get("payload", {})
        origin_file = func_payload.get("file_path", "")
        func_content = func_payload.get("content_preview", "")

        # Extract dependencies (types and function calls)
        type_refs = extract_type_references(func_content, language)
        func_calls = extract_function_calls(func_content, language)
        all_deps = type_refs + func_calls

        # Find locations of dependencies
        dependencies = []
        unique_files = set()

        for dep in all_deps[:20]:  # Limit to first 20 dependencies
            # Search for dependency definition
            dep_results = await _semantic_search_impl(
                query=f"definition {dep} struct class function",
                collection_name=collection_name,
                limit=3,
                score_threshold=0.5
            )

            if dep_results.get("results"):
                dep_payload = dep_results["results"][0].get("payload", {})
                dep_file = dep_payload.get("file_path", "")
                unique_files.add(dep_file)

                # Calculate distance
                if dep_file == origin_file:
                    distance = 0
                    location = "same_file"
                elif _same_module(dep_file, origin_file):
                    distance = 1
                    location = "same_module"
                elif _same_repo(dep_file, origin_file):
                    distance = 2
                    location = "different_module"
                else:
                    distance = 3
                    location = "external"

                dependencies.append({
                    "name": dep,
                    "location": location,
                    "distance": distance,
                    "file": dep_file
                })

        # Calculate average distance
        if dependencies:
            avg_distance = sum(d["distance"] for d in dependencies) / len(dependencies)
        else:
            avg_distance = 0

        # Calculate scattering penalty (0-40 based on # unique files)
        scattering_penalty = min(40, len(unique_files) * 4)

        # Calculate density score: 100 - (avg_distance * 20 + scattering_penalty)
        density_score = max(0, 100 - (avg_distance * 20 + scattering_penalty))

        # Generate suggestions
        suggestions = []
        if avg_distance > 2:
            suggestions.append("Consider moving frequently used types closer to this function")
        if len(unique_files) > 10:
            suggestions.append(f"High scattering: dependencies span {len(unique_files)} files")

        result = {
            "density_score": round(density_score, 1),
            "grade": score_to_grade(density_score),
            "context_distance": round(avg_distance, 2),
            "dependencies": dependencies[:15],  # Limit for response size
            "total_dependencies": len(dependencies),
            "scattering_analysis": {
                "unique_files": len(unique_files),
                "scattering_penalty": scattering_penalty,
                "scattering_index": "high" if len(unique_files) > 8 else "moderate" if len(unique_files) > 4 else "low"
            },
            "suggestions": suggestions
        }

        # Cache result
        _query_cache.put("contextual_density", collection_name, cache_params, result)

        return result

    except NotFoundError:
        raise
    except Exception as e:
        logger.exception(f"Contextual density analysis failed: {e}")
        raise ToolError(f"Analysis failed: {str(e)}") from e


def _same_module(file1: str, file2: str) -> bool:
    """Check if two files are in the same module (same directory)."""
    dir1 = "/".join(file1.split("/")[:-1])
    dir2 = "/".join(file2.split("/")[:-1])
    return dir1 == dir2


def _same_repo(file1: str, file2: str) -> bool:
    """Check if two files are in the same repository."""
    # Simplified check - assumes repo name is in path
    return file1.split("/")[0] == file2.split("/")[0]


# ============================================================================
# Tool 4: Dependency Entropy Analysis (Priority 4)
# ============================================================================

async def _analyze_dependency_entropy_impl(
    collection_name: str = "arda_code_rust",
    scope: str = "repository"
) -> dict:
    """
    Internal implementation of dependency entropy analysis.

    Args:
        collection_name: Target collection to analyze
        scope: Analysis scope (repository, module)

    Returns:
        Dictionary with entropy score, cycles, god modules, and coupling metrics
    """
    try:
        logger.info(f"🔗 Analyzing dependency entropy: {collection_name} (scope={scope})")

        # Check cache
        cache_params = {"scope": scope}
        cached_result = _query_cache.get("dependency_entropy", collection_name, cache_params)
        if cached_result:
            logger.info("   ⚡ Returned from cache")
            return cached_result

        # Search for all code chunks to build dependency graph
        search_results = await _semantic_search_impl(
            query="module import use require function class struct",
            collection_name=collection_name,
            limit=50,
            score_threshold=0.4
        )

        # Build dependency graph
        chunks = search_results.get("results", [])
        graph = build_dependency_graph(chunks)

        # Detect cycles
        cycles = detect_cycles(graph)

        # Find god modules
        god_modules = find_god_modules(graph, threshold=5)  # Lower threshold for smaller codebases

        # Calculate coupling metrics
        coupling_metrics = calculate_coupling_metrics(graph)

        # Calculate score components (each 0-25 points)
        # 1. Coupling ratio score: Lower coupling = higher score
        coupling_score = max(0, 25 - (coupling_metrics["coupling_ratio"] * 10))

        # 2. Cycle penalty: No cycles = full points
        cycle_penalty = min(25, len(cycles) * 5)
        cycle_score = max(0, 25 - cycle_penalty)

        # 3. God module penalty: Fewer god modules = higher score
        god_module_penalty = min(25, len(god_modules) * 8)
        god_module_score = max(0, 25 - god_module_penalty)

        # 4. Layering bonus: Assume 15 points for now (would need architecture analysis)
        layering_score = 15

        # Total entropy score
        entropy_score = coupling_score + cycle_score + god_module_score + layering_score

        # Format cycles for output
        cycles_detected = []
        for cycle in cycles[:10]:  # Limit to first 10
            cycles_detected.append({
                "cycle": cycle,
                "length": len(cycle),
                "severity": "major" if len(cycle) <= 3 else "minor"
            })

        # Generate recommendations
        recommendations = []
        if len(cycles) > 0:
            recommendations.append(f"Break {len(cycles)} circular dependencies")
        if len(god_modules) > 0:
            recommendations.append(f"Refactor {len(god_modules)} god modules with high coupling")
        if coupling_metrics["coupling_ratio"] > 2.0:
            recommendations.append("Overall coupling is high - consider architectural refactoring")

        result = {
            "entropy_score": round(entropy_score, 1),
            "grade": score_to_grade(entropy_score),
            "coupling_metrics": coupling_metrics,
            "cycles_detected": cycles_detected,
            "total_cycles": len(cycles),
            "god_modules": god_modules[:5],  # Limit for response size
            "total_god_modules": len(god_modules),
            "score_breakdown": {
                "coupling": round(coupling_score, 1),
                "no_cycles": round(cycle_score, 1),
                "no_god_modules": round(god_module_score, 1),
                "layering": round(layering_score, 1)
            },
            "recommendations": recommendations
        }

        # Cache result
        _query_cache.put("dependency_entropy", collection_name, cache_params, result)

        return result

    except Exception as e:
        logger.exception(f"Dependency entropy analysis failed: {e}")
        raise ToolError(f"Analysis failed: {str(e)}") from e


# ============================================================================
# Tool 5: Organizational Memory Analysis (Priority 5)
# ============================================================================

async def _analyze_organizational_memory_impl(
    repo_url: str,
    days_back: int = 90,
    ai_markers: Optional[List[str]] = None
) -> dict:
    """
    Internal implementation of organizational memory analysis.

    Args:
        repo_url: Repository URL to analyze
        days_back: Number of days to look back for PRs
        ai_markers: List of markers to detect AI-generated PRs

    Returns:
        Dictionary with memory score, PR metrics, and effectiveness analysis
    """
    try:
        logger.info(f"🧠 Analyzing organizational memory: {repo_url} ({days_back} days)")

        # Import GitHub utilities
        from src.utils.github import fetch_pr_metrics, detect_ai_generated_pr, find_follow_up_fixes
        from datetime import datetime, timedelta

        # Check cache
        cache_params = {"repo_url": repo_url, "days_back": days_back}
        cached_result = _query_cache.get("organizational_memory", "github", cache_params)
        if cached_result:
            logger.info("   ⚡ Returned from cache")
            return cached_result

        if not _github_token:
            raise ToolError("GitHub token not configured (GHCR_TOKEN environment variable)")

        # Calculate since date
        since_date = (datetime.now() - timedelta(days=days_back)).isoformat()

        # Fetch PR metrics
        pr_metrics = await fetch_pr_metrics(repo_url, since_date, _github_token)

        # Default AI markers if not provided
        if not ai_markers:
            ai_markers = ["copilot", "cursor", "claude", "chatgpt", "co-authored-by.*claude"]

        # Classify PRs as AI or human
        ai_prs = []
        human_prs = []

        for pr in pr_metrics:
            if detect_ai_generated_pr(pr, ai_markers):
                ai_prs.append(pr)
            else:
                human_prs.append(pr)

        # Calculate metrics for AI PRs
        if ai_prs:
            ai_avg_merge_time = sum(pr["time_to_merge"] for pr in ai_prs) / len(ai_prs)
            ai_avg_reviews = sum(pr["review_count"] for pr in ai_prs) / len(ai_prs)
        else:
            ai_avg_merge_time = 0
            ai_avg_reviews = 0

        # Calculate metrics for human PRs
        if human_prs:
            human_avg_merge_time = sum(pr["time_to_merge"] for pr in human_prs) / len(human_prs)
            human_avg_reviews = sum(pr["review_count"] for pr in human_prs) / len(human_prs)
        else:
            human_avg_merge_time = 0
            human_avg_reviews = 0

        # Find follow-up fixes
        follow_up_fixes = find_follow_up_fixes(pr_metrics, window_days=7)
        ai_fix_rate = len([f for f in follow_up_fixes if f["original_pr"] in [pr["number"] for pr in ai_prs]]) / max(len(ai_prs), 1)
        human_fix_rate = len([f for f in follow_up_fixes if f["original_pr"] in [pr["number"] for pr in human_prs]]) / max(len(human_prs), 1)

        # Calculate score components (each 0-25 points)
        # 1. Merge time score: Faster = better (relative to human baseline)
        if human_avg_merge_time > 0 and ai_avg_merge_time > 0:
            merge_time_ratio = ai_avg_merge_time / human_avg_merge_time
            merge_time_score = max(0, 25 - ((merge_time_ratio - 1) * 25))
        else:
            merge_time_score = 15  # Default if no data

        # 2. Review efficiency: Fewer reviews = better
        if human_avg_reviews > 0 and ai_avg_reviews > 0:
            review_ratio = ai_avg_reviews / human_avg_reviews
            review_score = max(0, 25 - ((review_ratio - 1) * 25))
        else:
            review_score = 15

        # 3. Fix rate: Fewer follow-ups = better
        fix_rate_score = max(0, 25 - (ai_fix_rate * 100))

        # 4. Trend: Assume improving (would need time-series analysis)
        trend_score = 15

        # Total memory score
        memory_score = merge_time_score + review_score + fix_rate_score + trend_score

        # Generate recommendations
        recommendations = []
        if ai_avg_merge_time > human_avg_merge_time:
            recommendations.append(f"AI PRs take {round((ai_avg_merge_time / human_avg_merge_time - 1) * 100, 1)}% longer to merge")
        else:
            recommendations.append(f"AI PRs merge {round((1 - ai_avg_merge_time / human_avg_merge_time) * 100, 1)}% faster")

        if ai_fix_rate > 0.15:
            recommendations.append(f"High AI fix rate ({round(ai_fix_rate * 100, 1)}%) - focus on quality over speed")

        result = {
            "memory_score": round(memory_score, 1),
            "grade": score_to_grade(memory_score),
            "pr_metrics": {
                "total_prs": len(pr_metrics),
                "ai_generated_prs": len(ai_prs),
                "ai_percentage": round(len(ai_prs) / max(len(pr_metrics), 1) * 100, 1)
            },
            "effectiveness_metrics": {
                "ai_prs": {
                    "avg_merge_time_hours": round(ai_avg_merge_time, 1),
                    "avg_review_count": round(ai_avg_reviews, 1),
                    "follow_up_fix_rate": round(ai_fix_rate, 2)
                },
                "human_prs": {
                    "avg_merge_time_hours": round(human_avg_merge_time, 1),
                    "avg_review_count": round(human_avg_reviews, 1),
                    "follow_up_fix_rate": round(human_fix_rate, 2)
                },
                "comparison": {
                    "merge_time_ratio": round(ai_avg_merge_time / max(human_avg_merge_time, 1), 2),
                    "fix_rate_ratio": round(ai_fix_rate / max(human_fix_rate, 1), 2)
                }
            },
            "score_breakdown": {
                "merge_time": round(merge_time_score, 1),
                "review_efficiency": round(review_score, 1),
                "fix_rate": round(fix_rate_score, 1),
                "trend": round(trend_score, 1)
            },
            "recommendations": recommendations
        }

        # Cache result
        _query_cache.put("organizational_memory", "github", cache_params, result)

        return result

    except Exception as e:
        logger.exception(f"Organizational memory analysis failed: {e}")
        raise ToolError(f"Analysis failed: {str(e)}") from e


# ============================================================================
# Tool 6: Aggregate Oink Score (Aggregator)
# ============================================================================

async def _calculate_oink_score_impl(
    collection_name: str = "arda_code_rust",
    scope: str = "repository",
    repo_url: Optional[str] = None,
    include_github_metrics: bool = True
) -> dict:
    """
    Internal implementation of aggregate oink score calculation.

    Args:
        collection_name: Target collection to analyze
        scope: Analysis scope
        repo_url: Repository URL for GitHub metrics
        include_github_metrics: Whether to include organizational memory analysis

    Returns:
        Dictionary with overall oink score, metric breakdown, and badges
    """
    try:
        logger.info(f"🐷 Calculating Oink Score: {collection_name}")

        # Run all metrics in parallel (except organizational memory if no repo_url)
        tasks = [
            _analyze_semantic_coherence_impl(collection_name, scope),
            _analyze_test_elasticity_impl(collection_name),
            _analyze_dependency_entropy_impl(collection_name, scope),
        ]

        # Add organizational memory if requested and repo URL provided
        if include_github_metrics and repo_url:
            tasks.append(_analyze_organizational_memory_impl(repo_url))

        # Note: Contextual density requires a function name, so we skip it for repo-wide score
        # It's meant for function-level analysis

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Extract scores (handle exceptions)
        coherence_result = results[0] if not isinstance(results[0], Exception) else None
        elasticity_result = results[1] if not isinstance(results[1], Exception) else None
        entropy_result = results[2] if not isinstance(results[2], Exception) else None
        memory_result = results[3] if len(results) > 3 and not isinstance(results[3], Exception) else None

        # Build scores dict
        scores = {}
        if coherence_result:
            scores["semantic_coherence"] = coherence_result["coherence_score"]
        if elasticity_result:
            scores["test_elasticity"] = elasticity_result["elasticity_score"]
        if entropy_result:
            scores["dependency_entropy"] = entropy_result["entropy_score"]
        if memory_result:
            scores["organizational_memory"] = memory_result["memory_score"]

        # Define weights
        if memory_result:
            weights = {
                "semantic_coherence": 0.20,
                "test_elasticity": 0.25,
                "dependency_entropy": 0.20,
                "organizational_memory": 0.15,
            }
        else:
            # Redistribute weights if no GitHub metrics
            weights = {
                "semantic_coherence": 0.25,
                "test_elasticity": 0.35,
                "dependency_entropy": 0.25,
            }

        # Calculate weighted oink score
        oink_score = calculate_weighted_score(scores, weights)

        # Generate badges (markdown)
        grade = score_to_grade(oink_score)
        color = _grade_to_color(grade)
        badges = {
            "markdown": f"![Oink Score](https://img.shields.io/badge/Oink%20Score-{oink_score}%20({grade})-{color})",
            "html": f'<img src="https://img.shields.io/badge/Oink%20Score-{oink_score}%20({grade})-{color}" alt="Oink Score">'
        }

        # Aggregate recommendations
        recommendations = []
        if coherence_result and coherence_result.get("recommendations"):
            recommendations.extend(coherence_result["recommendations"][:2])
        if elasticity_result and elasticity_result.get("recommendations"):
            recommendations.extend(elasticity_result["recommendations"][:2])
        if entropy_result and entropy_result.get("recommendations"):
            recommendations.extend(entropy_result["recommendations"][:1])

        result = {
            "oink_score": oink_score,
            "grade": grade,
            "metric_breakdown": {
                "semantic_coherence": {
                    "score": scores.get("semantic_coherence"),
                    "weight": weights.get("semantic_coherence", 0),
                    "grade": coherence_result["grade"] if coherence_result else "N/A"
                },
                "test_elasticity": {
                    "score": scores.get("test_elasticity"),
                    "weight": weights.get("test_elasticity", 0),
                    "grade": elasticity_result["grade"] if elasticity_result else "N/A"
                },
                "dependency_entropy": {
                    "score": scores.get("dependency_entropy"),
                    "weight": weights.get("dependency_entropy", 0),
                    "grade": entropy_result["grade"] if entropy_result else "N/A"
                },
                "organizational_memory": {
                    "score": scores.get("organizational_memory"),
                    "weight": weights.get("organizational_memory", 0),
                    "grade": memory_result["grade"] if memory_result else "N/A"
                }
            },
            "badges": badges,
            "recommendations": recommendations,
            "analysis_scope": scope,
            "collection": collection_name
        }

        return result

    except Exception as e:
        logger.exception(f"Oink score calculation failed: {e}")
        raise ToolError(f"Calculation failed: {str(e)}") from e


def _grade_to_color(grade: str) -> str:
    """Convert letter grade to badge color."""
    if grade.startswith("A"):
        return "brightgreen"
    elif grade.startswith("B"):
        return "green"
    elif grade.startswith("C"):
        return "yellow"
    elif grade.startswith("D"):
        return "orange"
    else:
        return "red"


# ============================================================================
# Tool Registration
# ============================================================================

def register_tools(mcp: FastMCP):
    """Register all code quality analysis tools with the MCP server."""

    @mcp.tool()
    async def analyze_semantic_coherence(
        collection_name: str = "arda_code_rust",
        scope: str = "repository",
        file_path: Optional[str] = None
    ) -> dict:
        """
        Analyze code naming quality and semantic coherence.

        Detects generic function names (process, handle, do, etc.), single-letter variables,
        and other naming issues that make code harder for AI to understand.

        Args:
            collection_name: Collection to analyze (e.g. code_rust, code_typescript, or with prefix)
            scope: Analysis scope - "repository", "file", or "pr"
            file_path: Optional specific file to analyze (when scope="file")

        Returns:
            Dictionary with coherence_score (0-100), grade, issues_found, and recommendations

        Use this to answer: "How good are the function names?", "Are there generic names?",
        "What naming issues exist?"
        """
        return await _analyze_semantic_coherence_impl(collection_name, scope, file_path)

    @mcp.tool()
    async def analyze_test_elasticity(
        collection_name: str = "arda_code_rust",
        module_path: Optional[str] = None
    ) -> dict:
        """
        Analyze test quality and elasticity.

        Evaluates whether tests protect against changes or just verify current implementation.
        Checks for over-mocking, weak assertions, and test coverage.

        Args:
            collection_name: Collection to analyze
            module_path: Optional specific module to analyze

        Returns:
            Dictionary with elasticity_score (0-100), test_coverage_map, brittle_tests, and recommendations

        Use this to answer: "How good are the tests?", "Are tests over-mocked?",
        "Do tests protect against regressions?"
        """
        return await _analyze_test_elasticity_impl(collection_name, module_path)

    @mcp.tool()
    async def analyze_contextual_density(
        function_name: str,
        collection_name: str = "arda_code_rust",
        max_depth: int = 3
    ) -> dict:
        """
        Analyze how much code must be read to understand a function.

        Measures information locality by finding dependencies and calculating their distance
        from the function being analyzed.

        Args:
            function_name: Name of function to analyze
            collection_name: Collection containing the function
            max_depth: Maximum dependency depth to trace (default: 3)

        Returns:
            Dictionary with density_score (0-100), dependencies, scattering_analysis, and suggestions

        Use this to answer: "How easy is this function to understand?",
        "Are dependencies scattered or nearby?"
        """
        return await _analyze_contextual_density_impl(function_name, collection_name, max_depth)

    @mcp.tool()
    async def analyze_dependency_entropy(
        collection_name: str = "arda_code_rust",
        scope: str = "repository"
    ) -> dict:
        """
        Analyze dependency coupling and entropy.

        Detects circular dependencies, god modules (over-depended), and measures overall
        coupling in the codebase.

        Args:
            collection_name: Collection to analyze
            scope: Analysis scope - "repository" or "module"

        Returns:
            Dictionary with entropy_score (0-100), cycles_detected, god_modules, and coupling_metrics

        Use this to answer: "Are there circular dependencies?", "Which modules are god modules?",
        "How tightly coupled is the code?"
        """
        return await _analyze_dependency_entropy_impl(collection_name, scope)

    @mcp.tool()
    async def analyze_organizational_memory(
        repo_url: str,
        days_back: int = 90,
        ai_markers: Optional[List[str]] = None
    ) -> dict:
        """
        Analyze AI code effectiveness using GitHub PR metrics.

        Tracks PR merge times, review counts, and follow-up fixes to measure how well
        AI-generated code performs compared to human-written code.

        Args:
            repo_url: Repository URL (e.g., "git@github.com:org/repo.git")
            days_back: Number of days to analyze (default: 90)
            ai_markers: Optional list of markers to detect AI PRs (e.g., ["copilot", "cursor"])

        Returns:
            Dictionary with memory_score (0-100), pr_metrics, effectiveness_metrics, and trend_analysis

        Use this to answer: "How effective is AI-generated code?", "Do AI PRs need more reviews?",
        "What's the AI fix rate?"
        """
        return await _analyze_organizational_memory_impl(repo_url, days_back, ai_markers)

    @mcp.tool()
    async def calculate_oink_score(
        collection_name: str = "arda_code_rust",
        scope: str = "repository",
        repo_url: Optional[str] = None,
        include_github_metrics: bool = True
    ) -> dict:
        """
        Calculate comprehensive "Oink Score" across all code quality metrics.

        Aggregates semantic coherence, test elasticity, dependency entropy, and optionally
        organizational memory into a single score suitable for badges and dashboards.

        Args:
            collection_name: Collection to analyze
            scope: Analysis scope - "repository" or "module"
            repo_url: Optional repository URL for GitHub PR metrics
            include_github_metrics: Whether to include organizational memory (default: True)

        Returns:
            Dictionary with oink_score (0-100), grade, metric_breakdown, badges, and recommendations

        Use this to answer: "What's the overall code quality?", "Generate an oink score badge",
        "How AI-ready is this codebase?"
        """
        return await _calculate_oink_score_impl(collection_name, scope, repo_url, include_github_metrics)
