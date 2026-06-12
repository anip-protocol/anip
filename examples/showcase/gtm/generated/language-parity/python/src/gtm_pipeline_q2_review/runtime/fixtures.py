"""Fixture-backed GTM prioritization and outreach data."""
from __future__ import annotations


LEAD_COHORTS = {
    "inbound_last_week": [
        {"lead_id": "lead_1001", "account_name": "Acme Corporation", "source": "website_inbound", "segment": "enterprise", "owner_scope": "East", "priority_score": 94, "priority_band": "hot", "confidence": 0.94, "rationale": "High intent, enterprise ICP fit, and recent demo request.", "recommended_queue": "sales"},
        {"lead_id": "lead_1002", "account_name": "Codehow", "source": "website_inbound", "segment": "commercial", "owner_scope": "East", "priority_score": 91, "priority_band": "hot", "confidence": 0.91, "rationale": "Repeat product-page engagement and strong ICP fit.", "recommended_queue": "sales"},
        {"lead_id": "lead_1003", "account_name": "Condax", "source": "website_inbound", "segment": "enterprise", "owner_scope": "West", "priority_score": 88, "priority_band": "hot", "confidence": 0.89, "rationale": "High-value account with strong buying signals.", "recommended_queue": "sales"},
        {"lead_id": "lead_1004", "account_name": "Dalttechnology", "source": "website_inbound", "segment": "mid_market", "owner_scope": "Central", "priority_score": 84, "priority_band": "warm", "confidence": 0.86, "rationale": "Good engagement and healthy ICP alignment.", "recommended_queue": "sdr"},
    ],
    "webinar_q2": [
        {"lead_id": "lead_2001", "account_name": "Finjob", "source": "webinar", "segment": "enterprise", "owner_scope": "East", "priority_score": 89, "priority_band": "hot", "confidence": 0.9, "rationale": "Executive webinar attendance and requested follow-up.", "recommended_queue": "sales"},
        {"lead_id": "lead_2002", "account_name": "J-Texon", "source": "webinar", "segment": "commercial", "owner_scope": "West", "priority_score": 81, "priority_band": "warm", "confidence": 0.83, "rationale": "Good engagement but smaller likely deal size.", "recommended_queue": "sdr"},
        {"lead_id": "lead_2003", "account_name": "Konex", "source": "webinar", "segment": "mid_market", "owner_scope": "West", "priority_score": 78, "priority_band": "warm", "confidence": 0.8, "rationale": "Moderate engagement and reasonable ICP fit.", "recommended_queue": "sdr"},
    ],
}

ACCOUNT_COHORTS = {
    "expansion_candidates_q2": [
        {"account_name": "Acme Corporation", "segment": "enterprise", "owner_scope": "East", "priority_score": 96, "priority_band": "hot", "confidence": 0.95, "rationale": "Expansion candidate with strong usage and open pipeline.", "ranking_basis": "deal_likelihood"},
        {"account_name": "Codehow", "segment": "commercial", "owner_scope": "East", "priority_score": 90, "priority_band": "hot", "confidence": 0.9, "rationale": "Strong engagement and expansion-ready signals.", "ranking_basis": "deal_likelihood"},
        {"account_name": "Condax", "segment": "enterprise", "owner_scope": "West", "priority_score": 86, "priority_band": "warm", "confidence": 0.87, "rationale": "Good propensity but longer procurement cycle.", "ranking_basis": "deal_likelihood"},
    ],
    "at_risk_q2": [
        {"account_name": "Acme Corporation", "segment": "enterprise", "owner_scope": "Central", "priority_score": 91, "priority_band": "hot", "confidence": 0.9, "rationale": "Highest risk-adjusted retention opportunity with clear recovery path.", "ranking_basis": "deal_likelihood"},
        {"account_name": "J-Texon", "segment": "commercial", "owner_scope": "West", "priority_score": 88, "priority_band": "hot", "confidence": 0.88, "rationale": "High urgency because the account is at risk and near renewal.", "ranking_basis": "deal_likelihood"},
        {"account_name": "Finjob", "segment": "enterprise", "owner_scope": "East", "priority_score": 84, "priority_band": "warm", "confidence": 0.85, "rationale": "Meaningful renewal risk but reachable in current quarter.", "ranking_basis": "deal_likelihood"},
    ],
}

OUTREACH_TARGETS = {
    "Condax": {"industry": "industrial manufacturing", "persona": "VP of Operations", "region": "East", "priority_context": "high-priority expansion candidate", "pain_point": "fragmented forecasting and slow handoff between revenue teams", "proof_point": "governed pipeline review with approval-aware follow-up planning", "next_step": "a short operations-focused discovery call"},
    "Acme Corporation": {"industry": "industrial equipment", "persona": "Revenue Operations Director", "region": "Central", "priority_context": "at-risk account needing tighter GTM coordination", "pain_point": "stalled opportunities and uneven rep follow-through", "proof_point": "bounded risk reviews and explainable next-best actions", "next_step": "a practical walkthrough of its stalled-opportunity posture"},
    "Codehow": {"industry": "software and digital services", "persona": "Head of GTM Systems", "region": "East", "priority_context": "high-fit target for follow-up acceleration", "pain_point": "manual scoring and inconsistent routing decisions", "proof_point": "governed scoring and approval-gated routing previews", "next_step": "a systems-focused follow-up conversation"},
}

OBJECTION_THEMES = {
    "pricing": {
        "label": "pricing",
        "variants": [
            {"variant_id": "pricing_v1", "message": "Frame the conversation around pipeline waste reduction before discussing pricing.", "rationale": "Keeps the conversation on measurable operating value."},
            {"variant_id": "pricing_v2", "message": "Offer a bounded pilot focused on one GTM workflow instead of a broad rollout.", "rationale": "Reduces perceived risk and keeps scope concrete."},
        ],
    },
    "competitor": {
        "label": "competitor comparison",
        "variants": [
            {"variant_id": "competitor_v1", "message": "Position governed service boundaries and auditability as the differentiator.", "rationale": "Shifts the comparison away from feature checklists toward control and trust."},
            {"variant_id": "competitor_v2", "message": "Use the multi-service proof to show predictable composition rather than one opaque agent.", "rationale": "Shows operational realism instead of generic autonomy claims."},
        ],
    },
    "implementation_risk": {
        "label": "implementation risk",
        "variants": [
            {"variant_id": "implementation_v1", "message": "Anchor on ANIP in front of existing systems so the buyer does not need a full rebuild.", "rationale": "Directly reduces perceived migration cost."},
            {"variant_id": "implementation_v2", "message": "Use Phase 1 through Phase 4 proof points to show incremental rollout instead of a big-bang launch.", "rationale": "Demonstrates controlled adoption."},
        ],
    },
}
