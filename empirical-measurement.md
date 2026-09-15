# Empirical Impact: Measured, Not Asserted

Externalized state makes it structurally possible to discard an agent's context between
steps: the thread of work survives, because it was never in the transcript to begin with.
That is a property of the protocol. Whether discarding is worth doing is not. Once the
option exists, taking it is an arithmetic question about token prices, and the arithmetic
belongs to the harness and the workload, not to the state layer. What follows is a
measurement of that operating strategy. It is not a measurement of the protocol, and it
does not depend on the protocol being present: any system that can externalize its
execution state faces the same arithmetic the moment it gains the option.

The brief we were given assumed that discarding context saves a great deal of inference,
because carried material is otherwise re-read on every step. Our own cost model, computed
before the run, predicted the opposite for a corpus of this size. The run confirmed the
model's sign - and then falsified three of the model's internals. Those three falsifications
are the most useful output of the exercise, and they are stated as corrections below.

## What was measured, and how

Two arms, the same task, the same files, the same model, the same machine, back to back.

- **Carry arm.** One context executes all six steps of a plan in sequence. Everything read
  or produced in step *k* is still present in step *k+1*.
- **Discard arm.** Six fresh contexts, one step each, run sequentially. The only hand-off
  between steps was a small result file on disk - a property of this test rig, not a
  constraint of the state layer.

Two repetitions per arm, in the order carry, discard, discard, carry, so that a linear
drift over the measurement window cannot land on one arm alone. Two is below the three
repetitions per arm our own protocol required: at two against two the smallest one-sided
permutation p obtainable is 1/6, so the design cannot produce a statistically significant
result at all, and we report this run as a sign check rather than as a test. In total:
14 isolated agent runs, 103 model requests. The task was a six-step analysis over a corpus
of roughly 11,000 tokens of production source: five independent inspection steps and a
closing synthesis step that depends on all five.

Four methodological commitments carry the result, and they are the part of this section we
would ask a reviewer to attack first.

**Billing is reconstructed per request, not aggregated.** Uncached input, cache writes by
retention class, cache reads and output are kept apart throughout, because their prices
differ by more than an order of magnitude and a single blended figure hides the entire
effect. Each request is counted once, from the final record for that request id. This is
not a formality: naive summation of every line overcounts, and it overcounts the two arms
by different amounts. Left uncorrected it would have roughly doubled the effect we report.

**Cache warmth is reported and normalised, not averaged away.** It was not under our
control in this run - one arm happened to start cold because it ran first, which is a
property of the execution order and not of the arm. Every reading is therefore recomputed
under three warmth assumptions, applied identically to both arms; the first version of that
normalisation applied them inconsistently, and the arithmetic review caught it before
publication. Correcting it moved the equal-warmth margin against the discard arm, not for
it. Warmth is the largest lever on the *size* of the margin we report, and a run that does
not report it is reporting the cache, not the strategy.

**The order is mirrored** (A-B-B-A), which is the only defence available at this sample
size against a trend over the measurement window being read as an arm effect.

**The run was reviewed adversarially.** Three independent reviews: an arithmetic recheck
that reproduced all four runs by hand from the raw records, a quality review of all 24
produced documents against the source material, and a review whose explicit brief was to
break the conclusion. That review filed nine objections; five of them bear on the
conclusion. Three changed what we believe and are stated below as corrections. The
remaining two are stated under *What is not shown*: the corpus we ran was the one our own
preparation had listed as the comparison case rather than the one it had laid out for the
decision, and the threshold our model claimed lies outside the range in which the carrying
arm can exist at all.

## The result, in the form it actually holds

Discarding context cut input tokens by roughly a quarter and raised output tokens by
roughly a fifth, averaged over two runs per arm. We do not quote those to a decimal place
either: with two runs per arm, the spread *inside* the discard arm is over a third of the
difference *between* the arms on input tokens, and over half of it on output tokens.

On total cost, the discard arm was more expensive in every single run, with no overlap
between the arms under any of the three warmth readings. That is the most robust statement
this run produces. Depending on how restart warmth is priced, the same four runs yield a
margin between +9.9 and +89.1 percent. Only one genuinely cold start was observed - the
first agent of the batch - so the expensive end of that range is computed from it, not run.

