"""ASTRA knowledge catalog.

Everything the crew sees about *what* to measure, *why*, *how space changes it* and *what to do*
lives here, next to the thresholds the rules engine uses. Keeping content and rules together means
the explanation an astronaut reads always matches the logic that classified their reading.

Thresholds carry a `sources` list: the id of every NASA document that backs them (see
`engine/app/sources.py`). The catalog does not invent a number it cannot point at.
"""

from __future__ import annotations

from typing import Any

from .sources import ENVIRONMENT_SOURCES, HAZARD_SOURCES, METRIC_SOURCES, ORGAN_SOURCES, SOURCES

MISSION = {
    "name": "MERIDIAN-1",
    "summary": "Long-duration exploration mission (fictional) used for the ASTRA demo.",
    # The mission is fictional, but its launch date is a real one inside the 2026-11-03..2026-11-14
    # Mars launch window, so the Earth-Mars light time ASTRA computes is the real one.
    "launch_utc": "2026-11-12T00:00:00Z",
}

# Mission clock used when the demo database is seeded: Day 142, 09:12 MET.
SEED_DAY = 142
SEED_SECONDS_OF_DAY = 9 * 3600 + 12 * 60
HISTORY_DAYS = 30
CAREER_LIMIT_MSV = 600.0
MISSION_DOSE_AT_SEED_MSV = 248.0

# How long the outbound leg of the Mars transit lasts, in mission days. The signal delay during
# transit is scaled from the real Earth-Mars light time over this span.
TRANSIT_DAYS = 180

# Solar conjunction: the Sun sits between Earth and Mars, so the radio link is degraded and the
# round trip can stretch to hours. ASTRA warns when the Sun-Earth-Mars elongation drops below
# this many degrees.
# TODO(verify): NASA does not publish a single "conjunction threshold" number; 3 degrees is the
# value ASTRA uses to flag a degraded link, and it is derived from the Horizons elongation
# column rather than quoted from a NASA document.
CONJUNCTION_SOT_DEG = 3.0
# How far ahead of the conjunction ASTRA starts warning the crew.
CONJUNCTION_WARNING_DAYS = 30

# The OSDR EDA cabin series starts with days of a constant 200 ppm, which the sensor reports
# before it has real data (outdoor air is about 420 ppm). Readings at or below this are dropped.
CABIN_FILL_PPM = 200.0
# The seeded demo moment (SEED_DAY) lands on this date of the real RR-7 series, a stretch where the
# 7-day CO2 average sits above the OCHMO 2.5 mmHg Watch level, so the demo opens on a real story.
CABIN_DEMO_DATE = "2018-07-24"

STATUSES = ("ok", "watch", "act")
STATUS_LABEL = {"ok": "Nominal", "watch": "Watch", "act": "Act"}

# --------------------------------------------------------------------------------------------
# Hazards (NASA Human Research Program: five hazards of human spaceflight, "RIDGE")
# --------------------------------------------------------------------------------------------
# Each hazard's "metrics" is derived from the metrics' own hazard lists (see below METRICS).
HAZARDS: list[dict[str, Any]] = [
    {
        "id": "R",
        "name": "Space radiation",
        "short": "Radiation",
        "summary": "Outside Earth's magnetic field, crews are exposed to galactic cosmic rays and solar "
        "particle events that damage cells and DNA.",
        "effects": [
            "Higher long-term cancer risk",
            "Possible effects on the central nervous system and cognition",
            "Cataracts and cardiovascular changes over time",
            "Acute radiation sickness during a strong solar particle event",
        ],
        "countermeasures": [
            "Track cumulative dose against the career limit",
            "Shelter in the most shielded module during solar storms",
            "Keep water and supplies placed as shielding",
        ],
    },
    {
        "id": "I",
        "name": "Isolation & confinement",
        "short": "Isolation",
        "summary": "Small crews live and work in a tiny volume for months, far from family, with little "
        "privacy and a fixed routine.",
        "effects": [
            "Low mood, stress and irritability",
            "Disturbed or shortened sleep",
            "Slower reactions and attention lapses",
            "Friction inside the crew",
        ],
        "countermeasures": [
            "Daily mood check-ins and private psychological support",
            "Protected sleep windows and lighting schedules",
            "Regular contact with family and meaningful leisure time",
        ],
    },
    {
        "id": "D",
        "name": "Distance from Earth",
        "short": "Distance",
        "summary": "The further the crew goes, the longer the communication delay and the longer it takes "
        "to get help, supplies or a ride home.",
        "effects": [
            "No quick evacuation: problems must be handled on board",
            "Signals to Mars take about 4-24 minutes one way",
            "Limited medicines, equipment and medical expertise",
        ],
        "countermeasures": [
            "Onboard decision support that works with zero connectivity",
            "Clear escalation: self-care, Crew Medical Officer, flight surgeon",
            "Store-and-forward summaries timed to communication windows",
        ],
    },
    {
        "id": "G",
        "name": "Gravity fields",
        "short": "Gravity",
        "summary": "Weightlessness during transit and partial gravity on the Moon (0.17 g) or Mars "
        "(0.38 g) change how bones, muscles, fluids and the heart behave.",
        "effects": [
            "Bone loss of roughly 1-1.5% per month in weight-bearing bones",
            "Muscle loss and weaker heart (deconditioning)",
            "Fluid shift toward the head: puffy face, congestion, SANS vision changes",
            "Dizziness and fainting when gravity returns",
        ],
        "countermeasures": [
            "About 2 hours of resistive and aerobic exercise every day",
            "Weekly vision self-checks",
            "Good hydration to protect the kidneys from bone calcium",
        ],
    },
    {
        "id": "E",
        "name": "Hostile closed environment",
        "short": "Environment",
        "summary": "The habitat is a sealed machine: its air, water, noise, temperature and microbes all "
        "affect the crew, and dust from the Moon or Mars is sharp and reactive.",
        "effects": [
            "CO2 build-up causing headaches and fatigue",
            "Infections spreading easily, immune changes, viral reactivation",
            "Dust irritating lungs and eyes after surface activities",
            "Noise and temperature disturbing sleep",
        ],
        "countermeasures": [
            "Watch breathing rate and blood oxygen, cross-check cabin CO2",
            "Hand hygiene and early symptom reporting",
            "Post-EVA breathing checks on surface missions",
        ],
    },
]

# --------------------------------------------------------------------------------------------
# Symptoms used by the daily symptom check
# --------------------------------------------------------------------------------------------
SYMPTOMS: list[dict[str, Any]] = [
    {"id": "headache", "label": "Headache", "organ": "brain", "red_flag": False},
    {"id": "fatigue", "label": "Unusual fatigue", "organ": "brain", "red_flag": False},
    {"id": "congestion", "label": "Nasal congestion", "organ": "lungs", "red_flag": False},
    {"id": "cough", "label": "Cough", "organ": "lungs", "red_flag": False},
    {"id": "sore_throat", "label": "Sore throat", "organ": "immune", "red_flag": False},
    {"id": "nausea", "label": "Nausea", "organ": "brain", "red_flag": False},
    {"id": "back_pain", "label": "Back pain", "organ": "musculo", "red_flag": False},
    {"id": "eye_irritation", "label": "Eye irritation", "organ": "eyes", "red_flag": False},
    {"id": "rash", "label": "Skin rash", "organ": "immune", "red_flag": False},
    {"id": "dizziness", "label": "Dizziness", "organ": "heart", "red_flag": False},
    {"id": "chest_pain", "label": "Chest pain or pressure", "organ": "heart", "red_flag": True},
    {"id": "short_breath", "label": "Shortness of breath", "organ": "lungs", "red_flag": True},
    {"id": "confusion", "label": "Confusion", "organ": "brain", "red_flag": True},
    {"id": "vision_loss", "label": "Sudden vision change", "organ": "eyes", "red_flag": True},
]
RED_FLAG_SYMPTOMS = {s["id"] for s in SYMPTOMS if s["red_flag"]}

