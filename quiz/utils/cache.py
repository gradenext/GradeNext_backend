# utils/cache.py
from django.core.cache import cache
import hashlib
import logging

logger = logging.getLogger(__name__)

class QuestionCache:
    # Cache configuration
    CACHE_SIZE = 100  # Maximum questions per cache key
    CACHE_TTL = 604800  # 7 days in seconds (3600 * 24 * 7)
    PURGE_RATIO = 0.2  # Remove 20% oldest when full

    @staticmethod
    def generate_key(grade, subject, topic, level, revision=False):
        """
        Creates a standardized cache key with versioning
        Format: v1_questions_{grade}_{subject}_{topic}_{level}_[revision]
        """
        base = f"v1_questions_{grade}_{subject}_{topic}_{level}".lower()
        return f"revision_{base}" if revision else base

    @staticmethod
    def get(key):
        """
        Retrieve cached questions with fail-safe handling
        Returns list of questions or empty list on failure
        """
        try:
            return cache.get(key, [])
        except Exception as e:
            logger.error(f"Cache get failed for key {key}: {str(e)}")
            return []

    @staticmethod
    def add(key, question):
        """
        Add a question to cache with deduplication and size management
        """
        try:
            # Get current cache state
            cached = QuestionCache.get(key)
            new_signature = QuestionCache.generate_signature(question)
            
            # Deduplication check
            cached = [
                q for q in cached
                if QuestionCache.generate_signature(q) != new_signature
            ]

            # Size management
            if len(cached) >= QuestionCache.CACHE_SIZE:
                purge_count = int(QuestionCache.CACHE_SIZE * QuestionCache.PURGE_RATIO)
                cached = cached[purge_count:]  # Remove oldest entries
                logger.debug(f"Purged {purge_count} entries from cache {key}")

            # Add new question
            cached.append(question)
            
            # Set updated cache
            cache.set(key, cached, timeout=QuestionCache.CACHE_TTL)
            logger.debug(f"Updated cache {key} with new question. New size: {len(cached)}")
            
        except Exception as e:
            logger.error(f"Cache update failed for key {key}: {str(e)}")

    @staticmethod
    def generate_signature(question):
        """
        Create unique content-based signature using multiple question aspects
        """
        content = (
            f"{question['question_text']}-"
            f"{'-'.join(question['options'])}-"
            f"{question['explanation']}-"
            f"{question['hint']}"
        )
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    @staticmethod
    def clear_key(key):
        """
        Force-clear specific cache key
        """
        try:
            cache.delete(key)
            logger.info(f"Cleared cache key: {key}")
            return True
        except Exception as e:
            logger.error(f"Cache clear failed for key {key}: {str(e)}")
            return False

    @staticmethod
    def get_cache_metrics():
        """
        Returns cache statistics and health metrics
        """
        return {
            'max_size': QuestionCache.CACHE_SIZE,
            'ttl': QuestionCache.CACHE_TTL,
            'purge_ratio': QuestionCache.PURGE_RATIO,
            'estimated_keys': len(cache._cache) if hasattr(cache, '_cache') else 'unknown'
        }