We are deliberately not reducing this to one number. The spread *within* the discard arm
was 48 percent of the measured difference *between* the arms. A figure quoted to one
decimal place would assert more than the data carries. What the run supports is the sign,
under stated conditions:

> On a carried payload of roughly 11,000 tokens, with steps seconds apart, in a
> general-purpose agent harness with the cache layout it shipped with in September 2026,
> discarding context between steps cost more than carrying it, and the work was
> indistinguishable.

Every clause in that sentence is load-bearing. Change the payload, the spacing, or the
harness, and the sign is not guaranteed to survive.

On quality: no measurable difference at n=2. All 24 produced documents met the required
structure. Of the seven breakpoint claims we traced line by line against the source, none
turned out to be invented. The only two factual errors found were in the carry arm; the
only finding pointing the other way was a synthesis in the carry arm that joined two steps
into a contradiction no discard run produced, although every discard run had the same
ingredients on disk - the one hard hint that discarding misses something. Both are single
cases out of four runs. We report the whole as "no measurable difference", not as "equal" -
four runs are enough to exclude a gross collapse in quality and not enough for more.

On wall-clock time: measured, and not reportable. The spread within a single arm was about
six times the difference between the arms, and part of that spread is a 146-second stall in
one run during which no work was done at all. The data would have permitted us to quote a
percentage. Quoting it would have been noise with a decimal point.

Two things the cost figure does not settle. **Cost is not an energy measure.** The discard
arm processed fewer tokens and paid more money, because the tokens moved from a cheap price
class to an expensive one; we did not measure energy, and fewer billed tokens do not
translate into less computation, since a cache write is a full prefill where a cache read is
not. **And where an input rate limit binds rather than a budget, the sign of the relevant
quantity is the opposite of the sign of the cost:** in this run the carry arm needed about
1.3 times the input-token throughput for the same work.

## What the measurement corrected in our own model

We had a cost model before the run. The run falsified parts of it, and that is the most
useful thing it produced.

**Correction 1. Carrying cost 2.96 times what our model predicted - for two reasons we had
both got wrong.** The model assumed 2.5 model requests per step; we measured 4.17 in the
carry arm. And it counted the carried payload as the source material, where the transcripts
show source material *plus* tool output, intermediate results and the model's own reasoning
crossing every step boundary - 3.61 times the nominal payload, counted in tokens. The 2.96
is the resulting cost ratio, not a token ratio. Every break-even threshold we had computed
was therefore about three times too high. Corrected, the warm threshold falls from roughly
108,000 carried tokens to roughly 36,500, which moves the task size we had sized for our own
codebase - an estimated 25,000 to 45,000 tokens - from comfortably below the line to sitting
on it.

**Correction 2. Most of the penalty was the harness, not the strategy.** Roughly 82 percent
of what each warm restart cost in this run was an unchanged block of standing text - tool
definitions, environment description - that the harness re-*writes* into the cache on every
restart instead of *reading* it, at 12.5 times the price, as measured in September 2026.
Priced as a read, a restart would have cost less than the per-step saving the discard arm
actually achieved: recomputed on this run's own numbers - recomputed, not run again - the
discard arm would have won it, by about four cents. That margin is inside the run-to-run
spread we decline to quote above, which is precisely the point: it moves the answer from a
clear loss to a coin toss. That is a property of a particular execution harness and a
particular cache layout at a particular date. It is not a property of discarding context,
and it is not a property of the protocol.

**Correction 3. Chain length does not cancel out.** Our model showed the number of steps
cancelling from both sides of the balance, and concluded that no chain is long enough to
make discarding pay. That holds only if the total payload is held fixed while the chain is
cut into finer steps. Hold the *step size* fixed instead - the normal case, where more work
means more steps rather than smaller ones - and the balance is quadratic against carrying:
with warm restarts, and with the per-token carrying cost measured in this run, discarding
wins from roughly nine steps of 5,000 tokens each, and sooner for larger steps. With cold
restarts the crossover moves out by the cold-to-warm restart ratio, into the low twenties.
Chain length is back in the equation.

