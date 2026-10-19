"""Date-selection API contracts; no destructive operations."""
import unittest
from fastapi import HTTPException
from app import history_date_filters, HISTORY_DAY_SQL

class HistoryDateFilterTests(unittest.TestCase):
    def test_single_day(self):
        clauses,params=history_date_filters("2026-10-19","2026-10-19")
        self.assertEqual(params,["2026-10-19","2026-10-19"])
        self.assertEqual(len(clauses),2)
    def test_range(self):
        clauses,params=history_date_filters("2026-09-01","2026-10-19")
        self.assertEqual(len(clauses),2)
        self.assertEqual(params,["2026-09-01","2026-10-19"])
    def test_selected_days(self):
        clauses,params=history_date_filters(dates="2026-09-15,2026-10-19")
        self.assertEqual(len(clauses),1)
        self.assertEqual(params,[["2026-09-15","2026-10-19"]])
    def test_invalid_dates(self):
        for kwargs in ({"from_date":"2026-02-30"},{"dates":"2026-10-45"},{"from_date":"2026-10-19","to_date":"2026-10-01"}):
            with self.assertRaises(HTTPException):history_date_filters(**kwargs)
    def test_legacy_date_format_supported(self):
        self.assertIn("substring(data from 7 for 4)",HISTORY_DAY_SQL)

if __name__=="__main__":unittest.main()
