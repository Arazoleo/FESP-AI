# Usability Evaluation Report - Cycle 2

Companion data for *Neuro-Symbolic Graph-RAG for Academic Advising: A Three-Cycle
Evaluation of a University Web Chatbot* 

---

## 1. Purpose and scope

This cycle evaluated the interaction layer of the deployed undergraduate advising
chatbot. It is a **formative** study: with ten participants it is designed to
surface interaction problems and characterize task success, not to support
inferential statistics or between-group comparison.

Two other cycles are reported in the paper and are out of scope here: automated
accessibility conformance (Cycle 1, AMAWeb/WCAG 2.1) and answer-consistency
benchmarking against baselines (Cycle 3). For the record, the Cycle 1 issues
were corrected after the initial assessment of 3 August 2026 and a re-test
returned no errors on either page.

## 2. Protocol

Each session had three stages:

1. **Observed execution.** The participant completed six task flows unaided. The
   moderator remained silent throughout and did not intervene, hint, or answer
   questions during execution. Completion therefore reflects *unassisted*
   success.
2. **Structured interview.** The participant rated the ease of each of the six
   flows on a 1–5 scale, then answered the ten items of the System Usability
   Scale (SUS) on a five-point agreement scale.
3. **Retrospective account.** The participant recorded a free-form audio message
   describing what confused them, what they felt was missing, and whether they
   would trust the system's answers.

Some participants also discussed the system informally with the moderator outside
these three stages. Those exchanges are not part of the recorded protocol.

**Sampling.** Purposive, covering seven distinct undergraduate programs of the
institute. The rationale is coverage rather than representativeness: each program
has a different curricular matrix in the knowledge graph, so sampling across
programs ensures every matrix was exercised by a student able to recognize an
incorrect answer about their own degree.

**Ethics.** Participants consented to recording and the data are reported
anonymized. <!-- TODO: if the project has IRB / CEP approval, add the protocol
number here. If it does not, leave this sentence as-is and do not claim
approval. -->

## 3. Participants

| ID | Age | Program |
|----|-----|---------|
| P1 | 21 | Computer Science |
| P2 | 25 | Biomedical Engineering |
| P3 | 24 | Materials Engineering |
| P4 | 19 | Biomedical Engineering |
| P5 | 21 | Computer Engineering |
| P6 | 21 | Science and Technology |
| P7 | 22 | Computational Mathematics |
| P8 | 23 | Biotechnology |
| P9 | 24 | Computer Engineering |
| P10 | 21 | Science and Technology |

Ages 19–25, mean 22.1. No participant reported a disability, so this cycle
provides no evidence about accessibility for users with disabilities.

## 4. Task flows

| # | Flow | Primary path |
|---|------|--------------|
| F1 | Prerequisites of a course | symbolic |
| F2 | Electives of a program | symbolic |
| F3 | Instructors of a course | symbolic |
| F4 | Faculty contact details | symbolic |
| F5 | Institutional news (conference registration) | document retrieval |
| F6 | Complementary-activity requirements | document retrieval |

## 5. Task success

**All ten participants completed all six flows without moderator intervention.**
Unassisted success rate: 60/60 (100%).

Success was recorded as task completion. It does not separately certify that the
returned answer was factually correct - answer correctness is measured
independently in Cycle 3.

## 6. Perceived ease (1–5)

### Per participant

| ID | F1 | F2 | F3 | F4 | F5 | F6 | Mean |
|----|----|----|----|----|----|----|------|
| P1 | 5 | 5 | 4 | 5 | 5 | 5 | 4.83 |
| P2 | 5 | 5 | 4 | 4 | 5 | 5 | 4.67 |
| P3 | 5 | 4 | 5 | 5 | 5 | 5 | 4.83 |
| P4 | 4 | 5 | 5 | 5 | 3 | 5 | 4.50 |
| P5 | 5 | 5 | 4 | 5 | 5 | 4 | 4.67 |
| P6 | 5 | 5 | 5 | 5 | 4 | 5 | 4.83 |
| P7 | 5 | 4 | 4 | 5 | 5 | 5 | 4.67 |
| P8 | 5 | 5 | 5 | 4 | 5 | 5 | 4.83 |
| P9 | 5 | 3 | 5 | 5 | 5 | 5 | 4.67 |
| P10 | 5 | 5 | 5 | 5 | 5 | 4 | 4.83 |

### Per flow

| Flow | Mean | Median | Min | Ratings below 5 |
|------|------|--------|-----|-----------------|
| F1 Prerequisites | 4.90 | 5 | 4 | 1 |
| F2 Electives | 4.60 | 5 | 3 | 3 |
| F3 Instructors | 4.60 | 5 | 4 | 4 |
| F4 Faculty contact | 4.80 | 5 | 4 | 2 |
| F5 Institutional news | 4.70 | 5 | 3 | 2 |
| F6 Complementary activities | 4.80 | 5 | 4 | 2 |

