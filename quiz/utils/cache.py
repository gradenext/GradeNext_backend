from django.core.cache import cache
import hashlib

class QuestionCache:
    @staticmethod
    def generate_key(grade, subject, topic, level, revision=False):
        base = f"questions_{grade}_{subject}_{topic}_{level}"
        return f"revision_{base}" if revision else base

    @staticmethod
    def get(key):
        return cache.get(key, [])

    @staticmethod
    def add(key, question):
        cached = QuestionCache.get(key)
        signature = QuestionCache.generate_signature(question)
        
        if not any(QuestionCache.generate_signature(q) == signature for q in cached):
            if len(cached) >= 20:
                cached = cached[5:]
            cached.append(question)
            cache.set(key, cached, timeout=3600*24)

    @staticmethod
    def generate_signature(question):
        content = f"{question['question_text']}-{'-'.join(question['options'])}"
        return hashlib.sha256(content.encode()).hexdigest()