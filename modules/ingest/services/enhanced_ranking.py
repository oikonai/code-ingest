"""
Enhanced ranking system for semantic search results.
Implements multi-factor scoring to improve result relevance.
"""

import re
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass
from .content_filter import content_filter

@dataclass
class SearchContext:
    """Context information for search query."""
    query: str
    inferred_intent: str
    domain: str
    language_preference: List[str]
    is_frontend_query: bool
    is_backend_query: bool
    is_contract_query: bool

class EnhancedRanker:
    """Multi-factor ranking system for search results."""
    
    def __init__(self):
        # Query intent patterns
        self.intent_patterns = {
            'business_logic': [
                'loan', 'credit', 'payment', 'transaction', 'interest', 
                'balance', 'deposit', 'withdrawal', 'origination', 'closeout'
            ],
            'authentication': [
                'auth', 'login', 'logout', 'session', 'token', 'magic link',
                'verification', 'user', 'password', 'oauth'
            ],
            'kyc_compliance': [
                'kyc', 'compliance', 'identity', 'verification', 'investor',
                'accredited', 'documents', 'regulatory'
            ],
            'blockchain': [
                'contract', 'ethereum', 'proof', 'blockchain', 'solidity',
                'verifier', 'sp1', 'zk', 'zero knowledge'
            ],
            'frontend_ui': [
                'component', 'react', 'ui', 'form', 'page', 'modal',
                'button', 'interface', 'frontend', 'tsx', 'jsx'
            ],
            'backend_api': [
                'api', 'handler', 'endpoint', 'server', 'database',
                'middleware', 'router', 'service'
            ],
            'trading': [
                'marketplace', 'deal', 'trading', 'pool', 'liquidity',
                'investor', 'portfolio', 'market'
            ]
        }
        
        # Language preferences by query type
        self.language_preferences = {
            'frontend_ui': ['typescript', 'javascript', 'jsx', 'tsx'],
            'backend_api': ['rust'],
            'blockchain': ['solidity'],
            'business_logic': ['rust', 'solidity'],
        }
    
    def analyze_query_context(self, query: str) -> SearchContext:
        """Analyze query to determine search context and intent."""
        query_lower = query.lower()
        
        # Determine primary intent
        intent_scores = {}
        for intent, keywords in self.intent_patterns.items():
            score = sum(1 for keyword in keywords if keyword in query_lower)
            if score > 0:
                intent_scores[intent] = score
        
        primary_intent = max(intent_scores.items(), key=lambda x: x[1])[0] if intent_scores else 'general'
        
        # Determine domain focus
        domain_mapping = {
            'business_logic': 'finance',
            'trading': 'finance', 
            'authentication': 'auth',
            'kyc_compliance': 'kyc',
            'blockchain': 'contracts',
            'frontend_ui': 'ui',
            'backend_api': 'api'
        }
        domain = domain_mapping.get(primary_intent, 'unknown')
        
        # Language preferences
        lang_prefs = self.language_preferences.get(primary_intent, ['rust', 'typescript', 'solidity'])
        
        return SearchContext(
            query=query,
            inferred_intent=primary_intent,
            domain=domain,
            language_preference=lang_prefs,
            is_frontend_query='frontend' in primary_intent or 'ui' in primary_intent,
            is_backend_query='backend' in primary_intent or 'api' in primary_intent,
            is_contract_query='blockchain' in primary_intent
        )
    
    def calculate_enhanced_score(self, base_similarity: float, result: Dict[str, Any], 
                                context: SearchContext) -> float:
        """Calculate enhanced relevance score using multiple factors."""
        payload = result['payload']
        
        # Start with base semantic similarity
        score = base_similarity
        
        # Factor 1: File priority boost
        file_path = payload.get('file_path', '')
        priority, file_boost = content_filter.classify_file_priority(file_path)
        score *= file_boost
        
        # Factor 2: Business domain alignment
        chunk_domain = payload.get('business_domain', 'unknown')
        if context.domain != 'unknown' and chunk_domain == context.domain:
            score *= 1.4  # Strong domain match
        elif chunk_domain in ['finance', 'auth', 'kyc'] and context.domain in ['finance', 'auth', 'kyc']:
            score *= 1.2  # Related business domains
        
        # Factor 3: Language preference alignment
        chunk_language = payload.get('language', 'unknown')
        if chunk_language in context.language_preference:
            preference_index = context.language_preference.index(chunk_language)
            score *= (1.3 - preference_index * 0.1)  # Higher boost for preferred languages
        

        # Factor 4: Repository relevance
        repo_id = payload.get('repo_id', '')
        # Boost results from repos matching query type (frontend/backend)
        # Config-driven: use repo_type from repository config if available
        if context.is_frontend_query and 'frontend' in repo_id.lower():
            score *= 1.5  # Boost frontend repo for UI queries
        elif context.is_backend_query and 'backend' in repo_id.lower():
            score *= 1.3  # Boost backend repo for API queries
        
        # Factor 5: Content type relevance
        item_type = payload.get('item_type', '')
        component_type = payload.get('repo_component', '')
        
        if context.is_frontend_query:
            if item_type in ['component', 'function'] and 'app' in repo_id:
                score *= 1.4
        elif context.is_backend_query:
            if item_type in ['fn', 'struct'] and component_type in ['api', 'core']:
                score *= 1.3
        
        # Factor 6: Complexity and size consideration
        complexity = payload.get('complexity_score', 1.0)
        if 2.0 <= complexity <= 8.0:  # Sweet spot for meaningful code chunks
            score *= 1.1
        elif complexity > 10.0:  # Very complex code might be less readable
            score *= 0.9
        
        # Factor 7: Content preview relevance (keyword matching)
        content_preview = payload.get('content_preview', '').lower()
        query_words = set(context.query.lower().split())
        preview_words = set(content_preview.split())
        keyword_overlap = len(query_words.intersection(preview_words)) / len(query_words)
        score *= (1.0 + keyword_overlap * 0.3)
        
        # Factor 8: Penalty for overly generic results
        item_name = payload.get('item_name', '').lower()
        generic_names = ['test', 'util', 'helper', 'mock', 'example', 'std']
        if any(generic in item_name for generic in generic_names):
            score *= 0.6
        
        return score
    
    def diversify_results(self, results: List[Dict], max_per_file: int = 2, 
                         max_per_type: int = 3) -> List[Dict]:
        """Ensure result diversity to prevent repetitive results."""
        diversified = []
        file_counts = {}
        type_counts = {}
        
        # Sort by enhanced score first
        sorted_results = sorted(results, key=lambda x: x.get('enhanced_score', x['score']), reverse=True)
        
        for result in sorted_results:
            payload = result['payload']
            file_path = payload.get('file_path', '')
            item_type = payload.get('item_type', '')
            item_name = payload.get('item_name', '')
            
            # Skip if we already have enough from this file
            if file_counts.get(file_path, 0) >= max_per_file:
                continue
            
            # Skip if we already have enough of this type
            type_key = f"{item_type}_{item_name}"
            if type_counts.get(type_key, 0) >= max_per_type:
                continue
            
            diversified.append(result)
            file_counts[file_path] = file_counts.get(file_path, 0) + 1
            type_counts[type_key] = type_counts.get(type_key, 0) + 1
            
            # Stop when we have enough diverse results  
            if len(diversified) >= 20:
                break
        
        return diversified
    
    def enhance_search_results(self, query: str, raw_results: Dict[str, List[Dict]]) -> Dict[str, List[Dict]]:
        """Apply enhanced ranking to search results."""
        context = self.analyze_query_context(query)
        enhanced_results = {}
        
        for language, lang_results in raw_results.items():
            if not lang_results:
                enhanced_results[language] = []
                continue
            
            # Calculate enhanced scores
            for result in lang_results:
                enhanced_score = self.calculate_enhanced_score(
                    result['score'], result, context
                )
                result['enhanced_score'] = enhanced_score
                result['context_info'] = {
                    'inferred_intent': context.inferred_intent,
                    'domain_match': result['payload'].get('business_domain') == context.domain,
                    'language_preferred': result['payload'].get('language') in context.language_preference[:2]
                }
            
            # Sort by enhanced score and diversify
            sorted_results = sorted(lang_results, key=lambda x: x['enhanced_score'], reverse=True)
            diversified = self.diversify_results(sorted_results)
            
            enhanced_results[language] = diversified
        
        return enhanced_results

# Global instance
enhanced_ranker = EnhancedRanker()