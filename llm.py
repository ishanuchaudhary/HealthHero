"""
HealthHero — Local LLM Module (No API Key Required)
=====================================================
This module replaces the original OpenAI-dependent llm.py with a fully
local disease prediction engine powered by a trained RandomForest model.

How it works:
  1. On startup, loads the saved model artifacts from ./model/
  2. When a user sends a message, it extracts symptoms using keyword matching
  3. Runs the trained model to predict the top 3 most likely diseases
  4. Builds a structured, empathetic health response — no internet needed

Requirements:
  - Run train_model.py ONCE first to generate the ./model/ folder
  - pip install scikit-learn pandas joblib
"""

import asyncio
import os
import re
from typing import List, Dict, AsyncGenerator

import joblib
import numpy as np

# ─────────────────────────────────────────────
# MODEL LOADING
# ─────────────────────────────────────────────

MODEL_DIR = "model"

def _load_artifacts():
    """Load trained model artifacts. Returns (clf, le, symptom_cols, diseases) or None."""
    required = ["model.pkl", "encoder.pkl", "symptoms.pkl", "diseases.pkl"]
    if not all(os.path.exists(os.path.join(MODEL_DIR, f)) for f in required):
        print("⚠  Model artifacts not found in ./model/")
        print("   Run:  python train_model.py  to train the model first.")
        return None, None, None, None
    try:
        clf          = joblib.load(os.path.join(MODEL_DIR, "model.pkl"))
        le           = joblib.load(os.path.join(MODEL_DIR, "encoder.pkl"))
        symptom_cols = joblib.load(os.path.join(MODEL_DIR, "symptoms.pkl"))
        diseases     = joblib.load(os.path.join(MODEL_DIR, "diseases.pkl"))
        print(f"✓ Local model loaded — {len(diseases)} diseases, {len(symptom_cols)} symptoms")
        return clf, le, symptom_cols, diseases
    except Exception as e:
        print(f"⚠  Error loading model: {e}")
        return None, None, None, None


CLF, LE, SYMPTOM_COLS, ALL_DISEASES = _load_artifacts()

# Build readable name map: "joint_pain" → "joint pain"
SYMPTOM_READABLE = {s: s.replace("_", " ") for s in (SYMPTOM_COLS or [])}
# Reverse map for matching: "joint pain" → "joint_pain"
READABLE_TO_KEY  = {v: k for k, v in SYMPTOM_READABLE.items()}


# ─────────────────────────────────────────────
# RED-FLAG DETECTION (safety — always on)
# ─────────────────────────────────────────────

RED_FLAG_KEYWORDS = [
    "chest pain", "pressure in chest", "shortness of breath", "cannot breathe",
    "blue lips", "face blue", "fainting", "passed out", "unconscious",
    "worst headache", "stroke", "face droop", "arm weakness", "speech slurred",
    "stiff neck", "seizure", "seizing", "severe abdominal pain", "abdomen rigid",
    "testicular torsion", "allergic shock", "anaphylaxis", "throat closing",
    "swelling tongue", "uncontrolled bleeding", "bleeding won't stop",
    "pregnancy bleeding", "severe pregnancy pain",
    "suicidal", "self-harm", "want to die",
]

def _has_red_flags(text: str) -> bool:
    t = text.lower()
    return any(kw in t for kw in RED_FLAG_KEYWORDS)


# ─────────────────────────────────────────────
# SYMPTOM EXTRACTION
# ─────────────────────────────────────────────

def extract_symptoms(user_text: str) -> List[str]:
    """
    Extract symptom keywords from free-form user text.
    Returns a list of matched symptom column names (e.g. ['joint_pain', 'fever']).
    """
    if not SYMPTOM_COLS:
        return []

    text = user_text.lower()
    # Normalize: remove punctuation, collapse spaces
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    matched = []
    for col in SYMPTOM_COLS:
        readable = col.replace("_", " ")
        # Match either the raw key or readable version
        if readable in text or col in text:
            matched.append(col)
            continue
        # Also try individual word overlap for multi-word symptoms
        words = readable.split()
        if len(words) >= 2 and all(w in text for w in words):
            matched.append(col)

    return matched


def build_feature_vector(detected_symptoms: List[str]) -> np.ndarray:
    """Convert a list of detected symptom column names into a binary feature vector."""
    vec = np.zeros(len(SYMPTOM_COLS), dtype=int)
    sym_index = {s: i for i, s in enumerate(SYMPTOM_COLS)}
    for sym in detected_symptoms:
        if sym in sym_index:
            vec[sym_index[sym]] = 1
    return vec.reshape(1, -1)


