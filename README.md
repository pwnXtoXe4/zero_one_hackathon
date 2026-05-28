# Zero One Hack_01

**36 hours. Real infrastructure. European AI sovereignty.**

Welcome to the central repository for Zero One Hack_01, hosted by [Lumos Consulting](https://lumos-consulting.at) at [AI Factory Austria](https://aifactory.at) in Vienna, with compute provided by [HPE](https://www.hpe.com) on the Leonardo GPU Cluster (64× A100s).

This is not a basic-LLM-wrapper hackathon. We're here to build infrastructure-level AI on European compute, with real corporate problem statements and 36 hours to ship.

---

## Quick links

- 🌐 **Docs**: [docs.zero-one.lumos-consulting.at](https://docs.zero-one.lumos-consulting.at/)
- 💬 **Discord**: https://discord.gg/e6rrVbcD5
- 📍 **Venue**: AI Factory Austria (AI:AT), Vienna
- 

---

## The three tracks

| Track                | Partner  | What you'll build                                                                                                               |
| -------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------------- |
| 🧾 **Insurance AI**   | UNIQA    | An AI-guided conversion flow that replaces a static form-based insurance calculator. Persona-based simulations on Leonardo.     |
| ⚙️ **Industrial AI**  | Infineon | Train and benchmark sequence models on semiconductor process flows. Does your model learn real process logic, or just memorize? |
| 📈 **Forecasting AI** | Sybilion | Build a decision agent on top of a probabilistic forecasting API. Live mid-run plot twist on Sunday.                            |

Each track's full briefing, data, and starter materials live in [`/tracks/`](./tracks/). 

---

## Schedule

### Friday, 29 May
| Time  | What                                            |
| ----- | ----------------------------------------------- |
| 18:00 | Doors open, registration, drinks                |
| 19:00 | Opening keynote                                 |
| 19:30 | Track presentations (UNIQA, Infineon, Sybilion) |
| 20:30 | Team formation, track commitment                |
| 21:00 | **Hacking starts**                              |
| 23:00 | Kitchen closes (food available throughout)      |

### Saturday, 30 May
| Time  | What                                  |
| ----- | ------------------------------------- |
| 08:00 | Breakfast                             |
| 10:00 | Workshop: Leonardo cluster onboarding |
| 12:30 | Lunch                                 |
| 14:00 | Mentor office hours (per track)       |
| 18:00 | Dinner                                |
| 20:00 | Optional: lightning talks             |
| 24:00 | Quiet hours (venue stays open)        |

### Sunday, 31 May
| Time  | What                                            |
| ----- | ----------------------------------------------- |
| 08:00 | Breakfast                                       |
| 09:00 | **Submission deadline (PRs open)**              |
| 09:00 | Final 6 hours: polish demos, prep presentations |
| 13:00 | Lunch                                           |
| 14:00 | **Submission deadline (PRs locked)**            |
| 14:30 | Final presentations begin                       |
| 17:30 | Jury deliberation                               |
| 18:30 | Awards ceremony                                 |
| 19:30 | Closing drinks                                  |

Schedule may shift by ±30 min — check Slack `#announcements` for live updates.

---

## What's provided

- **Compute**: Leonardo GPU Cluster (A100s). Per-team quota and access instructions in [`/infrastructure/leonardo_access.md`](./infrastructure/leonardo_access.md).
- **Food & drinks**: All meals, snacks, coffee, soft drinks throughout. Dietary requirements collected at registration.
- **Workspace**: Power, fast WiFi, monitors on request, breakout rooms for team calls.
- **Mentors**: Domain experts from each partner company, plus ML/infra mentors from Lumos and HPE.
- **API credits and tokens**: Track-specific, documented in each track's README.


---

## How submissions work

1. **Fork this repo**
2. Work in your fork under `/submissions/{your-team-name}/`
3. Open a **Pull Request** to this repo by Sunday 10:00 — the PR timestamp is your submission timestamp
4. Each PR must include the deliverables listed in [`/submission/TEMPLATE.md`](./submission/TEMPLATE.md)
5. After 10:00, PRs are locked. No edits, no exceptions.

Late commits within your own fork are fine — only the PR timestamp matters.

---

## Judging

Each track has its own rubric in [`/judging/rubrics.md`](./judging/rubrics.md). All tracks share these baseline expectations:

- **Working artifact** — not a slideware demo, something that actually runs
- **Reproducibility** — your repo should let someone else re-run your work
- **Honest evaluation** — show what worked, show what didn't, show what you measured
- **Visible reasoning** — explain *why* you made the technical choices you did

---

## Code of conduct & house rules

- Be kind. Be useful. Be honest about your work.
- AI Factory Austria is a working facility — respect equipment, doors, quiet hours.
- Mentors are here to unblock you, not to write your code. Use them well.
- The Leonardo cluster is shared infrastructure. No cryptomining, no training on copyrighted data, no abuse of compute. Violations = disqualification.
- See [`CODE_OF_CONDUCT.md`](./CODE_OF_CONDUCT.md) for the full version.

---

## Get help

| Channel                                    | Use for                             |
| ------------------------------------------ | ----------------------------------- |
| `#announcements`                           | Schedule changes, important updates |
| `#industrial`,`#insurance`, `#forecasting` | Track-specific questions            |
| `#infra`                                   | Leonardo, GPU quota, WiFi, hardware |
| `#general`                                 | Everything else                     |
| In-person Lumos desk (lobby)               | Anything urgent                     |

---

*Looking forward to seeing what you build.* 🚀