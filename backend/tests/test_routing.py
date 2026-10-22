import pytest
from datetime import datetime, timezone, timedelta
from backend.app.contracts.items import ItemSpec
from backend.app.contracts.mandate import MandateBody
from backend.app.router.scoring import derive_urgency, score_and_rank_offers, apply_hard_filters
from backend.app.router.aggregator import router_aggregator
from backend.app.merchants.catalogs import reset_chaos
from backend.app.scheduler.virtual_clock import clock

@pytest.mark.asyncio
async def test_urgent_paper_selects_quick_commerce():
    reset_chaos()
    now = clock.now()
    # Needed in 30 minutes, stock = 0 -> URGENT
    needed_by = now + timedelta(minutes=30)
    spec = ItemSpec()
    mandate = MandateBody()

    decision, all_offers, filtered_out = await router_aggregator.find_and_decide(
        intent_id="intent-test-urgent",
        query="a4 paper",
        qty=1.0,
        needed_by=needed_by,
        spec=spec,
        stock_qty=0.0,
        perishable=False,
        fulfilment_class="any",
        mandate=mandate,
        user_said_urgent=True
    )

    assert decision is not None
    assert decision.urgency_class == "URGENT"
    # MegaMart takes >24 hours, so it must be filtered out by arrival time
    assert "megamart" in decision.filtered_out
    # Quick commerce (Quick10 or ZipBasket) must win
    assert decision.chosen_offer.merchant_id in ["quick10", "zipbasket"]

@pytest.mark.asyncio
async def test_planned_protein_selects_marketplace():
    reset_chaos()
    now = clock.now()
    # Needed in 10 days, stock = 5 -> PLANNED
    needed_by = now + timedelta(days=10)
    spec = ItemSpec()
    mandate = MandateBody()

    decision, all_offers, filtered_out = await router_aggregator.find_and_decide(
        intent_id="intent-test-planned",
        query="protein powder",
        qty=1.0,
        needed_by=needed_by,
        spec=spec,
        stock_qty=5.0,
        perishable=False,
        fulfilment_class="any",
        mandate=mandate,
        user_said_urgent=False
    )

    assert decision is not None
    assert decision.urgency_class == "PLANNED"
    # MegaMart offers lowest price ($34.99 vs $44.99) and arrives in 1 day, easily before 10 days
    assert decision.chosen_offer.merchant_id == "megamart"