# ─────────────────────────────────────────────
# DISEASE PREDICTION
# ─────────────────────────────────────────────

def predict_diseases(detected_symptoms: List[str], top_n: int = 3):
    """
    Run the trained RandomForest model and return top N predictions.
    Returns list of (disease_name, confidence_percent) tuples.
    """
    if CLF is None or not detected_symptoms:
        return []

    vec   = build_feature_vector(detected_symptoms)
    proba = CLF.predict_proba(vec)[0]  # confidence per class

    # Get top N indices by probability
    top_indices = np.argsort(proba)[::-1][:top_n]
    results = []
    for idx in top_indices:
        disease    = LE.classes_[idx]
        confidence = round(proba[idx] * 100, 1)
        if confidence > 0.5:          # skip near-zero predictions
            results.append((disease, confidence))
    return results


# ─────────────────────────────────────────────
# DISEASE-SPECIFIC ADVICE (curated)
# ─────────────────────────────────────────────

DISEASE_ADVICE = {
    "Common Cold": [
        "Rest as much as possible for the next 48–72 hours",
        "Drink warm fluids — herbal tea, warm water with honey",
        "Use steam inhalation to ease nasal congestion",
        "Gargle with warm salt water for sore throat relief",
        "OTC options: paracetamol for fever/aches, saline nasal spray",
    ],
    "Influenza": [
        "Rest strictly — flu can worsen quickly with activity",
        "Stay well-hydrated; aim for 2–3 litres of fluids daily",
        "Paracetamol or ibuprofen for fever and body aches (per label)",
        "Isolate to avoid spreading to others for 5–7 days",
        "Seek care if fever exceeds 39°C or breathing becomes difficult",
    ],
    "Dengue": [
        "Rest completely and monitor temperature every 6 hours",
        "Maintain very high fluid intake — ORS/coconut water preferred",
        "DO NOT take ibuprofen or aspirin — use only paracetamol",
        "Watch for warning signs: bleeding gums, severe abdominal pain",
        "Visit a doctor immediately for a platelet count blood test",
    ],
    "Typhoid": [
        "Strict bed rest is essential",
        "Eat soft, easily digestible foods — khichdi, curd, boiled rice",
        "Drink only boiled or purified water",
        "Antibiotics are required — consult a doctor promptly",
        "Avoid raw vegetables and street food during recovery",
    ],
    "Malaria": [
        "Visit a doctor or diagnostic lab for a blood smear test immediately",
        "Antimalarial medication must be prescribed — do not self-medicate",
        "Stay well-hydrated and rest completely",
        "Use mosquito nets and repellents to prevent re-infection",
        "Complete the full course of any prescribed medication",
    ],
    "Diabetes": [
        "Monitor your blood glucose levels regularly",
        "Follow a low-glycaemic diet — reduce refined carbs and sugars",
        "Stay physically active — 30 min of moderate exercise daily",
        "Never skip prescribed insulin or oral medications",
        "Schedule a HbA1c test every 3 months",
    ],
    "Hypertension": [
        "Reduce sodium intake — aim for under 2g/day",
        "Avoid alcohol, smoking, and high-stress situations",
        "Monitor your blood pressure at home daily",
        "Take prescribed antihypertensive medications consistently",
        "Engage in light aerobic exercise: walking 30 min/day",
    ],
    "Migraine": [
        "Move to a quiet, dark, cool room and lie down",
        "Apply a cold or warm compress on your forehead/neck",
        "Stay hydrated — dehydration is a common migraine trigger",
        "OTC: ibuprofen or paracetamol at onset (not after pain peaks)",
        "Track triggers in a diary: food, sleep, screen time, stress",
    ],
    "Chicken Pox": [
        "Trim fingernails short and avoid scratching — prevent scarring",
        "Apply calamine lotion to soothe itching",
        "Take lukewarm oatmeal baths for relief",
        "Use paracetamol for fever — AVOID aspirin in children",
        "Isolate until all blisters have crusted over (5–7 days)",
    ],
    "Jaundice": [
        "Complete rest and avoid all physical exertion",
        "Eat a high-carb, low-fat diet — fruit juices, rice, boiled vegetables",
        "Drink plenty of fluids including sugarcane juice and lemon water",
        "Absolutely avoid alcohol and fatty/oily food",
        "Get liver function tests done; consult a doctor for the cause",
    ],
    "Urinary Tract Infection": [
        "Drink 2–3 litres of water daily to flush bacteria",
        "Avoid caffeine, alcohol, and citrus until symptoms resolve",
        "Urinate frequently — do not hold it in",
        "Antibiotics will be required — visit a GP promptly",
        "Women: wipe front to back; avoid scented hygiene products",
    ],
    "Acne": [
        "Wash affected areas gently twice daily with a mild cleanser",
        "Avoid touching your face — this transfers bacteria",
        "Use non-comedogenic (oil-free) moisturisers and sunscreen",
        "Don't pop or squeeze pimples — this worsens scarring",
        "See a dermatologist if over-the-counter treatments don't help in 6 weeks",
    ],
    "GERD": [
        "Eat smaller, more frequent meals — avoid large portions",
        "Avoid lying down within 3 hours of eating",
        "Elevate the head of your bed by 15–20 cm",
        "Avoid triggers: caffeine, spicy food, alcohol, citrus, chocolate",
        "OTC antacids or H2 blockers can help; see a doctor for persistent symptoms",
    ],
    "Arthritis": [
        "Apply warm/cold packs to affected joints for 15–20 min",
        "Engage in gentle low-impact exercises: swimming, yoga, walking",
        "Maintain a healthy weight to reduce joint load",
        "OTC: ibuprofen or naproxen for pain (check with your doctor first)",
        "Physiotherapy is very effective — ask your doctor for a referral",
    ],
    "Bronchial Asthma": [
        "Identify and avoid your triggers: dust, smoke, pets, cold air",
        "Always carry your rescue inhaler (salbutamol) with you",
        "Use a peak flow meter to monitor your lung function daily",
        "Keep your home well-ventilated and dust-free",
        "See a respiratory specialist to review your preventer medication",
    ],
}

