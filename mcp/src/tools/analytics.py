"""MCP tools for dashboard analytics - searchability, clustering, usage stats, architecture, docs."""

import logging
import asyncio
import numpy as np
from typing import List, Optional, Dict, Tuple
from fastmcp import FastMCP
from fastmcp.exceptions import ToolError, NotFoundError

# Import helper functions
from src.utils.code_analysis import (
    score_to_grade,
    build_dependency_graph,
    find_layer_violations,
    analyze_service_boundaries,
    analyze_pattern_consistency,
    extract_api_contracts,
    has_documentation,
    assess_doc_quality,
    extract_function_names,
    detect_naming_convention,
)

logger = logging.getLogger(__name__)

# Global state - will be set by server module
_semantic_search_impl = None
_qdrant_client = None
_query_cache = None
_prompt_tracker = None


def set_analytics_globals(semantic_search_fn, qdrant_client, query_cache, prompt_tracker):
    """
    Set global state references needed by analytics tools.

    Args:
        semantic_search_fn: Function to perform semantic search
        qdrant_client: Qdrant client instance
        query_cache: Query cache instance
        prompt_tracker: Prompt usage tracker instance
    """
    global _semantic_search_impl, _qdrant_client, _query_cache, _prompt_tracker
    _semantic_search_impl = semantic_search_fn
    _qdrant_client = qdrant_client
    _query_cache = query_cache
    _prompt_tracker = prompt_tracker


# ============================================================================
# Tool 1: Searchability Analysis
# ============================================================================

async def _analyze_searchability_impl(
    collection_name: str = "arda_code_rust",
    sample_queries: Optional[List[str]] = None,
    num_samples: int = 20
) -> dict:
    """
    Internal implementation of searchability analysis.

    Args:
        collection_name: Collection to analyze
        sample_queries: Optional list of queries to test
        num_samples: Number of sample queries to generate if not provided

    Returns:
        Dictionary with searchability score and analysis
    """
    try:
        logger.info(f"🔍 Analyzing searchability: {collection_name}")

        # Check cache
        cache_params = {"num_samples": num_samples}
        cached_result = _query_cache.get("searchability", collection_name, cache_params)
        if cached_result:
            logger.info("   ⚡ Returned from cache")
            return cached_result

        # Generate or use provided sample queries
        if not sample_queries:
            sample_queries = [
                "function implementation",
                "class definition",
                "error handling",
                "api endpoint",
                "database query",
                "authentication",
                "validation logic",
                "payment processing",
                "user management",
                "configuration",
                "testing utilities",
                "data transformation",
                "service integration",
                "cache management",
                "logging",
                "middleware",
                "route handler",
                "model schema",
                "utility function",
                "async operation"
            ][:num_samples]

        # Run queries in parallel
        search_tasks = [
            _semantic_search_impl(
                query=query,
                collection_name=collection_name,
                limit=10,
                score_threshold=0.3
            )
            for query in sample_queries
        ]

        results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Analyze scores
        all_scores = []
        successful_queries = 0

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.warning(f"  Query '{sample_queries[i]}' failed: {result}")
                continue

            if result.get("results"):
                successful_queries += 1
                scores = [r.get("score", 0) for r in result["results"]]
                all_scores.extend(scores)

        if not all_scores:
            raise ToolError("No successful queries - collection may be empty or unreachable")

        # Calculate statistics
        avg_score = np.mean(all_scores)
        median_score = np.median(all_scores)
        p95_score = np.percentile(all_scores, 95)
        min_score = np.min(all_scores)

        # Calculate coverage
        high_quality = sum(1 for s in all_scores if s > 0.7) / len(all_scores)
        medium_quality = sum(1 for s in all_scores if 0.5 <= s <= 0.7) / len(all_scores)
        low_quality = sum(1 for s in all_scores if s < 0.5) / len(all_scores)

        # Searchability score (0-100)
        searchability_score = avg_score * 100

        # Generate recommendations
        recommendations = []
        if avg_score < 0.5:
            recommendations.append("Low average relevance - consider re-indexing or improving chunking strategy")
        if high_quality < 0.3:
            recommendations.append(f"Only {high_quality*100:.1f}% high-quality results - improve embedding quality")
        if successful_queries < len(sample_queries) * 0.8:
            recommendations.append("Many queries failed - check collection health")

        result = {
            "searchability_score": round(searchability_score, 1),
            "grade": score_to_grade(searchability_score),
            "query_performance": {
                "avg_score": round(avg_score, 3),
                "median_score": round(median_score, 3),
                "p95_score": round(p95_score, 3),
                "min_score": round(min_score, 3),
                "queries_tested": len(sample_queries),
                "successful_queries": successful_queries
            },
            "coverage_analysis": {
                "high_quality_coverage": round(high_quality, 3),
                "medium_coverage": round(medium_quality, 3),
                "low_coverage": round(low_quality, 3)
            },
            "recommendations": recommendations
        }

        # Cache result
        _query_cache.put("searchability", collection_name, cache_params, result)

        return result

    except Exception as e:
        logger.exception(f"Searchability analysis failed: {e}")
        raise ToolError(f"Analysis failed: {str(e)}") from e


