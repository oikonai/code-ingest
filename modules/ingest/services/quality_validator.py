"""
Quality validation system for semantic search improvements.
Tests and validates search result quality across different scenarios.
"""

from typing import Dict, List, Any, Tuple
from modules.ingest import IngestionPipeline
from .enhanced_ranking import enhanced_ranker

class SearchQualityValidator:
    """Validate and test semantic search quality improvements."""
    
    def __init__(self):
        self.pipeline = None
        self.test_queries = [
            # Business Logic Queries
            {
                'query': 'loan origination process',
                'expected_domains': ['finance'],
                'expected_languages': ['rust'],
                'expected_components': ['api', 'core'],
                'avoid_patterns': ['test', 'lib', 'openzeppelin']
            },
            {
                'query': 'payment processing handler',
                'expected_domains': ['finance'],
                'expected_languages': ['rust'],
                'expected_components': ['api'],
                'avoid_patterns': ['mock', 'example']
            },
            {
                'query': 'kyc verification workflow',
                'expected_domains': ['kyc', 'auth'],
                'expected_languages': ['rust'],
                'expected_components': ['api', 'core'],
                'avoid_patterns': ['test']
            },
            
            # Frontend Queries
            {
                'query': 'react login component',
                'expected_domains': ['ui', 'auth'],
                'expected_languages': ['typescript', 'javascript'],
                'expected_repos': ['arda-credit-app'],
                'avoid_patterns': ['contracts/lib']
            },
            {
                'query': 'trading interface dashboard',
                'expected_domains': ['ui', 'finance'],
                'expected_languages': ['typescript'],
                'expected_repos': ['arda-credit-app'],
                'avoid_patterns': ['test', 'lib']
            },
            
            # Smart Contract Queries
            {
                'query': 'loan verification contract',
                'expected_domains': ['contracts'],
                'expected_languages': ['solidity'],
                'expected_components': ['contracts'],
                'avoid_patterns': ['lib/openzeppelin', 'lib/forge-std', 'test']
            },
            {
                'query': 'zero knowledge proof verification',
                'expected_domains': ['contracts'],
                'expected_languages': ['solidity', 'rust'],
                'avoid_patterns': ['mock', 'example']
            }
        ]
    
    def initialize_pipeline(self):
        """Initialize the ingestion pipeline for testing."""
        if not self.pipeline:
            self.pipeline = IngestionPipeline()
    
    def test_query_quality(self, query_test: Dict) -> Dict[str, Any]:
        """Test a single query and evaluate result quality."""
        self.initialize_pipeline()
        
        query = query_test['query']
        print(f"\n🔍 Testing: '{query}'")
        
        # Get raw results
        raw_results = self.pipeline.search_across_languages(query, limit=10)
        
        # Apply enhanced ranking
        enhanced_results = enhanced_ranker.enhance_search_results(query, raw_results)
        
        # Analyze results quality
        analysis = {
            'query': query,
            'total_results': sum(len(results) for results in enhanced_results.values()),
            'languages_found': list(enhanced_results.keys()),
            'quality_scores': {},
            'issues_found': [],
            'improvements': []
        }
        
        for language, results in enhanced_results.items():
            if not results:
                continue
                
            lang_analysis = self._analyze_language_results(results, query_test)
            analysis['quality_scores'][language] = lang_analysis
            
            # Check for quality issues
            self._check_quality_issues(results, query_test, analysis['issues_found'])
            
            # Identify improvements
            self._identify_improvements(results, query_test, analysis['improvements'])
        
        return analysis
    
    def _analyze_language_results(self, results: List[Dict], query_test: Dict) -> Dict[str, Any]:
        """Analyze results for a specific language."""
        if not results:
            return {'relevance_score': 0, 'diversity_score': 0, 'quality_score': 0}
        
        total_relevance = 0
        unique_files = set()
        unique_components = set()
        core_results = 0
        
        for result in results[:5]:  # Analyze top 5 results
            payload = result['payload']
            enhanced_score = result.get('enhanced_score', result['score'])
            
            # Relevance scoring
            total_relevance += enhanced_score
            
            # Diversity tracking
            unique_files.add(payload.get('file_path', ''))
            unique_components.add(payload.get('repo_component', ''))
            
            # Core vs peripheral code
            file_path = payload.get('file_path', '').lower()
            if any(core_path in file_path for core_path in ['src/', 'api/src/', 'contracts/src/']):
                core_results += 1
        
        avg_relevance = total_relevance / len(results[:5])
        diversity_score = len(unique_files) / min(5, len(results))  # Unique files in top 5
        core_ratio = core_results / min(5, len(results))
        
        quality_score = (avg_relevance * 0.4 + diversity_score * 0.3 + core_ratio * 0.3)
        
        return {
            'relevance_score': avg_relevance,
            'diversity_score': diversity_score,
            'core_code_ratio': core_ratio,
            'quality_score': quality_score,
            'unique_files': len(unique_files),
            'unique_components': len(unique_components)
        }
    
    def _check_quality_issues(self, results: List[Dict], query_test: Dict, issues: List[str]):
        """Check for common quality issues in results."""
        if not results:
            issues.append("No results returned")
            return
        
        # Check for avoid patterns
        avoid_patterns = query_test.get('avoid_patterns', [])
        for result in results[:3]:  # Check top 3 results
            file_path = result['payload'].get('file_path', '').lower()
            for pattern in avoid_patterns:
                if pattern in file_path:
                    issues.append(f"Unwanted pattern '{pattern}' in top results: {file_path}")
        
        # Check for repetitive results
        item_names = [r['payload'].get('item_name', '') for r in results[:5]]
        if len(set(item_names)) < len(item_names) * 0.6:  # Less than 60% unique
            issues.append("Results lack diversity - too many similar items")
        
        # Check for expected languages
        expected_langs = query_test.get('expected_languages', [])
        found_langs = [r['payload'].get('language', '') for r in results[:3]]
        if expected_langs and not any(lang in found_langs for lang in expected_langs):
            issues.append(f"Expected languages {expected_langs} not found in top results")
    
    def _identify_improvements(self, results: List[Dict], query_test: Dict, improvements: List[str]):
        """Identify improvements made by enhanced ranking."""
        if not results:
            return
        
        # Check if enhanced scoring improved relevance
        enhanced_scores = [r.get('enhanced_score', 0) for r in results[:3]]
        base_scores = [r.get('score', 0) for r in results[:3]]
        
        if any(enh > base for enh, base in zip(enhanced_scores, base_scores)):
            improvements.append("Enhanced ranking boosted relevant results")
        
        # Check domain alignment
        expected_domains = query_test.get('expected_domains', [])
        top_domains = [r['payload'].get('business_domain', '') for r in results[:3]]
        if any(domain in top_domains for domain in expected_domains):
            improvements.append("Good business domain alignment in top results")
        
        # Check for core code prioritization
        top_files = [r['payload'].get('file_path', '') for r in results[:3]]
        core_files = [f for f in top_files if any(core in f for core in ['src/', 'api/src/'])]
        if len(core_files) >= 2:
            improvements.append("Core application code prioritized over libraries")
    
    def run_comprehensive_validation(self) -> Dict[str, Any]:
        """Run comprehensive validation across all test queries."""
        print("🧪 RUNNING COMPREHENSIVE SEARCH QUALITY VALIDATION")
        print("=" * 60)
        
        overall_results = {
            'total_queries': len(self.test_queries),
            'query_results': [],
            'overall_quality': 0,
            'common_issues': [],
            'improvement_summary': []
        }
        
        total_quality = 0
        issue_counts = {}
        improvement_counts = {}
        
        for query_test in self.test_queries:
            try:
                result = self.test_query_quality(query_test)
                overall_results['query_results'].append(result)
                
                # Aggregate quality scores
                for lang_scores in result['quality_scores'].values():
                    total_quality += lang_scores.get('quality_score', 0)
                
                # Count issues
                for issue in result['issues_found']:
                    issue_type = issue.split(':')[0] if ':' in issue else issue
                    issue_counts[issue_type] = issue_counts.get(issue_type, 0) + 1
                
                # Count improvements
                for improvement in result['improvements']:
                    improvement_counts[improvement] = improvement_counts.get(improvement, 0) + 1
                
            except Exception as e:
                print(f"❌ Error testing query '{query_test['query']}': {e}")
        
        # Calculate overall metrics
        total_scored_queries = sum(
            len(r['quality_scores']) for r in overall_results['query_results']
        )
        overall_results['overall_quality'] = (
            total_quality / total_scored_queries if total_scored_queries > 0 else 0
        )
        
        # Common issues (appearing in >50% of queries)
        threshold = len(self.test_queries) * 0.5
        overall_results['common_issues'] = [
            f"{issue} (in {count} queries)" 
            for issue, count in issue_counts.items() 
            if count >= threshold
        ]
        
        # Improvement summary
        overall_results['improvement_summary'] = [
            f"{improvement} (in {count} queries)"
            for improvement, count in improvement_counts.items()
        ]
        
        self._print_validation_summary(overall_results)
        return overall_results
    
    def _print_validation_summary(self, results: Dict[str, Any]):
        """Print validation summary."""
        print(f"\n📊 VALIDATION SUMMARY")
        print("=" * 40)
        print(f"Overall Quality Score: {results['overall_quality']:.2f}/1.0")
        print(f"Queries Tested: {results['total_queries']}")
        
        if results['common_issues']:
            print(f"\n⚠️ Common Issues:")
            for issue in results['common_issues']:
                print(f"  - {issue}")
        
        if results['improvement_summary']:
            print(f"\n✅ Improvements Detected:")
            for improvement in results['improvement_summary']:
                print(f"  - {improvement}")
        
        # Quality breakdown by query
        print(f"\n📈 Quality Breakdown:")
        for query_result in results['query_results']:
            query = query_result['query']
            avg_quality = sum(
                scores.get('quality_score', 0) 
                for scores in query_result['quality_scores'].values()
            ) / max(1, len(query_result['quality_scores']))
            print(f"  '{query[:30]}...': {avg_quality:.2f}")

# Usage function
def validate_search_quality():
    """Main function to run search quality validation."""
    validator = SearchQualityValidator()
    return validator.run_comprehensive_validation()

if __name__ == "__main__":
    validate_search_quality()