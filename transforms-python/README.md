WBDG UFC PDF Scraper – Python Transform for Palantir Foundry

Repository: repo://transforms-python
Primary transform file: src/myproject/datasets/wbdg_scraper.py

1  Purpose

This repository contains a lightweight Python transform that crawls the Unified Facilities Criteria (UFC) catalogue on the Whole Building Design Guide website (https://www.wbdg.org/dod/ufc) and streams every publicly linked PDF into a Foundry Media Set for downstream OCR, text extraction, or archival access.  UFC documents govern DoD‑wide planning and engineering criteria and are only distributed in electronic form (wbdg.org).

Key features

External System – outbound HTTP calls are routed through a REST API Data Connection, making network egress explicit (palantir.com).

Media set output – each PDF is written as an individual media item, the recommended pattern for unstructured binaries in Foundry (palantir.com, palantir.com).

Lightweight profile – no Spark spin‑up; ideal for <10 k PDFs.

Crawl log table – every build writes a diagnostic log to a tabular dataset, simplifying monitoring and debugging.

2  Transform Logic (high‑level)

Seed URL – Starts at https://www.wbdg.org/dod/ufc.

Recursive crawl – Follows any link that remains under /dod/ufc; collects all anchors whose href ends in .pdf.

Streaming upload – Downloads each PDF through the External System’s HTTPS client and immediately calls MediaSetOutput.put_media_item() (palantir.com).

Version‑in‑place – If a filename already exists, Foundry versions the item transparently.

Crawl log – Success / error events are appended to wbdg_crawl_log (Spark table) for observability.

For full code with verbose comments, see wbdg_scraper.py.

3  Repository Structure

Path

Purpose

src/myproject/datasets/wbdg_scraper.py

Main transform (crawler + uploader)

src/myproject/datasets/__init__.py

Package marker

requirements.txt

Third‑party Python deps (requests, beautifulsoup4)

build.gradle

Gradle config for Python transforms & unit tests

README.md

This file

4  Getting Started

4.1  Open in Foundry

Navigate to Code Repositories → open transforms‑python repo.

Build once to create the media set (path named in the @transform decorator); second build populates PDFs.

4.2  Local Development (palantir.com)

Click the “Work locally” button (top‑right of the repo UI).  Foundry generates a Conda env and a local Gradle wrapper so you can iterate with autoreload.  Recommended workflow:

./gradlew :transforms-python:runLocally \
  --args "src/myproject/datasets/wbdg_scraper.py"

The runner honours your repo’s requirements.txt, giving parity with the remote build.

4.3  Unit Testing

Enable PyTest defaults by adding to build.gradle:

plugins {
  id("com.palantir.transforms.lang.pytest-defaults")
}

Then author tests under src/myproject/tests/ and run ./gradlew test.

4.4  Data Expectations

Add the transforms-expectations library from the left‑hand Library search panel and define expectations in a sibling .expectations.py file (palantir.com).

5  Input / Output Contracts

Name

Type

Description

wbdg_source

External System (REST API)

HTTPS connection to www.wbdg.org; controls credentials, egress policy, and export markings.

wbdg_pdfs

Media Set

One media item per UFC PDF (~3‑20 MB each).

crawl_log

Table

Build‑time log with stages crawl_error, crawl_complete, upload_ok, upload_error.

6  Operational Notes

Refresh cadence – schedule the transform daily; UFC updates are irregular (~monthly) (wbdg.org).

Downstream OCR – Use Foundry’s built‑in Text Extraction board for bulk OCR (palantir.com).

Error handling – Network errors are logged but non‑fatal; the crawler continues so partial harvests don’t fail the pipeline.

Egress policy – External System encapsulates domain whitelisting; no inline credential handling required (palantir.com).

7  Further Reading

Foundry Media Set docs (palantir.com)

Foundry External Systems guide (palantir.com)

Foundry Python transforms overview (palantir.com)

UFC master index (wbdg.org)

Example UFC PDF (Structural Engineering) (wbdg.org)

Palantir Transforms API reference (palantir.com)