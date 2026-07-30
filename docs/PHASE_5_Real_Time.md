\# Phase 5 — Real-Time Transport



\## Objective



Replace polling with real-time updates.



\---



\## Current



15-second polling.



\---



\## Target



WebSocket



Fallback



Polling



\---



\## Technical Goals



Push only changed data.



Avoid



\- full JSON reload

\- full map redraw

\- full vehicle list rebuild



Reuse markers.



Update only changed vehicles.



\---



\## Acceptance



Vehicle movement appears live.



Bandwidth reduced.



No visible UI refresh.



Polling remains as fallback.

