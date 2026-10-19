"""Disposition endpoint regression contracts; use isolated fake DB cursor."""
import unittest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
import app

class DispositionTests(unittest.TestCase):
    def test_existing_exact_url_can_change_state(self):
        payload=app.JobDisposition(url="https://example.com/jobs/123",title="Product Manager",company="Acme",state="Candidatado")
        cursor=MagicMock()
        cursor.fetchone.return_value=(11,"Descartado",app.url_key(payload.url))
        conn=MagicMock()
        conn.__enter__.return_value.cursor.return_value.__enter__.return_value=cursor
        with patch.object(app,"require_auth",return_value=True),patch.object(app.psycopg,"connect",return_value=conn):
            result=app.mark_job_disposition(payload,MagicMock())
        self.assertTrue(result["saved"])
        self.assertTrue(result["updated"])
        self.assertEqual(result["state"],"Candidatado")
        self.assertTrue(any("UPDATE jh_history" in call.args[0] for call in cursor.execute.call_args_list))

    def test_pair_collision_with_different_url_not_overwritten(self):
        payload=app.JobDisposition(url="https://example.com/jobs/new",title="Product Manager",company="Acme",state="Candidatado")
        cursor=MagicMock()
        cursor.fetchone.return_value=(11,"Descartado","example.com/jobs/old")
        conn=MagicMock()
        conn.__enter__.return_value.cursor.return_value.__enter__.return_value=cursor
        with patch.object(app,"require_auth",return_value=True),patch.object(app.psycopg,"connect",return_value=conn):
            with self.assertRaises(HTTPException) as caught:
                app.mark_job_disposition(payload,MagicMock())
        self.assertEqual(caught.exception.status_code,409)
        self.assertFalse(any("UPDATE jh_history" in call.args[0] for call in cursor.execute.call_args_list))

if __name__=="__main__":unittest.main()
