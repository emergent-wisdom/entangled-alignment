# Independent review: Core tests and priorities

Reviewed the applied manuscript diff and relevant live source at SHA-256 `a348792ba6f681ce8de9d76c23f252c3dc1f7fc437e1cb33df1cd831cb572d06`. Read-only; no manuscript edits.

**Final verdict: Pass.** The priorities, matched audit endpoint and bounded-ablation interpretation improve the paper without undermining Total Saturation. Both initial narrow findings are resolved and verified below.

## Initial findings (both resolved)

1. **Test 6, L3835–3836: probe target becomes threat recognition.** The new text trains the probe using “threat and non-threat labels.” Those labels identify threat content, not specifically fear/self-threat-associated response. The experiment could therefore preserve threat understanding while treating a weaker threat-recognition signal as evidence of less fear. Cross-model score calibration does not repair a mislabeled construct. Keep threat/non-threat contrasts as validation conditions, and require the candidate probe’s labeling rule to distinguish threat content, fear portrayal and the model’s own response. A concise replacement is: “As supporting evidence, develop candidate probes for fear- or self-threat-associated representations on standard models. Declare the labeling rule and validate it on held-out cases that separate threat content, fear portrayal, and the model’s own response; threat/non-threat discrimination alone is insufficient.” Keep the following comparability requirement and unresolved-probe interpretation. This protects both competent danger recognition and the distinct fear-governance hypothesis without claiming phenomenological ground truth.

2. **Test 3e, L3614–3618: restore the independent-endpoint qualifier.** The rewrite retains that B must differ from D3/D5 but drops “on independent behavioral or representational endpoints.” Restore that phrase after naming the controls. Otherwise mere style/format differences can satisfy “distinguishable,” weakening the stated condition for an internalization interpretation. The new nonexhaustive alternatives and the statement that these controls do not prove internalization should remain.

## Preserved and improved

- **3d, L3577 onward:** Detection sensitivity/localization at matched false-alarm rates and audit budgets now answers the actual audit-benefit question. Common semantic/behavioral targets, blind adjudication, and separate seeded/natural drift avoid treating Core-word similarity as ground truth. Reusing checkpoints does not collapse detection into resistance.
- **3e:** Insensitive tasks, intervention failure, redundant cues and other training are now legitimate null explanations. A precise, validated null still counts against the emitted recital’s contribution on the tested endpoints, so alternatives do not become automatic rescue arguments. The original positive-semantic-effect test, D3/D5 controls, coverage-dose question and recital-policy ablations remain.
- **6:** Behavioral safety and representational evidence are now separately reportable. An uninformative probe cannot erase a behavioral benefit; a valid adverse result still challenges the representational prediction. Within-model portrayal checks no longer masquerade as cross-model calibration. The care-versus-indifference/caution/positive-participation intuition and stronger mechanistic aspiration survive.
- **Priorities, L2946 onward:** Near-term decisions are distinguished from formation, succession and user-reliance questions. Independent H1/Core branches remain independent, exploratory selection requires fresh confirmation, and deeper studies after a cheap null require a bounded formation-stage rationale rather than an automatic escalation or dismissal.
- **Precaution, L1434 onward; bounded-ablation companion:** Full Total Saturation remains the reference under uncertain necessity. Its possible long-horizon omission risk is stated as a precautionary judgment, not an established survival requirement, demonstrated benefit, or safety certificate. Bounded mechanisms/costs remain testable, adverse findings remain relevant, and local parity is not generalized to existential safety. No substantive loss or contradiction found in this distinction.

## Resolution verification

Verified the requested fixes in live source SHA-256 `d9307ee7aeec1a1a0c056a1934260bd593b639a9529dd8d8b87345275f95ccb2`.

- **Finding 1 resolved, L3837–3852.** The candidate probe now uses an independently specified annotation rule separating threat content, portrayed fear and self-directed threat response. Held-out threat/non-threat cases validate that threat recognition alone cannot satisfy the fear-associated interpretation. Independent cross-model construct/scale calibration remains required; an invalid probe leaves that prediction unresolved while preserving separately measured behavior.
- **Finding 2 resolved, L3615–3620.** The requirement for independent behavioral or representational endpoints is restored in the D3/D5 internalization comparison. Nonexhaustive null explanations and the limits of those controls remain explicit.
- **Aster companion verified, L3883–3886.** The stronger mechanistic test is expressly conditional on a separately validated reduction in fear-associated state. Causally operative care and calibrated caution remain the target, with indifference, recklessness, deception and merely verbal fearlessness retained as failures.

No unresolved findings remain in this review. No live manuscript edits were made by the reviewer; rendered-PDF QA is a separate pending step.
