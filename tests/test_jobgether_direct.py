"""Jobgether v1 contract and multi-source isolation; all tests are offline."""
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit

from collectors import JobgetherHTTPError, collect, pull
from search_filters import classify, search_terms


def listing(term, suffix="1"):
    return {"jobs": [{"id": suffix, "title": term.title(),
                      "company": "Example", "location": "Brazil - Remote",
                      "url": "https://jobgether.com/offer/" + suffix,
                      "postedAt": "2026-11-04T10:00:00Z"}]}


class JobgetherDirectTests(unittest.TestCase):
    def test_four_critical_terms_use_supported_get_contract(self):
        terms=("product manager", "product owner", "project manager", "pmo")
        calls=[]

        def fake_request(url,headers=None):
            calls.append(url)
            query=parse_qs(urlsplit(url).query)
            return listing(query["keyword"][0],str(len(calls)))

        with patch("collectors.fetch_json",side_effect=fake_request):
            for term in terms:
                detail,jobs=pull("Jobgether",term,"Brazil")
                self.assertEqual(detail["status"],"ok")
                self.assertEqual(detail["received"],1)
                self.assertEqual(jobs[0]["published"],"2026-11-04T10:00:00Z")
        self.assertEqual(len(calls),4)
        for url,term in zip(calls,terms):
            self.assertEqual((urlsplit(url).scheme,urlsplit(url).netloc,urlsplit(url).path),
                             ("https","jobgether.com","/api/v1/jobs"))
            self.assertEqual(parse_qs(urlsplit(url).query),
                             {"keyword":[term],"sort":["date"],"limit":["25"],
                              "locations":["brazil"]})

    def test_true_empty_result_is_success_zero(self):
        with patch("collectors.fetch_json",return_value={"jobs":[],"pagination":{"hasMore":False}}):
            detail,jobs=pull("Jobgether","pmo","Brazil")
        self.assertEqual((detail["status"],detail["received"],jobs),("ok",0,[]))

    def test_http_400_records_safe_problem_details_not_zero_success(self):
        body=json.dumps({"code":"invalid_parameter","field":"locations",
                         "detail":"Invalid value for 'locations': \"Brazil\"",
                         "token":"secret-should-not-appear","cookies":"sensitive"}).encode()
        error=HTTPError("https://jobgether.com/api/v1/jobs",400,"Bad Request",
                        {"Content-Type":"application/problem+json; charset=utf-8"},io.BytesIO(body))
        with patch("collectors.urllib.request.urlopen",side_effect=error):
            with self.assertRaises(JobgetherHTTPError) as raised:
                pull("Jobgether","product manager","Brazil")
        self.assertEqual(raised.exception.status,400)
        self.assertEqual(raised.exception.code,"invalid_parameter")
        self.assertEqual(raised.exception.field,"locations")
        self.assertNotIn("secret",str(raised.exception))

    def test_failed_direct_does_not_abort_lever_or_other_terms(self):
        def fake_pull(source,term,location):
            if source=="Jobgether" and term=="product manager":
                raise JobgetherHTTPError(400,"application/problem+json","invalid_parameter",
                                         "locations","Invalid location")
            return {"source":source,"term":term,"status":"ok","received":1},[
                {"url":"https://example.com/posting/"+term.replace(" ","-"),
                 "company":"Example","title":term}]

        with patch("collectors.pull",side_effect=fake_pull),patch("collectors.BOARDS",{"Lever":("jobgether",)}):
            found,details=collect(["product manager","pmo"],"BR","all")
        self.assertEqual(len(found),3)  # same URL from multiple sources is deduplicated
        failures=[d for d in details if d["status"]=="error"]
        self.assertEqual(len(failures),1)
        self.assertEqual(failures[0]["source"],"Jobgether")
        self.assertEqual(failures[0]["term"],"product manager")
        self.assertEqual(failures[0]["http_status"],400)
        self.assertTrue(any(d["source"]=="Lever" and d["status"]=="ok" for d in details))
        self.assertTrue(any(d["source"]=="Jobgether" and d["term"]=="pmo" and d["status"]=="ok" for d in details))

    def test_lever_jobgether_fallback_keeps_its_existing_endpoint(self):
        seen=[]
        def fake_request(url,headers=None):
            seen.append(url)
            return [{"text":"Product Manager","hostedUrl":"https://example.com/lever/1",
                     "categories":{"location":"Brazil"}}]
        with patch("collectors.fetch_json",side_effect=fake_request):
            _,jobs=pull("Lever","jobgether")
        self.assertEqual(len(jobs),1)
        self.assertEqual(urlsplit(seen[0]).netloc,"api.lever.co")
        self.assertIn("location=Brazil",seen[0])

    def test_filter_contract_remains_profile_specific_after_collection(self):
        with patch("collectors.fetch_json",return_value=listing("Product Manager")):
            _,jobs=pull("Jobgether","product manager","Brazil")
        self.assertEqual(len(jobs),1)
        father=classify(jobs[0],search_terms("Product Manager"),"BR","remote",7)
        other=classify(jobs[0],search_terms("Data Scientist"),"BR","remote",7)
        self.assertNotEqual(father[0],"excluded")
        self.assertEqual(other[0],"excluded")

    def test_zero_in_one_source_does_not_block_other_source(self):
        def fake_pull(source,term,location):
            if source=="Jobgether":
                return {"source":source,"term":term,"status":"ok","received":0},[]
            return {"source":source,"term":term,"status":"ok","received":1},[
                {"url":"https://example.com/lever/1","title":"PMO","company":"Example"}]
        with patch("collectors.pull",side_effect=fake_pull),patch("collectors.BOARDS",{"Lever":("jobgether",)}):
            found,details=collect(["pmo"],"BR","all")
        self.assertEqual(len(found),1)
        self.assertEqual([d["status"] for d in details],["ok","ok","ok"])
        self.assertEqual(next(d for d in details if d["source"]=="Jobgether")["received"],0)


if __name__=="__main__":
    unittest.main()
