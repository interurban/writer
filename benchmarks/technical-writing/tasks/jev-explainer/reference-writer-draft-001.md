# Reference: pre-fix harness output (regression fixture, do not edit)

Observed Writer output for the `jev-explainer` brief before the
editorial-framing capability existed: technically dense, fully sourced
(5 primary sources, 6 verified claims), but editorially flat — no
one-sentence thesis, inventory structure, forgettable opening.

Use: regression-test that reframed output preserves every technical
fact below while beating this text on the `framing` criterion.

---

Jev is TypeSafe AI's "System One" model: a model built to turn natural-language context into constrained decisions rather than generate prose. Treat it less like a chatbot and more like a probabilistic function at an application boundary.

A request contains state—a string, JSON object, or array of text—and one or more typed questions. Choice selects among named options. Score places the state on developer-defined ordered levels. Noul answers a yes/no proposition with a probability. Choice and Score also return probability distributions and a derived confidence value. Questions in one request see the same state, but Jev evaluates them independently and in parallel.

That interface changes the architecture. Instead of asking an LLM to "analyze this ticket and decide what to do," ask atomic questions: which queue fits, whether the message requests a refund, and how severe the issue is. Combine those results with policy, permissions, thresholds, and deterministic checks in code. The model supplies judgment; your program retains control.

This fits routing, classification, reranking, guardrails, rubric scoring, and fast paths in agent loops. It is not a replacement for a reasoning model when a task needs planning, explanation, code generation, or multi-step inference. Jev currently accepts text, not images or audio, and closed answer spaces can hide a bad taxonomy unless you include "other" or an escalation path.

The probabilities are operational signals, not guarantees. Calibrate thresholds on representative data and by consequence: an uncertain documentation tag may be harmless; an uncertain refund authorization should go to review. Pin a version if behavior stability matters, because the `jev-latest` alias can move.

The pattern is simple: structure the relevant state, ask narrow questions, inspect distributions, and make the final decision in code. Jev's value is not that it thinks for the application; it makes semantic judgment behave like an inspectable API.