# --------------------------------------------------------------------------------------------
# Metrics
#   ok / watch: inclusive [low, high] ranges. Outside "watch" means ACT.
#   ok2 / watch2: second value (diastolic blood pressure).
#   rule "relative": ranges are % change against the crew member's reference value.
#   min_sd: floor for the personal-baseline standard deviation (avoids silly z-scores).
#   red: thresholds that jump straight to tier 2 (flight surgeon).
# --------------------------------------------------------------------------------------------
METRICS: list[dict[str, Any]] = [
    {
        "id": "hr", "label": "Heart rate", "short": "HR", "unit": "bpm", "decimals": 0,
        "category": "Heart & circulation", "organ": "heart", "hazards": ["G", "I", "D"],
        "input": {"kind": "number", "min": 25, "max": 220, "step": 1, "placeholder": "64"},
        "ok": [50, 100], "watch": [40, 120], "axis": [35, 140], "min_sd": 4.0,
        "red": {"below": 40, "above": 140},
        # After exercise or an EVA the heart is still recovering, so a higher rate is expected.
        # TODO(verify): illustrative recovery bands for the 30 minutes after exertion, not taken from
        # a NASA document. A rate still above 150 bpm half an hour after exercise is not normal recovery.
        "context_sensitive": True,
        "active": {"ok": [50, 130], "watch": [40, 150], "red": {"below": 40, "above": 180}},
        "device": "Finger pulse oximeter or chest strap", "duration": "2 min",
        "how": [
            "Rest, seated or restrained, for 5 minutes. No exercise in the last 30 minutes.",
            "Clip the pulse oximeter on a warm fingertip, or wear the chest strap.",
            "Keep still for 30 seconds and read the beats per minute.",
        ],
        "why": "Resting heart rate is a quick window into the cardiovascular system. Fever, dehydration, "
        "stress, poor sleep and heart deconditioning all push it up.",
        "space": "In weightlessness the heart works less and can decondition. Fluid shift and stress change "
        "its rhythm, and returning to gravity can make it race.",
        "guide": {
            "ok": "Within your normal range. Keep your exercise routine going.",
            "watch": "Slightly out of range. Rest for 10 minutes, drink water and measure again. If it stays "
            "out of range, log how you feel and re-check in 4 hours.",
            "act": "Out of the safe range. Stop strenuous activity and measure again now. If confirmed, call "
            "the Crew Medical Officer. With chest pain, fainting or breathlessness, open EMERGENCY.",
        },
        "escalate": "Call the Crew Medical Officer if resting heart rate stays below 40 or above 120, or "
        "with palpitations, chest pain or fainting.",
        "prevent": ["Daily aerobic exercise", "2+ litres of fluids", "Protected sleep window"],
    },
    {
        "id": "bp", "label": "Blood pressure", "short": "BP", "unit": "mmHg", "decimals": 0,
        "category": "Heart & circulation", "organ": "heart", "hazards": ["G", "D"],
        "input": {"kind": "bp", "min": 50, "max": 260, "step": 1, "placeholder": "116/76"},
        "ok": [90, 129], "watch": [85, 139], "ok2": [60, 84], "watch2": [50, 89],
        "axis": [45, 170], "min_sd": 3.5,
        "red": {"above": 180, "below": 80, "above2": 110},
        # TODO(verify): illustrative post-exertion bands (systolic stays raised for a while after exercise).
        "context_sensitive": True,
        "active": {"ok": [90, 159], "watch": [85, 179], "ok2": [60, 89], "watch2": [50, 99],
                   "red": {"above": 200, "below": 80, "above2": 115}},
        "device": "Automatic upper-arm cuff", "duration": "3 min",
        "how": [
            "Sit or strap in with your feet supported and rest for 5 minutes.",
            "Wrap the cuff on your bare upper arm, 2 cm above the elbow, at heart level.",
            "Stay silent and still while it inflates. Record systolic / diastolic.",
        ],
        "why": "Blood pressure shows how hard the heart and vessels are working. It reveals cardiovascular "
        "strain early and helps prepare the body for gravity on landing.",
        "space": "Without gravity, about 2 litres of fluid shift toward the head. The body re-tunes blood "
        "pressure control, which can lead to dizziness or fainting when gravity returns.",
        "guide": {
            "ok": "Normal. No action needed.",
            "watch": "Borderline. Rest quietly for 15 minutes and measure again. Go easy on salt and caffeine "
            "today and re-check tonight.",
            "act": "Out of range. Measure again on the other arm. If it is still 140/90 or higher, or the top "
            "number is below 85, notify the Crew Medical Officer. With headache, vision change or chest "
            "pain, open EMERGENCY.",
        },
        "escalate": "Call the Crew Medical Officer for repeated readings of 140/90 or higher, systolic below "
        "85, or symptoms such as headache, dizziness or vision change.",
        "prevent": ["Aerobic exercise", "Moderate salt", "Hydration", "Stress management"],
    },
    {
        "id": "spo2", "label": "Blood oxygen", "short": "SpO₂", "unit": "%", "decimals": 0,
        "category": "Lungs & breathing", "organ": "lungs", "hazards": ["E", "D"],
        "input": {"kind": "number", "min": 50, "max": 100, "step": 1, "placeholder": "98"},
        "ok": [95, 100], "watch": [92, 100], "axis": [84, 100], "min_sd": 0.8,
        "red": {"below": 90},
        "device": "Finger pulse oximeter", "duration": "1 min",
        "how": [
            "Warm your hand and remove anything covering the fingertip.",
            "Clip the oximeter on and keep the hand still at heart level.",
            "Wait 30 seconds for a stable reading.",
        ],
        "why": "Oxygen saturation shows whether your lungs, blood and the cabin air are doing their job.",
        "space": "A sealed cabin can build up CO2. Lunar and Martian dust can irritate the airways, and a "
        "chest infection spreads easily in a small crew.",
        "guide": {
            "ok": "Normal.",
            "watch": "A bit low. Measure on another finger and check the cabin CO2 / O2 display. Take slow, "
            "deep breaths and re-check in 10 minutes.",
            "act": "Low oxygen. Measure again now. If confirmed, call the Crew Medical Officer and check the "
            "cabin atmosphere. With breathlessness or confusion, open EMERGENCY.",
        },
        "escalate": "Call the Crew Medical Officer if SpO2 stays below 92%, and immediately if below 90% or "
        "with breathlessness.",
        "prevent": ["Monitor cabin CO2", "Keep dust out after EVAs", "Report coughs early"],
    },
    {
        "id": "resp", "label": "Breathing rate", "short": "RR", "unit": "/min", "decimals": 0,
        "category": "Lungs & breathing", "organ": "lungs", "hazards": ["E"],
        "input": {"kind": "number", "min": 4, "max": 60, "step": 1, "placeholder": "15"},
        "ok": [12, 20], "watch": [10, 24], "axis": [6, 32], "min_sd": 1.0,
        "red": {"above": 30, "below": 8},
        # TODO(verify): illustrative post-exertion bands.
        "context_sensitive": True,
        "active": {"ok": [12, 28], "watch": [10, 34], "red": {"above": 40, "below": 8}},
        "device": "Timer (or wearable)", "duration": "1 min",
        "how": [
            "Sit still for 2 minutes.",
            "Count breaths for 30 seconds: one rise and fall is one breath. A crewmate can count quietly.",
            "Multiply by 2.",
        ],
        "why": "Breathing rate rises early with infection, fever, high CO2, anxiety or heart strain, often "
        "before anything else changes.",
        "space": "CO2 pockets can form where air does not circulate, such as around a sleeping bag. Fast "
        "breathing can be the body's first response.",
        "guide": {
            "ok": "Normal.",
            "watch": "Re-count after 5 minutes of calm breathing. Check temperature and SpO2 as well.",
            "act": "Call the Crew Medical Officer and check the cabin CO2. With breathlessness or chest pain, "
            "open EMERGENCY.",
        },
        "escalate": "Call the Crew Medical Officer if breathing stays above 24 per minute at rest.",
        "prevent": ["Ventilate sleeping areas", "Hand hygiene", "Post-EVA dust control"],
    },
    {
        "id": "temp", "label": "Body temperature", "short": "Temp", "unit": "°C", "decimals": 1,
        "category": "Immune & metabolism", "organ": "immune", "hazards": ["E", "R", "D"],
        "input": {"kind": "number", "min": 30, "max": 43, "step": 0.1, "placeholder": "36.9"},
        "ok": [36.1, 37.5], "watch": [35.5, 38.0], "axis": [35.0, 39.6], "min_sd": 0.15,
        "red": {"above": 39.5, "below": 35.0},
        "device": "Oral or forehead thermometer", "duration": "2 min",
        "how": [
            "No eating, drinking or exercise for 15 minutes before measuring.",
            "Place the thermometer under the tongue, or use the forehead sensor.",
            "Wait for the beep and record °C.",
        ],
        "why": "Fever is the body's first infection alarm. In a closed habitat, catching an infection early "
        "protects the whole crew.",
        "space": "Immune function changes in space, and dormant viruses can reactivate. Crew core temperature "
        "can also run up to about 1 °C higher on long missions, so ASTRA also flags a reading that is unusual "
        "for you, even inside the normal range.",
        "guide": {
            "ok": "Normal.",
            "watch": "Slightly off. Drink fluids, rest and re-check in 2 hours. Note any chills, cough or "
            "sore throat.",
            "act": "Fever above 38 °C (or below 35.5 °C). Notify the Crew Medical Officer, limit close "
            "contact with crewmates and log symptoms every 2 hours.",
        },
        "escalate": "Call the Crew Medical Officer for any fever above 38 °C, and immediately above 39.5 °C.",
        "prevent": ["Hand hygiene", "Separate personal items", "Sleep and nutrition"],
    },
    {
        "id": "glucose", "label": "Blood glucose", "short": "Glucose", "unit": "mg/dL", "decimals": 0,
        "category": "Immune & metabolism", "organ": "metabolism", "hazards": ["G", "D"],
        "input": {"kind": "number", "min": 20, "max": 600, "step": 1, "placeholder": "88"},
        "ok": [70, 99], "watch": [55, 125], "axis": [40, 170], "min_sd": 4.0,
        "red": {"below": 54, "above": 250},
        "device": "Finger-stick glucometer", "duration": "2 min",
        "how": [
            "Measure fasting, before breakfast.",
            "Clean the fingertip and lance its side. In weightlessness the blood forms a dome and won't drip.",
            "Touch the strip to the drop and read mg/dL.",
        ],
        "why": "Glucose shows how the body turns food into energy and links nutrition, activity and "
        "metabolism.",
        "space": "Spaceflight can reduce insulin sensitivity, and long missions have a fixed, limited menu. "
        "Lower activity makes it worse.",
        "guide": {
            "ok": "Normal fasting level.",
            "watch": "Outside the fasting target. If low (below 70): eat 15 g of fast carbohydrate and re-test "
            "in 15 minutes. If high: re-test tomorrow fasting and review meals and activity.",
            "act": "Out of range. Below 55: take fast carbohydrate now, re-test in 15 minutes and tell a "
            "crewmate. 126 or higher fasting: re-test and notify the Crew Medical Officer.",
        },
        "escalate": "Call the Crew Medical Officer for fasting values of 126 or higher on two days, or any "
        "value below 55.",
        "prevent": ["Eat the full planned menu", "Daily exercise", "Regular meal times"],
    },
    {
        "id": "hydration", "label": "Fluid intake", "short": "Fluids", "unit": "L", "decimals": 1,
        "category": "Immune & metabolism", "organ": "kidneys", "hazards": ["G", "E"],
        "input": {"kind": "number", "min": 0, "max": 8, "step": 0.1, "placeholder": "2.2"},
        "ok": [2.0, 5.0], "watch": [1.5, 6.0], "axis": [0.5, 5.5], "min_sd": 0.15,
        "red": {},
        "device": "Drink bag counter / water dispenser log", "duration": "30 s",
        "how": [
            "Add up the drink bags and water you have had today.",
            "Include water used to rehydrate food.",
            "Enter the total in litres.",
        ],
        "why": "Fluids keep blood volume and the kidneys healthy and help you think clearly.",
        "space": "You feel less thirsty in weightlessness. Calcium released from shrinking bones raises the "
        "risk of kidney stones, and plenty of water lowers it.",
        "guide": {
            "ok": "Good hydration. Keep it steady.",
            "watch": "A bit low. Drink 500 ml over the next hour and set a reminder.",
            "act": "Too low (or too high). Drink steadily to reach at least 2 L, and tell the Crew Medical "
            "Officer if you have flank pain or dark urine.",
        },
        "escalate": "Call the Crew Medical Officer for flank or back pain with low intake. It can be a "
        "kidney stone.",
        "prevent": ["Keep a drink bag in sight", "Drink with every meal", "Extra water on exercise days"],
    },
    {
        "id": "mass", "label": "Body mass", "short": "Mass", "unit": "kg", "decimals": 1, "rule": "relative",
        "category": "Immune & metabolism", "organ": "metabolism", "hazards": ["G"],
        "input": {"kind": "number", "min": 30, "max": 150, "step": 0.1, "placeholder": "70.0"},
        "ok": [-3, 3], "watch": [-5, 5], "axis": None, "min_sd": 0.3,
        "red": {},
        "device": "Inertial body-mass measurement device", "duration": "3 min",
        "how": [
            "Measure before breakfast, after using the toilet.",
            "Strap into the mass device and hold still while it oscillates. Scales don't work in weightlessness.",
            "Read the mass in kg.",
        ],
        "why": "Weight loss is an early sign that you are not eating enough or are losing muscle.",
        "space": "Appetite often drops in space, and muscle shrinks without gravity. Many crews lose weight "
        "without noticing.",
        "guide": {
            "ok": "Within 3% of your mission reference mass.",
            "watch": "3-5% change from your reference. Eat the full menu, add snacks, and keep resistive "
            "exercise.",
            "act": "More than 5% change. Tell the Crew Medical Officer and review your diet plan with ground "
            "nutrition.",
        },
        "escalate": "Call the Crew Medical Officer for a change of more than 5% from your reference mass.",
        "prevent": ["Eat all planned meals", "Resistive exercise", "Weekly weigh-ins"],
    },
    {
        "id": "nutrition", "label": "Food intake", "short": "Food", "unit": "%", "decimals": 0,
        "category": "", "organ": "metabolism", "hazards": ["I", "D"],
        "input": {"kind": "number", "min": 0, "max": 200, "step": 5, "placeholder": "100"},
        "ok": [90, 130], "watch": [75, 150], "axis": [40, 160], "min_sd": 6,
        "red": {},
        "device": "Meal plan / food log", "duration": "1 min",
        "how": [
            "Look at today's meal plan.",
            "Estimate how much of it you ate, as a percentage: the full plan is 100%.",
            "Count snacks and drinks that have calories.",
        ],
        "why": "Eating enough protects muscle, bone, immunity and mood. Under-eating is common on long missions "
        "and slowly weakens every other system.",
        "space": "Appetite drops in weightlessness, food gets monotonous and some vitamins degrade over months, "
        "so crews often eat only about 80% of what they need. Calcium and vitamin D matter more while bones are "
        "losing mass.",
        "guide": {
            "ok": "Good. You're eating to plan.",
            "watch": "Below plan. Add a snack with protein, try a different menu item or share a crew meal.",
            "act": "Well below plan (or far above it). Tell the Crew Medical Officer, especially with weight "
            "loss, nausea or low mood.",
        },
        "escalate": "Call the Crew Medical Officer if you eat less than 75% of plan for 3 days, or with weight "
        "loss above 3%.",
        "prevent": ["Eat with the crew", "Rotate menu items", "Protein at every meal",
                    "Calcium and vitamin D as prescribed"],
    },
    {
        "id": "sleep", "label": "Sleep", "short": "Sleep", "unit": "h", "decimals": 1,
        "category": "Mind & sleep", "organ": "brain", "hazards": ["I"],
        "input": {"kind": "number", "min": 0, "max": 16, "step": 0.1, "placeholder": "7.5"},
        "ok": [7.0, 9.5], "watch": [6.0, 12.0], "axis": [3.5, 10.0], "min_sd": 0.3,
        "red": {},
        "device": "Sleep watch (actigraphy) or sleep log", "duration": "30 s",
        "how": [
            "Read last night's hours from your sleep watch, or estimate from lights-out to wake-up.",
            "Subtract time spent awake during the night.",
            "Note what disturbed you: noise, light, temperature or worries.",
        ],
        "why": "Sleep debt quietly erodes mood, reaction time and safety, and you often don't notice it "
        "yourself.",
        "space": "Noise, workload, odd light cycles (16 sunrises a day in orbit) and isolation shorten crew "
        "sleep. Many astronauts average under 6.5 hours.",
        "guide": {
            "ok": "Good night. Keep the same sleep window.",
            "watch": "Short night. Protect tonight's 8.5-hour window, dim screens an hour before bed and "
            "avoid caffeine after 14:00.",
            "act": "Serious sleep debt. Tell the Commander before any critical task, schedule recovery sleep "
            "and talk to the Crew Medical Officer about sleep support.",
        },
        "escalate": "Tell the Crew Medical Officer if sleep is under 6 hours on 3 nights in a row.",
        "prevent": ["Fixed sleep window", "Lighting schedule", "Eye mask and ear plugs"],
    },
    {
        "id": "mood", "label": "Mood", "short": "Mood", "unit": "/5", "decimals": 0,
        "category": "Mind & sleep", "organ": "brain", "hazards": ["I"],
        "input": {"kind": "mood", "min": 1, "max": 5, "step": 1, "placeholder": "4",
                  "labels": ["Awful", "Low", "Okay", "Good", "Great"]},
        "ok": [4, 5], "watch": [3, 5], "axis": [1, 5], "min_sd": 0.45,
        "red": {},
        "device": "Self-report", "duration": "30 s",
        "how": [
            "Pause for 30 seconds and notice how you feel right now.",
            "Pick the face that fits best. There is no wrong answer.",
            "Your answer stays private unless you choose to share it.",
        ],
        "why": "Low mood is easier to fix early, and it protects the whole crew's cohesion.",
        "space": "Isolation, confinement, monotony and distance from loved ones are major spaceflight hazards "
        "on long missions.",
        "guide": {
            "ok": "Good. Keep the routines that help you.",
            "watch": "A bit low. Plan something you enjoy, call family at the next comm window, and get some "
            "exercise and light.",
            "act": "Low mood. You're not alone. Talk to a trusted crewmate or the Crew Medical Officer today, "
            "and book a private session with ground psychological support.",
        },
        "escalate": "Talk to the Crew Medical Officer if mood stays at 2 or lower, or 3 for a week.",
        "prevent": ["Leisure time", "Family calls", "Exercise", "Shared crew meals"],
    },
    {
        "id": "reaction", "label": "Reaction time", "short": "Reaction", "unit": "ms", "decimals": 0,
        "category": "Mind & sleep", "organ": "brain", "hazards": ["I", "R"],
        "input": {"kind": "reaction", "min": 100, "max": 2000, "step": 1, "placeholder": "260"},
        "ok": [100, 320], "watch": [100, 400], "axis": [180, 480], "min_sd": 12,
        "red": {},
        "device": "This tablet: tap test", "duration": "1 min",
        "how": [
            "Sit comfortably with your finger ready.",
            "Tap the pad the moment it turns green. There are 3 trials.",
            "Your score is the average.",
        ],
        "why": "A one-minute alertness test. Fatigue, sleep debt, stress and high CO2 slow you down before "
        "you notice. It matters before EVAs, docking or driving a rover.",
        "space": "Sleep loss, workload and radiation exposure can all affect attention and reaction speed.",
        "guide": {
            "ok": "Sharp. Good to go for critical tasks.",
            "watch": "Slower than usual. Avoid critical tasks for now, rest, drink water and re-test in 2 hours.",
            "act": "Much slower. Do not perform critical operations. Tell the Commander and re-test after "
            "sleep.",
        },
        "escalate": "Tell the Commander before any critical task if reaction time is above 400 ms.",
        "prevent": ["Sleep", "Breaks between tasks", "Check cabin CO2"],
    },
    {
        "id": "exercise", "label": "Exercise", "short": "Exercise", "unit": "min", "decimals": 0,
        "category": "Bones & muscles", "organ": "musculo", "hazards": ["G"],
        "input": {"kind": "number", "min": 0, "max": 400, "step": 5, "placeholder": "120"},
        "ok": [120, 600], "watch": [60, 600], "axis": [0, 200], "min_sd": 8,
        "red": {},
        "device": "Resistive device, treadmill, cycle", "duration": "2 h",
        "how": [
            "Do resistive loading (squats, deadlifts, heel raises) plus aerobic work (treadmill or cycle).",
            "Count the warm-up but not the breaks.",
            "Enter today's total minutes.",
        ],
        "why": "Loading bones and muscles every day is the main defence against bone loss and "
        "deconditioning.",
        "space": "Unloaded bones lose roughly 1-1.5% of their mass per month, most at the hips and spine. "
        "Space-station crews exercise about 2 hours a day to slow this.",
        "guide": {
            "ok": "Target met. Your bones and muscles thank you.",
            "watch": "Below the 2-hour target. Add a resistive session today that loads the legs, hips and "
            "spine.",
            "act": "Far below target. Tell the Commander. Rescheduling exercise is a mission priority, not "
            "an option.",
        },
        "escalate": "Tell the Commander if exercise falls below 60 minutes on 2 days in a row.",
        "prevent": ["Book exercise like any other task", "Train with a crewmate", "Track loads"],
    },
    {
        "id": "vision", "label": "Vision check", "short": "Vision", "unit": "", "decimals": 0,
        "category": "Bones & muscles", "organ": "eyes", "hazards": ["G", "R"],
        "input": {"kind": "amsler", "min": 0, "max": 2, "step": 1, "placeholder": "0",
                  "labels": ["No distortion", "Slight blur", "Wavy or missing lines"]},
        "ok": [0, 0], "watch": [0, 1], "axis": [0, 2], "min_sd": 0.3,
        "red": {},
        "device": "Amsler grid on this tablet", "duration": "2 min",
        "how": [
            "Hold the tablet at reading distance in good light. Wear your usual glasses.",
            "Cover one eye and look only at the centre dot.",
            "Notice whether any lines look wavy, blurred or missing. Then repeat with the other eye.",
        ],
        "why": "A simple weekly self-check that catches vision changes early.",
        "space": "Fluid shift toward the head raises pressure behind the eyes. Many long-duration crew "
        "members develop Spaceflight-Associated Neuro-ocular Syndrome (SANS): optic-disc swelling, "
        "flattening of the eye and blurred near vision.",
        "guide": {
            "ok": "No distortion. Check again next week.",
            "watch": "Slight blur. Re-check tomorrow and mention it to the Crew Medical Officer. The ground "
            "team may request an eye ultrasound.",
            "act": "Lines look wavy or missing. Tell the Crew Medical Officer today. An onboard eye "
            "examination is needed.",
        },
        "escalate": "Tell the Crew Medical Officer about any new blur, wavy or missing lines.",
        "prevent": ["Weekly check", "Report early", "Fluid-shift countermeasures if prescribed"],
    },
    {
        "id": "symptoms", "label": "Symptom check", "short": "Symptoms", "unit": "", "decimals": 0,
        "category": "Mind & sleep", "organ": "general", "hazards": ["E", "I", "R", "D"],
        "input": {"kind": "symptoms", "min": 0, "max": 20, "step": 1, "placeholder": "0"},
        "ok": [0, 0], "watch": [0, 2], "axis": [0, 5], "min_sd": 0.5,
        "red": {},
        "device": "Self-report", "duration": "1 min",
        "how": [
            "Think about the last 24 hours.",
            "Tick every symptom you noticed, even mild ones.",
            "Red-flag symptoms (chest pain, breathlessness, confusion, sudden vision change) mean EMERGENCY.",
        ],
        "why": "Small symptoms often appear before measurements change. Patterns across the crew can reveal "
        "an infection or an air-quality problem.",
        "space": "Headaches (CO2), congestion (fluid shift), back pain (spine lengthening) and nausea are "
        "common in spaceflight.",
        "guide": {
            "ok": "No symptoms. Great.",
            "watch": "Some symptoms. Rest, drink water and re-check tomorrow. ASTRA will watch for patterns.",
            "act": "Several symptoms, or a red-flag symptom. Tell the Crew Medical Officer now. Red-flag "
            "symptoms: open EMERGENCY.",
        },
        "escalate": "Any red-flag symptom means an immediate call to the Crew Medical Officer and EMERGENCY.",
        "prevent": ["Hand hygiene", "Cabin air checks", "Stretching for back pain"],
    },
]
METRIC_BY_ID: dict[str, dict[str, Any]] = {m["id"]: m for m in METRICS}

