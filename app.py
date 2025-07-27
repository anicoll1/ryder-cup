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
CHALLENGES = [
    "🦅 NO TEE FOR YOU","💬 CADDY’S CHOICE","🪖 FULL METAL PUTTER",
    "📏 STUBBY STICKS ONLY","👶 BABY GRIP","🙃 BACKWARDS GRIP",
    "🦶 HAPPY GILMORE ONLY","🐦 FLAMINGO MODE"
]

# --- Helpers ---
@st.cache_data
def parse_matches(text):
    m=[]
    for line in text.splitlines():
        if "vs" in line:
            left,right = line.split("vs")
            p1=[x.strip() for x in left.split("&")]
            p2=[x.strip() for x in right.split("&")]
            m.append((p1,p2))
    return m

@st.cache_data
def compute_points(hole_scores,p1,p2):
    if len(p1)==1:
        pts={p1[0]:0,p2[0]:0}
        for sc in hole_scores.values():
            s1,s2=sc.get(p1[0]),sc.get(p2[0])
            if s1==None or s2==None: continue
            if s1<s2: pts[p1[0]]+=1
            elif s1>s2: pts[p2[0]]+=1
                            else:
                    st.info("No hole scores entered yet.")

                # --- Challenge Activation ---
                st.subheader("Sabotage Challenges")
                if challenges:
                    st.write("Used:", [f"{c['challenger']}@{c['hole']}" for c in challenges])
                ch1, ch2, ch3 = st.columns([2,3,1])
                challenger = ch1.selectbox("Who?", options=p1+p2, key=f"challenger_{i}_{idx}_{hole}")
                challenge_choice = ch2.selectbox("Challenge", options=CHALLENGES, key=f"challenge_{i}_{idx}_{hole}")
                if ch3.button("Activate Challenge", key=f"activate_{i}_{idx}_{hole}"):
                    half = 1 if hole <= 9 else 2
                    used = [c for c in challenges if c['challenger']==challenger and c['half']==half]
                    if used:
                        st.error(f"{challenger} already used a challenge this half.")
                    else:
                        new = {"hole": hole, "half": half, "challenger": challenger, "challenge": challenge_choice}
                        challenges.append(new)
                        scores_col.update_one({"day": i, "match_index": idx}, {"$set": {"challenges": challenges}}, upsert=True)
                        st.success(f"Challenge activated: {challenge_choice} on hole {hole}")

                # Display challenges table
                if challenges:
                    cr = [{"Hole": c["hole"], "Player": c["challenger"], "Challenge": c["challenge"]} for c in challenges]
                    st.table(pd.DataFrame(cr))
                else:
                    st.info("No challenges used yet.")
st.markdown("---")
st.caption("Deployed on Streamlit Cloud with MongoDB backend.")
