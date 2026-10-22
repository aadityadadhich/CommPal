from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from backend.app.contracts.items import ItemSpec, FulfilmentClass
from backend.app.contracts.orders import Offer, DecisionScoreBreakdown, UrgencyClass, Decision
from backend.app.contracts.mandate import MandateBody

URGENCY_WEIGHTS = {
    "URGENT": {"price": 0.15, "eta": 0.55, "rating": 0.10, "fit": 0.20},
    "ROUTINE": {"price": 0.25, "eta": 0.40, "rating": 0.15, "fit": 0.20},
    "PLANNED": {"price": 0.55, "eta": 0.10, "rating": 0.15, "fit": 0.20},
}

def derive_urgency(
    needed_by: datetime,
    current_time: datetime,
    stock_qty: float,
    user_said_urgent: bool = False,
    perishable: bool = False
) -> UrgencyClass:
    slack_seconds = (needed_by - current_time).total_seconds()
    slack_hours = slack_seconds / 3600.0

    if user_said_urgent or stock_qty <= 0 or slack_hours < 2.0:
        return "URGENT"
    elif slack_hours <= 48.0 or perishable:
        return "ROUTINE"
    else:
        return "PLANNED"

def apply_hard_filters(
    offers: List[Offer],
    qty: float,
    needed_by: datetime,
    current_time: datetime,
    spec: ItemSpec,
    perishable: bool,
    fulfilment_class: FulfilmentClass,
    mandate: MandateBody
) -> Tuple[List[Offer], Dict[str, str]]:
    valid_offers: List[Offer] = []
    filtered_out: Dict[str, str] = {}

    for off in offers:
        m_id = off.merchant_id
        # 1. Stock check
        if off.stock_qty < qty:
            filtered_out[m_id] = f"Insufficient stock: requested {qty}, available {off.stock_qty}."
            continue

        # 2. Mandate allowlist & blocklist
        if m_id in mandate.merchants.block:
            filtered_out[m_id] = f"Merchant '{off.merchant_name}' is blocked by spending mandate."
            continue
        if mandate.merchants.allow and m_id not in mandate.merchants.allow:
            filtered_out[m_id] = f"Merchant '{off.merchant_name}' is not in mandate allowlist."
            continue

        # 3. Minimum rating
        if off.rating < spec.min_rating:
            filtered_out[m_id] = f"Rating {off.rating} below required minimum {spec.min_rating}."
            continue

        # 4. Arrival time check
        arrival_time = current_time + timedelta(minutes=off.eta_minutes)
        if arrival_time > needed_by:
            late_hours = (arrival_time - needed_by).total_seconds() / 3600.0
            filtered_out[m_id] = f"Arrival ({off.eta_minutes} mins) exceeds deadline by {late_hours:.1f} hours."
            continue

        # 5. Fulfilment class / perishability check
        if perishable and fulfilment_class == "quick" and off.eta_minutes > 120:
            filtered_out[m_id] = f"Perishable item requires quick delivery (<2h); merchant ETA is {off.eta_minutes} mins."
            continue

        # 6. Brand requirement check
        if spec.required_brand and spec.brand_pref:
            if spec.brand_pref.lower() not in off.brand.lower() and spec.brand_pref.lower() not in off.title.lower():
                filtered_out[m_id] = f"Brand mismatch: requested '{spec.brand_pref}', merchant offers '{off.brand}'."
                continue

        valid_offers.append(off)

    return valid_offers, filtered_out