# --------------------------------------------------------------------------------------------
# Measurement context
#   Heart rate, blood pressure and breathing rate depend on what the crew member was doing just
#   before. Resting ranges only apply at rest; after exercise or an EVA ASTRA uses the metric's
#   "active" bands, keeps the reading out of the personal baseline, and asks for a resting re-check.
# --------------------------------------------------------------------------------------------
CONTEXTS: list[dict[str, Any]] = [
    {"id": "rest", "label": "Resting", "detail": "Seated or restrained for 5+ minutes, no exercise in the "
     "last 30 minutes", "active": False},
    {"id": "just_woke", "label": "Just woke up", "detail": "Before getting up or moving around", "active": False},
    {"id": "after_exercise", "label": "After exercise", "detail": "Within 30 minutes of a workout",
     "active": True},
    {"id": "after_eva", "label": "After an EVA", "detail": "Within an hour of a spacewalk or heavy suit work",
     "active": True},
]
CONTEXT_BY_ID: dict[str, dict[str, Any]] = {c["id"]: c for c in CONTEXTS}
ACTIVE_CONTEXTS = {c["id"] for c in CONTEXTS if c["active"]}
DEFAULT_CONTEXT = "rest"
# A resting reading needs this long since exercise; an exercise log inside it makes ASTRA read the
# measurement as post-exercise.
RECENT_EXERCISE_S = 30 * 60
# Routine tasks whose readings are taken after exertion by design.
TASK_CONTEXT = {"post_eva": "after_eva"}
RECHECK_AFTER_MIN = 30

