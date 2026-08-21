# Recovery Copilot

An agentic system that decides what to do with a failed payment — retry it, cascade it to a different payment method, or hand it off to compliant customer outreach — instead of the industry-default fixed-schedule retry.

## Why

Indian businesses on Razorpay see 8–15% payment failure rates. Most of that is recoverable: expired cards alone cause 42% of subscription failures, and full-stack smart recovery reaches 65–75% recovery vs. 30–45% industry median for naive retry logic. This project builds that smart layer.

## Architecture

Failed payment → Classifier Agent (decline code → category) → Strategy Agent (retry / cascade / circuit-break / drop) → Dunning Agent (compliant customer outreach) → logged decision trace.

Deterministic rules handle most decisions. The LLM is only called for ambiguous decline codes and message drafting.

## Status

Work in progress — built for the Razorpay AI Buildathon (Revenue Recovery track).

## Setup

    python -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt

## Project layout

    src/taxonomy/    decline code lookup
    src/simulator/   synthetic transaction generator + baseline
    src/agents/      classifier, strategy, dunning agents
    src/dashboard/   streamlit demo
    tests/           pytest tests