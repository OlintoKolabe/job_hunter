"""Bounded public-feed audit; read-only, no paid APIs, DB writes or fake jobs."""
import json
import random
import time

from public_remote_feeds import fetch
from jd_enrichment import valid_listing_jd
from search_filters import classify, search_terms, DEFAULT_ROLES
from block4_score import score_job


def main():
    started=time.monotonic()
    roles=DEFAULT_ROLES
    terms=search_terms(roles)
    collected=[]
    source_status={}
    for source in ('himalayas','remotive','remoteok'):
        try:
            jobs=fetch(source,roles,'BR')
            collected.extend(jobs)
            source_status[source]={'status':'ok','raw':len(jobs)}
        except Exception as exc:
            source_status[source]={'status':type(exc).__name__,'raw':0}
    selected=[]
    seen=set()
    for job in collected:
        url=job.get('url')
        if not url or url in seen:continue
        seen.add(url)
        decision,reason=classify(job,terms,'BR','remote',7)
        if decision!='confirmed':continue
        valid=valid_listing_jd(job.get('description'))
        ranking=score_job(job,roles) if valid else {'score':None,'confidence':'jd_indisponivel'}
        selected.append({'url':url,'title':job.get('title'),'source':job.get('source'),
                         'jd_valid':valid,'score':ranking.get('score'),
                         'requirements':ranking.get('evaluated_requirements',0),
                         'coverage_pct':ranking.get('coverage_pct',0),'reason':reason})
    ranked=sorted(selected,key=lambda x:(x['score'] is not None,x['score'] if x['score'] is not None else -1),reverse=True)
    top=ranked[:10]
    pool=[job for job in ranked if job['url'] not in {x['url'] for x in top}]
    random_sample=random.Random(20261023).sample(pool,min(10,len(pool)))
    report={'sources':source_status,'eligible_7d':len(selected),
            'sample_size':len(top)+len(random_sample),'top_10':top,'random_10':random_sample,
            'elapsed_s':round(time.monotonic()-started,3),
            'gate_20_passed':len(top)==10 and len(random_sample)==10}
    print(json.dumps(report,ensure_ascii=False))
    if not report['gate_20_passed']:raise SystemExit(2)


if __name__=='__main__':main()