# --------------------------------------------------------------------------------------------
# Organs (body map)
# --------------------------------------------------------------------------------------------
ORGANS: list[dict[str, Any]] = [
    {
        "id": "brain", "name": "Brain & behavior", "metrics": ["sleep", "mood", "reaction"],
        "hazards": ["I", "D", "R"],
        "function": "Controls mood, sleep, attention, decisions and, with the inner ear, balance: the crew's most "
        "important tool.",
        "space": "Isolation, confinement, odd light cycles and workload disturb sleep and mood. Deep-space "
        "radiation may affect cognition over long missions. The inner ear's balance organs misread weightlessness "
        "at first (space motion sickness) and again after landing, when balance takes days to recover.",
        "actions": ["Protect an 8.5-hour sleep window", "Use scheduled lighting",
                    "Call family or psych support at the next comm window"],
    },
    {
        "id": "eyes", "name": "Eyes & vision", "metrics": ["vision"], "hazards": ["G", "R", "E"],
        "function": "Vision for every task, from reading displays to docking.",
        "space": "Fluid shift toward the head can swell the optic disc, where the optic nerve enters the eye, and "
        "flatten the eye: "
        "Spaceflight-Associated Neuro-ocular Syndrome (SANS).",
        "actions": ["Weekly Amsler grid self-check", "Report any new blur", "Ground may request an eye ultrasound"],
    },
    {
        "id": "heart", "name": "Heart & circulation", "metrics": ["hr", "bp"], "hazards": ["G", "R"],
        "function": "Pumps blood and oxygen to every organ.",
        "space": "With less work to do the heart can decondition. Fluid shift changes blood pressure, and "
        "returning to gravity can cause dizziness or fainting.",
        "actions": ["Daily aerobic exercise", "At least 2 L of fluids", "Report chest pain or fainting at once"],
    },
    {
        "id": "lungs", "name": "Lungs & breathing", "metrics": ["spo2", "resp"], "hazards": ["E"],
        "function": "Brings oxygen in and removes CO2.",
        "space": "CO2 can build up in a sealed cabin. On the Moon and Mars, fine reactive dust can irritate "
        "the airways after EVAs.",
        "actions": ["Check cabin CO2 if you have a headache", "Dust control after EVAs",
                    "Re-measure SpO2 if breathless"],
    },
    {
        "id": "metabolism", "name": "Metabolism & nutrition", "metrics": ["glucose", "mass", "nutrition"],
        "hazards": ["D", "E"],
        "function": "Turns food into energy and keeps blood sugar stable.",
        "space": "Appetite changes, a limited menu and less activity can lead to weight loss and lower "
        "insulin sensitivity.",
        "actions": ["Eat the full planned menu", "Weekly body-mass check", "Fasting glucose each morning"],
    },
    {
        "id": "immune", "name": "Immune system", "metrics": ["temp"], "hazards": ["R", "E", "I"],
        "function": "Defends against infection. Fever is its alarm signal.",
        "space": "Stress, radiation and closed living change immune function. Dormant viruses can reactivate, "
        "and microbes spread easily in a sealed habitat.",
        "actions": ["Hand hygiene", "Report fever or sore throat early", "Keep personal items separate if ill"],
    },
    {
        "id": "kidneys", "name": "Kidneys & fluids", "metrics": ["hydration"], "hazards": ["G", "E"],
        "function": "Filter the blood and balance fluids and minerals.",
        "space": "Calcium released from shrinking bones raises kidney-stone risk, and the sense of thirst is "
        "weaker in weightlessness.",
        "actions": ["Drink at least 2 L a day", "Extra water on exercise days", "Report flank pain"],
    },
    {
        "id": "musculo", "name": "Bones & muscles", "metrics": ["exercise"], "hazards": ["G"],
        "function": "Bones and muscles give support, movement and calcium storage.",
        "space": "Unloaded bones lose roughly 1-1.5% of their mass per month, most at the hips and spine. "
        "Anti-gravity muscles of the calves, thighs, hips and back waste fastest, and the spine lengthens, "
        "causing back pain.",
        "actions": ["About 2 hours of exercise daily", "Load the hips, legs and spine", "Stretch for back pain"],
    },
]
ORGAN_BY_ID: dict[str, dict[str, Any]] = {o["id"]: o for o in ORGANS}
SYMPTOM_BY_ID: dict[str, dict[str, Any]] = {s["id"]: s for s in SYMPTOMS}

