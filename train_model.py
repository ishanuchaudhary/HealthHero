"""
HealthHero — Local Model Training Script
=========================================
Run this ONCE to train and save your disease prediction model.
No API key needed. Works fully offline after training.

Usage:
    python train_model.py

Output (saved to ./model/ folder):
    model.pkl         — trained RandomForest classifier
    encoder.pkl       — label encoder for disease names
    symptoms.pkl      — ordered list of symptom feature names
    diseases.pkl      — list of all disease names the model knows
"""

import os
import urllib.request
import pandas as pd
import numpy as np
import joblib
import random
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, classification_report

# ─────────────────────────────────────────────
# 1. DATASET SETUP
# ─────────────────────────────────────────────

DATA_DIR  = "data"
MODEL_DIR = "model"

# Multiple URLs to try (in order)
DATASET_URLS = [
    "https://raw.githubusercontent.com/anujdutt9/Disease-Prediction-from-Symptoms/master/dataset/training.csv",
    "https://raw.githubusercontent.com/Vardaan-02/Minor-Project/main/Data/dataset.csv",
    "https://raw.githubusercontent.com/mananvpanchal/Disease-Prediction/main/Training.csv",
]

# ─────────────────────────────────────────────
# BUILT-IN DATASET (fallback if download fails)
# 25 diseases × ~60 symptoms, 100 samples per disease
# ─────────────────────────────────────────────

ALL_SYMPTOMS = [
    "fever", "chills", "sweating", "headache", "fatigue", "weakness",
    "nausea", "vomiting", "diarrhea", "stomach_pain", "loss_of_appetite",
    "cough", "sore_throat", "runny_nose", "sneezing", "congestion",
    "shortness_of_breath", "chest_pain", "rapid_heartbeat",
    "joint_pain", "muscle_pain", "back_pain", "neck_pain",
    "skin_rash", "itching", "blisters", "yellowing_of_skin",
    "yellowing_of_eyes", "dark_urine", "pale_stool",
    "frequent_urination", "burning_urination", "blood_in_urine",
    "excessive_thirst", "excessive_hunger", "blurred_vision",
    "weight_loss", "weight_gain", "night_sweats",
    "swollen_lymph_nodes", "swollen_joints", "stiff_joints",
    "runny_eyes", "watery_eyes", "sensitivity_to_light",
    "dizziness", "confusion", "memory_loss",
    "anxiety", "depression", "mood_swings", "irritability",
    "hair_loss", "cold_intolerance", "constipation",
    "abdominal_bloating", "heartburn", "acid_reflux",
    "high_blood_pressure", "swollen_feet", "palpitations",
]

# Disease → core symptom sets (high-probability symptoms for that disease)
DISEASE_SYMPTOM_MAP = {
    "Common Cold":          ["runny_nose", "sneezing", "congestion", "sore_throat", "cough", "fatigue", "headache"],
    "Influenza":            ["fever", "chills", "muscle_pain", "headache", "fatigue", "cough", "sore_throat", "weakness"],
    "Dengue":               ["fever", "headache", "joint_pain", "muscle_pain", "skin_rash", "fatigue", "nausea", "vomiting"],
    "Malaria":              ["fever", "chills", "sweating", "headache", "nausea", "vomiting", "fatigue", "muscle_pain"],
    "Typhoid":              ["fever", "headache", "stomach_pain", "weakness", "loss_of_appetite", "constipation", "nausea"],
    "Pneumonia":            ["fever", "chills", "cough", "shortness_of_breath", "chest_pain", "fatigue", "sweating"],
    "Diabetes":             ["excessive_thirst", "frequent_urination", "excessive_hunger", "weight_loss", "blurred_vision", "fatigue"],
    "Hypertension":         ["headache", "high_blood_pressure", "dizziness", "palpitations", "swollen_feet", "fatigue", "chest_pain"],
    "Migraine":             ["headache", "nausea", "vomiting", "sensitivity_to_light", "dizziness", "fatigue"],
    "Arthritis":            ["joint_pain", "stiff_joints", "swollen_joints", "fatigue", "weakness", "back_pain"],
    "Gastroenteritis":      ["nausea", "vomiting", "diarrhea", "stomach_pain", "fever", "weakness", "fatigue"],
    "Urinary Tract Infection": ["frequent_urination", "burning_urination", "blood_in_urine", "fever", "stomach_pain", "fatigue"],
    "Jaundice":             ["yellowing_of_skin", "yellowing_of_eyes", "dark_urine", "pale_stool", "fatigue", "nausea", "stomach_pain"],
    "Chicken Pox":          ["fever", "skin_rash", "itching", "blisters", "fatigue", "headache", "loss_of_appetite"],
    "Bronchial Asthma":     ["shortness_of_breath", "cough", "chest_pain", "wheezing", "fatigue"],
    "GERD":                 ["heartburn", "acid_reflux", "chest_pain", "nausea", "abdominal_bloating", "sore_throat"],
    "Anemia":               ["fatigue", "weakness", "dizziness", "headache", "rapid_heartbeat", "cold_intolerance", "pale_stool"],
    "Hypothyroidism":       ["weight_gain", "fatigue", "cold_intolerance", "constipation", "hair_loss", "depression", "weakness"],
    "Anxiety":              ["anxiety", "palpitations", "rapid_heartbeat", "sweating", "dizziness", "fatigue", "irritability"],
    "Depression":           ["depression", "fatigue", "weight_loss", "anxiety", "mood_swings", "memory_loss", "irritability"],
    "Dengue Hemorrhagic Fever": ["fever", "skin_rash", "joint_pain", "vomiting", "fatigue", "headache", "nausea", "chills"],
    "Tuberculosis":         ["cough", "night_sweats", "weight_loss", "fatigue", "fever", "chest_pain", "weakness", "loss_of_appetite"],
    "COVID-19":             ["fever", "cough", "fatigue", "shortness_of_breath", "headache", "loss_of_appetite", "muscle_pain"],
    "Allergy":              ["sneezing", "runny_nose", "itching", "watery_eyes", "runny_eyes", "skin_rash", "congestion"],
    "Sinusitis":            ["headache", "congestion", "runny_nose", "sore_throat", "facial_pain", "fatigue", "cough"],
}

