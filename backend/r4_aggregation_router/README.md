# Role 4: Aggregation & Router Engineer (R4)
**Scope:** Merchant adapter protocol, mock merchant implementations (Quick10, ZipBasket, CornerStore, MegaMart, BulkBarn), mock catalogs with seeded pricing, chaos flags (out-of-stock, price spikes, merchant down), urgency-aware router scoring (`slack = needed_by - now`), and runner-up explanations.  
**Ownership Boundary (SRDD 7.2):** The router never talks to the wallet or money services. It evaluates candidate offers strictly on price, delivery time (ETA), ratings, and fit.