# One source of truth for hazard links: each metric names the hazards it watches. A hazard lists exactly the
# metrics that name it, and a body system carries every hazard of its metrics (plus any it names itself).
for _h in HAZARDS:
    _h["metrics"] = [m["id"] for m in METRICS if _h["id"] in m["hazards"]]
for _o in ORGANS:
    _linked = {h for k in _o["metrics"] for h in METRIC_BY_ID[k]["hazards"]} | set(_o["hazards"])
    _o["hazards"] = [h["id"] for h in HAZARDS if h["id"] in _linked]
# Measurements are grouped by the body system they belong to, everywhere in the app.
for _m in METRICS:
    _m["category"] = ORGAN_BY_ID[_m["organ"]]["name"] if _m["organ"] in ORGAN_BY_ID else "General"

# Every threshold, hazard and body system points at the NASA documents behind it.
# (Environments are attached further down, once ENVIRONMENTS exists.)
for _m in METRICS:
    _m["sources"] = list(METRIC_SOURCES.get(_m["id"], []))
for _h in HAZARDS:
    _h["sources"] = list(HAZARD_SOURCES.get(_h["id"], []))
for _o in ORGANS:
    _o["sources"] = list(ORGAN_SOURCES.get(_o["id"], []))

# --------------------------------------------------------------------------------------------
# Environments
# --------------------------------------------------------------------------------------------
ENVIRONMENTS: list[dict[str, Any]] = [
    {
        "id": "transit", "name": "Mars transit vehicle", "kind": "Spacecraft", "location": "Deep space",
        "gravity_g": 0.0, "gravity": "0 g · microgravity", "delay_s": 760.0,
        "delay_note": "varies 4-24 min with planet positions", "radiation_msv_day": 1.84,
        "evacuation": "None. Return to Earth is months away.",
        "med_kit": "Full onboard medical kit with ultrasound and defibrillator",
        "risks": ["No evacuation", "Highest radiation dose", "Long comm delay", "Bone and muscle loss"],
        "tip": "Deep space, no evacuation. ASTRA runs fully on board, and a reply from Earth takes about 25 "
        "minutes round-trip.",
        "extra_tasks": [],
    },
    {
        "id": "station", "name": "Space station (low Earth orbit)", "kind": "Space station",
        "location": "Low Earth orbit", "gravity_g": 0.0, "gravity": "µg · microgravity",
        "delay_s": 0.5, "delay_note": "near real-time link", "radiation_msv_day": 0.5,
        "evacuation": "Emergency return to Earth possible within hours",
        "med_kit": "Station medical kit, ultrasound, defibrillator",
        "risks": ["Bone and muscle loss", "Fluid shift and SANS", "Sleep disruption (16 sunrises a day)"],
        "tip": "The flight surgeon is available almost in real time, and an emergency return to Earth is "
        "possible within hours.",
        "extra_tasks": [],
    },
    {
        "id": "rover", "name": "Pressurized lunar rover", "kind": "Rover", "location": "Moon",
        "gravity_g": 0.17, "gravity": "0.17 g · lunar gravity", "delay_s": 1.3,
        "delay_note": "1.3 s each way",
        # TODO(verify): planning estimate for the lunar surface, not yet tied to a NASA measurement
        # (the MSL/RAD rates are for deep space and Mars). Shown as an estimate in the app.
        "radiation_msv_day": 1.4,
        "evacuation": "Drive back to base (hours), then days to Earth",
        "med_kit": "Compact rover kit, limited oxygen reserve",
        "risks": ["Lunar dust in lungs and eyes", "Small cabin", "Limited medical kit", "Higher radiation"],
        "tip": "Small cabin, limited medical kit. Lunar dust irritates lungs and eyes, so watch SpO2 and "
        "breathing rate after every EVA.",
        "extra_tasks": [{"id": "post_eva", "time": "16:30", "title": "Post-EVA breathing check",
                         "metrics": ["spo2", "resp"], "xp": 20}],
    },
    {
        "id": "lunar", "name": "Lunar surface base", "kind": "Surface base", "location": "Moon",
        "gravity_g": 0.17, "gravity": "0.17 g · lunar gravity", "delay_s": 1.3,
        "delay_note": "1.3 s each way",
        # TODO(verify): planning estimate for the lunar surface, not yet tied to a NASA measurement.
        "radiation_msv_day": 0.6,
        "evacuation": "Return to Earth takes days",
        "med_kit": "Base medical bay with ultrasound and defibrillator",
        "risks": ["Partial-gravity bone loss", "Lunar dust", "Isolation"],
        "tip": "One-sixth gravity still unloads your bones, so keep resistive exercise. Getting home takes "
        "days, not hours.",
        "extra_tasks": [{"id": "post_eva", "time": "16:30", "title": "Post-EVA breathing check",
                         "metrics": ["spo2", "resp"], "xp": 20}],
    },
    {
        "id": "mars", "name": "Mars surface base", "kind": "Surface base", "location": "Mars",
        "gravity_g": 0.38, "gravity": "0.38 g · Mars gravity", "delay_s": 760.0,
        "delay_note": "varies 4-24 min with planet positions", "radiation_msv_day": 0.64,
        "evacuation": "None. Earth return windows open every 26 months.",
        "med_kit": "Base medical bay, limited resupply",
        "risks": ["Long comm delay", "Martian dust (perchlorates)", "Isolation", "Partial-gravity deconditioning"],
        "tip": "About 0.64 mSv/day on the surface. Dust storms can cut power and delay EVAs, so medical "
        "autonomy is essential.",
        "extra_tasks": [{"id": "post_eva", "time": "16:30", "title": "Post-EVA breathing check",
                         "metrics": ["spo2", "resp"], "xp": 20}],
    },
]
ENV_BY_ID: dict[str, dict[str, Any]] = {e["id"]: e for e in ENVIRONMENTS}
DEFAULT_ENV = "transit"

# The NASA documents behind each environment's numbers.
for _e in ENVIRONMENTS:
    _e["sources"] = list(ENVIRONMENT_SOURCES.get(_e["id"], []))

# --------------------------------------------------------------------------------------------
# Crew (fictional)
# --------------------------------------------------------------------------------------------
CREW: list[dict[str, Any]] = [
    {"id": "ana", "name": "Ana Ribeiro", "title": "Cdr.", "role": "Commander", "initials": "AR",
     "hue": 196, "prior_dose_msv": 60.0, "base_xp": 1340, "mass_ref": 64.0, "is_cmo": False},
    {"id": "kenji", "name": "Kenji Arai", "title": "Dr.", "role": "Crew Medical Officer", "initials": "KA",
     "hue": 262, "prior_dose_msv": 110.0, "base_xp": 1580, "mass_ref": 72.0, "is_cmo": True},
    {"id": "sara", "name": "Sara Okafor", "title": "Eng.", "role": "Flight Engineer", "initials": "SO",
     "hue": 152, "prior_dose_msv": 0.0, "base_xp": 1720, "mass_ref": 61.0, "is_cmo": False},
    {"id": "lucas", "name": "Lucas Moreau", "title": "Dr.", "role": "Mission Specialist", "initials": "LM",
     "hue": 28, "prior_dose_msv": 35.0, "base_xp": 980, "mass_ref": 78.0, "is_cmo": False},
]
CREW_BY_ID: dict[str, dict[str, Any]] = {c["id"]: c for c in CREW}

# Fictional crew profiles. History items name the indicators they make more likely to drift ("watch"), and
# "influence" says how, so the profile can link a past condition to today's readings.
CREW_PROFILES: dict[str, dict[str, Any]] = {
    "ana": {
        "age": 46, "nationality": "Brazil", "height_cm": 168, "blood_type": "O+",
        "background": "Former test pilot. Third long-duration flight; leads EVA planning.",
        "career": {"days_in_space": 402, "evas": 4, "eva_hours": 27.5},
        "missions": [
            {"name": "ISS Expedition 58/59", "year": 2018, "days": 186},
            {"name": "Gateway crew rotation 2", "year": 2024, "days": 74},
        ],
        "allergies": ["Penicillin (rash)"],
        "medications": ["Melatonin 3 mg as needed for sleep shifts"],
        "history": [
            {"year": 2019, "condition": "Kidney stone (left, passed)", "status": "resolved",
             "watch": ["hydration"],
             "influence": "Bone loss in microgravity raises urine calcium. With her history, low fluid intake "
                          "is the main lever for a repeat stone."},
            {"year": 2018, "condition": "Sleep disruption on ISS", "status": "managed",
             "watch": ["sleep", "mood", "reaction"],
             "influence": "Short sleep showed up as slower reaction times and low mood on her last flight. "
                          "Watch for the same pattern before EVAs."},
        ],
    },
    "kenji": {
        "age": 41, "nationality": "Japan", "height_cm": 174, "blood_type": "A+",
        "background": "Emergency physician and the crew's medical officer. Second flight.",
        "career": {"days_in_space": 318, "evas": 1, "eva_hours": 6.8},
        "missions": [{"name": "ISS Expedition 66/67", "year": 2021, "days": 175}],
        "allergies": [],
        "medications": ["Corrective lenses (-2.25 D)"],
        "history": [
            {"year": 2022, "condition": "Borderline high blood pressure", "status": "monitoring",
             "watch": ["bp", "hr"],
             "influence": "Family history of hypertension. Fluid shifts and stress in flight can push his "
                          "pressure up first; diet and aerobic exercise kept it in range on the ground."},
            {"year": 2021, "condition": "Mild optic disc swelling after ISS flight (SANS)", "status": "monitoring",
             "watch": ["vision"],
             "influence": "Crew who had SANS before are more likely to get it again. Any blur or change on the "
                          "weekly vision check should be reported early."},
        ],
    },
    "sara": {
        "age": 36, "nationality": "Nigeria", "height_cm": 165, "blood_type": "B+",
        "background": "Life-support engineer. First long-duration flight.",
        "career": {"days_in_space": 143, "evas": 2, "eva_hours": 13.1},
        "missions": [],
        "allergies": ["Shellfish"],
        "medications": [],
        "history": [
            {"year": 2016, "condition": "Right knee ACL reconstruction", "status": "resolved",
             "watch": ["exercise", "mass"],
             "influence": "Muscle and bone loss hit the repaired knee first. The 2-hour exercise block "
                          "protects it; skipped sessions matter more for her."},
            {"year": 2004, "condition": "Childhood asthma (no attacks since)", "status": "resolved",
             "watch": ["spo2", "resp"],
             "influence": "Cabin dust and high CO2 can bring back airway irritation. A drop in oxygen or a "
                          "rise in breathing rate is worth a re-check."},
        ],
    },
    "lucas": {
        "age": 39, "nationality": "France", "height_cm": 181, "blood_type": "AB-",
        "background": "Planetary geologist. Second flight; runs the science programme.",
        "career": {"days_in_space": 231, "evas": 0, "eva_hours": 0.0},
        "missions": [{"name": "Gateway crew rotation 1", "year": 2023, "days": 88}],
        "allergies": ["Ibuprofen (stomach upset)"],
        "medications": ["Omeprazole 20 mg daily for reflux"],
        "history": [
            {"year": 2020, "condition": "Pneumonia (hospitalised 4 days)", "status": "resolved",
             "watch": ["temp", "resp", "spo2"],
             "influence": "In-flight immune changes plus a past lung infection: a fever with faster breathing "
                          "should be treated as a possible chest infection early."},
            {"year": 2017, "condition": "Acid reflux (GERD)", "status": "managed",
             "watch": ["nutrition", "mass"],
             "influence": "Reflux gets worse in microgravity and can put him off food. Low food intake and "
                          "weight loss are the signs to act on."},
        ],
    },
}

