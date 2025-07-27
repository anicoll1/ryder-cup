import streamlit as st
import certifi
from pymongo import MongoClient

# Page config for mobile-friendly, full-width layout
st.set_page_config(page_title="Ryder Cup Scorekeeper", layout="wide", initial_sidebar_state="collapsed")

# Load MongoDB URI from secrets
MONGODB_URI = st.secrets["mongodb_uri"]
client = MongoClient(MONGODB_URI, tlsCAFile=certifi.where())
db = client["ryder_cup"]
scores_col = db["matches"]

st.title("🏌️ Ryder Cup Golf Tournament")
st.markdown("### Cronin's Golf Resort")

# Define daily match descriptions and rules
DAY_DETAILS = {
    1: {"subtitle": "Singles Matches (18 Holes)",
        "rules": ["One-on-one match play.", "1 pt win, 0.5 pt tie.", "4 pts total."]},
    2: {"subtitle": "2v2 Scramble (18 Holes)",
        "rules": ["Pick best tee shot, both play.", "1 pt match, 0.5 pt tie.", "2 pts total."]},
    3: {"subtitle": "Alternate Shot (Foursomes, 18 Holes)",
        "rules": ["One ball, alternate shots & tees.", "1 pt match, 0.5 pt tie.", "2 pts total."]}
}

# Sabotage challenges
CHALLENGES = [
    "🦅 NO TEE FOR YOU", "💬 CADDY’S CHOICE", "🪖 FULL METAL PUTTER", 
    "📏 STUBBY STICKS ONLY", "👶 BABY GRIP", "🙃 BACKWARDS GRIP", 
    "🦶 HAPPY GILMORE ONLY", "🐦 FLAMINGO MODE"
]

# Parse match strings
@st.cache_data
def parse_matches(lines):
    m=[]
    for line in lines.splitlines():
        if "vs" in line:
            left,right=line.split("vs")
            p1=[x.strip() for x in left.split("&")]
            p2=[x.strip() for x in right.split("&")]
            m.append((p1,p2))
    return m

# Default settings in hidden expander
with st.expander("⚙️ Settings (tap to expand)", expanded=False):
    team_a = [p.strip() for p in st.text_input("Team A", "Nikhit, Andrew, Matt C, Greg").split(",")]
    team_b = [p.strip() for p in st.text_input("Team B", "Aaron, Tony, Matt N, Ryan").split(",")]
    d1 = st.text_area("Day 1 Matches", "Nikhit vs Aaron\nAndrew vs Tony\nMatt C vs Matt N\nGreg vs Ryan")
    d2 = st.text_area("Day 2 Matches", "Nikhit & Matt C vs Aaron & Matt N\nAndrew & Greg vs Tony & Ryan")
    d3 = st.text_area("Day 3 Matches", "Nikhit & Andrew vs Aaron & Tony\nMatt C & Greg vs Matt N & Ryan")
    matches = {1: parse_matches(d1), 2: parse_matches(d2), 3: parse_matches(d3)}

# Tournament scoreboard
def get_tourney_score():
    S={"Team A":0,"Team B":0}
    for day,ms in matches.items():
        for idx,(p1,p2) in enumerate(ms):
            rec=scores_col.find_one({"day":day,"match_index":idx})
            if not rec: continue
            if len(p1)==1:
                t=rec.get("total_points",{})
                S["Team A"]+=t.get(p1[0],0); S["Team B"]+=t.get(p2[0],0)
            else:
                t=rec.get("team_points",{})
                S["Team A"]+=t.get("Team A",0); S["Team B"]+=t.get("Team B",0)
    return S

# Display top scoreboard side-by-side for mobile taps
col1,col2=st.columns(2)
with col1:
    st.subheader("🏆 Overall Score")
    st.metric("Team A","",get_tourney_score()["Team A"])
with col2:
    st.subheader("🏆 Overall Score")
    st.metric("Team B","",get_tourney_score()["Team B"])

# Day tabs for quick switch
tabs = st.tabs([f"Day {i}" for i in (1,2,3)])
for i,tab in enumerate(tabs, start=1):
    with tab:
        st.subheader(f"Day {i}: {DAY_DETAILS[i]['subtitle']}")
        st.markdown("- " + "\n- ".join(DAY_DETAILS[i]["rules"]))
        # Day score summary
        day_totals={"Team A":0,"Team B":0}
        for idx,(p1,p2) in enumerate(matches[i]):
            rec=scores_col.find_one({"day":i,"match_index":idx})
            if rec:
                key="total_points" if len(p1)==1 else "team_points"
                pts=rec.get(key,{})
                day_totals["Team A"]+=pts.get(p1[0] if len(p1)==1 else "Team A",0)
                day_totals["Team B"]+=pts.get(p2[0] if len(p2)==1 else "Team B",0)
        st.write(f"**Day {i} Totals:** Team A: {day_totals['Team A']} — Team B: {day_totals['Team B']}")
        # Each match expander
        for idx,(p1,p2) in enumerate(matches[i]):
            exp=st.expander(f"Match {idx+1}: {' & '.join(p1)} vs {' & '.join(p2)}")
            with exp:
                rec=scores_col.find_one({"day":i,"match_index":idx}) or {}
                hole_scores=rec.get("hole_scores",{})
                challenges=rec.get("challenges",[])
                hole=st.select_slider("Hole", options=list(range(1,19)), key=f"h_{i}_{idx}")
                c1,c2=st.columns(2)
                default=hole_scores.get(hole,{})
                if len(p1)==1:
                    s1=c1.number_input(p1[0],1,10,default.get(p1[0],1),key=f"{i}_{idx}_{hole}_0")
                    s2=c2.number_input(p2[0],1,10,default.get(p2[0],1),key=f"{i}_{idx}_{hole}_1")
                    entry={p1[0]:s1,p2[0]:s2}
                else:
                    s1=c1.number_input(' & '.join(p1),1,10,default.get("Team A",1),key=f"{i}_{idx}_{hole}_0")
                    s2=c2.number_input(' & '.join(p2),1,10,default.get("Team B",1),key=f"{i}_{idx}_{hole}_1")
                    entry={"Team A":s1,"Team B":s2}
                if st.button("Save",key=f"save_{i}_{idx}_{hole}"):
                    hole_scores[hole]=entry
                    keyp="total_points" if len(p1)==1 else "team_points"
                    pts=compute_points(hole_scores,p1,p2)
                    update={"players":(p1,p2),"hole_scores":hole_scores,keyp:pts}
                    scores_col.update_one({"day":i,"match_index":idx},{"$set":update},upsert=True)
                    st.toast(f"Saved Hole {hole}")
                # Challenges
                used=[f"{c['challenger']}@{c['hole']}" for c in challenges]
                st.write("Used:", used)
                ch1,ch2,ch3=st.columns([2,3,1])
                challenger=ch1.selectbox("Who?",options=p1+p2,key=f"c_{i}_{idx}")
                chall=ch2.selectbox("Challenge",options=CHALLENGES,key=f"ch_{i}_{idx}")
                if ch3.button("Go",key=f"a_{i}_{idx}_{hole}"):
                    half=1 if hole<=9 else 2
                    if any(c['challenger']==challenger and c['half']==half for c in challenges):
                        st.error("Used already")
                    else:
                        nu={"hole":hole,"half":half,"challenger":challenger,"challenge":chall}
                        challenges.append(nu)
                        scores_col.update_one({"day":i,"match_index":idx},{"$set":{"challenges":challenges}},upsert=True)
                        st.toast("Challenge set")
                # Show entries
                st.write("Holes:", sorted(hole_scores.items()))

st.markdown("---")
