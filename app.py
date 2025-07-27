import streamlit as st
import pandas as pd
import certifi
from pymongo import MongoClient

# --- Configuration ---
st.set_page_config(page_title="Ryder Cup Scorekeeper", layout="wide", initial_sidebar_state="collapsed")

# Load MongoDB URI
uri = st.secrets.get("MONGODB_URI")
if not uri:
    st.error("Please set MONGODB_URI in Streamlit Secrets.")
    st.stop()

# Connect with TLS CA
try:
    client = MongoClient(
        uri,
        tlsCAFile=certifi.where(),
        connectTimeoutMS=30000,
        serverSelectionTimeoutMS=30000
    )
    client.admin.command('ping')
except Exception as e:
    st.error(f"MongoDB connection failed: {e}")
    st.stop()

db = client["ryder_cup"]
scores_col = db["matches"]

# --- Constants ---
DAY_DETAILS = {
    1: {"subtitle": "Singles Matches (18 Holes)",
        "rules": ["One-on-one match play.", "1 pt win, 0.5 tie.", "4 pts total"]},
    2: {"subtitle": "2v2 Scramble (18 Holes)",
        "rules": ["Pick best tee shot, both play.", "1 pt match, 0.5 tie.", "2 pts total"]},
    3: {"subtitle": "Alternate Shot (Foursomes, 18 Holes)",
        "rules": ["One ball, alternate shots & tees.", "1 pt match, 0.5 tie.", "2 pts total"]}
}
# Define sabotage challenges and their descriptions
CHALLENGE_DESCRIPTIONS = {
    "🦅 NO TEE FOR YOU": "On the next tee box, the target must hit their driver directly off the ground—no tee allowed.",
    "💬 CADDY’S CHOICE": "You choose the target’s club for their next shot.",
    "🪖 FULL METAL PUTTER": "Target must putt the next hole using a wedge or hybrid—no putter allowed.",
    "📏 STUBBY STICKS ONLY": "For the next hole, the target can only use clubs shorter than a 9-iron (putter, wedges).",
    "👶 BABY GRIP": "Opponent must grip their club halfway down the shaft, like a toddler holding a broomstick.",
    "🙃 BACKWARDS GRIP": "Opponent must hold the club with their hands reversed—left hand low for righties.",
    "🦶 HAPPY GILMORE ONLY": "Opponent must attempt a running swing for the next shot.",
    "🐦 FLAMINGO MODE": "Hit the next swing standing on one foot (balance challenge!)."
}
# Keys for UI dropdowns
CHALLENGES = list(CHALLENGE_DESCRIPTIONS.keys())

# --- Helpers ---
@st.cache_data
def parse_matches(text):
    matches = []
    for line in text.splitlines():
        if "vs" in line:
            left, right = line.split("vs")
            p1 = [x.strip() for x in left.split("&")]
            p2 = [x.strip() for x in right.split("&")]
            matches.append((p1, p2))
    return matches

@st.cache_data
def compute_points(hole_scores, p1, p2):
    if len(p1) == 1:
        pts = {p1[0]: 0, p2[0]: 0}
        for sc in hole_scores.values():
            s1, s2 = sc.get(p1[0]), sc.get(p2[0])
            if s1 is None or s2 is None:
                continue
            if s1 < s2:
                pts[p1[0]] += 1
            elif s1 > s2:
                pts[p2[0]] += 1
            else:
                    st.info("No challenges used yet."))

st.markdown("---")
st.caption("Deployed on Streamlit Cloud with MongoDB backend.")