# --------------------------------------------------------------------------------------------
# Daily routine (every task lists the measurements it collects)
# --------------------------------------------------------------------------------------------
BASE_TASKS: list[dict[str, Any]] = [
    {"id": "morning", "time": "07:30", "title": "Morning vitals", "metrics": ["hr", "bp", "spo2"], "xp": 30},
    {"id": "glucose", "time": "07:45", "title": "Fasting glucose", "metrics": ["glucose"], "xp": 15},
    {"id": "sleep", "time": "08:00", "title": "Sleep log", "metrics": ["sleep"], "xp": 10},
    {"id": "exercise", "time": "10:00", "title": "Exercise block (2 h)", "metrics": ["exercise"], "xp": 40},
    {"id": "reaction", "time": "14:00", "title": "Alertness test", "metrics": ["reaction"], "xp": 15},
    {"id": "evening", "time": "18:00", "title": "Evening check", "metrics": ["temp", "resp"], "xp": 20},
    {"id": "fluids", "time": "20:30", "title": "Food & fluids log", "metrics": ["hydration", "nutrition"],
     "xp": 15},
    {"id": "wellbeing", "time": "21:00", "title": "Mood & symptoms", "metrics": ["mood", "symptoms"], "xp": 20},
]
WEEKLY_TASKS: list[dict[str, Any]] = [
    {"id": "mass", "time": "07:50", "title": "Weekly body mass", "metrics": ["mass"], "xp": 10},
    {"id": "vision", "time": "09:30", "title": "Weekly vision self-check", "metrics": ["vision"], "xp": 20},
]
WEEKLY_DAY_MOD = 2  # weekly tasks run on mission days where day % 7 == 2 (Day 142 is one)
ADHOC_XP = 5
# Dynamic XP for a finished scheduled check, on top of its base XP (which already scales with the check's effort).
# All of it rewards doing, timing and consistency, never what a reading says (Honest Orbit, below).
ON_TIME_BONUS = 10          # done before its time or within ON_TIME_WINDOW_S after it
ON_TIME_WINDOW_S = 30 * 60
CLOSE_TIME_BONUS = 5        # done within CLOSE_TIME_WINDOW_S after its time
CLOSE_TIME_WINDOW_S = 2 * 3600
STREAK_XP_PER_DAY = 2       # every finished check while a streak runs: +2 per streak day ...
STREAK_XP_CAP = 10          # ... up to +10, so a long streak helps but never dominates
FULL_ORBIT_XP = 40          # every scheduled check of the day finished (once a day)
COMEBACK_XP = 15            # the first finished check after a missed day: coming back is what counts

# --------------------------------------------------------------------------------------------
# Gamification
# --------------------------------------------------------------------------------------------
LEVELS = ["Cadet", "Crew Member", "Health Steward", "Guardian", "Sentinel", "Flight Legend"]
XP_PER_LEVEL = 500

# "Honest Orbit": no XP and no badge ever depends on what a reading says (good or bad), only on actions: measuring,
# logging, closing loops, helping crewmates, drilling. Rewarding values would make it pay to round a number up or
# leave a symptom out, the failure mode documented in pilots who hide conditions to avoid being grounded.
BADGES: list[dict[str, Any]] = [
    {"id": "first_light", "name": "First Light", "icon": "sunrise",
     "description": "Complete a scheduled check before 08:00", "group": "habit"},
    {"id": "steady_pulse", "name": "Steady Pulse", "icon": "heart-pulse",
     "description": "Log heart rate 10 days in a row", "group": "habit"},
    {"id": "iron_orbit", "name": "Iron Orbit", "icon": "dumbbell",
     "description": "Log your exercise block 7 days in a row", "group": "habit"},
    {"id": "night_watch", "name": "Night Watch", "icon": "moon",
     "description": "Log your sleep 7 days in a row", "group": "habit"},
    {"id": "hydro_hero", "name": "Hydro Hero", "icon": "droplets",
     "description": "Log food and fluids 7 days in a row", "group": "habit"},
    {"id": "mind_sharp", "name": "Mind Sharp", "icon": "zap",
     "description": "Do the alertness test 7 days in a row", "group": "habit"},
    {"id": "clear_sight", "name": "Clear Sight", "icon": "eye",
     "description": "Do the weekly vision check 4 weeks in a row", "group": "habit"},
    {"id": "habit_locked", "name": "Habit Locked", "icon": "lock",
     "description": "Finish your checks on 66 days (missed days don't reset it)", "group": "habit"},
    {"id": "loop_closer", "name": "Loop Closer", "icon": "repeat",
     "description": "Re-measure within 2 days after a Watch or Act result, 3 times", "group": "candor"},
    {"id": "comeback", "name": "Back on Track", "icon": "rotate-ccw",
     "description": "Finish your checks the day after a missed day", "group": "candor"},
    {"id": "drill_ready", "name": "Drill Ready", "icon": "siren",
     "description": "Complete an emergency protocol drill", "group": "crew"},
    {"id": "buddy_check", "name": "Buddy Check", "icon": "handshake",
     "description": "Acknowledge a crewmate's alert", "group": "crew"},
    {"id": "crew_keeper", "name": "Crew Keeper", "icon": "users",
     "description": "Help the crew reach 90% of its daily checks", "group": "crew"},
]
BADGE_GROUPS = {"habit": "Routine", "candor": "Honesty & follow-through", "crew": "Crew"}
CREW_GOAL_RATIO = 0.9
CREW_GOAL_REWARD = "Crew movie night"

# How XP is earned: shown in the app exactly as enforced in services.save_reading / ack_attention / emergencies.
LOOP_XP = 10        # re-measure within LOOP_WINDOW_DAYS after a Watch or Act result
LOOP_WINDOW_DAYS = 2
BUDDY_XP = 5        # acknowledge a crewmate's alert (once per alert)
BUDDY_DAILY_CAP = 3  # ... and at most 3 a day, so acknowledging a whole queue at once cannot farm XP
QUEST_XP = 30       # finish a personal quest (once per quest per mission week)
DRILL_XP = 50
STREAK_DAY_RATIO = 0.75  # a day counts for streaks when 75 % of its scheduled checks are done
HABIT_DAYS = 66          # Lally et al. 2010: median time to automaticity
SHIELD_EVERY = 7         # one streak shield per 7 streak days ...
SHIELD_MAX = 2           # ... holding at most 2
XP_RULES: list[dict[str, Any]] = [
    {"what": "Finish a scheduled check", "xp": "10-40",
     "note": "Bigger checks earn more: Sleep log 10, Morning vitals 30, Exercise block 40"},
    {"what": "On time", "xp": f"{ON_TIME_BONUS} / +{CLOSE_TIME_BONUS}",
     "note": f"Done early or within {ON_TIME_WINDOW_S // 60} min of its time; +{CLOSE_TIME_BONUS} within "
             f"{CLOSE_TIME_WINDOW_S // 3600} hours"},
    {"what": "Streak", "xp": f"{STREAK_XP_PER_DAY} a day",
     "note": f"Added to every check while your streak runs, up to +{STREAK_XP_CAP}"},
    {"what": "Full orbit", "xp": str(FULL_ORBIT_XP), "note": "Every scheduled check of the day done (once a day)"},
    {"what": "Welcome back", "xp": str(COMEBACK_XP), "note": "Your first check after a missed day"},
    {"what": "Extra reading", "xp": str(ADHOC_XP), "note": "First one per measurement per day"},
    {"what": "Close the loop", "xp": str(LOOP_XP),
     "note": f"Re-measure within {LOOP_WINDOW_DAYS} days after a Watch or Act result"},
    {"what": "Buddy check", "xp": str(BUDDY_XP),
     "note": f"Acknowledge a crewmate's alert (once per alert, up to {BUDDY_DAILY_CAP} a day)"},
    {"what": "Personal quest", "xp": str(QUEST_XP), "note": "Once per quest per mission week"},
    {"what": "Emergency drill", "xp": str(DRILL_XP), "note": "First completed drill"},
    {"what": "What a reading says", "xp": "0",
     "note": "Good or bad, a value never changes XP. Report exactly what you measure."},
]

