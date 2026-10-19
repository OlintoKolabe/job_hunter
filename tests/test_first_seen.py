import unittest
from unittest.mock import MagicMock
from first_seen import flag_new_jobs

class FirstSeenTests(unittest.TestCase):
    def test_only_new_ids_receive_badge(self):
        connection=MagicMock()
        cur=connection.cursor.return_value.__enter__.return_value
        cur.fetchall.return_value=[("example.com/jobs/123",)]
        jobs=[{"url":"https://example.com/jobs/123","title":"PM"},
              {"url":"https://example.com/jobs/456","title":"PO"}]
        flagged=flag_new_jobs(connection,jobs,lambda url:url.replace("https://",""))
        self.assertEqual([j["is_new"] for j in flagged],[True,False])
        self.assertIn("ON CONFLICT(normalized_url) DO NOTHING",cur.execute.call_args.args[0])

    def test_no_urls_no_database_writes(self):
        connection=MagicMock()
        self.assertEqual(flag_new_jobs(connection,[{"title":"PM"}],lambda url:""),[{"title":"PM"}])
        connection.cursor.assert_not_called()

if __name__=="__main__":
    unittest.main()
