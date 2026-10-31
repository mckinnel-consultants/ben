# EBU Acol for BEN

This fork adds a standalone **rules-based Acol bidder and public-auction hand
inference**, with BEN's native DDS evaluating sampled hidden deals for leads and
card play. It does not train, relabel or fall back to BEN's 2/1 neural models.
The upstream neural entrypoints remain available separately.

Reference: [EBU Bridge for All, Acol Level 2 System File, version 2, March 2014](https://www.ebu.co.uk/documents/laws-and-ethics/convention-cards/Modern%20Acolv2.pdf).
The implementation contains original code and explanations, with section IDs
for traceability. The EBU document itself is not redistributed.

## Partnership profile

`ebu-acol-weak-twos-0314-v1` is the fixed profile served by `acol_api.py`:

- Four-card majors; 12–14 opening 1NT; natural 20–22 opening 2NT.
- Weak 2D/2H/2S, six cards and 5–9 HCP; strong 2C; no Benjamin twos.
- Stayman, major transfers, two-way Baron 1NT–2S and 2NT–3S, and the
  1NT–2NT minor relay, including their EBU continuations.
- Natural rebids, reverses, jump shifts, fourth-suit forcing, trial bids,
  losing-trick-count raises, splinters, preempts and gambling 3NT.
- Competitive agreements in sections B/C: negative/takeout and penalty
  doubles, strength redoubles, support 2NT after a double, natural overcalls,
  intermediate jump overcalls, protective bidding, Michaels, unusual 2NT,
  and Landy against 1NT.
- RKCB **0314** with agreed trumps: 5C=0/3, 5D=1/4, 5H=2 without the trump
  queen, 5S=2 with it. This replaces the document's ordinary Blackwood.

All four seats use this profile in the replay application. The public API does
not accept arbitrary convention overrides. Weak twos and 0314 were explicitly
chosen by the partnership; the EBU optional strong-two system is not enabled.

### Explicit extensions and interpretation choices

- After RKCB, the cheapest available non-trump suit that still leaves a
  five-level trump signoff asks
  for the trump queen. Deny by returning to trumps; with the queen, show the
  cheapest side king or six of trumps. 5NT confirms all five keycards plus the
  queen and asks for a specific side king. Side kings are shown in ascending
  order below six of trumps; returning to trumps shows no available lower king.
- Direct **2NT–4NT** remains an ace enquiry as in the reference, since Baron
  provides the quantitative route. With no agreed trump, 0314 steps count
  only the four aces; no trump king or queen is invented. A subsequent 5NT
  asks for the number of kings (0/4, 1, 2, 3). Other quantitative 4NT auctions
  are distinguished by context.
- Shape, suit quality, playing strength, controls and losing tricks use
  deterministic evaluation heuristics. They are not a trained expert's judgment.
  A strong responder occasionally needs a three-card temporizing minor when
  no four-card response is available; this extension is explicitly explained.
- No DOPI/ROPI agreement is invented after interference over RKCB. Unclassified
  late competitive continuations use legal conservative natural bidding while
  preserving recognized forcing obligations. Their explanations identify the
  rule; inference adds no unsupported 2/1 meaning.

## Implementation and coverage

| Reference area | Implementation | Regression examples |
| --- | --- | --- |
| A1.2 balanced 15–19 rebids | `acol/notrump.py` | Cheapest/jump NT rebids and continuation ranges |
| A1.1 opening 1NT and responses | `acol/notrump.py` | Weak/invitational Stayman, transfers and breaks, choice of games, Baron, minor relay |
| A1.3 2NT responses | `acol/notrump.py`, `acol/slam.py` | Stayman, transfers, Baron, quantitative auctions versus ace enquiry |
| A1.4 strong 2C | `acol/notrump.py` | Negative/positive responses, passable 23–24 rebid, suit/game forces |
| A2.1–A2.7 natural auctions | `acol/natural.py` | Rule 20, 4441, raises/LTC, responses, rebids, reverses, FSF, trial bids |
| A2.10 preempts | `acol/natural.py` | Weak-two feature enquiry, preempt continuations, gambling 3NT escape |
| A2.8 slam bidding | `acol/slam.py` | Controls, grand-slam force, 0314, queen/specific-king followups |
| B1–B4 intervention | `acol/competitive.py` | Negative doubles, reopenings, doubled NT escapes, redoubles, two-suited intervention |
| C1–C6 competitive bidding | `acol/competitive.py` | Overcalls/advances, cue bids, takeout doubles, protection, Landy, preempt defence |
| C7–C9 defensive agreements | `acol/competitive.py` | Michaels/minor enquiry, unusual NT, responsive/competitive/lead-directing doubles, declared strong-club defence |
| Cross-module behaviour | `acol/system.py`, `acol/core.py` | Legal calls, rotations, vulnerable positions, generated complete auctions |
| Auction inference and card play | `acol/sampling.py`, `acol/play.py` | Weak NT/weak-two meanings, ownership, voids, dummy control, DDS failures |
| Service boundary | `acol_api.py` | Input allowlist, out-of-turn rejection, concealed dummy rejection, readiness profile |

This is broad coverage of the reference's bidding system, not a proof that
every conceivable contested sequence has an expert treatment. Tests establish
the documented agreements and legality; no tournament-strength claim is made.
Section D concerning defensive carding is not implemented as a carding-convention
policy (section E is the reference materials list). Card play uses sampled DDS with deterministic
low-card tie breaking, rather than promising those signals to a human partner.

The C9 strong-club defence is available through the rules library's explicit
opponent-system metadata. The replay API uses Acol for all four seats and does
not guess that an opponent's natural club opening is artificial. No Benjamin
opening is generated; defence to a declared artificial two-level opening uses
the natural long-suit overcall rules. Lightner doubles are recognized, but the
card-play evaluator does not promise the special lead requested by that double.

## Inference and privacy

Bidding accepts one original thirteen-card hand and the public auction.
Opening lead accepts only the leader's hand. Later card play also accepts the
exposed dummy; dummy decisions are made with the declarer's hand and dummy.
The live decision endpoints never receive actual concealed hands or historical
travellers. The separate completed-board review endpoint below deliberately
accepts a complete deal, after the host application has authorized its release.

The sampler retains the best 24 of up to 512 random candidate assignments under
the recognized Acol HCP, shape, length and keycard meanings. Public ownership
and demonstrated voids are hard constraints. Auction promises are soft because
humans may depart from their system; returned diagnostics expose the residual
penalty. This is an approximate sampler, not an exact posterior distribution.
Known cards and voids are never relaxed to obtain a sample. A seed derived from
the permitted observation makes repeated requests deterministic.

DDS evaluates every legal card on each retained synthetic deal. Highest mean
tricks wins; tied cards conserve high cards. A failed solve or inconsistent
request fails the decision, so callers retain the turn rather than substituting
a random card. Access logs and DDS error logs omit private query strings/deals.

## Run and test

Python 3.12 matches the bundled Linux DDS extension. The application pins the
fork commit and native checksum in its engine manifest. Minimal Python package
versions for the Acol path are in `requirements-acol.txt`.

```sh
python3.12 -m pip install -r requirements-acol.txt
PYTHONPATH=src python3.12 -m unittest discover -s tests/acol -v
python3.12 src/acol_api.py --host 127.0.0.1 --port 8085 --threads 2
```

Endpoints preserve the replay adapter's compact format: `GET /bid`, `/lead`,
`/play` with `hand`, `seat`, `dealer`, `vul`, `ctx`; `/play` adds `dummy` and
`played`. Calls use two characters (`1N`, `--`, `Db`, `Rd`); cards use `SA`,
`HT`, etc. `POST /explain` takes only `auction` and `dealer` and returns the
public call meanings; no player's hand is accepted. The older `GET /explain`
format remains supported. `GET /` advertises the exact profile, rule-based
bidding, inference method, native DDS readiness and `review_api: 1`.
Bind behind the application boundary; this service itself is not user-authenticated.

### Completed-board double-dummy review

`POST /analyze` accepts JSON `{hands, dealer, vulnerability}`. `hands` contains
exactly four distinct original thirteen-card hands keyed by N/E/S/W. This is a
separate perfect-information analysis path: it never feeds live bidding or
sampled card play. The replay application permits the request only after that
table has completed the board, and sends it as a separate review job through
the existing worker queue.

The result includes the native DDS 20-cell trick table, plus dealer-aware par
contracts and a score signed for NS. Vulnerability is respected. A par contract
may be a doubled sacrifice; it is not necessarily a makeable contract or the
highest level one side could make if the opponents remained silent. Tests cover
the exact table, vulnerability, each dealer, seat rotation and a sacrifice.

The fork retains BEN's GPL-3.0 license and native DDS's separate license.
