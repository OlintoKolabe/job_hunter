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

    def test_deletion_is_owner_scoped_and_never_removes_running_job(self):
        conn = MagicMock()
        conn.__enter__.return_value = conn
        cursor = conn.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = ("deleted-id",)
        with patch.object(cv_queue, "_db", return_value=conn):
            result = cv_queue.delete_job("unused", object(), 42,
                                         "12345678-1234-1234-1234-123456789012")
        self.assertEqual(result, "deleted")
        sql, args = cursor.execute.call_args.args
        self.assertIn("owner_id=%s AND id=%s", sql)
        self.assertIn("status IN ('queued','ready','failed')", sql)
        self.assertEqual(args[0], 42)

    def test_worker_starts_in_real_asgi_lifespan(self):
        from pathlib import Path
        source = Path("app.py").read_text()
        lifespan = source.split("async def cv_lifespan(app):",1)[1].split("app.router.lifespan_context",1)[0]
        self.assertIn("start(DATABASE,mu,_queued_generate)", lifespan)
        self.assertNotIn('@app.on_event("startup")\ndef start_cv_queue_worker', source)

    def test_claim_serializes_single_oldest_job(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = ("job", 7, {}, 1, 12.3)
        row = cv_queue._claim(cursor)
        self.assertEqual(row[0], "job")
        sql = cursor.execute.call_args.args[0]
        self.assertIn("FOR UPDATE SKIP LOCKED LIMIT 1", sql)
        self.assertIn("ORDER BY created_at", sql)
        self.assertIn("started_at-created_at", sql)

    def test_queue_poll_does_not_repeat_schema_ddl(self):
        from pathlib import Path
        source = Path("app.py").read_text()
        status_handler = source.split('def resume_queue_status(', 1)[1].split('@app.delete(', 1)[0]
        self.assertNotIn('ensure_schema(', status_handler)
        self.assertIn('started_at', Path('cv_queue.py').read_text())
        self.assertIn('_wakeup.wait(timeout=5)', Path('cv_queue.py').read_text())
        self.assertIn('ensure_schema(db_url, mu)', Path('cv_queue.py').read_text())
    def test_two_workers_use_distinct_advisory_locks(self):
        from pathlib import Path
        source=Path('cv_queue.py').read_text()
        self.assertIn('for lane in range(2):',source)
        self.assertIn('lock_key=LOCK_KEY+lane',source)
        self.assertIn('FOR UPDATE SKIP LOCKED LIMIT 1',source)


if __name__ == "__main__":
    unittest.main()
