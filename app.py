import streamlit as st
import certifi
from pymongo import MongoClient

# --- Configuration ---
st.set_page_config(page_title="Ryder Cup Scorekeeper", layout="wide", initial_sidebar_state="collapsed")

# Load MongoDB URI from Streamlit Cloud Secrets
db_uri = st.secrets.get("MONGODB_URI")
if not db_uri:
    st.error("MONGODB_URI not found in Streamlit Secrets. Please add it under Settings → Secrets.")
    st.stop()

# Connect to MongoDB with TLS
client = MongoClient(
    db_uri,
    tls=True,
    tlsCAFile=certifi.where(),
    connectTimeoutMS=30000,
    serverSelectionTimeoutMS=30000
)
db = client["ryder_cup"]
scores_col = db["matches"]

# --- Constants ---
DAY_DETAILS = {
    1: {"subtitle": "Singles Matches (18 Holes)",
        "rules": ["One-on-one match play.", "1 pt win, 0.5 pt tie.", "4 pts total."]},
    2: {"subtitle": "2v2 Scramble (18 Holes)",
        "rules": ["Pick best tee shot, both play.", "1 pt match, 0.5 pt tie.", "2 pts total."]},
    3: {"subtitle": "Alternate Shot (Foursomes, 18 Holes)",
        "rules": ["One ball, alternate shots & tees.", "1 pt match, 0.5 pt tie.", "2 pts total."]}
}
CHALLENGES = [
    "🦅 NO TEE FOR YOU", "💬 CADDY’S CHOICE", "🪖 FULL METAL PUTTER",
    "📏 STUBBY STICKS ONLY", "👶 BABY GRIP", "🙃 BACKWARDS GRIP",
    "🦶 HAPPY GILMORE ONLY", "🐦 FLAMINGO MODE"
]

# --- Helpers ---
@st.cache_data
def parse_matches(lines):
    matches = []
    for line in lines.splitlines():
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
        for scores in hole_scores.values():
            s1 = scores.get(p1[0]); s2 = scores.get(p2[0])
            if s1 is None or s2 is None: continue
            if s1 < s2: pts[p1[0]] += 1
            elif s1 > s2: pts[p2[0]] += 1
            else: pts[p1[0]] += 0.5; pts[p2[0]] += 0.5
        return pts
    else:
        pts = {"Team A": 0, "Team B": 0}
        for scores in hole_scores.values():
            s1 = scores.get("Team A"); s2 = scores.get("Team B")
            if s1 is None or s2 is None: continue
            if s1 < s2: pts["Team A"] += 1
            elif s1 > s2: pts["Team B"] += 1
            else: pts["Team A"] += 0.5; pts["Team B"] += 0.5
        return pts

# --- Settings Expander ---
with st.expander("⚙️ Settings (tap)", expanded=False):
    team_a = [p.strip() for p in st.text_input("Team A players", "Nikhit, Andrew, Matt C, Greg").split(",")]
    team_b = [p.strip() for p in st.text_input("Team B players", "Aaron, Tony, Matt N, Ryan").split(",")]
    d1 = st.text_area("Day 1 Matches", "Nikhit vs Aaron\nAndrew vs Tony\nMatt C vs Matt N\nGreg vs Ryan")
    d2 = st.text_area("Day 2 Matches", "Nikhit & Matt C vs Aaron & Matt N\nAndrew & Greg vs Tony & Ryan")
    d3 = st.text_area("Day 3 Matches", "Nikhit & Andrew vs Aaron & Tony\nMatt C & Greg vs Matt N & Ryan")
    matches = {1: parse_matches(d1), 2: parse_matches(d2), 3: parse_matches(d3)}

# --- Tournament Scoreboard ---
def get_tourney_score():
    S = {"Team A": 0, "Team B": 0}
    for day, ms in matches.items():
        for idx, (p1, p2) in enumerate(ms):
            rec = scores_col.find_one({"day": day, "match_index": idx}) or {}
            key = "total_points" if len(p1) == 1 else "team_points"
            pts = rec.get(key, {})
            if len(p1) == 1:
                S["Team A"] += pts.get(p1[0], 0)
                S["Team B"] += pts.get(p2[0], 0)
            else:
                S["Team A"] += pts.get("Team A", 0)
                S["Team B"] += pts.get("Team B", 0)
    return S