# The mission's psychological arc. Long isolated missions show a morale dip in their third quarter (Bechtel &
# Berning 1991; Stuster 2010, ISS journals) and progressive inactivity (Mars-500, Basner et al. 2013), so the game
# changes with the chapter and watches each person's momentum.
CHAPTERS: list[dict[str, Any]] = [
    {"id": "departure", "name": "Departure", "focus": "Build the routine",
     "detail": "Early repetitions build habits fastest. Small daily wins matter most now."},
    {"id": "cruise", "name": "Deep cruise", "focus": "Keep the rhythm",
     "detail": "The novelty wears off. Crew operations rotate weekly to keep it fresh."},
    {"id": "long_middle", "name": "The long middle", "focus": "Third-quarter guard",
     "detail": "Morale tends to dip in the third quarter of long missions. Crew operations count double, and when "
               "your momentum drops a day counts once your core checks are done."},
    {"id": "approach", "name": "Approach", "focus": "Get Mars-ready",
     "detail": "Arrival needs fit, rested crew. Every check now feeds the landing-readiness picture."},
]

# Weekly cooperative challenges, rotated by mission week. Each counts actions, never values.
CREW_OPERATIONS: list[dict[str, Any]] = [
    {"id": "full_logbook", "name": "Full Logbook", "detail": "Crew reaches 90% of its scheduled checks",
     "unit": "crew days", "target": 5},
    {"id": "roll_call", "name": "Morning Roll Call", "detail": "Each crew member logs morning vitals before 08:00",
     "unit": "check-ins", "target": 20},
    {"id": "night_log", "name": "Night Log", "detail": "Each crew member logs sleep every day",
     "unit": "logs", "target": 24},
    {"id": "steady_hands", "name": "Steady Hands", "detail": "Each crew member does the alertness test",
     "unit": "tests", "target": 20},
    {"id": "loop_sweep", "name": "Loop Sweep", "detail": "Re-measure every Watch or Act result within 2 days",
     "unit": "loops closed", "target": 6},
]

# Real on-board rewards the crew unlocks together, by crew-goal days reached this mission week.
PERKS: list[dict[str, Any]] = [
    {"days": 3, "name": "Crew picks the exercise playlist", "icon": "music"},
    {"days": 5, "name": "Crew movie night", "icon": "popcorn"},
    {"days": 7, "name": "+10 min on each family video call", "icon": "radio-tower"},
]

# --------------------------------------------------------------------------------------------
# Escalation ladder
# --------------------------------------------------------------------------------------------
ESCALATION = [
    {"tier": 0, "name": "Self-care", "who": "You",
     "when": "Nominal results, or a first Watch result.",
     "action": "Follow the guidance and measure again on schedule."},
    {"tier": 1, "name": "Crew Medical Officer", "who": "Onboard CMO",
     "when": "Any Act result, a Watch result lasting 3 days, or a reading very unusual for you.",
     "action": "The CMO is alerted on board and reviews your trend with you."},
    {"tier": 2, "name": "Flight surgeon", "who": "Ground medical team",
     "when": "Red-flag values, an Act result lasting 2 days, or any emergency.",
     "action": "A priority packet is sent to Earth. Keep following the onboard protocol while it travels."},
]

# --------------------------------------------------------------------------------------------
# The five guiding questions from the challenge brief, answered
# --------------------------------------------------------------------------------------------
FAQ: list[dict[str, Any]] = [
    {"id": "which", "q": "Which measurements can be performed in space?",
     "a": ["Heart rate and blood oxygen with a finger pulse oximeter, and blood pressure with an automatic cuff.",
           "Breathing rate by counting, and temperature with an oral or forehead thermometer.",
           "Blood glucose with a finger-stick meter (the drop forms a dome in weightlessness).",
           "Body mass with an inertial mass device, because scales don't work without gravity.",
           "Sleep with an actigraphy watch, mood by self-report, and alertness with a reaction-time test.",
           "Vision with an Amsler grid, plus ground-guided ultrasound for deeper checks."]},
    {"id": "why", "q": "Why is an exam needed?",
     "a": ["Far from Earth there is no quick evacuation, and help is minutes to months away.",
           "Slow problems such as bone loss, vision changes and low mood stay hidden until late.",
           "Regular readings build a personal baseline, so 'unusual' means unusual for you."]},
    {"id": "how", "q": "How do spaceflight hazards affect these indicators?",
     "a": ["Gravity: fluid shift changes blood pressure and heart rate and can cause SANS. Unloaded bones lose "
           "about 1-1.5% per month.",
           "Isolation and distance: shorter sleep, lower mood and slower reactions.",
           "Closed environment: CO2 raises breathing rate and causes headaches, and microbes cause fever.",
           "Radiation: long-term cancer and nervous-system risk, and acute sickness in a solar storm."]},
    {"id": "when", "q": "When does a result need the crew or flight surgeons?",
     "a": ["Self-care for Nominal results or a first Watch.",
           "The Crew Medical Officer for any Act result, a Watch lasting 3 days, or a reading very unusual for you.",
           "The flight surgeon for red-flag values, an Act result lasting 2 days, or any emergency. In an "
           "emergency, act on the onboard protocol first and never wait for Earth."]},
    {"id": "prevent", "q": "What actions prevent a critical condition?",
     "a": ["About 2 hours of resistive and aerobic exercise daily.",
           "A protected sleep window and lighting schedule.",
           "At least 2 L of fluids and the full planned menu.",
           "Storm shelter and a dose budget for radiation.",
           "Social contact, leisure and psychological support.",
           "Hand hygiene, cabin-air checks and early symptom reporting."]},
]