Three further constants come from prior calibration over 175 production agent runs carrying
2,582 real model requests on the same machine, and they bound the result. A cold restart
costs about 2.66 times a warm one for the model measured here - 2.56 when warm and cold
restarts are matched for preamble size. Warmth follows a five-minute retention window: the
rule predicts 152 of 164 observed restarts, though the observations immediately at that
boundary are sparse and its exact position rests partly on the published cache TTL rather
than on a dense series of our own. And a "warm" restart is only about two thirds warm - the
cache-read share of a warm start ran near two thirds in the calibration set and never
exceeded 90 percent - because the task-specific part of the preamble is written fresh
either way. The consequence sharpens the conditions above: the operating case this
architecture exists for - a plan whose steps may be hours apart - is structurally the *cold*
case, which is the expensive end of the range, and the case no laboratory run with steps
seconds apart exercises at all.

## Why the answer is a surface, not a number

The break-even point is not a threshold on one axis. It moves along at least three, and any
figure quoted without all three is true only of the run it came from.

- **Payload carried per step.** The cost of carrying grows with what is carried and is paid
  again on every request of every later step. This axis favours discarding as it grows, and
  it is the axis our own model got wrong by a factor of three.
- **Length of the chain.** At fixed step size the carried cost grows with the square of the
  chain while the cost of restarting grows linearly. Long chains favour discarding; short
  ones do not.
- **How the executing harness partitions its cache.** This axis is not about the workload at
  all, and in the run reported here it was the dominant term. A harness that reads its
  standing preamble rather than rewriting it would have reversed this run without a single
  token of the workload changing.

A fourth term belongs in the same balance and is missing from every figure above: the cost
of carrying results between steps in files, which a discarding arm cannot avoid. We can size
it only by estimate, so we name it and do not count it.

This is why the resource-efficiency claim in this document is a methodology and a shape,
not a headline percentage. We can say which axes the surface runs along, which way it tilts,
and which term dominated in the one run we have. We cannot say where it crosses zero. A
single number would conceal exactly the three things an operator needs in order to know
whether it applies to them.

> Token reduction is never the sole objective. The objective is the equilibrium of reduced
> compute and undiminished output quality: no destructive truncation, no summarization that
> discards detail a later query will need.

## What is not shown

This run does not establish where the surface crosses zero. Its corpus sits about a factor
of three below even the corrected warm threshold, so it confirms that a prediction lands on
the expected side of the curve; it does not locate the curve. The two objections held back
above belong here.

**The corpus we ran was not the one prepared for the decision.** A larger corpus of roughly
86,000 tokens - above the corrected warm threshold - had been laid out for exactly this
question, and the run went ahead on the smaller one, which the same preparation listed as
the comparison case and expected to lose. What was measured, therefore, is that a corpus
chosen to sit below the threshold sits below the threshold.

**At the old threshold the carrying arm could not have existed.** In this run the carrying
context ended at about five times the nominal payload it carried. Extrapolated with that
growth factor, a carried payload at the original 108,000-token threshold would have required
roughly three times the context window the harness provides. Read together with the
corrected threshold, the cost question and the feasibility question turn out not to be two
questions: the payload size at which discarding starts to pay and the payload size at which
carrying starts to break down fall in the same region - which is the region this
architecture was built for. We state that as a consequence of two estimates, not as a
measurement.

It says nothing about chains whose steps genuinely depend on each other - in the measured
task, step *k* never needed material from step *j<k*, and a dependent chain would force the
discard arm to re-supply that material at write prices. That is the strongest untested
argument *against* discarding, and it is the next thing we intend to measure, alongside the
prepared corpus at the threshold and a run with the cache boundary corrected. That run will
carry three repetitions per arm and cold restarts; this one had two and warm ones.

By our own pre-registered criteria, this run should have been discarded. It broke two of
them: we required three repetitions per arm and ran two, and our preparation predicted 13
model requests per step and named 12 as the point below which the expected result flips,
where we measured 4.17. Nothing here is therefore offered as a statistically significant
result. We report it because the corrections survive the sample size even where the
percentages do not.

We are publishing the method and the corrections before the headline number deliberately.
A resource-efficiency claim that cannot survive an auditor asking how it was measured is
not an asset, and a model that has never been caught being wrong by its own measurement has
usually not been measured against. It is also why the pilot enquiry asks for approximate
corpus size and target agent harness: those are two of the three axes above.
