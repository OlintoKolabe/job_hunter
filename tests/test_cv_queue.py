"""ATS queue isolation and endpoint wiring regression tests."""
import unittest
from unittest.mock import MagicMock, patch

import cv_queue


class CvQueueTests(unittest.TestCase):
    def test_enqueued_request_is_durable_and_owner_scoped(self):
        conn = MagicMock()
        conn.__enter__.return_value = conn
        cursor = conn.cursor.return_value.__enter__.return_value
        with patch.object(cv_queue, "_db", return_value=conn):
            job_id = cv_queue.enqueue("unused", object(), 42,
                                      {"url":"https://example.org/job","title":"PM"})
        query, args = cursor.execute.call_args.args
        self.assertIn("INSERT INTO public.jh_cv_queue", query)
        self.assertEqual(args[0], job_id)
        self.assertEqual(args[1], 42)

    def test_download_query_always_requires_owner(self):
        conn = MagicMock()
        conn.__enter__.return_value = conn
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = None
        with patch.object(cv_queue, "_db", return_value=conn):
            row = cv_queue.get_document("unused", object(), 7,
                                        "12345678-1234-1234-1234-123456789012")
        self.assertIsNone(row)
        query, args = cursor.execute.call_args.args
        self.assertIn("owner_id=%s AND id=%s", query)
        self.assertEqual(args[0], 7)

    def test_worker_starts_in_real_asgi_lifespan(self):
        from pathlib import Path
        source = Path("app.py").read_text()
        lifespan = source.split("async def cv_lifespan(app):",1)[1].split("app.router.lifespan_context",1)[0]
        self.assertIn("start(DATABASE,mu,_queued_generate)", lifespan)
        self.assertNotIn('@app.on_event("startup")\ndef start_cv_queue_worker', source)

    def test_claim_serializes_single_oldest_job(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = ("job", 7, {}, 1)
        row = cv_queue._claim(cursor)
        self.assertEqual(row[0], "job")
        sql = cursor.execute.call_args.args[0]
        self.assertIn("FOR UPDATE SKIP LOCKED LIMIT 1", sql)
        self.assertIn("ORDER BY created_at", sql)


if __name__ == "__main__":
    unittest.main()