def score_and_rank_offers(
    offers: List[Offer],
    urgency: UrgencyClass,
    spec: ItemSpec
) -> Tuple[Optional[Offer], Optional[Offer], List[DecisionScoreBreakdown], Dict[str, float]]:
    if not offers:
        return None, None, [], URGENCY_WEIGHTS[urgency]

    weights = URGENCY_WEIGHTS[urgency]
    min_price = min(o.landed_price for o in offers)
    max_price = max(o.landed_price for o in offers)
    min_eta = min(o.eta_minutes for o in offers)
    max_eta = max(o.eta_minutes for o in offers)

    scored_list = []
    breakdowns = []

    for o in offers:
        # Price score (lower price -> higher score)
        if max_price == min_price:
            price_score = 1.0
        else:
            price_score = 1.0 - (o.landed_price - min_price) / (max_price - min_price)

        # ETA score (faster -> higher score)
        if max_eta == min_eta:
            eta_score = 1.0
        else:
            eta_score = 1.0 - (o.eta_minutes - min_eta) / (max_eta - min_eta)

        # Rating score normalized from [3.5, 5.0] to [0.0, 1.0]
        rating_score = max(0.0, min(1.0, (o.rating - 3.5) / 1.5))

        # Fit score
        spec_match = 1.0
        if spec.brand_pref and spec.brand_pref.lower() in o.brand.lower():
            spec_match = 1.0
        elif spec.brand_pref:
            spec_match = 0.5
        fit_score = 0.6 * spec_match + 0.4 * o.reliability

        total_score = (
            weights["price"] * price_score +
            weights["eta"] * eta_score +
            weights["rating"] * rating_score +
            weights["fit"] * fit_score
        )

        breakdown = DecisionScoreBreakdown(
            offer_id=o.id,
            merchant_id=o.merchant_id,
            price_score=round(price_score, 4),
            eta_score=round(eta_score, 4),
            rating_score=round(rating_score, 4),
            fit_score=round(fit_score, 4),
            total_score=round(total_score, 4)
        )
        breakdowns.append(breakdown)
        scored_list.append((total_score, -o.landed_price, o.reliability, o))

    # Sort descending by: total_score, then lower landed_price (-price), then reliability
    scored_list.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    chosen = scored_list[0][3]
    runner_up = scored_list[1][3] if len(scored_list) > 1 else None

    return chosen, runner_up, breakdowns, weights

def generate_decision_explanation(
    chosen: Offer,
    runner_up: Optional[Offer],
    urgency: UrgencyClass,
    filtered_out: Dict[str, str]
) -> str:
    eta_str = f"{chosen.eta_minutes} mins" if chosen.eta_minutes < 60 else f"{chosen.eta_minutes // 60} hours"
    
    if runner_up:
        price_diff = chosen.landed_price - runner_up.landed_price
        runner_eta = f"{runner_up.eta_minutes} mins" if runner_up.eta_minutes < 60 else f"{runner_up.eta_minutes // 60} hours"
        
        if urgency == "URGENT":
            explanation = (
                f"Selected {chosen.merchant_name} ($ {chosen.landed_price:.2f}, arriving in {eta_str}) because the need is urgent. "
                f"Runner-up {runner_up.merchant_name} is ${abs(price_diff):.2f} "
                f"{'cheaper' if price_diff > 0 else 'more expensive'}, but arrives in {runner_eta}."
            )
        elif urgency == "PLANNED":
            explanation = (
                f"Selected {chosen.merchant_name} ($ {chosen.landed_price:.2f}) because it offers the lowest landed price for planned restocking. "
                f"Runner-up {runner_up.merchant_name} is ${abs(price_diff):.2f} more expensive."
            )
        else: # ROUTINE
            explanation = (
                f"Selected {chosen.merchant_name} ($ {chosen.landed_price:.2f}, ETA {eta_str}) for the best balanced price and delivery schedule. "
                f"Runner-up {runner_up.merchant_name} quoted ${runner_up.landed_price:.2f}."
            )
    else:
        explanation = (
            f"Selected {chosen.merchant_name} ($ {chosen.landed_price:.2f}, ETA {eta_str}) as the sole qualifying offer meeting stock and delivery requirements."
        )

    if filtered_out:
        reasons_summary = ", ".join(f"{m}: {r}" for m, r in list(filtered_out.items())[:2])
        explanation += f" (Excluded: {reasons_summary})"

    return explanation