def generate_builtin_dataset(samples_per_disease=120, noise_prob=0.08):
    """
    Generate a synthetic training dataset from the symptom map above.
    Each sample = one row with binary symptom columns + disease label.
    Noise is added so the model learns robust patterns, not just exact matches.
    """
    random.seed(42)
    np.random.seed(42)

    rows = []
    for disease, core_symptoms in DISEASE_SYMPTOM_MAP.items():
        for _ in range(samples_per_disease):
            row = {s: 0 for s in ALL_SYMPTOMS}
            # Add core symptoms with occasional drop (simulates partial reporting)
            for sym in core_symptoms:
                if sym in row:
                    row[sym] = 1 if random.random() > 0.10 else 0
            # Add random noise symptoms
            for sym in ALL_SYMPTOMS:
                if row[sym] == 0 and random.random() < noise_prob:
                    row[sym] = 1
            row["prognosis"] = disease
            rows.append(row)

    df = pd.DataFrame(rows)
    return df


def try_download_dataset():
    """Try multiple URLs. Returns True if any succeeds, False if all fail."""
    os.makedirs(DATA_DIR, exist_ok=True)
    train_path = os.path.join(DATA_DIR, "training.csv")

    if os.path.exists(train_path):
        print(f"  ✓ Dataset already exists — skipping download.")
        return True

    for i, url in enumerate(DATASET_URLS, 1):
        try:
            print(f"  ↓ Trying source {i}/{len(DATASET_URLS)}: {url[:60]}...")
            urllib.request.urlretrieve(url, train_path)
            print(f"  ✓ Downloaded successfully.")
            return True
        except Exception as e:
            print(f"  ✗ Failed ({type(e).__name__})")

    print("  ⚠  All downloads failed — using built-in dataset instead.")
    return False


# ─────────────────────────────────────────────
# 2. DATA LOADING & PREPROCESSING
# ─────────────────────────────────────────────

def load_and_preprocess(use_builtin: bool):
    """Load data (downloaded CSV or built-in), return X_train, X_test, y_train, y_test, symptom_cols."""

    if use_builtin:
        print("  Building dataset from built-in disease-symptom map ...")
        df = generate_builtin_dataset(samples_per_disease=120)
        # 80/20 train-test split
        from sklearn.model_selection import train_test_split as tts
        train_df, test_df = tts(df, test_size=0.2, random_state=42, stratify=df["prognosis"])
    else:
        train_path = os.path.join(DATA_DIR, "training.csv")
        test_path  = os.path.join(DATA_DIR, "testing.csv")
        train_df   = pd.read_csv(train_path)
        # testing.csv might not have downloaded — fall back to split
        if os.path.exists(test_path):
            test_df = pd.read_csv(test_path)
        else:
            from sklearn.model_selection import train_test_split as tts
            train_df, test_df = tts(train_df, test_size=0.2, random_state=42)

    # Drop unnamed columns that some CSVs have
    train_df = train_df.loc[:, ~train_df.columns.str.contains("^Unnamed")]
    test_df  = test_df.loc[:,  ~test_df.columns.str.contains("^Unnamed")]

    target_col   = "prognosis"
    symptom_cols = [c for c in train_df.columns if c != target_col]

    X_train = train_df[symptom_cols].values
    y_train = train_df[target_col].values
    X_test  = test_df[symptom_cols].values
    y_test  = test_df[target_col].values

    print(f"\n  Dataset summary:")
    print(f"    Training samples   : {len(X_train)}")
    print(f"    Testing  samples   : {len(X_test)}")
    print(f"    Symptoms (features): {len(symptom_cols)}")
    print(f"    Diseases (classes) : {len(set(y_train))}")

    return X_train, y_train, X_test, y_test, symptom_cols


