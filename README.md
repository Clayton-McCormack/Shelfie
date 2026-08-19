# Shelfie

Shelfie turns a bookshelf photo into a personal library. The Expo client uploads a photo to Django, a local CPU model finds candidate book regions, Gemini reads title/author text from numbered crops, and a local matcher resolves each read against a deliberately messy catalog. Uncertain results are routed to human review.

## Run locally

Commands below are for Windows PowerShell from the repository root.

```powershell
py -3.12 -m venv backend\venv
backend\venv\Scripts\python.exe -m pip install -r backend\requirements.txt
backend\venv\Scripts\python.exe backend\manage.py migrate
backend\venv\Scripts\python.exe backend\manage.py runserver 0.0.0.0:8000
```

In a second PowerShell window:

```powershell
Set-Location mobile
npm install
npx expo start -c
```

Open the QR code with Expo Go while the phone and laptop are on the same Wi-Fi network. The app derives the laptop address from Expo's development URL and uses port 8000 for Django, so no LAN IP is hard-coded.

### Providers

The default fake provider needs no credentials and keeps the app runnable offline. To use real Gemini reads, copy the template and edit the ignored local file:

```powershell
Copy-Item backend\.env.example backend\.env
notepad backend\.env
```

```text
VISION_PROVIDER=gemini
GEMINI_API_KEY=your-google-ai-studio-key
GEMINI_MODEL=gemini-3.1-flash-lite
```

Restart Django after changing `.env`. Never commit `backend\.env`.

Run matcher tests with:

```powershell
Set-Location backend
.\venv\Scripts\python.exe -m pytest -q
```

## Architecture

```text
Expo photo -> Django API
                 |
                 +-> local YOLOv8n on CPU (COCO book class)
                 |      -> OpenCV vertical-edge fallback
                 |
                 +-> numbered contact sheets (up to 8 crops each)
                 |      -> Gemini hosted VLM -> validated JSON reads
                 |
                 -> local catalog matcher -> auto add / review / unmatched
                                                |
                                                -> SQLite library
```

The local stage handles geometry: it finds plausible book regions without network cost and avoids sending a full shelf photo to the hosted model. YOLOv8n is filtered to the COCO `book` class; when it returns fewer than two regions, a classical OpenCV vertical-edge fallback runs. Both zero detections and local model failures produce usable responses.

The hosted stage handles the semantic visual task: reading noisy title and author text. Shelfie sends numbered contact sheets rather than making one request per spine. Gemini is constrained to JSON keyed by crop number; Pydantic validates that response before matching. Missing credentials, timeout, HTTP errors, and malformed provider data are shown as a provider-unavailable state rather than crashing the app.

Analysis currently runs inline and returns `200`. A background job with `202` and polling is deliberately left as production follow-up work.

## Catalog and matching

`catalog.csv` contains 150 curated rows with:

```text
id,title,alt_titles,author,author_variants,year,edition,series,volume_of,notes
```

The catalog was seeded with AI assistance, then deliberately structured around common books and the required ambiguity cases: multiple editions, US/UK title changes, same-title different books, omnibuses alongside volumes, title-substring traps, accents, initials, and `Lastname, Firstname` author forms. Exact string matching would fail by design.

The matcher normalizes punctuation, case, diacritics, articles, and author variants, then scores every catalog row. Title similarity is 75% of the score and author similarity 25%; a strong author can modestly rescue a damaged title read. Alternate-title matches and strict title containment receive penalties.

The important confidence signal is the margin between first and second place. A score of 0.90 is not trusted if the runner-up is 0.89: the read is ambiguous, so it goes to review.

| Outcome | Rule | Behaviour |
|---|---|---|
| Automatic | confidence >= 0.85 | Persist the catalog book in SQLite |
| Review | plausible, below automatic threshold | User confirms, corrects, or discards |
| Unmatched | best score < 0.45 | Read remains visible; it is never silently added |

This is intentionally conservative: an unnecessary review tap is cheaper than silently corrupting a library.

## Key decisions and tradeoffs

- **YOLOv8n plus OpenCV fallback:** both run locally on CPU, keeping geometric detection private and free per image. The tradeoff is imperfect detection on dense, angled, or occluded spines because YOLO's COCO `book` class is not a spine-specific model.
- **Gemini 3.1 Flash-Lite for hosted reading:** it accepts image input, supports schema-constrained JSON, and produced a low paid-tier cost estimate. The tradeoff is external API latency and a dependency on a configured key.
- **Eight-crop contact sheets:** batching prevents an API call per spine and reduces request overhead. The tradeoff is that several crops wait on the same hosted request.
- **Conservative confidence thresholds:** the title/author score and best-versus-runner-up margin prefer review over a wrong automatic library addition. The tradeoff is more user taps for ambiguous books.
- **Inline analysis and no upload cache:** these were consciously deferred to keep the submitted slice small and reliable. A production follow-up would use persisted jobs with polling and SHA-256 idempotency for repeated uploads.

## Measured latency and cost

Measurements used the fixed shelf photos in `test_photos/`, local CPU YOLOv8n, Django's development server, and Gemini 3.1 Flash-Lite. Each row is one real end-to-end request; hardware, image content, and hosted-service latency will vary.

| Image | Regions / reads | Batches | Local detection | Hosted reading | Matching | Total |
|---|---:|---:|---:|---:|---:|---:|
| aneta-pawlik | 20 / 20 | 3 | 3.11s | 15.53s | 0.07s | 18.71s |
| pexels-ambam | 19 / 19 | 3 | 0.48s | 8.92s | 0.04s | 9.46s |
| pexels-mehmet | 12 / 12 | 2 | 0.62s | 16.38s | 0.02s | 17.02s |
| pexels-melalaka | 14 / 14 | 2 | 0.25s | 9.05s | 0.02s | 9.32s |
| **Average** | **16.25 / 16.25** | **2.5** | **1.12s** | **12.47s** | **0.03s** | **13.63s** |

Hosted reading dominates latency. The local exhaustive 150-row matching pass is effectively negligible, supporting a simple, inspectable scoring algorithm rather than a more complex retrieval system.

Gemini reports token counts for each analysis. On `pexels-melalaka`, 2,335 input tokens and 568 output tokens produced an estimated paid-tier cost of **$0.001436 per image** (about 0.14 cents), using configured Gemini 3.1 Flash-Lite rates of $0.25/million input tokens and $1.50/million output tokens. Development used the free tier; this is a reproducible paid-tier estimate, not a charge observed during testing.

## Failure behaviour

- Missing or non-image uploads return a clear client error.
- Local model/image decoding failures surface a visible detection failure state.
- Zero regions returns an empty usable result.
- Gemini timeout, HTTP failure, missing key, or malformed JSON surface a visible provider failure state.
- The fake provider allows app and test runs without a network connection or key.

## Known limitations

- YOLO's general COCO `book` class is not a dedicated book-spine detector, so narrow, angled, occluded, or dense shelves can be under-detected.
- The 150-row catalog is intentionally limited; books outside it should route to review/unmatched rather than be falsely matched.
- Upload SHA-256 idempotency/caching is not implemented, so a re-upload repeats model work.
- SQLite and Django's development server are exercise-only choices, not deployment infrastructure.

## Test photos

The fixed development and measurement images live in `test_photos/`; see `test_photos/README.md` for the source note. Runtime uploads and generated crops live under `backend/media/` and are ignored by Git.
