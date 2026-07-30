\# Phase 1 — Live Update Architecture



\## Objective



Replace disruptive refresh behavior with incremental updates.



\---



\## Current Problems



The Dispatch page refreshes every 15 seconds.



Problems:



\- page flickers

\- map reloads

\- scroll position resets

\- selected vehicle is lost

\- opened panels collapse

\- dispatcher loses focus



\---



\## Requirements



Preserve



\- selected vehicle

\- selected trip

\- selected stop

\- expanded panels

\- filters

\- search text

\- map zoom

\- map center

\- popup state

\- scroll position



Do NOT



\- redesign UI

\- change backend API

\- change database schema



\---



\## Technical Goals



Replace



Full refresh



with



Incremental synchronization.



Only update:



\- changed markers

\- changed cards

\- changed ETA values

\- changed status badges



Never recreate the entire page.



\---



\## Acceptance Criteria



✓ No visible page refresh



✓ Map never resets



✓ Vehicle selection survives refresh



✓ Scroll position survives refresh



✓ Existing API unchanged



✓ No regression

