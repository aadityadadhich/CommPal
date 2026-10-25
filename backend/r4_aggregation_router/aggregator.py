import os
from channel3_sdk import Channel3
from dotenv import load_dotenv
load_dotenv(dotenv_path="keys.env")

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
