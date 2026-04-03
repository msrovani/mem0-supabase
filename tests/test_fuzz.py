"""
Fuzz Testing — Property-based and fuzz testing for Mem0 components.

Tests edge cases, malformed inputs, and boundary conditions
on individual components that don't require full Memory initialization.

Usage:
    pytest tests/test_fuzz.py -v
"""

import unittest


class TestPIIFuzzing(unittest.TestCase):
    def test_email_variations(self):
        from mem0.security.context_firewall import ContextFirewall
        fw = ContextFirewall()
        for text in ["test@example.com", "admin@company.org", "a@b.co"]:
            r = fw.redact_text(text)
            self.assertIn("[EMAIL_REDACTED]", r.redacted_text)

    def test_cpf_redaction(self):
        from mem0.security.context_firewall import ContextFirewall
        fw = ContextFirewall()
        r = fw.redact_text("cpf: 123.456.789-00")
        self.assertIn("[CPF_REDACTED]", r.redacted_text)

    def test_mixed_pii(self):
        from mem0.security.context_firewall import ContextFirewall
        fw = ContextFirewall()
        r = fw.redact_text("Contact test@example.com, phone: (555) 123-4567, from IP 10.0.0.1")
        self.assertIn("[EMAIL_REDACTED]", r.redacted_text)
        self.assertIn("[PHONE_REDACTED]", r.redacted_text)
        self.assertIn("[IP_REDACTED]", r.redacted_text)

    def test_clean_text(self):
        from mem0.security.context_firewall import ContextFirewall
        fw = ContextFirewall()
        r = fw.redact_text("Hello world no PII here")
        self.assertTrue(r.is_clean)

    def test_empty_text(self):
        from mem0.security.context_firewall import ContextFirewall
        fw = ContextFirewall()
        r = fw.redact_text("")
        self.assertTrue(r.is_clean)


class TestCircuitBreakerFuzz(unittest.TestCase):
    def test_rapid_failures(self):
        from mem0.error_boundaries import CircuitBreaker, CircuitBreakerError
        cb = CircuitBreaker(name="test", failure_threshold=2, recovery_timeout=1)
        for _ in range(5):
            try:
                cb.call(lambda: 1 / 0)
            except (ZeroDivisionError, CircuitBreakerError):
                pass
        self.assertEqual(cb.state, "open")

    def test_recovery(self):
        import time
        from mem0.error_boundaries import CircuitBreaker
        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_timeout=0.5)
        try:
            cb.call(lambda: 1 / 0)
        except ZeroDivisionError:
            pass
        time.sleep(0.6)
        self.assertEqual(cb.call(lambda: "ok"), "ok")
        self.assertEqual(cb.state, "closed")


class TestSmartCacheFuzz(unittest.TestCase):
    def test_concurrent_access(self):
        import threading
        from unittest.mock import MagicMock
        from mem0.smart_cache import SmartCache
        mock_hybrid = MagicMock()
        mock_hybrid.get.return_value = None
        mock_hybrid.set = MagicMock()
        cache = SmartCache(hybrid_cache=mock_hybrid, auto_tune=False)
        errors = []

        def worker(n):
            try:
                for i in range(50):
                    cache.get(query_embedding=[float(i)] * 10)
                    cache.set(f"q{i}", [float(i)] * 10, f"r{i}")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(errors), 0)

    def test_stats(self):
        from unittest.mock import MagicMock
        from mem0.smart_cache import SmartCache
        mock_hybrid = MagicMock()
        mock_hybrid.get.return_value = None
        mock_hybrid.set = MagicMock()
        cache = SmartCache(hybrid_cache=mock_hybrid, auto_tune=False)
        for i in range(5):
            cache.get(query_embedding=[float(i)] * 10)
        s = cache.get_stats()
        self.assertEqual(s["misses"], 5)
        self.assertEqual(s["total_gets"], 5)


class TestTemplatesFuzz(unittest.TestCase):
    def test_missing_fields(self):
        from mem0.templates import TemplateRegistry
        reg = TemplateRegistry()
        with self.assertRaises(ValueError):
            reg.validate("fact", {"user_id": "u1"})

    def test_defaults(self):
        from mem0.templates import TemplateRegistry
        reg = TemplateRegistry()
        r = reg.validate("fact", {"content": "test", "user_id": "u1"})
        self.assertIn("confidence", r)
        self.assertEqual(r["confidence"], 0.5)

    def test_unknown_template(self):
        from mem0.templates import TemplateRegistry
        reg = TemplateRegistry()
        with self.assertRaises(ValueError):
            reg.validate("nonexistent", {"data": "test"})


if __name__ == "__main__":
    unittest.main()