Of 60 ratings, 46 were at the maximum, 12 were 4, and 2 were 3.

**Observations.**

- Friction concentrated on the two faculty-related flows (F3, F4) and on
  electives (F2). F3 drew four sub-maximal ratings, the most of any flow.
- F1, the flow most dependent on symbolic reasoning, was rated highest.
- Symbolic flows (F1–F4) averaged **4.72**; document-retrieval flows (F5–F6)
  averaged **4.75**. The architectural distinction that drives answer accuracy in
  Cycle 3 was **not** perceptible at the interface level. A hypothesis that user
  perception would track the execution path was tested and not supported.
- Two ratings lack a recorded cause and were not followed up during the session:
  P9's 3 on F2, and P4's 3 on F5.

### Recorded causes for sub-maximal ratings

| Participant | Flow | Reported cause |
|-------------|------|----------------|
| P4 | F1 | Preferred a graph visualization of the dependency structure over a textual list. |

Other sub-maximal ratings were not attributed to a specific cause during the
session.

## 7. System Usability Scale

### Item matrix

Items 1, 3, 5, 7, 9 are positively worded; items 2, 4, 6, 8, 10 are negatively
worded.

| ID | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | Score |
|----|---|---|---|---|---|---|---|---|---|----|-------|
| P1 | 5 | 2 | 5 | 1 | 5 | 1 | 3 | 2 | 5 | 1 | 90.0 |
| P2 | 5 | 1 | 5 | 1 | 5 | 1 | 3 | 1 | 4 | 2 | 90.0 |
| P3 | 5 | 2 | 5 | 1 | 5 | 1 | 3 | 2 | 3 | 1 | 85.0 |
| P4 | 5 | 2 | 5 | 1 | 5 | 1 | 3 | 2 | 5 | 1 | 90.0 |
| P5 | 5 | 1 | 5 | 1 | 5 | 1 | 3 | 1 | 4 | 2 | 90.0 |
| P6 | 5 | 1 | 5 | 1 | 5 | 1 | 3 | 1 | 4 | 2 | 90.0 |
| P7 | 5 | 1 | 5 | 1 | 5 | 1 | 3 | 1 | 5 | 2 | 92.5 |
| P8 | 5 | 2 | 5 | 1 | 5 | 1 | 3 | 2 | 5 | 1 | 90.0 |
| P9 | 5 | 2 | 5 | 1 | 5 | 1 | 3 | 2 | 5 | 1 | 90.0 |
| P10 | 5 | 1 | 5 | 1 | 5 | 1 | 3 | 1 | 5 | 2 | 92.5 |

**Scoring.** Odd items contribute (response − 1); even items contribute
(5 − response). The sum of all ten contributions is multiplied by 2.5, giving a
score from 0 to 100. The SUS score is **not** a percentage.

### Summary

| Statistic | Value |
|-----------|-------|
| Mean | **90.0** |
| Median | 90.0 |
| SD | 2.04 |
| Range | 85.0 – 92.5 |
| Reference mean (literature) | 68 |

### Item-level observations

- **Item 7** ("most people would learn this system quickly") is the only item on
  which *every* participant scored below the maximum, all at 3. Participants
  attributed this to varying familiarity with conversational interfaces in the
  wider student population rather than to their own experience. It is the only
  item where the judgment is about *other people*.
- **Item 9** (confidence) was the only positively worded item with variance
  across participants, ranging 3 to 5.