# ─────────────────────────────────────────────
# 3. TRAINING
# ─────────────────────────────────────────────

def train(X_train, y_train):
    le    = LabelEncoder()
    y_enc = le.fit_transform(y_train)

    print("\n  Training RandomForest (200 trees) ...")
    clf = RandomForestClassifier(
        n_estimators=200,
        max_depth=None,
        min_samples_split=2,
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(X_train, y_enc)
    print("  ✓ Training complete.")
    return clf, le


# ─────────────────────────────────────────────
# 4. EVALUATION
# ─────────────────────────────────────────────

def evaluate(clf, le, X_test, y_test):
    y_test_enc = le.transform(y_test)
    y_pred     = clf.predict(X_test)
    acc        = accuracy_score(y_test_enc, y_pred)

    print(f"\n  ── Evaluation Results ──────────────────────")
    print(f"  Test Accuracy : {acc * 100:.2f}%")

    report = classification_report(
        y_test_enc, y_pred,
        target_names=le.classes_,
        zero_division=0,
        output_dict=True,
    )
    macro = report["macro avg"]
    print(f"  Macro Precision : {macro['precision']:.4f}")
    print(f"  Macro Recall    : {macro['recall']:.4f}")
    print(f"  Macro F1-Score  : {macro['f1-score']:.4f}")
    print(f"  ────────────────────────────────────────────")
    return acc


# ─────────────────────────────────────────────
# 5. SAVE
# ─────────────────────────────────────────────

def save_model(clf, le, symptom_cols):
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(clf,           os.path.join(MODEL_DIR, "model.pkl"))
    joblib.dump(le,            os.path.join(MODEL_DIR, "encoder.pkl"))
    joblib.dump(symptom_cols,  os.path.join(MODEL_DIR, "symptoms.pkl"))
    joblib.dump(list(le.classes_), os.path.join(MODEL_DIR, "diseases.pkl"))

    print(f"\n  ✓ Artifacts saved to ./{MODEL_DIR}/")
    print(f"    model.pkl    — RandomForest classifier")
    print(f"    encoder.pkl  — LabelEncoder  ({len(le.classes_)} diseases)")
    print(f"    symptoms.pkl — Feature list  ({len(symptom_cols)} symptoms)")
    print(f"    diseases.pkl — Disease names")


# ─────────────────────────────────────────────
# 6. FEATURE IMPORTANCE
# ─────────────────────────────────────────────

def show_top_symptoms(clf, symptom_cols, top_n=10):
    importances = clf.feature_importances_
    ranked = sorted(zip(symptom_cols, importances), key=lambda x: x[1], reverse=True)
    print(f"\n  Top {top_n} most important symptoms for diagnosis:")
    for i, (sym, imp) in enumerate(ranked[:top_n], 1):
        bar = "█" * int(imp * 300)
        print(f"  {i:2}. {sym:<35} {bar} ({imp:.4f})")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("=" * 50)
    print("  HealthHero — Model Training")
    print("=" * 50)

    print("\n[1/5] Attempting dataset download ...")
    downloaded = try_download_dataset()

    print("\n[2/5] Loading & preprocessing data ...")
    X_train, y_train, X_test, y_test, symptom_cols = load_and_preprocess(use_builtin=not downloaded)

    print("\n[3/5] Training model ...")
    clf, le = train(X_train, y_train)

    print("\n[4/5] Evaluating model ...")
    acc = evaluate(clf, le, X_test, y_test)

    print("\n[5/5] Saving model artifacts ...")
    save_model(clf, le, symptom_cols)

    show_top_symptoms(clf, symptom_cols)

    print("\n" + "=" * 50)
    print(f"  ✅ Done! Model accuracy: {acc * 100:.1f}%")
    print("  Run:  uvicorn app:app --reload")
    print("  HealthHero now runs fully offline — no API key needed!")
    print("=" * 50)