# ============================================================================
# Tool 2: Topic Clustering Analysis
# ============================================================================

async def _analyze_topic_clusters_impl(
    collection_name: str = "arda_code_rust",
    num_clusters: int = 10,
    min_cluster_size: int = 5
) -> dict:
    """
    Internal implementation of topic clustering analysis.

    Args:
        collection_name: Collection to analyze
        num_clusters: Number of clusters to create
        min_cluster_size: Minimum size for a valid cluster

    Returns:
        Dictionary with clusters and coherence scores
    """
    try:
        logger.info(f"🎯 Analyzing topic clusters: {collection_name} (k={num_clusters})")

        # Check cache
        cache_params = {"num_clusters": num_clusters, "min_cluster_size": min_cluster_size}
        cached_result = _query_cache.get("topic_clusters", collection_name, cache_params)
        if cached_result:
            logger.info("   ⚡ Returned from cache")
            return cached_result

        # Import clustering libraries
        from sklearn.cluster import KMeans
        from sklearn.decomposition import PCA
        from sklearn.metrics import silhouette_score
        from collections import Counter
        import re

        # Fetch vectors from Qdrant
        logger.info("  📦 Fetching vectors from Qdrant...")

        # Sample up to 1000 points for performance
        limit = 1000
        offset = None
        points = []

        scroll_result = _qdrant_client.scroll(
            collection_name=collection_name,
            limit=limit,
            with_vectors=True,
            with_payload=True
        )

        points.extend(scroll_result[0])

        if not points:
            raise NotFoundError(f"No points found in collection {collection_name}")

        logger.info(f"  ✓ Fetched {len(points)} points")

        # Extract vectors and payloads
        vectors = np.array([point.vector for point in points])
        payloads = [point.payload for point in points]

        # Dimensionality reduction (4096 -> 50 dims)
        logger.info("  🔄 Reducing dimensionality...")
        pca = PCA(n_components=min(50, len(vectors)))
        vectors_reduced = pca.fit_transform(vectors)

        # Perform clustering
        logger.info(f"  🎲 Clustering into {num_clusters} groups...")
        actual_clusters = min(num_clusters, len(points))
        kmeans = KMeans(n_clusters=actual_clusters, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(vectors_reduced)

        # Calculate silhouette score
        silhouette_avg = silhouette_score(vectors_reduced, cluster_labels) if len(points) > num_clusters else 0.5

        # Build clusters
        clusters_data = {}
        for i, label in enumerate(cluster_labels):
            if label not in clusters_data:
                clusters_data[label] = []
            clusters_data[label].append({
                "payload": payloads[i],
                "vector": vectors[i],
                "vector_reduced": vectors_reduced[i]
            })

        # Analyze each cluster
        clusters_output = []

        for cluster_id, cluster_points in clusters_data.items():
            if len(cluster_points) < min_cluster_size:
                continue

            # Calculate coherence (avg pairwise cosine similarity)
            cluster_vectors = np.array([p["vector"] for p in cluster_points])

            # Sample pairs for efficiency if cluster is large
            if len(cluster_vectors) > 20:
                indices = np.random.choice(len(cluster_vectors), 20, replace=False)
                sample_vectors = cluster_vectors[indices]
            else:
                sample_vectors = cluster_vectors

            # Cosine similarity
            from sklearn.metrics.pairwise import cosine_similarity
            similarities = cosine_similarity(sample_vectors)
            # Average of upper triangle (excluding diagonal)
            coherence = np.mean(similarities[np.triu_indices_from(similarities, k=1)])

            # Extract top terms from content
            all_text = []
            files_in_cluster = []

            for p in cluster_points[:20]:  # Sample first 20
                payload = p["payload"]
                content = payload.get("content_preview", "")
                all_text.append(content.lower())

                files_in_cluster.append({
                    "file_path": payload.get("file_path", "unknown"),
                    "relevance_to_cluster": 1.0,  # All in cluster are equally relevant
                    "lines": f"{payload.get('start_line', 0)}-{payload.get('end_line', 0)}",
                    "preview": content[:200]
                })

            # Extract common words (simple frequency analysis)
            words = []
            for text in all_text:
                words.extend(re.findall(r'\b[a-z]{4,}\b', text))  # 4+ letter words

            word_counts = Counter(words)
            # Filter out common stop words
            stop_words = {'that', 'this', 'with', 'from', 'have', 'will', 'your', 'they', 'been', 'were', 'said', 'each', 'which', 'their', 'there', 'would', 'could', 'should'}
            top_terms = [w for w, c in word_counts.most_common(10) if w not in stop_words][:5]

            # Generate cluster label from top terms
            label = " ".join(top_terms[:3]) if top_terms else f"cluster_{cluster_id}"

            # Find centroid example (point closest to cluster center)
            centroid = kmeans.cluster_centers_[cluster_id]
            distances = np.linalg.norm(np.array([p["vector_reduced"] for p in cluster_points]) - centroid, axis=1)
            closest_idx = np.argmin(distances)
            centroid_example = cluster_points[closest_idx]["payload"].get("content_preview", "")[:300]

            clusters_output.append({
                "cluster_id": int(cluster_id),
                "label": label,
                "coherence_score": round(float(coherence), 3),
                "size": len(cluster_points),
                "files": files_in_cluster[:10],  # Limit to 10 files
                "top_terms": top_terms,
                "centroid_example": centroid_example
            })

        # Sort clusters by size
        clusters_output.sort(key=lambda x: x["size"], reverse=True)

        # Calculate outliers (clusters smaller than min_size)
        outliers = sum(len(pts) for label, pts in clusters_data.items() if len(pts) < min_cluster_size)

        result = {
            "clusters": clusters_output,
            "clustering_metrics": {
                "silhouette_score": round(float(silhouette_avg), 3),
                "num_clusters": len(clusters_output),
                "avg_cluster_size": round(np.mean([c["size"] for c in clusters_output]), 1) if clusters_output else 0,
                "outliers": outliers
            },
            "recommendations": [
                f"Found {len(clusters_output)} coherent topics",
                f"Average coherence: {np.mean([c['coherence_score'] for c in clusters_output]):.2f}" if clusters_output else "No clusters"
            ]
        }

        # Cache result (longer TTL for expensive clustering)
        _query_cache.put("topic_clusters", collection_name, cache_params, result)

        return result

    except Exception as e:
        logger.exception(f"Topic clustering analysis failed: {e}")
        raise ToolError(f"Analysis failed: {str(e)}") from e


# ============================================================================
# Tool 3: Prompt Usage Statistics
# ============================================================================

def _get_prompt_usage_stats_impl(
    time_window: str = "session",
    sort_by: str = "usage_count"
) -> dict:
    """
    Internal implementation of prompt usage statistics.

    Args:
        time_window: Time window for stats (currently only "session" supported)
        sort_by: Sort criterion - "usage_count", "success_rate", or "avg_time"

    Returns:
        Dictionary with prompt usage statistics
    """
    try:
        logger.info(f"📊 Getting prompt usage stats (sort_by={sort_by})")

        if not _prompt_tracker:
            raise ToolError("Prompt tracker not initialized")

        # Get stats from tracker
        stats = _prompt_tracker.get_stats(time_window=time_window, sort_by=sort_by)

        return stats

    except Exception as e:
        logger.exception(f"Prompt usage stats failed: {e}")
        raise ToolError(f"Analysis failed: {str(e)}") from e


# ============================================================================
# Tool 4: Architecture Coherence Analysis
# ============================================================================

async def _analyze_architecture_coherence_impl(
    collection_name: str = "arda_code_rust",
    scope: str = "repository"
) -> dict:
    """
    Internal implementation of architecture coherence analysis.

    Args:
        collection_name: Collection to analyze
        scope: Analysis scope

    Returns:
        Dictionary with architecture coherence analysis
    """
    try:
        logger.info(f"🏗️  Analyzing architecture coherence: {collection_name}")

        # Check cache
        cache_params = {"scope": scope}
        cached_result = _query_cache.get("architecture_coherence", collection_name, cache_params)
        if cached_result:
            logger.info("   ⚡ Returned from cache")
            return cached_result

        # Search for all code chunks
        search_result = await _semantic_search_impl(
            query="function class module implementation",
            collection_name=collection_name,
            limit=50,
            score_threshold=0.3
        )

        chunks = search_result.get("results", [])

        if not chunks:
            raise NotFoundError(f"No code found in collection {collection_name}")

        # Build dependency graph
        graph = build_dependency_graph(chunks)

        # 1. Layer Violation Detection
        violations = find_layer_violations(graph, chunks)
        layer_score = max(0, 100 - (len(violations) * 10))

        # 2. Service Boundary Analysis
        boundary_analysis = analyze_service_boundaries(graph, chunks)

        # 3. Pattern Consistency Analysis
        pattern_analysis = analyze_pattern_consistency(chunks)

        # 4. API Contract Adherence
        apis = extract_api_contracts(chunks)

        # Check naming consistency
        naming_conventions = {}
        for api in apis:
            convention = api["naming_convention"]
            naming_conventions[convention] = naming_conventions.get(convention, 0) + 1

        total_apis = len(apis)
        if total_apis > 0:
            # Find dominant convention
            dominant_convention = max(naming_conventions.items(), key=lambda x: x[1]) if naming_conventions else ("unknown", 0)
            consistent_apis = dominant_convention[1]
            api_score = (consistent_apis / total_apis) * 100
        else:
            api_score = 100  # No APIs means no inconsistency
            consistent_apis = 0

        # Identify naming issues
        naming_issues = []
        if total_apis > 0 and len(naming_conventions) > 1:
            for api in apis[:10]:  # Sample first 10
                if api["naming_convention"] != dominant_convention[0]:
                    naming_issues.append({
                        "api": f"{api['method']} {api['path']}",
                        "issue": f"Uses {api['naming_convention']} instead of {dominant_convention[0]}",
                        "recommendation": f"Rename to use {dominant_convention[0]}"
                    })

        # Calculate weighted architecture coherence score
        weights = {
            "layer": 0.30,
            "boundary": 0.30,
            "pattern": 0.20,
            "api": 0.20
        }

        architecture_coherence_score = (
            layer_score * weights["layer"] +
            boundary_analysis["score"] * weights["boundary"] +
            pattern_analysis["score"] * weights["pattern"] +
            api_score * weights["api"]
        )

        # Generate recommendations
        recommendations = []
        if len(violations) > 0:
            recommendations.append(f"Fix {len(violations)} layer violations")
        if boundary_analysis["avg_boundary_clarity"] < 0.7:
            recommendations.append("Improve service boundary clarity")
        if len(pattern_analysis.get("inconsistencies", [])) > 0:
            recommendations.append("Standardize code patterns")
        if len(naming_issues) > 0:
            recommendations.append(f"Fix API naming inconsistencies")

        result = {
            "architecture_coherence_score": round(architecture_coherence_score, 1),
            "grade": score_to_grade(architecture_coherence_score),
            "layer_violations": {
                "score": round(layer_score, 1),
                "violations_found": violations[:10],  # Top 10
                "total_violations": len(violations)
            },
            "service_boundaries": boundary_analysis,
            "pattern_consistency": pattern_analysis,
            "api_adherence": {
                "score": round(api_score, 1),
                "total_apis": total_apis,
                "consistent_apis": consistent_apis,
                "dominant_convention": dominant_convention[0] if naming_conventions else "unknown",
                "naming_issues": naming_issues
            },
            "recommendations": recommendations
        }

        # Cache result
        _query_cache.put("architecture_coherence", collection_name, cache_params, result)

        return result

    except Exception as e:
        logger.exception(f"Architecture coherence analysis failed: {e}")
        raise ToolError(f"Analysis failed: {str(e)}") from e


# ============================================================================
# Tool 5: Documentation Gap Analysis
# ============================================================================

async def _analyze_documentation_gaps_impl(
    collection_name: str = "arda_code_rust",
    scope: str = "repository"
) -> dict:
    """
    Internal implementation of documentation gap analysis.

    Args:
        collection_name: Collection to analyze
        scope: Analysis scope

    Returns:
        Dictionary with documentation gap analysis
    """
    try:
        logger.info(f"📚 Analyzing documentation gaps: {collection_name}")

        # Check cache
        cache_params = {"scope": scope}
        cached_result = _query_cache.get("documentation_gaps", collection_name, cache_params)
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

        # Search for function/class definitions
        search_result = await _semantic_search_impl(
            query="function class struct enum interface implementation",
            collection_name=collection_name,
            limit=50,
            score_threshold=0.4
        )

        chunks = search_result.get("results", [])

        if not chunks:
            raise NotFoundError(f"No code found in collection {collection_name}")

        # Analyze documentation
        total_items = 0
        documented_items = 0
        public_total = 0
        public_documented = 0
        private_total = 0
        private_documented = 0

        critical_gaps = []
        quality_metrics = {
            "total_doc_length": 0,
            "docs_with_examples": 0,
            "docs_with_params": 0,
            "docs_with_returns": 0,
            "doc_count": 0
        }

        for chunk in chunks:
            payload = chunk.get("payload", {})
            content = payload.get("content_preview", "")
            file_path = payload.get("file_path", "")
            item_name = payload.get("item_name", "")
            start_line = payload.get("start_line", 0)

            # Extract functions
            functions = extract_function_names(content, language)

            for func_name, is_public in functions:
                total_items += 1

                if is_public:
                    public_total += 1
                else:
                    private_total += 1

                # Check for documentation
                has_docs, doc_text = has_documentation(content, language, start_line)

                if has_docs:
                    documented_items += 1
                    if is_public:
                        public_documented += 1
                    else:
                        private_documented += 1

                    # Assess quality
                    quality = assess_doc_quality(doc_text)
                    quality_metrics["total_doc_length"] += quality["length"]
                    quality_metrics["doc_count"] += 1
                    if quality["has_example"]:
                        quality_metrics["docs_with_examples"] += 1
                    if quality["has_params"]:
                        quality_metrics["docs_with_params"] += 1
                    if quality["has_returns"]:
                        quality_metrics["docs_with_returns"] += 1
                else:
                    # Undocumented item
                    severity = "critical" if is_public else "major"

                    if is_public or len(critical_gaps) < 20:  # Prioritize public APIs
                        critical_gaps.append({
                            "file_path": file_path,
                            "item_name": func_name,
                            "item_type": "function",
                            "visibility": "public" if is_public else "private",
                            "severity": severity,
                            "lines": f"{start_line}-{start_line + 10}",
                            "reason": "Public API without documentation" if is_public else "Function without documentation"
                        })

        # Calculate coverage
        coverage_percentage = (documented_items / total_items * 100) if total_items > 0 else 0
        public_coverage = (public_documented / public_total * 100) if public_total > 0 else 100
        private_coverage = (private_documented / private_total * 100) if private_total > 0 else 100

        # Calculate quality metrics
        avg_doc_length = quality_metrics["total_doc_length"] / quality_metrics["doc_count"] if quality_metrics["doc_count"] > 0 else 0

        # Sort critical gaps by severity
        critical_gaps.sort(key=lambda x: 0 if x["severity"] == "critical" else 1)

        # Generate recommendations
        recommendations = []
        if coverage_percentage < 50:
            recommendations.append(f"Low documentation coverage ({coverage_percentage:.1f}%) - prioritize documenting public APIs")
        if public_coverage < 80:
            recommendations.append(f"Only {public_coverage:.1f}% of public APIs are documented")
        if quality_metrics["docs_with_params"] < quality_metrics["doc_count"] * 0.5:
            recommendations.append("Many docs lack parameter descriptions")

        result = {
            "documentation_score": round(coverage_percentage, 1),
            "grade": score_to_grade(coverage_percentage),
            "coverage": {
                "total_items": total_items,
                "documented_items": documented_items,
                "undocumented_items": total_items - documented_items,
                "coverage_percentage": round(coverage_percentage, 1)
            },
            "by_visibility": {
                "public": {
                    "total": public_total,
                    "documented": public_documented,
                    "percentage": round(public_coverage, 1)
                },
                "private": {
                    "total": private_total,
                    "documented": private_documented,
                    "percentage": round(private_coverage, 1)
                }
            },
            "by_file_type": {
                language: {
                    "coverage": round(coverage_percentage, 1)
                }
            },
            "critical_gaps": critical_gaps[:20],  # Top 20
            "quality_analysis": {
                "avg_doc_length": round(avg_doc_length, 1),
                "docs_with_examples": quality_metrics["docs_with_examples"],
                "docs_with_params": quality_metrics["docs_with_params"],
                "docs_with_returns": quality_metrics["docs_with_returns"]
            },
            "recommendations": recommendations
        }

        # Cache result
        _query_cache.put("documentation_gaps", collection_name, cache_params, result)

        return result

    except Exception as e:
        logger.exception(f"Documentation gap analysis failed: {e}")
        raise ToolError(f"Analysis failed: {str(e)}") from e


# ============================================================================
# Tool Registration
# ============================================================================

def register_tools(mcp: FastMCP):
    """Register all dashboard analytics tools with the MCP server."""

    @mcp.tool()
    async def analyze_searchability(
        collection_name: str = "arda_code_rust",
        sample_queries: Optional[List[str]] = None,
        num_samples: int = 20
    ) -> dict:
        """
        Analyze search quality and calculate searchability scores for a collection.

        Tests multiple sample queries against the collection to measure average relevance
        scores, coverage distribution, and search effectiveness.

        Args:
            collection_name: Collection to analyze (default: "arda_code_rust")
            sample_queries: Optional list of specific queries to test
            num_samples: Number of sample queries to generate if not provided (default: 20)

        Returns:
            Dictionary with:
            - searchability_score: Overall score 0-100
            - grade: Letter grade A-F
            - query_performance: Stats (avg, median, p95, min scores)
            - coverage_analysis: Distribution of result quality
            - recommendations: Improvement suggestions

        Use this to answer: "How searchable is this collection?", "What's the search quality?"
        """
        return await _analyze_searchability_impl(collection_name, sample_queries, num_samples)

    @mcp.tool()
    async def analyze_topic_clusters(
        collection_name: str = "arda_code_rust",
        num_clusters: int = 10,
        min_cluster_size: int = 5
    ) -> dict:
        """
        Extract topic clusters from vector embeddings with coherence scores.

        Uses K-means clustering on code embeddings to identify semantic topics, with
        automatic labeling and file mappings for dashboard exploration.

        Args:
            collection_name: Collection to analyze (default: "arda_code_rust")
            num_clusters: Number of clusters to create (default: 10)
            min_cluster_size: Minimum cluster size to include (default: 5)

        Returns:
            Dictionary with:
            - clusters: List of clusters with labels, coherence, files, and examples
            - clustering_metrics: Silhouette score, avg cluster size, outliers
            - recommendations: Analysis insights

        Use this to answer: "What topics exist in the code?", "Show me code clusters"
        """
        return await _analyze_topic_clusters_impl(collection_name, num_clusters, min_cluster_size)

    @mcp.tool()
    async def get_prompt_usage_stats(
        time_window: str = "session",
        sort_by: str = "usage_count"
    ) -> dict:
        """
        Get prompt usage statistics and analytics.

        Tracks execution counts, success rates, and performance metrics for all prompts
        since server start.

        Args:
            time_window: Time window for stats - "session" (default)
            sort_by: Sort criterion - "usage_count" (default), "success_rate", or "avg_time"

        Returns:
            Dictionary with:
            - total_prompt_executions: Total count across all prompts
            - prompts: List of prompt stats (usage, success rate, timing, rank)
            - insights: Most/least popular, highest success rate, slowest

        Use this to answer: "Which prompts are most used?", "What's the prompt success rate?"
        """
        return _get_prompt_usage_stats_impl(time_window, sort_by)

    @mcp.tool()
    async def analyze_architecture_coherence(
        collection_name: str = "arda_code_rust",
        scope: str = "repository"
    ) -> dict:
        """
        Comprehensive architecture coherence analysis.

        Analyzes 4 aspects: layer violations, service boundary clarity, pattern consistency,
        and API contract adherence. Essential for AI readiness assessment.

        Args:
            collection_name: Collection to analyze (default: "arda_code_rust")
            scope: Analysis scope - "repository" (default) or "module"

        Returns:
            Dictionary with:
            - architecture_coherence_score: Overall score 0-100
            - grade: Letter grade A-F
            - layer_violations: Layer dependency violations with severity
            - service_boundaries: Cross-service coupling analysis
            - pattern_consistency: Code pattern usage consistency
            - api_adherence: API naming convention consistency
            - recommendations: Architecture improvement suggestions

        Use this to answer: "Are there layer violations?", "How clear are service boundaries?",
        "Is the architecture coherent?"
        """
        return await _analyze_architecture_coherence_impl(collection_name, scope)

    @mcp.tool()
    async def analyze_documentation_gaps(
        collection_name: str = "arda_code_rust",
        scope: str = "repository"
    ) -> dict:
        """
        Detect undocumented code and measure documentation quality.

        Analyzes documentation coverage, identifies critical gaps (especially public APIs),
        and assesses documentation quality.

        Args:
            collection_name: Collection to analyze (default: "arda_code_rust")
            scope: Analysis scope - "repository" (default) or "module"

        Returns:
            Dictionary with:
            - documentation_score: Coverage percentage 0-100
            - grade: Letter grade A-F
            - coverage: Total/documented/undocumented counts
            - by_visibility: Public vs private API coverage
            - critical_gaps: Prioritized list of undocumented items
            - quality_analysis: Doc quality metrics (length, params, returns, examples)
            - recommendations: Documentation improvement suggestions

        Use this to answer: "What's the documentation coverage?", "Which APIs lack docs?",
        "Where are the documentation gaps?"
        """
        return await _analyze_documentation_gaps_impl(collection_name, scope)