DEFAULT_ADVICE = [
    "Rest adequately and avoid strenuous activity",
    "Maintain good hydration — 2–3 litres of water per day",
    "Monitor your symptoms and note any changes in severity",
    "Eat light, nutritious meals; avoid processed or oily food",
    "If symptoms persist beyond 48–72 hours or worsen, see a doctor",
]

def get_advice(disease_name: str) -> List[str]:
    """Return disease-specific advice, falling back to general advice."""
    for key, advice in DISEASE_ADVICE.items():
        if key.lower() in disease_name.lower() or disease_name.lower() in key.lower():
            return advice
    return DEFAULT_ADVICE


# ─────────────────────────────────────────────
# RESPONSE BUILDER
# ─────────────────────────────────────────────

def _build_response(user_text: str) -> str:
    """Core function: text in → structured health response out."""

    # 1. Empty / greeting
    if not user_text or len(user_text.strip()) < 3:
        return (
            "Hey there! 😊 I'm HealthHero — your offline AI health assistant.\n\n"
            "Tell me what symptoms you're experiencing and I'll guide you through "
            "what they might mean, what to do, and when to see a doctor.\n\n"
            "Examples you can type:\n"
            "  • \"I have a fever, chills, and joint pain\"\n"
            "  • \"I've been having headaches and nausea for 2 days\"\n"
            "  • \"I feel fatigue and have a skin rash\"\n\n"
            "Go ahead — I'm listening! 🩺"
        )

    # 2. Red flag check — always runs before anything else
    if _has_red_flags(user_text):
        return (
            "⚠️ **This sounds urgent. Please seek emergency care immediately "
            "or call your local emergency number (102 / 112).**\n\n"
            "**What to do right now:**\n"
            "- Call 102 (ambulance) or 112 (emergency) immediately\n"
            "- Do not drive yourself — have someone take you or wait for help\n"
            "- Keep someone with you; stay as calm as possible\n"
            "- Follow any instructions from the emergency operator\n\n"
            "---\n"
            "*This is general information only. Emergency care is needed now.*"
        )

    # 3. Symptom extraction
    detected = extract_symptoms(user_text)

    # 4. Prediction
    predictions = predict_diseases(detected, top_n=3) if detected else []

    # 5. Assemble response
    lines = []

    # ── Quick Take ──
    if predictions:
        top_disease, top_conf = predictions[0]
        lines.append(
            f"Thanks for sharing that! 😊 Based on the symptoms you've described, "
            f"this could be related to **{top_disease}**. Let's go through it carefully.\n"
        )
    else:
        lines.append(
            "Thanks for reaching out! 😊 I wasn't able to detect specific symptoms "
            "from your message — could you describe what you're feeling in more detail?\n\n"
            f"**Tip:** Try describing symptoms like: *fever, cough, joint pain, fatigue, "
            f"nausea, skin rash, headache, chills, etc.*\n"
        )
        lines.append(
            "---\n"
            "*This is general health information, not a diagnosis. "
            "Always consult a healthcare professional for medical advice.*"
        )
        return "\n".join(lines)

    # ── Symptoms Detected ──
    readable_syms = [s.replace("_", " ") for s in detected]
    lines.append(
        f"**Symptoms I detected:**\n"
        + "\n".join(f"  • {s}" for s in readable_syms)
        + "\n"
    )

    # ── What It Could Be ──
    lines.append("**What this could be:**")
    for disease, conf in predictions:
        bar_len = int(conf / 5)
        bar = "█" * bar_len + "░" * (20 - bar_len)
        lines.append(f"  • {disease:<30} {bar} {conf:.1f}% match")
    lines.append("")

    # ── What To Do Now ──
    advice = get_advice(predictions[0][0])
    lines.append("**What you can do now:**")
    for tip in advice:
        lines.append(f"  • {tip}")
    lines.append("")

    # ── Red Flags ──
    lines.append(
        "**Watch for these warning signs (seek emergency care if any appear):**\n"
        "  • High fever above 39°C / 102°F that doesn't come down\n"
        "  • Difficulty breathing or chest pain\n"
        "  • Severe headache, confusion, or loss of consciousness\n"
        "  • Signs of dehydration: no urination, dry mouth, sunken eyes\n"
    )

    # ── When to Seek Care ──
    lines.append(
        "**When to seek care:**\n"
        "  🚨 **Emergency (ER/102):** Any warning sign above\n"
        "  🏥 **Doctor visit:** Symptoms lasting more than 3 days or worsening\n"
        "  💊 **Self-care:** If mild and less than 48 hours, try the steps above first\n"
    )

    # ── Follow-Up ──
    lines.append(
        "**Follow-up plan:**\n"
        "  • Check your symptoms again in 24–48 hours\n"
        "  • Note your temperature, pain level (0–10), and fluid intake\n"
        "  • Message me again anytime — I'm always here! 😊\n"
    )

    lines.append(
        "---\n"
        "*This is general health information based on symptom patterns, "
        "not a medical diagnosis. Please consult a qualified healthcare professional "
        "for any medical concerns.*"
    )

    return "\n".join(lines)


