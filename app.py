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
    "🦅 NO TEE FOR YOU", "💬 CADDY’S CHOICE", "🪖 FULL METAL PUTTER",
    "📏 STUBBY STICKS ONLY", "👶 BABY GRIP", "🙃 BACKWARDS GRIP",
    "🦶 HAPPY GILMORE ONLY", "🐦 FLAMINGO MODE"
]

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
                pts[p1[0]] += 0.5
                pts[p2[0]] += 0.5
        return pts
    pts = {"Team A": 0, "Team B": 0}
    for sc in hole_scores.values():
        s1, s2 = sc.get("Team A"), sc.get("Team B")
        if s1 is None or s2 is None:
            continue
        if s1 < s2:
            pts["Team A"] += 1
        elif s1 > s2:
            pts["Team B"] += 1
        else:
            pts["Team A"] += 0.5
            pts["Team B"] += 0.5
    return pts

# --- Settings ---
with st.expander("⚙️ Settings (tap to configure)", expanded=False):
    team_a = [p.strip() for p in st.text_input("Team A players", "Nikhit, Andrew, Matt C, Greg").split(",")]
    team_b = [p.strip() for p in st.text_input("Team B players", "Aaron, Tony, Matt N, Ryan").split(",")]
    d1 = st.text_area("Day 1 Matches", "Nikhit vs Aaron\nAndrew vs Tony\nMatt C vs Matt N\nGreg vs Ryan")
    d2 = st.text_area("Day 2 Matches", "Nikhit & Matt C vs Aaron & Matt N\nAndrew & Greg vs Tony & Ryan")
    d3 = st.text_area("Day 3 Matches", "Nikhit & Andrew vs Aaron & Tony\nMatt C & Greg vs Matt N & Ryan")
    matches = {1: parse_matches(d1), 2: parse_matches(d2), 3: parse_matches(d3)}

# --- Tournament Scoreboard & Reset ---
st.title("🏌️ Ryder Cup Scorekeeper")
col1, col2 = st.columns(2)
totals = {"Team A": 0, "Team B": 0}
for day, ms in matches.items():
    for idx, (p1, p2) in enumerate(ms):
        rec = scores_col.find_one({"day": day, "match_index": idx}) or {}
        key = "total_points" if len(p1) == 1 else "team_points"
        pts = rec.get(key, {})
        if len(p1) == 1:
            totals["Team A"] += pts.get(p1[0], 0)
            totals["Team B"] += pts.get(p2[0], 0)
        else:
            totals["Team A"] += pts.get("Team A", 0)
            totals["Team B"] += pts.get("Team B", 0)
col1.metric("Team A", totals["Team A"])
col1.markdown(f"**Roster A:** {', '.join(team_a)}")
col2.metric("Team B", totals["Team B"])
col2.markdown(f"**Roster B:** {', '.join(team_b)}")
if st.button("Reset Tournament", key="reset_all"):
    scores_col.delete_many({})
    st.success("Tournament reset.")
    try:
        st.experimental_rerun()
    except AttributeError:
        st.stop()

