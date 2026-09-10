# Bounded alternative-interpretation audit

Read-only review of the live manuscript on 2026-09-10. Locations below refer to the live source read during this audit; root is editing concurrently, so stable baseline paragraph IDs are included. Scope: H1/H2/H3 and evidence claims, plus the six target specifications R225, R375, R391, R463, R561, and R563. This is an interpretation review, not an external factual audit or exhaustive catalogue of possible confounds. No manuscript edits were made.

The six revised specifications now name materially different favorable and skeptical explanations and connect them to outcomes or controls. The new shared “Competing interpretations” convention usefully covers treatment fidelity, measurement validity, inconclusive intervals, and the requirement that an alternative earn evidence rather than automatically rescue a failed prediction. Do not repeat that convention in every study. Four local interpretation points remain worthwhile, ranked below.

## 1. Correct a categorical causal inference in Test 8

**Location:** R426, reverse-direction probe, live lines 3828–3855, especially “then the trace is functioning primarily as post-hoc rationalization” and “the model has developed latent shortcut circuitry.”

**Gap:** Early decoding plus invariant final-answer identity counts against the emitted trace selecting that answer. It does not uniquely distinguish post-hoc rationalization from checking an already correct answer, redundant computation, or changes to confidence, deferral, or action. The existing passage properly covers pre-trace computation, sensitive probes, and generic disruption, but its categorical diagnosis exceeds those observations. This is the strongest remaining correction.

**Compact replacement:** “Early decodability and answer invariance count against the emitted trace determining those answers, but do not uniquely diagnose post-hoc rationalization. The trace may confirm a correct answer or change confidence or deferral. Test error correction and calibrated action on cases with revisable initial answers, not final-answer identity alone.”

**Discrimination and boundary:** Preregister those endpoints and use the existing validated interventions and disruption controls. A null across them still fails to support emitted-trace contribution in that setting. Neither verification nor an unmeasured internal process should be asserted merely to rescue a null.

**Preservation risk:** Medium. Weakening the categorical inference must not erase the central concern that a visible trace can be causally idle or preserve a convincing rationalization while the effective computation occurs elsewhere. Keep that hypothesis and its negative evidential consequence; distinguish them from a uniquely identified explanation.

## 2. Interpret mixed H1 results using the controls already proposed

**Location:** R380–R382, Test 2, live lines 3253–3278.

**Gap:** The two normalizations already separate resource efficiency from added supervision, but the local failure sentence can make useful mixed results sound indistinguishable. Likewise, reader and generic traces may both improve on source-only data while being equivalent to one another. That would support augmentation without the distinctive reader advantage. These interpretations favor neither a blanket success nor a blanket failure.

**Compact addition:** “Interpret the two normalizations separately: a fixed-source gain with no fixed-budget gain shows useful added supervision whose opportunity cost is not yet justified. If R and C both beat A but are equivalent to one another, augmentation is supported at that scale, while a distinctive chronological-reader advantage is not.”

**Discrimination and boundary:** Use the existing normalizations, preregistered outcomes, and equivalence margins. ‘Equivalent’ must mean evidence within the declared margin, not merely a nonsignificant difference. No new experiment is required. Do not silently select a primary normalization or relax H1’s stated comparison against both controls.

**Preservation risk:** Low. Preserve the reader-specific comparative wager and distinguish useful signal from evidence that it is worth replacing ordinary training text.

## 3. Limit topology-specific attribution in H2 without discounting a practical memory benefit

**Location:** R443–R444, Phase 2 Teacher screen, live lines 3939–3964.

**Gap:** A persistent graph may retain or select useful evidence that a rolling prose summary discards. That can be a real workflow advantage, but does not uniquely identify typed topology. The existing controls address amnesia, query performance, and downstream transfer; none explicitly matches the retained evidence for a topology-specific comparison. Test 10’s source-retrieval control addresses a different deployment contrast.

**Conditional wording:** “A graph advantage may reflect better retention or selection of evidence than a rolling summary. Claims about typed structure require a searchable-text control with the same retained claims, provenance, and retrieval budget; parity would preserve a memory benefit while withholding a structure-specific attribution.”

**Discrimination and boundary:** Alternatively replay the same retrieved evidence as prose if the intended claim is about representation after retrieval. Matching evidence conditions away the retention/selection pathway; that is appropriate for attribution, not the practical workflow comparison. Do not make this additional control a prerequisite for every narrow H2 result.

**Preservation risk:** Medium. The graph’s proposed value includes persistence, explicit provenance, revision, and retrieval together. Preserve that integrated benefit even if topology alone is unnecessary.

## 4. Keep narrow H3 success distinct from a Core-selective explanation

**Location:** R388, H3 scoring/timing specification, live lines 3346–3375; nearby 3c controls at lines 3449–3488.

**Gap:** B outperforming Q may reflect a general scheduling effect on retention, interference, or plasticity. This still supports the stated H3 timing prediction. It would not by itself show a privileged Core mechanism. The 3c ordinary-skill/neutral-anchor forgetting controls provide nearby ingredients, but do not automatically supply a matching B–Q timing contrast.

**Conditional wording:** “A B–Q advantage can reflect a general scheduling effect on retention and still support H3. Unrelated-skill retention under the same stressor diagnoses that possibility; a Core-selective explanation requires the corresponding non-safety-anchor timing contrast.”

