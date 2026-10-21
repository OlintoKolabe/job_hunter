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

    def test_pair_collision_with_different_url_creates_independent_decision(self):
        payload=app.JobDisposition(url="https://example.com/jobs/new",title="Product Manager",company="Acme",state="Candidatado")
        cursor=MagicMock()
        cursor.fetchone.return_value=(11,"Descartado","example.com/jobs/old")
        conn=MagicMock()
        conn.__enter__.return_value.cursor.return_value.__enter__.return_value=cursor
        with patch.object(app,"require_auth",return_value=True),patch.object(app.psycopg,"connect",return_value=conn):
            result=app.mark_job_disposition(payload,MagicMock())
        self.assertTrue(result["saved"])
        self.assertFalse(result["already_recorded"])
        calls=[call for call in cursor.execute.call_args_list if "INSERT INTO jh_history" in call.args[0]]
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0].args[1][4],"")
        self.assertFalse(any("UPDATE jh_history" in call.args[0] for call in cursor.execute.call_args_list))

    def test_lowercase_legacy_status_is_idempotent(self):
        payload=app.JobDisposition(url="https://example.com/jobs/123",title="Product Manager",company="Acme",state="Candidatado")
        cursor=MagicMock()
        cursor.fetchone.return_value=(11,"candidatado",app.url_key(payload.url))
        conn=MagicMock()
        conn.__enter__.return_value.cursor.return_value.__enter__.return_value=cursor
        with patch.object(app,"require_auth",return_value=True),patch.object(app.psycopg,"connect",return_value=conn):
            result=app.mark_job_disposition(payload,MagicMock())
        self.assertEqual(result["state"],"Candidatado")
        self.assertFalse(result["updated"])
        self.assertFalse(any("UPDATE jh_history" in call.args[0] for call in cursor.execute.call_args_list))

if __name__=="__main__":unittest.main()
