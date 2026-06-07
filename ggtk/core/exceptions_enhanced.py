"""
Enhanced exception classes with structured context and suggestions.
"""

from typing import Any, Dict, Optional
from .exceptions import GGTError


class EnhancedGGTError(GGTError):
    """Base exception with structured context and helpful suggestions."""
    
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        suggestion: Optional[str] = None,
        error_code: Optional[str] = None
    ):
        super().__init__(message)
        self.context = context or {}
        self.suggestion = suggestion
        self.error_code = error_code
    
    def __str__(self) -> str:
        base = super().__str__()
        parts = [base]
        
        if self.context:
            ctx_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            parts.append(f"[Context: {ctx_str}]")
        
        if self.suggestion:
            parts.append(f"\n💡 Suggestion: {self.suggestion}")
        
        if self.error_code:
            parts.append(f"\nError Code: {self.error_code}")
        
        return "\n".join(parts)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API responses."""
        return {
            'error_type': type(self).__name__,
            'message': str(self),
            'context': self.context,
            'suggestion': self.suggestion,
            'error_code': self.error_code,
        }


class GrammarLoadError(EnhancedGGTError):
    """Raised when a grammar cannot be loaded."""
    
    def __init__(
        self,
        language: str,
        reason: str,
        suggestion: str = None
    ):
        super().__init__(
            message=f"Failed to load grammar for '{language}': {reason}",
            context={'language': language, 'reason': reason},
            suggestion=suggestion or "Check that the language is registered and the YAML file exists",
            error_code="GRAMMAR_LOAD_ERROR"
        )


class MorphologicalAnalysisError(EnhancedGGTError):
    """Raised when morphological analysis fails."""
    
    def __init__(
        self,
        token: str,
        language: str,
        reason: str,
        suggestion: str = None
    ):
        super().__init__(
            message=f"Analysis failed for token '{token}' in {language}: {reason}",
            context={'token': token, 'language': language, 'reason': reason},
            suggestion=suggestion or "Verify the token is valid in the target language",
            error_code="ANALYSIS_ERROR"
        )


class GenerationError(EnhancedGGTError):
    """Raised when verb form generation fails."""
    
    def __init__(
        self,
        features: Dict[str, Any],
        reason: str,
        suggestion: str = None
    ):
        super().__init__(
            message=f"Generation failed: {reason}",
            context={'features': features, 'reason': reason},
            suggestion=suggestion or "Check that all required features are provided and valid",
            error_code="GENERATION_ERROR"
        )


class ValidationError(EnhancedGGTError):
    """Raised when validation fails."""
    
    def __init__(
        self,
        field: str,
        value: Any,
        reason: str,
        suggestion: str = None
    ):
        super().__init__(
            message=f"Validation failed for field '{field}': {reason}",
            context={'field': field, 'value': value, 'reason': reason},
            suggestion=suggestion,
            error_code="VALIDATION_ERROR"
        )


class CacheError(EnhancedGGTError):
    """Raised when cache operations fail."""
    
    def __init__(
        self,
        operation: str,
        key: str,
        reason: str
    ):
        super().__init__(
            message=f"Cache {operation} failed for key '{key}': {reason}",
            context={'operation': operation, 'key': key, 'reason': reason},
            suggestion="Try clearing the cache or restarting the service",
            error_code="CACHE_ERROR"
        )