# --- Day Tabs ---
tabs = st.tabs([f"Day {i}" for i in (1,2,3)])
for i, tab in enumerate(tabs, start=1):
    with tab:
        st.subheader(f"Day {i}: {DAY_DETAILS[i]['subtitle']}")
        st.markdown("- " + "\n- ".join(DAY_DETAILS[i]["rules"]))
        day_tot = {"Team A": 0, "Team B": 0}
        for idx, (p1, p2) in enumerate(matches[i]):
            rec = scores_col.find_one({"day": i, "match_index": idx}) or {}
            key = "total_points" if len(p1) == 1 else "team_points"
            pts = rec.get(key, {})
            if len(p1) == 1:
                day_tot["Team A"] += pts.get(p1[0], 0)
                day_tot["Team B"] += pts.get(p2[0], 0)
            else:
                day_tot["Team A"] += pts.get("Team A", 0)
                day_tot["Team B"] += pts.get("Team B", 0)
        st.write(f"**Totals:** A {day_tot['Team A']} — B {day_tot['Team B']}")
        for idx, (p1, p2) in enumerate(matches[i]):
            with st.expander(f"Match {idx+1}: {' & '.join(p1)} vs {' & '.join(p2)}"):
                rec = scores_col.find_one({"day": i, "match_index": idx}) or {"players": (p1, p2), "hole_scores": {}, "challenges": []}
                hole_scores = {int(k): v for k, v in rec.get("hole_scores", {}).items() if k.isdigit()}
                challenges = rec.get("challenges", [])
                if st.button("Clear Match Scores", key=f"clear_{i}_{idx}"):
                    scores_col.delete_one({"day": i, "match_index": idx})
                    st.success(f"Cleared Match {idx+1}.")
                    try:
                        st.experimental_rerun()
                    except AttributeError:
                        st.stop()
                hole = st.select_slider("Hole", options=list(range(1, 19)), key=f"h_{i}_{idx}")
                c1, c2 = st.columns(2)
                default = hole_scores.get(hole, {})
                if len(p1) == 1:
                    k1 = f"{i}_{idx}_{hole}_{p1[0]}"
                    k2 = f"{i}_{idx}_{hole}_{p2[0]}"
                    s1 = c1.number_input(p1[0], 1, 10, default.get(p1[0], 1), key=k1)
                    s2 = c2.number_input(p2[0], 1, 10, default.get(p2[0], 1), key=k2)
                    entry = {p1[0]: s1, p2[0]: s2}
                else:
                    p1k = ''.join(p1)
                    p2k = ''.join(p2)
                    s1 = c1.number_input(' & '.join(p1), 1, 10, default.get("Team A", 1), key=f"{i}_{idx}_{hole}_{p1k}")
                    s2 = c2.number_input(' & '.join(p2), 1, 10, default.get("Team B", 1), key=f"{i}_{idx}_{hole}_{p2k}")
                    entry = {"Team A": s1, "Team B": s2}
                if st.button("Save Hole Score", key=f"save_{i}_{idx}_{hole}"):
                    hole_scores[hole] = entry
                    pts = compute_points(hole_scores, p1, p2)
                    dbh = {str(k): v for k, v in hole_scores.items()}
                    update = {"day": i, "match_index": idx, "players": (p1, p2), "hole_scores": dbh}
                    update["total_points" if len(p1) == 1 else "team_points"] = pts
                    scores_col.update_one({"day": i, "match_index": idx}, {"$set": update}, upsert=True)
                    st.toast(f"Saved hole {hole}")
                if hole_scores:
                    rows = []
                    for h, sc in sorted(hole_scores.items()):
                        hpts = compute_points({h: sc}, p1, p2)
                        if len(p1) == 1:
                            rows.append({"Hole": h, p1[0]: sc[p1[0]], p2[0]: sc[p2[0]],
                                         f"{p1[0]} Pts": hpts[p1[0]], f"{p2[0]} Pts": hpts[p2[0]]})
                        else:
                            rows.append({"Hole": h, "Team A": sc["Team A"], "Team B": sc["Team B"],
                                         "Team A Pts": hpts["Team A"], "Team B Pts": hpts["Team B"]})
                    df = pd.DataFrame(rows).reset_index(drop=True)
                    st.dataframe(df, hide_index=True)
                else:
                    st.info("No hole scores entered yet.")
                # Challenge activation UI
                st.subheader("Sabotage Challenges")
                cols = st.columns([2, 3, 1])
                challenger = cols[0].selectbox("Who?", options=p1 + p2, key=f"challenger_{i}_{idx}_{hole}")
                challenge_choice = cols[1].selectbox("Challenge", options=CHALLENGES, key=f"challenge_{i}_{idx}_{hole}")
                if cols[2].button("Activate Challenge", key=f"activate_{i}_{idx}_{hole}"):
                    half = 1 if hole <= 9 else 2
                    if any(c['challenger'] == challenger and c['half'] == half for c in challenges):
                        st.error(f"{challenger} already used a challenge this half.")
                    else:
                        new = {"hole": hole, "half": half, "challenger": challenger, "challenge": challenge_choice}
                        challenges.append(new)
                        scores_col.update_one({"day": i, "match_index": idx}, {"$set": {"challenges": challenges}}, upsert=True)
                        st.success(f"Challenge activated: {challenge_choice} on hole {hole}")
                # Used challenges table
                if challenges:
                    df_ch = pd.DataFrame([{"Hole": c["hole"], "Player": c["challenger"], "Challenge": c["challenge"]} for c in challenges])
                    st.table(df_ch)
                else:
                    st.info("No challenges used yet.")

st.markdown("---")
st.caption("Deployed on Streamlit Cloud with MongoDB backend.")