# --------------------------------------------------------------------------------------------
# Emergency protocols (demo content: generic first-aid style, not flight rules)
# --------------------------------------------------------------------------------------------
PROTOCOLS: list[dict[str, Any]] = [
    {
        "id": "cardiac", "name": "Chest pain / collapse", "icon": "heart-crack",
        "summary": "A crewmate has chest pain, or has collapsed.",
        "pre": [
            {"id": "c1", "title": "Call it out",
             "detail": "Announce “medical emergency” on the crew loop. The Crew Medical Officer leads."},
            {"id": "c2", "title": "Secure patient and rescuer",
             "detail": "In weightlessness you will both drift. Use the medical restraint, foot loops or a wall."},
            {"id": "c3", "title": "Check response and breathing (10 s max)",
             "detail": "Tap the shoulders, call their name, and look for normal breathing."},
        ],
        "tracks": [
            {"id": "A", "label": "Not breathing normally", "steps": [
                {"id": "a1", "title": "Start CPR now",
                 "detail": "Use the restraint for back support, or the Evetts–Russomano handstand: feet "
                 "braced on the wall, hands on the chest, push with your legs.",
                 # TODO(verify): rate and source must come from the cited protocol (Evetts-Russomano CPR in
                 # microgravity, already cited in the catalog) and be confirmed by a person
                 "cue": None},
                {"id": "a2", "title": "Attach the defibrillator (AED)",
                 "detail": "Follow its voice prompts. Everyone stays clear while it analyses and shocks."},
                {"id": "a3", "title": "Keep the cycles going",
                 "detail": "Swap compressors every 2 minutes. ASTRA timestamps each step for the ground team."},
            ]},
            {"id": "B", "label": "Conscious, chest pain", "steps": [
                {"id": "b1", "title": "Rest and monitor",
                 "detail": "Keep them still and calm. Attach the monitor. HR, BP and SpO2 are logged every "
                 "5 minutes."},
                {"id": "b2", "title": "Onboard cardiac checklist",
                 "detail": "Give oxygen or medications only as written in the flight-surgeon-approved protocol."},
                {"id": "b3", "title": "Record what happened",
                 "detail": "Note when it started, what the pain feels like, where it spreads, and any other symptoms."},
                {"id": "b4", "title": "Be ready to switch to CPR",
                 "detail": "If they stop responding or stop breathing normally, switch to the other track."},
            ]},
        ],
        "post": [
            {"id": "p1", "title": "Priority packet to ground",
             "detail": ("Initial priority alert sent automatically at T+0. "
                        "Step timeline is transmitted upon completion."),
             "auto": True},
            {"id": "p2", "title": "Act now, update later",
             "detail": "Don't wait for Earth. Follow the protocol and send updates as things change."},
        ],
        "note": "Microgravity CPR: the Evetts–Russomano method was co-developed by Brazilian researcher "
        "Thais Russomano.",
    },
    {
        "id": "breathing", "name": "Breathing difficulty", "icon": "wind",
        "summary": "A crewmate is short of breath, or an atmosphere alarm is sounding.",
        "pre": [
            {"id": "c1", "title": "Call it out",
             "detail": "Announce the emergency. One crew member checks the cabin atmosphere displays."},
            {"id": "c2", "title": "Check the air first",
             "detail": "Is there a CO2, ammonia, smoke or pressure alarm? Protect yourself before helping."},
        ],
        "tracks": [
            {"id": "A", "label": "Atmosphere alarm", "steps": [
                {"id": "a1", "title": "Masks on",
                 "detail": "Put on emergency masks or oxygen for everyone, patient first if they can't."},
                {"id": "a2", "title": "Move to a safe module",
                 "detail": "Follow the alarm checklist and close the hatch behind you."},
                {"id": "a3", "title": "Monitor SpO2 and breathing",
                 "detail": "Measure every 5 minutes. ASTRA logs the values."},
            ]},
            {"id": "B", "label": "Air is normal", "steps": [
                {"id": "b1", "title": "Upright and anchored",
                 "detail": "Restrain them in an upright position and keep them calm."},
                {"id": "b2", "title": "Measure SpO2 and breathing rate",
                 "detail": "Repeat every 5 minutes. Below 90% means the oxygen protocol."},
                {"id": "b3", "title": "Look for a cause",
                 "detail": "Allergy, asthma, chest injury or infection: follow the matching onboard checklist."},
            ]},
        ],
        "post": [
            {"id": "p1", "title": "Priority packet to ground",
             "detail": ("Initial priority alert sent automatically at T+0. "
                        "Step timeline is transmitted upon completion."),
             "auto": True},
            {"id": "p2", "title": "Act now, update later",
             "detail": "Don't wait for Earth. Keep monitoring and send updates."},
        ],
        "note": "Dust from the Moon and Mars is fine and sharp, so always rule it out after an EVA.",
    },
    {
        "id": "head", "name": "Head injury / unconscious", "icon": "brain",
        "summary": "A crewmate hit their head or was found unresponsive.",
        "pre": [
            {"id": "c1", "title": "Call it out", "detail": "Announce the emergency. The CMO leads."},
            {"id": "c2", "title": "Protect the neck",
             "detail": "Avoid twisting the head and neck. Use the collar from the medical kit if one is available."},
            {"id": "c3", "title": "Check response and breathing", "detail": "If not breathing normally, use the "
             "chest pain / collapse protocol."},
        ],
        "tracks": [
            {"id": "A", "label": "Unconscious, breathing", "steps": [
                {"id": "a1", "title": "Keep the airway open",
                 "detail": "Restrain them gently on their side and watch the breathing continuously."},
                {"id": "a2", "title": "Check pupils every 5 minutes",
                 "detail": "Unequal or unresponsive pupils are a red flag for the ground team."},
            ]},
            {"id": "B", "label": "Conscious", "steps": [
                {"id": "b1", "title": "Neuro checks every 15 minutes",
                 "detail": "Check orientation, speech, pupils, and strength in hands and feet."},
                {"id": "b2", "title": "Watch for red flags",
                 "detail": "Worsening headache, vomiting, confusion or drowsiness: escalate immediately."},
            ]},
        ],
        "post": [
            {"id": "p1", "title": "Priority packet to ground",
             "detail": ("Initial priority alert sent automatically at T+0. "
                        "Step timeline is transmitted upon completion."),
             "auto": True},
            {"id": "p2", "title": "No critical tasks for 24 h",
             "detail": "The patient stays off EVAs and critical operations until cleared."},
        ],
        "note": "Loose objects become projectiles in weightlessness, so secure the area first.",
    },
    {
        "id": "allergy", "name": "Severe allergic reaction", "icon": "shield-alert",
        "summary": "Swelling, hives, or breathing trouble after food, medicine or exposure.",
        "pre": [
            {"id": "c1", "title": "Call it out", "detail": "Announce the emergency. The CMO leads."},
            {"id": "c2", "title": "Remove the trigger", "detail": "Stop the food or medicine, or move away from "
             "the exposure."},
        ],
        "tracks": [
            {"id": "A", "label": "Breathing or throat affected", "steps": [
                {"id": "a1", "title": "Epinephrine auto-injector",
                 "detail": "Use it as written in the onboard anaphylaxis checklist."},
                {"id": "a2", "title": "Oxygen and monitoring",
                 "detail": "Oxygen per protocol. SpO2 and breathing rate every 5 minutes."},
            ]},
            {"id": "B", "label": "Skin only", "steps": [
                {"id": "b1", "title": "Antihistamine per checklist",
                 "detail": "Follow the onboard allergy checklist."},
                {"id": "b2", "title": "Watch for 4 hours",
                 "detail": "If breathing or swallowing becomes difficult, switch to the other track."},
            ]},
        ],
        "post": [
            {"id": "p1", "title": "Priority packet to ground",
             "detail": ("Initial priority alert sent automatically at T+0. "
                        "Step timeline is transmitted upon completion."),
             "auto": True},
            {"id": "p2", "title": "Log the trigger", "detail": "Record it so the whole crew can avoid it."},
        ],
        "note": "Medicines can degrade faster in space radiation. Check expiry dates in the kit.",
    },
]
PROTOCOL_BY_ID: dict[str, dict[str, Any]] = {p["id"]: p for p in PROTOCOLS}

COMM_WINDOWS = ["13:00", "21:00"]

# --------------------------------------------------------------------------------------------
# Laboratory analytes from the Inspiration4 blood panels (OSD-569 and OSD-575)
# --------------------------------------------------------------------------------------------
LABS: list[dict[str, Any]] = [
    {"id": "glucose", "label": "Glucose", "unit": "mg/dL", "metric": "glucose",
     "sources": ["osdr_i4", "i4_omics"], "why": "How the body turns food into energy."},
    {"id": "creatinine", "label": "Creatinine", "unit": "mg/dL", "metric": "creatinine",
     "sources": ["osdr_i4"], "why": "How well the kidneys filter."},
    {"id": "sodium", "label": "Sodium", "unit": "mmol/L", "metric": "sodium",
     "sources": ["osdr_i4"], "why": "The body's main extracellular electrolyte."},
    {"id": "potassium", "label": "Potassium", "unit": "mmol/L", "metric": "potassium",
     "sources": ["osdr_i4"], "why": "Essential for muscle and nerve function."},
    {"id": "alt", "label": "ALT", "unit": "U/L", "metric": "alt",
     "sources": ["osdr_i4"], "why": "A liver enzyme; rises with liver stress."},
    {"id": "calcium", "label": "Calcium", "unit": "mg/dL", "metric": "calcium",
     "sources": ["osdr_i4"], "why": "Bone mineral, and it matters more in microgravity."},
    {"id": "wbc", "label": "White blood cells", "unit": "10^3/µL", "metric": "wbc",
     "sources": ["osdr_i4"], "why": "The infection-fighting part of the immune system."},
    {"id": "hemoglobin", "label": "Haemoglobin", "unit": "g/dL", "metric": "hemoglobin",
     "sources": ["osdr_i4"], "why": "How much oxygen the blood carries."},
    {"id": "platelets", "label": "Platelets", "unit": "10^3/µL", "metric": "platelets",
     "sources": ["osdr_i4"], "why": "Needed for clotting."},
    {"id": "neutrophils", "label": "Neutrophils", "unit": "cells/µL", "metric": "neutrophils",
     "sources": ["osdr_i4"], "why": "The first responders of the immune system."},
    {"id": "lymphocytes", "label": "Lymphocytes", "unit": "cells/µL", "metric": "lymphocytes",
     "sources": ["osdr_i4"], "why": "The adaptive part of the immune system."},
    {"id": "hematocrit", "label": "Hematocrit", "unit": "%", "metric": "hematocrit",
     "sources": ["osdr_i4"], "why": "The fraction of blood made of red cells."},
]
LAB_BY_ID: dict[str, dict[str, Any]] = {lab["id"]: lab for lab in LABS}

# --------------------------------------------------------------------------------------------
# Cabin air (CO2) — thresholds from NASA-STD-3001 and the OCHMO carbon dioxide brief
# --------------------------------------------------------------------------------------------
# The 3.0 mmHg Act threshold is NASA-STD-3001 Vol 2 requirement [V2 6004]: "The system shall
# limit the average one-hour CO2 partial pressure (ppCO2) in the habitable volume to no more
# than 3 mmHg." The 2.5 mmHg Watch threshold is from OCHMO-TB-004: "To keep the risk of
# headache below 1%, average 7-day CO2 needs to be maintained below 2.5 mmHg."
CABIN: dict[str, Any] = {
    "id": "cabin",
    "label": "Cabin CO2",
    "unit": "mmHg",
    "decimals": 2,
    "act_1h_mmhg": 3.0,
    "watch_7d_mmhg": 2.5,
    "sources": ["std3001v2", "ochmo_tb004", "osdr_eda"],
    "how": [
        "Read the CO2 partial pressure from the cabin atmosphere display.",
        "ASTRA compares it with the one-hour average and the 7-day average.",
        "If the cabin display shows only ppm, ASTRA converts it using the cabin pressure.",
    ],
    "why": "CO2 is the air quality number that moves the crew's own symptoms. Headaches, "
    "unusual fatigue and slower reactions all show up at the same CO2 levels, so the cabin "
    "explains symptoms the crew would otherwise blame on themselves.",
    "guide": {
        "ok": "Cabin air is within limits. Keep the routine that keeps it there.",
        "watch": "The 7-day average is drifting up. Check the CO2 scrubber and increase airflow. "
                 "Ventilate the sleeping area before lights-out and log any headache.",
        "act": "The one-hour average is above the 3 mmHg limit. Check the CO2 scrubber and "
               "increase airflow. Move the crew out of the module if it keeps rising, and tell "
               "the Crew Medical Officer.",
    },
    "actions": {
        "watch": ["Check the CO2 scrubber", "Increase cabin airflow", "Ventilate before sleep"],
        "act": ["Check the CO2 scrubber", "Increase cabin airflow",
                "Move the crew out of the module if it keeps rising",
                "Tell the Crew Medical Officer"],
    },
}


def public_catalog() -> dict[str, Any]:
    """Catalog payload served to the UI (rules included, so charts can draw the same bands)."""
    return {
        "mission": MISSION,
        "hazards": HAZARDS,
        "metrics": METRICS,
        "organs": ORGANS,
        "environments": ENVIRONMENTS,
        "crew": CREW,
        "symptoms": SYMPTOMS,
        "badges": BADGES,
        "levels": LEVELS,
        "xp_per_level": XP_PER_LEVEL,
        "escalation": ESCALATION,
        "faq": FAQ,
        "protocols": PROTOCOLS,
        "career_limit_msv": CAREER_LIMIT_MSV,
        "status_label": STATUS_LABEL,
        "sources": SOURCES,
        "contexts": CONTEXTS,
    }
