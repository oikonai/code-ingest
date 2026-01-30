"""
Content filtering and prioritization for semantic search quality.
Implements smart file filtering to improve search relevance.
"""

from pathlib import Path
from typing import Dict, List, Tuple
import re

class ContentFilter:
    """Filter and prioritize code content for semantic search."""
    
    def __init__(self):
        # High priority: Core application code that should dominate search results
        self.high_priority_patterns = [
            r'src/',                          # Main application source
            r'api/src/',                      # API handlers  
            r'cli/src/',                      # CLI implementation
            r'contracts/src/',                # Core smart contracts (not lib)
            r'/src/',                         # Source directories
            r'lib/src/',                      # Internal libraries
        ]
        
        # Medium priority: Important but not core business logic
        self.medium_priority_patterns = [
            r'db/',                           # Database related
            r'ethereum-client/',              # Blockchain integration
            r'program/',                      # ZK program
        ]
        
        # Low priority: Include but deprioritize in results
        self.low_priority_patterns = [
            r'scripts/',                      # Build/deployment scripts
            r'docs/',                         # Documentation
            r'examples/',                     # Example code
        ]
        
        # Noise patterns: Third-party/test code that drowns out core logic
        self.noise_patterns = [
            r'lib/sp1-contracts/',            # SP1 library contracts
            r'lib/openzeppelin-contracts/',   # OpenZeppelin library
            r'lib/forge-std/',                # Forge testing utilities
            r'node_modules/',                 # JavaScript dependencies
            r'\.test\.',                      # Test files
            r'\.spec\.',                      # Spec files
            r'/test/',                        # Test directories
            r'/tests/',                       # Test directories
        ]
        
        # Exclude entirely: Build artifacts, temp files, lock files
        self.exclude_patterns = [
            r'target/',                       # Rust build artifacts
            r'dist/',                         # Frontend build
            r'build/',                        # Build output
            r'\.next/',                       # Next.js build cache
            r'out/',                          # Next.js static export
            r'\.turbo/',                      # Turborepo cache
            r'\.git/',                        # Git metadata
            r'__pycache__/',                  # Python cache
            r'\.pytest_cache/',               # Pytest cache
            r'pnpm-lock\.yaml$',              # pnpm lock file (often >131K chars)
            r'package-lock\.json$',           # npm lock file
            r'yarn\.lock$',                   # Yarn lock file
            r'cargo\.lock$',                  # Rust lock file (lowercase for matching)
            r'poetry\.lock$',                 # Python Poetry lock file
            r'pipfile\.lock$',                # Python Pipfile lock file (lowercase for matching)
            r'gemfile\.lock$',                # Ruby lock file (lowercase for matching)
            r'composer\.lock$',               # PHP Composer lock file
            r'go\.sum$',                      # Go dependencies checksum
            r'safeconsole\.sol$',             # Auto-generated Forge console (427KB+)
            r'\.min\.js$',                    # Minified JavaScript (low semantic value)
            r'\.min\.css$',                   # Minified CSS (low semantic value)
            r'-lock\.json$',                  # Any *-lock.json files
        ]
        
        # Business logic indicators for extra relevance boost
        self.business_logic_indicators = [
            'loan', 'credit', 'payment', 'transaction', 'kyc', 'user', 'auth',
            'pool', 'marketplace', 'deal', 'investor', 'lender', 'borrower',
            'interest', 'balance', 'deposit', 'withdrawal', 'verification'
        ]
    
    def classify_file_priority(self, file_path: str) -> Tuple[str, float]:
        """
        Classify file priority and return (category, boost_multiplier).
        
        Returns:
            Tuple of (priority_category, relevance_boost_multiplier)
        """
        file_path = file_path.lower()
        
        # Check for exclusions first
        if any(re.search(pattern, file_path) for pattern in self.exclude_patterns):
            return ('exclude', 0.0)
        
        # Check for noise patterns
        if any(re.search(pattern, file_path) for pattern in self.noise_patterns):
            return ('noise', 0.2)
        
        # Check priority levels
        if any(re.search(pattern, file_path) for pattern in self.high_priority_patterns):
            return ('high', 1.5)
        elif any(re.search(pattern, file_path) for pattern in self.medium_priority_patterns):
            return ('medium', 1.0)
        elif any(re.search(pattern, file_path) for pattern in self.low_priority_patterns):
            return ('low', 0.7)
        
        # Default: medium priority
        return ('medium', 1.0)
    
    def calculate_content_relevance(self, content: str, file_path: str) -> float:
        """Calculate content relevance score based on business logic indicators."""
        content_lower = content.lower()
        file_path_lower = file_path.lower()
        
        # Base relevance score
        relevance = 1.0
        
        # Boost for business logic keywords in content
        business_keyword_count = sum(
            1 for keyword in self.business_logic_indicators 
            if keyword in content_lower
        )
        relevance += business_keyword_count * 0.1
        
        # Boost for business logic keywords in file path (stronger signal)
        file_keyword_count = sum(
            1 for keyword in self.business_logic_indicators 
            if keyword in file_path_lower
        )
        relevance += file_keyword_count * 0.2
        
        # Penalty for generic/utility content
        utility_patterns = ['test', 'util', 'helper', 'mock', 'example']
        utility_penalty = sum(
            1 for pattern in utility_patterns 
            if pattern in content_lower or pattern in file_path_lower
        )
        relevance -= utility_penalty * 0.15
        
        return max(0.1, relevance)  # Minimum relevance threshold
    
    def should_include_file(self, file_path: str) -> bool:
        """Determine if file should be included in ingestion."""
        priority, boost = self.classify_file_priority(file_path)
        return priority != 'exclude'
    
    def calculate_final_boost(self, content: str, file_path: str, metadata: Dict) -> float:
        """Calculate final relevance boost for a chunk."""
        # File priority boost
        priority, file_boost = self.classify_file_priority(file_path)
        
        # Content relevance boost
        content_boost = self.calculate_content_relevance(content, file_path)
        
        # Business domain boost
        domain_boost = 1.0
        business_domains = ['finance', 'auth', 'kyc', 'trading']
        if metadata.get('business_domain') in business_domains:
            domain_boost = 1.2
        
        # Repository boost
        repo_boost = 1.0
        if '/src/' in file_path and any(ui_term in content.lower() 
                                                  for ui_term in ['component', 'react', 'tsx', 'jsx']):
            repo_boost = 1.3  # Boost underrepresented React components
        
        return file_boost * content_boost * domain_boost * repo_boost

# Global instance
content_filter = ContentFilter()