- **P8** scored 5 on item 3 ("easy to use") and 2 on item 8 ("cumbersome to
  use"), a mild internal inconsistency between mirrored items. This is common in
  SUS administration and is why the instrument uses ten items rather than one.

### Ceiling effect

Eight of the ten items sat at or near the extreme for nearly all participants.
Combined with the moderator being the system's developer (see
[Limitations](#10-limitations)), the absolute score should be read with caution.
The relative pattern across items and flows is the more informative signal.

## 8. Retrospective accounts - thematic coding

Themes were derived from the ten free-form audio accounts. Counts are the number
of participants who raised each theme spontaneously.

### T1 - Trust grounded in sources, not fluency (6 participants)

P1, P2, P4, P5, P7, P9 justified their willingness to rely on the system by the
displayed sources and their official institutional origin, not by how well-written
the answers were. P7 explicitly valued that the assistant did not fabricate
information.

Representative reasoning:

- P3: would trust it partly because the answer structure is coherent and partly
  because a student already has enough context to spot an error, so verification
  is incremental rather than from scratch.
- P9: "would trust the answers because it shows the sources, which are UNIFESP's
  own."

### T2 - Trust is graduated, not binary (2 participants)

- **P6** would trust the answers generally but not for enrollment decisions,
  because those are hard to reverse. She also expected the system to *perform*
  actions such as simulating a schedule; it does not, and answers only from
  sources.
- **P8** would not trust it 100% and would verify via the source links - but her
  reservation was directed at the dispersion and inconsistency of the underlying
  institutional documents, not at the system.

In both cases the reservation concerns the stakes of the decision or the quality
of the source corpus rather than the framework itself.

### T3 - Missing detail on complementary activities (4 participants)

P4, P5, P6, P7 asked for a breakdown of what each category of complementary
activity accepts. This capability was already on the roadmap for the following
release; the cycle confirmed demand rather than revealing a new gap.

P5 framed it as an interaction request rather than a content one: instead of
dumping all categories, the system should *offer* the breakdown at the end of the
answer, anticipating the follow-up question.

### T4 - Preference for structured output (3 participants)

P2, P8, P9 preferred answers organized as topic lists over continuous prose. P2
specifically praised the syllabus being returned as bullet points. P8 also asked
for a larger font and stronger emphasis on the course name, and preferred the
prerequisite chain ordered from the course backward to its foundations rather
than the reverse.

### T5 - Expectations misaligned with system behavior (2 participants)

- **P3** assumed he had to start a new chat to clear conversational context. The
  system already manages context automatically. No functionality was missing; the
  interface did not communicate the behavior.
- **P4** asked about credit requirements and was routed to the visual planner,
  which *did* contain the requested information, but he expected a textual
  breakdown. Intent classification was correct - the mismatch concerned response
  modality.

Both are framed as communication gaps on the system side rather than user error.

### T6 - Requests for knowledge absent from the corpus (2 participants)

- **P2**: timetable and room data. Held in a separate project and not part of
  this system's corpus.
- **P8**: course-equivalence and credit-transfer rules, including courses no
  longer offered.

These are coverage limitations rather than reasoning failures: information absent
from the source documents can be neither retrieved nor validated.

### T7 - Conversation history (2 participants)

P1 and P7 asked for access to previous sessions, P7 associating it with login.
Together with T5, this points to limited visibility of conversational state.

### T8 - No confusion reported (5 participants)

P1, P5, P6, P7, P9 reported no confusion at all during use. P6 attributed this
partly to the system asking a clarifying question when a request was ambiguous.

### Other observations

- **P7** noted that the system would be especially useful to first-year students,
  who have not yet internalized the structure of their degree. This complements
  P3's reasoning in T1: the veteran trusts it because he can verify, the newcomer
  benefits because she could not easily find the information otherwise.
- **P3** hesitated visibly before submitting queries, reformulating before
  sending. He was the only participant to do so, and also gave the lowest
  confidence rating (item 9 = 3). With a single case, no association between the
  two can be claimed.

### Recording quality

The audio accounts of P7 and P8 transcribed poorly, with sections unrecoverable.
Coding for those two participants relies on the legible portions plus the
moderator's session notes. Their themes should be treated as less completely
captured than the rest.

## 9. Changes derived from this cycle

Implemented **after** the sessions and therefore **not evaluated** in this cycle:

| Change | Origin |
|--------|--------|
| Interactive dependency graph for prerequisite chains | P4 (T4 / ease rating on F1) |
| Follow-up prompt offering the per-category breakdown | P5 (T3) |

Planned before this cycle and confirmed by it:

| Change | Origin |
|--------|--------|
| Detailed complementary-activity requirements per category | P4, P5, P6, P7 (T3) |

## 10. Limitations

1. **Sample size.** Ten participants support formative conclusions only. No
   inferential statistics are reported and none should be computed from this
   data.
2. **Moderator bias.** Sessions were moderated by the system's developer, a
   condition known to inflate satisfaction ratings through social desirability.
   This is the most likely explanation for the ceiling effect in Section 7.
3. **Ceiling effect.** Most SUS items and most ease ratings sat at the maximum,
   compressing variance and limiting what the numbers can discriminate.
4. **No participants with disabilities.** Accessibility evidence in this project
   comes solely from automated conformance checking (Cycle 1). This cycle says
   nothing about assistive-technology use.
5. **Success criterion.** Task success records completion, not answer
   correctness. The two are measured separately.
6. **Unattributed ratings.** Two sub-maximal ease ratings have no recorded cause.
7. **Self-report and observation diverge in places.** P3 said in his account that
   he would trust the system, yet rated confidence 3; P8 rated confidence 5 yet
   said she would not trust it fully. Divergence between instrument and free
   recall is expected and is part of why three data sources were collected.

## 11. Data provenance

The per-item SUS matrix in Section 7 was **reconstructed from working notes**
across several rounds of correction, not transcribed in one pass from the
response sheets. One point is worth confirming against the originals:

- **Universal item 7 = 3.** All ten participants scoring identically on one item
  is a strong pattern. It is plausible and has a stated rationale (see
  Section 7), but it is worth confirming on the sheets.

Anyone reusing this data should verify Section 7 against the original response
sheets before citing the aggregate figures.
