import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import webhook_lab as w


class T(unittest.TestCase):
    def test_roundtrip(self):
        w.verify("{}", w.sign("{}", "s"), "s")

    def test_bad_secret(self):
        with self.assertRaises(ValueError):
            w.verify("{}", w.sign("{}", "s"), "x")

    def test_tampered(self):
        with self.assertRaises(ValueError):
            w.verify('{"a":2}', w.sign('{"a":1}', "s"), "s")

    def test_old_timestamp(self):
        with self.assertRaises(ValueError):
            w.verify("{}", w.sign("{}", "s", int(time.time()) - 1000), "s")

    def test_summary(self):
        ev = [w.sample_event("payment_intent.succeeded", 1000, "usd", "a"),
              w.sample_event("charge.refunded", 400, "usd", "b")]
        self.assertEqual(w.summarize(ev)["net"], {"USD": 600})


if __name__ == "__main__":
    unittest.main()