st.title("🏌️ Ryder Cup Scorekeeper")
col1, col2 = st.columns(2)
col1.metric("Team A", get_tourney_score()["Team A"] )
col2.metric("Team B", get_tourney_score()["Team B"] )

# --- Day Tabs ---
tabs = st.tabs([f"Day {i}" for i in (1,2,3)])
for i, tab in enumerate(tabs, start=1):
    with tab:
        st.subheader(f"Day {i}: {DAY_DETAILS[i]['subtitle']}")
        st.markdown("- " + "\n- ".join(DAY_DETAILS[i]["rules"]))
        # Day totals\        
        dt = {"Team A":0, "Team B":0}
        for idx, (p1, p2) in enumerate(matches[i]):
            rec = scores_col.find_one({"day": i, "match_index": idx}) or {}
            key = "total_points" if len(p1)==1 else "team_points"
            pts = rec.get(key, {})
            if len(p1) == 1:
                dt["Team A"] += pts.get(p1[0],0)
                dt["Team B"] += pts.get(p2[0],0)
            else:
                dt["Team A"] += pts.get("Team A",0)
                dt["Team B"] += pts.get("Team B",0)
        st.write(f"**Totals:** A {dt['Team A']} — B {dt['Team B']}")
        # Matches per day
        for idx, (p1, p2) in enumerate(matches[i]):
            with st.expander(f"Match {idx+1}: {' & '.join(p1)} vs {' & '.join(p2)}"):
                rec = scores_col.find_one({"day": i, "match_index": idx}) or {"players":(p1,p2), "hole_scores":{}, "challenges":[]}
                hole_scores = rec["hole_scores"]
                challenges = rec.get("challenges", [])
                hole = st.select_slider("Hole", options=list(range(1,19)), key=f"h_{i}_{idx}")
                c1, c2 = st.columns(2)
                default = hole_scores.get(hole, {})
                if len(p1)==1:
                    s1 = c1.number_input(p1[0], 1, 10, default.get(p1[0],1), key=f"{i}_{idx}_{hole}_0")
                    s2 = c2.number_input(p2[0], 1, 10, default.get(p2[0],1), key=f"{i}_{idx}_{hole}_1")
                    entry = {p1[0]: s1, p2[0]: s2}
                else:
                    s1 = c1.number_input(' & '.join(p1),1,10,default.get("Team A",1), key=f"{i}_{idx}_{hole}_0")
                    s2 = c2.number_input(' & '.join(p2),1,10,default.get("Team B",1), key=f"{i}_{idx}_{hole}_1")
                    entry = {"Team A": s1, "Team B": s2}
                if st.button("Save", key=f"save_{i}_{idx}_{hole}"):
                    hole_scores[hole] = entry
                    pts = compute_points(hole_scores, p1, p2)
                    update = {"day": i, "match_index": idx, "players": (p1, p2), "hole_scores": hole_scores}
                    if len(p1)==1:
                        update["total_points"] = pts
                    else:
                        update["team_points"] = pts
                    scores_col.update_one({"day": i, "match_index": idx}, {"$set": update}, upsert=True)
                    st.toast(f"Saved hole {hole}")
                # Challenges UI
                st.write("Used:", [f"{c['challenger']}@{c['hole']}" for c in challenges])
                ch1, ch2, ch3 = st.columns([2,3,1])
                challenger = ch1.selectbox("Who?", options=p1+p2, key=f"c_{i}_{idx}")
                chall = ch2.selectbox("Challenge", options=CHALLENGES, key=f"ch_{i}_{idx}")
                if ch3.button("Activate", key=f"a_{i}_{idx}_{hole}"):
                    half = 1 if hole <= 9 else 2
                    if any(c['challenger']==challenger and c['half']==half for c in challenges):
                        st.error("Already used this half.")
                    else:
                        nu = {"hole": hole, "half": half, "challenger": challenger, "challenge": chall}
                        rec.setdefault("challenges", []).append(nu)
                        scores_col.update_one({"day": i, "match_index": idx}, {"$set": {"challenges": rec["challenges"]}}, upsert=True)
                        st.toast("Challenge set")
                st.write("Holes:", sorted(hole_scores.items()))

st.markdown("---")
st.caption("Deployed on Streamlit Cloud with MongoDB backend.")
