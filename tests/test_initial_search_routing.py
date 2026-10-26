"""Search startup must not repeat company boards already in catalog scanning."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from collectors import collect


def catalog_boards():
    seed=json.loads((Path(__file__).resolve().parent.parent/"catalog_seed.json").read_text())
    return [(source,slug) for source,slugs in seed.items() for slug in slugs]


class InitialSearchRoutingTests(unittest.TestCase):
    def test_initial_all_preserves_keyword_search_and_deduplicates_boards(self):
        seen=[]
        def fake_pull(source,slug,location):
            seen.append((source,slug))
            return {"source":source,"term":slug,"status":"ok","received":0},[]
        terms=["query"+str(n) for n in range(12)]
        with patch("collectors.pull",side_effect=fake_pull):
            _,details=collect(terms,"BR","all",catalog_boards())
        self.assertEqual(len(details),24)
        self.assertEqual(len(set(seen)),24)
        self.assertEqual(sum(src=="Jobgether" for src,_ in seen),12)
        self.assertEqual(sum(src=="Workable" for src,_ in seen),12)
        self.assertFalse(any(src not in ("Jobgether","Workable") for src,_ in seen))

    def test_source_specific_search_does_not_change(self):
        with patch("collectors.pull",return_value=({"source":"Jobgether","status":"ok","received":0},[])):
            _,details=collect(["data scientist","data engineer"],"BR","jobgether")
        self.assertEqual(len(details),2)


if __name__=="__main__":
    unittest.main()