# ─────────────────────────────────────────────
# PUBLIC API  (same interface as original llm.py)
# app.py needs zero changes — these are drop-in replacements
# ─────────────────────────────────────────────

async def generate(messages: List[Dict[str, str]]) -> str:
    """Generate a response from conversation history. Drop-in for OpenAI version."""
    last_user = next(
        (m["content"] for m in reversed(messages) if m.get("role") == "user"), ""
    )
    return _build_response(last_user)


async def stream_generate(messages: List[Dict[str, str]]) -> AsyncGenerator[str, None]:
    """Stream a response word-by-word. Drop-in for OpenAI streaming version."""
    text  = await generate(messages)
    words = text.split(" ")
    for i, word in enumerate(words):
        if i > 0:
            yield " "
        for char in word:
            yield char
            await asyncio.sleep(0.008)
        await asyncio.sleep(0.015)


# ─────────────────────────────────────────────
# QUICK SELF-TEST (run: python llm.py)
# ─────────────────────────────────────────────

if __name__ == "__main__":
    import asyncio

    test_messages = [
        [{"role": "user", "content": "I have fever, chills, joint pain and headache"}],
        [{"role": "user", "content": "I am having nausea, vomiting and stomach pain"}],
        [{"role": "user", "content": "I feel itching and skin rash on my arm"}],
        [{"role": "user", "content": "chest pain and shortness of breath"}],
        [{"role": "user", "content": "hello"}],
    ]

    async def run_tests():
        print("=" * 60)
        print("HealthHero — Local Model Self-Test")
        print("=" * 60)
        for msgs in test_messages:
            print(f"\n🧑 User: {msgs[0]['content']}")
            print("-" * 40)
            response = await generate(msgs)
            # Print only first 300 chars for readability
            print(response[:400] + ("..." if len(response) > 400 else ""))
            print()

    asyncio.run(run_tests())