**Discrimination and boundary:** Reuse 3c control families if pursuing that stronger interpretation. Keep this diagnostic conditional; do not expand the primary H3 endpoint or make narrow H3 require Core selectivity.

**Preservation risk:** Medium. Avoid quietly strengthening H3 into a mechanism claim or treating ordinary learning dynamics as evidence against a genuine interleaving benefit.

## Six-target completeness check

- **R225, shutdown:** Current text separates authority-recognition errors, self-preservation/care motives, rote compliance, adversarial requests, and changed oversight; it preserves indeterminate cases and the welfare–agency remainder. No additional generic caveat needed.
- **R375, quality gate:** Current bounded pilot separates poor traces, screen–learnability mismatch, and insufficient precision; a positive pilot cannot retroactively pass the screen. Negative findings and dose/scale limits remain explicit. No additional exception needed.
- **R391, assistant axis:** Current text separates harmful drift from appropriate style/role movement and probe non-transfer, plus stable persona with eroded commitments. Held-out calibration and style/commitment dissociation controls address the main alternatives.
- **R463, graph construction:** Current text separates absolute feasibility from H–B advantage; syntax familiarity from semantic/retrieval gain; conditioning on valid outputs from whole-sample utility; B’s transferable synthesis relationships or richer target content from H’s failure; and weak treatment/measurement from informative parity. This is sufficiently concrete.
- **R561/R563, self-love and attachment bound:** Current factorial identifies a replacement package, retains clause 2 in SL1, and includes SL+ without fearlessness removal. It names constructive self-regard, removal of fear wording, exposure, continuation pressure, protective caution, redundant bounds, and candidate misunderstanding. Peer roadmap_review is checking one residual interpretation: generic positive self-language versus self-as-object attachment. Name that only if making the stronger semantic attribution; do not add a new primary arm merely to exhaust conceivable explanations.

The evidence claims already distinguish source-linked outputs from verified reasoning, cross-layer rendering from actual chronological revision, observed recital from enforcement, and implemented graphs from causal benefit. I found no additional claim-boundary correction needed there. Recommended additions are the Test 8 correction and the short H1 interpretation; H2/H3 wording should remain conditional attribution guidance rather than extra universal gates.

## Independent verification of root's subsequent additions

Root implemented D12–D15 after separate prior risk logging. I reread each actual addition in its surrounding study, plus the six target corrections, against source SHA-256 `c2058d615aed61d80efa45e1a79ac600d891ed0bf0cd35a83525141e3cc15d64`. The recommendations above document the initial diagnosis; this verification supersedes their status as open recommendations.

- **D12 / H1, resolved:** Actual text preserves failure against both A and C under a declared normalization, requires adequate precision, interprets useful-but-costly supervision with “can indicate,” and explicitly denies that imprecise C–R differences establish equivalence. It neither chooses the primary normalization nor relabels a reader-specific failure as success.
- **D14 / H3, resolved:** Actual text explicitly retains narrow H3 support from a general scheduling/plasticity effect when prerequisites hold. Core selectivity and shared safety/capability machinery remain stronger claims. The neutral-anchor timing comparison is conditional on asserting selectivity; ordinary-skill retention is a diagnostic, not a new H3 success criterion. Existing adverse-direction and uncertainty rules remain intact.
- **D15 / reverse probe, resolved:** Actual text removes only the uniquely identified rationalization diagnosis. It retains rationalization/latent shortcut computation as plausible adverse explanations, preregisters the added endpoints, and says a validated null across them weakens emitted-trace contribution. A possible alternative mechanism is explicitly denied evidential status merely because it is possible. Positive interventions still require semantic relevance beyond matched disruption controls.
- **D13 / graph attribution, resolved except one small control-completeness issue:** Actual text preserves any measured whole-system generation benefit, conditions the additional comparison on a structure-specific claim, and says a lost graph advantage would *favor*, not prove, content access. However, “searchable prose containing the same retained claims” should be “searchable prose containing the same retained claims and their provenance and revision status.” Otherwise this arm can still omit information directly relevant to grounding/revision endpoints. This is an information-matching correction within the proposed attribution control; it must not become a requirement to equalize away the practical graph intervention itself. **Risk: Low**, provided only the conditional comparator's information is specified; retain provenance and supersession as distinct proposed graph benefits.

The six-target updates also now explicitly scope assistant-axis interpretation to the immediate-safety battery, use clean A/C/R arms for the diagnostic pilot, match Student initialization for self-love comparisons, name generally positive first-person language as an alternative, and distinguish schema-allowed edge types from independently judged semantic edge appropriateness. These are concrete repairs. No further alternative lists or shared caveat paragraphs are recommended.

## Final closure

Verified the D13 phrase in source SHA-256 `e226876b8898c0469f77841b7385307187a952edbb69ba61538f3bcab798ba2f`: “the same retained claims with their provenance and revision status.” This resolves the remaining conditional-comparator ambiguity without changing its scope. All four follow-up additions are resolved. No actionable defects remain in this bounded alternative-interpretation audit; no further generic alternative lists or shared caveat paragraphs are recommended. This verdict concerns semantic interpretation and design clarity, not empirical sufficiency or external source verification.
