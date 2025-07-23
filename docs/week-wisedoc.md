
5. **Choose Hosting**  
- Option A: AWS Lambda + Container (via Zappa or Serverless Django)  
- Option B: EC2 t3.micro + RDS (Free-Tier)  
- Record decision; provision any free-tier resources

---

## Week 2 (Jul 30 – Aug 5, 2025): Scraper Prototype

1. **DRF View Stub**  
- Create `JobsAPIView` in `jobs/views.py`  
- Accept `request.query_params` for input

2. **Puppeteer & Chromium Layer**  
- Add `puppeteer-core` + `chrome-aws-lambda` to `requirements.txt`  
- Embed launch code in `get()` method  
- Return raw HTML in DRF `Response`

3. **Proxy Rotation**  
- Read `PROXY_POOL_URL`, `PROXY_USER`, `PROXY_PASS` from `settings.py`  
- Inject proxy args into `puppeteer.launch()`

4. **Local Testing**  
- Run via Django dev server; verify HTML fetch for sample keywords  
- Add basic unit test with saved HTML fixture

---

## Week 3 (Aug 6 – Aug 12, 2025): Parsing, Caching & Errors

1. **HTML Parsing**  
- In `views.py`, parse job cards using BeautifulSoup or lxml  
- Extract title, company, location, date, snippet, URL

2. **In-Memory Cache**  
- Use Django’s cache framework (e.g., LocMemCache) with 10 min TTL  
- Key: full query string

3. **Error Handling**  
- Catch navigation or parse exceptions  
- Return `502 Bad Gateway` on failures

4. **Tests**  
- Add tests for parsing logic and cache behavior

---

## Week 4 (Aug 13 – Aug 19, 2025): Deployment & CI/CD

1. **Containerization**  
- Write `Dockerfile` including Python, Chromium, and app code  
- Expose `CMD ["gunicorn", "project.wsgi"]`

2. **CI Pipeline**  
- Add GitHub Actions workflow: lint → test → build container

3. **Deploy to AWS Lambda**  
- Use Zappa or AWS SAM to deploy container to Lambda  
- Configure memory (1024 MB), timeout (30 s), env vars

4. **Health-Check Endpoint**  
- Add `GET /api/health/` returning `{"status":"ok"}`

---

## Week 5 (Aug 20 – Aug 26, 2025): RapidAPI & Documentation

1. **RapidAPI Listing**  
- Create API on RapidAPI Hub  
- Define `/jobs` endpoint, params, response schema

2. **Usage Plans**  
- Free: 200 calls/mo  
- Pro: 10 000 calls/mo @ $29  
- Business: 100 000 calls/mo @ $149

3. **Developer Docs**  
- Update `README.md` with curl examples  
- Publish Postman collection

4. **SDK Stub**  
- Provide minimal JavaScript or Python example code

---

## Week 6 (Aug 27 – Sep 2, 2025): Testing & Monitoring

1. **Beta Test**  
- Invite 5 users to try API; collect feedback

2. **Monitoring**  
- Integrate Sentry for error alerts  
- Set up UptimeRobot ping for health-check

3. **Adjust Quotas & Cache**  
- Based on feedback, tweak TTL and rate limits

---

## Week 7 (Sep 3 – Sep 9, 2025): Launch & Marketing

1. **Public Launch**  
- Announce on RapidAPI  
- Post Dev.to article: “How I built a LinkedIn Job API in a weekend”

2. **Community Engagement**  
- Share on Hacker News, Reddit r/SaaS  
- Answer Stack Overflow questions

3. **Social Media**  
- Tweet changelog and usage tips

---

## Week 8 (Sep 10 – Sep 16, 2025): Iterate & Upsell

1. **Analytics Review**  
- Monitor call volumes, error rates, churn

2. **Premium Features**  
- Add bulk job-fetch endpoint (`POST /jobs/bulk`)

3. **Second Niche**  
- Plan next micro-API based on this playbook

---

_End of Roadmap_  
