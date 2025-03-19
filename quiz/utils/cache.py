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
        # Store only question content without IDs
        clean_question = {k:v for k,v in question.items() if k != 'id'}
        if len(cached) >= 10:
            cached.pop(0)
        cached.append(clean_question)
        cache.set(key, cached, timeout=3600*24)
        
        
    @staticmethod
    def generate_hash(text):
        return hashlib.md5(text.encode()).hexdigest()