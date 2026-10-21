"""Ensure review jobs remain visible and all decision buttons share a component."""
import unittest
from pathlib import Path

class OpportunityUIContracts(unittest.TestCase):
    def test_reviews_in_main_result_map(self):
        s=Path("src/Opportunities.jsx").read_text()
        self.assertIn("visibleReviews.forEach(v=>{if(!combined.has(v.url))combined.set(v.url,{...v,confirmed:false})})",s)
    def test_shared_action_buttons_in_all_three_sections(self):
        s=Path("src/Opportunities.jsx").read_text()
        self.assertEqual(s.count("<DecisionActions job={v} pending={decisionNow.includes(v.url)} onDecision={markDecision}/>"),3)
        self.assertEqual(s.count("onClick={()=>markDecision(v,'Candidatado')}"),0)
        self.assertEqual(s.count("onClick={()=>markDecision(v,'Descartado')}"),0)

    def test_geography_priority_precedes_scores_and_dates(self):
        s=Path("src/Opportunities.jsx").read_text()
        self.assertIn("const geoPriority=v=>",s)
        self.assertIn("if(geoDiff)return geoDiff;",s)
        self.assertLess(s.index("if(geoDiff)return geoDiff;"),s.index("return sort==='recommendation'"))
        self.assertIn("if(explicitBrazil)return 0;",s)
        self.assertIn("if(latam)return 1;",s)
        self.assertIn("if(v.needs_verification?.includes('pais'))return 3;",s)
        self.assertIn(".sort((a,b)=>geoPriority(a)-geoPriority(b)).map(v=>",s)

if __name__=="__main__":unittest.main()
