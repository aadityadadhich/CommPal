# Role 5: Tech Lead & Backend Platform (R5)
**Scope:** Repository structure, FastAPI API routes, Pydantic shared contracts, database models and sessions, purchase pipeline orchestrator state machine (`DRAFT` -> `QUOTED` -> `DECIDED` -> `APPROVED` -> `AUTHORIZED` -> `PLACED` -> `CAPTURED`), inventory depletion tracking, virtual demo clock, and background tick worker.  
**Ownership Boundary (SRDD 7.2):** The orchestrator is the only coordinator that calls both the mandate engine (R2) and the wallet (R1), strictly enforcing the 3-phase execution order.
