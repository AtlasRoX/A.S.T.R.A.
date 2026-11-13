# Honest Orbit: ASTRA's crew-health game

**USP: a crew-health game you cannot win by hiding symptoms.** XP and badges never depend on what a reading
says, good or bad. They reward actions: measuring, logging, re-measuring after a warning, helping crewmates and
drilling. Crew members compete as one team against the mission, not against each other, and the game is paced to
the mission's known morale curve.

Code: `engine/app/gamification.py` (rules), `engine/app/catalog.py` (badges, chapters, crew operations, perks,
XP rules), `web/app/missions/page.tsx` (the Missions page). Tests: `engine/tests/test_game.py`.

## Research and the decision it drove

| Finding | Source | Design decision |
|---|---|---|
| Pilots under-report health conditions because disclosure can mean grounding. | Harvard survey of 1,848 pilots; Reuters reporting, 2025 | **Reward the act, never the value.** A fever earns the same XP as a normal reading. No badge needs a "good" number. |
| Game rewards raised daily self-report compliance (86% vs 78% e-diary, 71% paper) without changing the answers. | Use of in-game rewards to motivate daily self-report compliance, JMIR 2019 | Reward **completing** checks and logs. |
| Competition gave the largest and only lasting gain among support, collaboration and competition arms. | STEP UP trial, JAMA Internal Medicine 2019 (602 adults, 36 weeks) | Keep competition's pull, but aim it at **the crew's own last week**, not at crewmates. |
| Crew conflict is a formal NASA risk; it tends to rise over long missions. | NASA HRP Team Risk evidence report, 2022; ISS journal analyses | **No individual leaderboards.** Weekly crew operations and crew rewards are cooperative. |
| Morale tends to dip in the third quarter of isolated missions (evidence mixed but recurring). | Bechtel & Berning 1991; Stuster 2010 (ISS journals); van Wijk 2018 | **Mission chapters** follow the transit; in the third quarter (days 91-135) crew operations count double. |
| Crews became progressively sedentary over a 520-day isolation. | Mars-500, Basner et al., PNAS 2013 | **Momentum guard:** when a person's 7-day completion drops (below 60%, or 15 points down), a day counts for the streak once the two core checks (Morning vitals, Mood & symptoms) are done. These days show as "eased". |
| Broken streaks reduce engagement; being able to repair a streak softens it. | Silverman & Barasch, Journal of Consumer Research 2023 | **Streak shields** (one per 7 streak days, max 2) and a **Back on Track** badge. |
| Habit automaticity takes a median of about 66 days; missing a day did not derail it. | Lally et al., European Journal of Social Psychology 2010 | **Habit Locked** counts 66 days done in total, not in a row. |
| Mars missions need Earth-independent medical operations. | NASA EIMO concept of operations, 2024 | All game logic runs on board; it never needs the Earth link. |

## Rules (enforced in code, shown on the Missions page)

- Scheduled check: dynamic XP, every line written to the ledger on its own so the XP log, the Alerts log and the
  result screen show exactly what was earned and why:
  - base: the task's XP, which scales with its effort (Sleep log 10, Morning vitals 30, Exercise block 40);
  - on time: +10 when done early or within 30 minutes of its time, +5 within 2 hours;
  - streak: +2 per streak day, up to +10, on every check while the streak runs;
  - Full orbit: +40 once a day, when every scheduled check of the day is done;
  - Welcome back: +15 on the first check after a missed day (coming back is what counts).
- Rewards show in the Alerts log (XP per action with its breakdown, levels reached, badges earned), with a calm
  accent dot on the launcher; the red count stays for health alerts only.
- Extra reading: +5, only the first per measurement per day (no farming).
- Close the loop: +10 for re-measuring within 2 days after a Watch or Act result, whatever the new value.
- Buddy check: +5, once per crewmate alert acknowledged (never your own).
- Personal quest: +30, once per quest per mission week. Quests come from the person's own medical history
  (for example, a past kidney stone makes "log fluid intake 5 days in a row" a quest).
- Emergency drill: +50, first completed drill.
- What a reading says: 0. Always.

Crew rewards (playlist, movie night, longer family video calls) unlock by crew-goal days in the mission week and
take effect once the Commander approves them on the Missions page (only the Commander can). Simulated readings never earn XP or count toward anything.
