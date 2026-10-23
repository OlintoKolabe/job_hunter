"""Free public-source metadata needed before eligibility filters.

Never calls an LLM, generates scores, or infers a missing publication date.
"""
from concurrent.futures import ThreadPoolExecutor

from collectors import fetch_json, inhire_detail
from search_filters import role_match, search_terms, parse_date, classify, detect_work_mode, geo_verdict


def eligibility_audit(before, after, roles, country, mode, days):
    """Compare identical URLs, never counting unknown evidence as eligible."""
    terms=search_terms(roles)
    result={"raw":len(before),"confirmed_before":0,"confirmed_after":0,
            "recovered_confirmed":0,"lost_confirmed":0,"still_review":0,
            "missing_date_before":0,"missing_date_after":0,
            "unknown_mode_before":0,"unknown_mode_after":0,
            "unknown_country_before":0,"unknown_country_after":0,
            "by_source":{}}
    for old,new in zip(before,after):
        source=str(old.get("source") or "desconhecida").casefold()
        row=result["by_source"].setdefault(source,{"raw":0,"confirmed_before":0,"confirmed_after":0,
                                                   "recovered_confirmed":0,"still_review":0,
                                                   "missing_date":0,"unknown_mode":0,"unknown_country":0})
        row["raw"]+=1
        old_state,_=classify(old,terms,country,mode,days)
        new_state,_=classify(new,terms,country,mode,days)
        if old_state=="confirmed":
            result["confirmed_before"]+=1;row["confirmed_before"]+=1
        if new_state=="confirmed":
            result["confirmed_after"]+=1;row["confirmed_after"]+=1
        if old_state!="confirmed" and new_state=="confirmed":
            result["recovered_confirmed"]+=1;row["recovered_confirmed"]+=1
        if old_state=="confirmed" and new_state!="confirmed":result["lost_confirmed"]+=1
        if new_state=="review":result["still_review"]+=1;row["still_review"]+=1
        for job,suffix in ((old,"before"),(new,"after")):
            if not parse_date(job.get("published")):result["missing_date_"+suffix]+=1
            if detect_work_mode(job) is None:result["unknown_mode_"+suffix]+=1
            if geo_verdict(job,country)=="unknown":result["unknown_country_"+suffix]+=1
        if not parse_date(new.get("published")):row["missing_date"]+=1
        if detect_work_mode(new) is None:row["unknown_mode"]+=1
        if geo_verdict(new,country)=="unknown":row["unknown_country"]+=1
    return result


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
            metadata={"published":date if parse_date(date) else "",
                      "description":jd[:18000] if isinstance(jd,str) else ""}
            # Observed in the public job-details API (23 Oct 2026).
            # Keep structured evidence; never guess country or remote status.
            for field in ("workplaceType","workArrangement","remoteType","workMode",
                          "country","countryCode","countryName","city","state","region"):
                value=detail.get(field)
                if isinstance(value,str) and value.strip():metadata[field]=value[:200]
            location=detail.get("location")
            if isinstance(location,str) and location.strip():metadata["location"]=location[:200]
            elif isinstance(location,dict):
                for field in ("city","state","country","countryCode","countryName"):
                    value=location.get(field)
                    if isinstance(value,str) and value.strip():metadata[field]=value[:200]
                name=location.get("name") or location.get("label")
                if isinstance(name,str) and name.strip():metadata["location"]=name[:200]
            if isinstance(detail.get("isRemote"),bool):metadata["remote"]=detail["isRemote"]
            return i,metadata
        except Exception:
            return i,None
    with ThreadPoolExecutor(max_workers=8) as pool:
        for i,metadata in pool.map(fetch,selected):
            if metadata and any(value for value in metadata.values()):
                output[i]={**output[i],**{key:value for key,value in metadata.items() if value}}
                metrics["complete"]+=1
            else:
                metrics["failed"]+=1
    return output,metrics
