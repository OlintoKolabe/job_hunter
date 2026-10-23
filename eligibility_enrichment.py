"""Free public-source metadata needed before eligibility filters.

Never calls an LLM, generates scores, or infers a missing publication date.
"""
from concurrent.futures import ThreadPoolExecutor

from collectors import fetch_json, inhire_detail
from search_filters import role_match, search_terms, parse_date


def enrich_inhire_before_filter(jobs, roles, limit=16):
    """Fetch complete listing metadata only for role-relevant inHire jobs.

    Unfetched/failed records retain their original missing metadata. They must
    never be treated as date-confirmed, and do not trigger an AI charge.
    """
    terms=search_terms(roles)
    candidates=[(i,j) for i,j in enumerate(jobs)
                if str(j.get("source","")).casefold()=="inhire"
                and (not parse_date(j.get("published")) or not j.get("description"))
                and role_match(j.get("title",""),terms)
                and inhire_detail(j)]
    selected=candidates[:max(0,limit)]
    metrics={"eligible_for_detail":len(candidates),"attempted":len(selected),
             "complete":0,"failed":0,"deferred":len(candidates)-len(selected)}
    output=list(jobs)
    def fetch(pair):
        i,job=pair
        endpoint,headers=inhire_detail(job)
        try:
            response=fetch_json(endpoint,headers)
            detail=(response.get("jobPage") or response.get("page") or response) if isinstance(response,dict) else {}
            if not isinstance(detail,dict):return i,None
            date=detail.get("lastPublishedAt") or detail.get("publishedAt") or detail.get("createdAt")
            # lastPublishedAt is a real publication event; updatedAt is not.
            jd=detail.get("description") or detail.get("jobDescription") or ""
            return i,{"published":date if parse_date(date) else "",
                      "description":jd[:18000] if isinstance(jd,str) else ""}
        except Exception:
            return i,None
    with ThreadPoolExecutor(max_workers=8) as pool:
        for i,metadata in pool.map(fetch,selected):
            if metadata and (metadata["published"] or metadata["description"]):
                output[i]={**output[i],**{key:value for key,value in metadata.items() if value}}
                metrics["complete"]+=1
            else:
                metrics["failed"]+=1
    return output,metrics
