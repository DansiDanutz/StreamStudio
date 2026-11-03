## daily-episode-factory.md

- Stage 4, items 52–53. Long-take preparation tools have been retired. The custom Episode 1 motion storyboards, legacy compositor and mixer remain until their authored visual beats have been compared with the factory output.
- Production acceptance. Automated transcript comparisons cover wording. They do not establish that Dan accepts the locally generated narration as matching his avatar voice. A final listening review is outstanding.

### Website storyboard acceptance

Comparing the approved offline Episode 1 scene plans against the authored `tools/compose/motion/cards_v2.py` reveals three source mismatches before final composition. These are release checks for the factory renderer.

| Scene | Authored behavior | Current offline scene |
| --- | --- | --- |
| s6 | Hold Fake-Real, switch to Nervix Space at 1.05 seconds, then introduce the network. | The plan selects only Fake-Real. |
| s28 | Open the Nervix Space home page, then show the NervixPay listing when Dan says “Every project”. | The plan selects the submission form at /list. |
| s29 | Open the directory at /#explore and focus each named project as Dan lists it. | The plan still selects /list. |

Acceptance requires a rendered preview for each scene showing the page and focus changes at the scripted beats. Page changes should reuse separately prepared captures so an editor can retime a beat without recapturing the site.
