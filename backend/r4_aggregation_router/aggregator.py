import asyncio
import uuid
from typing import List, Dict, Optional, Tuple
from datetime import datetime

from backend.app.contracts.items import ItemSpec, FulfilmentClass
from backend.app.contracts.orders import Offer, Decision
from backend.app.contracts.mandate import MandateBody
from backend.r4_aggregation_router.adapters import MERCHANTS
from backend.r4_aggregation_router.scoring import (
    derive_urgency,
    apply_hard_filters,
    score_and_rank_offers,
    generate_decision_explanation
)
from backend.app.scheduler.virtual_clock import clock

class RouterAggregator:
    def __init__(self, timeout_seconds: float = 2.0):
        self.timeout_seconds = timeout_seconds

    async def query_all_merchants(self, query: str, spec: ItemSpec, qty: float) -> Tuple[List[Offer], Dict[str, str]]:
        tasks = []
        merchant_ids = list(MERCHANTS.keys())

        for m_id in merchant_ids:
            adapter = MERCHANTS[m_id]
            tasks.append(
                asyncio.wait_for(
                    adapter.search(query=query, spec=spec, qty=qty),
                    timeout=self.timeout_seconds
                )
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_offers: List[Offer] = []
        errors: Dict[str, str] = {}

        for m_id, res in zip(merchant_ids, results):
            if isinstance(res, asyncio.TimeoutError):
                errors[m_id] = f"Timeout: Merchant did not respond within {self.timeout_seconds}s."
            elif isinstance(res, Exception):
                errors[m_id] = f"Error: {str(res)}"
            elif isinstance(res, list):
                all_offers.extend(res)

        return all_offers, errors

    async def find_and_decide(
        self,
        intent_id: str,
        query: str,
        qty: float,
        needed_by: datetime,
        spec: ItemSpec,
        stock_qty: float,
        perishable: bool,
        fulfilment_class: FulfilmentClass,
        mandate: MandateBody,
        user_said_urgent: bool = False
    ) -> Tuple[Optional[Decision], List[Offer], Dict[str, str]]:
        now = clock.now()
        urgency = derive_urgency(
            needed_by=needed_by,
            current_time=now,
            stock_qty=stock_qty,
            user_said_urgent=user_said_urgent,
            perishable=perishable
        )

        all_offers, merchant_errors = await self.query_all_merchants(query=query, spec=spec, qty=qty)

        for off in all_offers:
            off.intent_id = intent_id

        filtered_offers, filter_reasons = apply_hard_filters(
            offers=all_offers,
            qty=qty,
            needed_by=needed_by,
            current_time=now,
            spec=spec,
            perishable=perishable,
            fulfilment_class=fulfilment_class,
            mandate=mandate
        )

        all_filtered = {**filter_reasons, **merchant_errors}
        if not filtered_offers:
            return None, all_offers, all_filtered

        chosen, runner_up, breakdowns, weights = score_and_rank_offers(
            offers=filtered_offers,
            urgency=urgency,
            spec=spec
        )

        if not chosen:
            return None, all_offers, all_filtered

        explanation = generate_decision_explanation(
            chosen=chosen,
            runner_up=runner_up,
            urgency=urgency,
            filtered_out=all_filtered
        )

        decision = Decision(
            id=f"dec-{uuid.uuid4().hex[:8]}",
            intent_id=intent_id,
            chosen_offer=chosen,
            runner_up_offer=runner_up,
            urgency_class=urgency,
            weights=weights,
            score_breakdown=breakdowns,
            filtered_out=all_filtered,
            explanation=explanation,
            created_at=now.isoformat()
        )

        return decision, all_offers, all_filtered

router_aggregator = RouterAggregator()
