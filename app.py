import streamlit as st
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from streamlit_js_eval import get_geolocation
import urllib.parse

# --- 1. אתחול זיכרון (Session State) ---
if 'total_km_today' not in st.session_state:
    st.session_state.total_km_today = 0.0

# --- 2. פונקציות עזר ---
def get_distance_km(origin_coords, destination):
    if not origin_coords or not destination: return 0.0, None
    try:
        geolocator = Nominatim(user_agent="ev_delivery_gps_vfinal")
        loc2 = geolocator.geocode(f"{destination}, Israel", timeout=10)
        if loc2:
            d = geodesic(origin_coords, (loc2.latitude, loc2.longitude)).km
            return d, (loc2.latitude, loc2.longitude)
        return 0.0, None
    except: return 0.0, None

def get_nav_link(dest_addr):
    encoded_dest = urllib.parse.quote(f"{dest_addr}, Israel")
    
    # משיכת הבחירה מה-key שהגדרנו ב-Sidebar
    v_type = st.session_state.get('my_vehicle', '')
    
    if "אופניים" in v_type or "E-Bike" in v_type:
        mode = "bicycling"
    elif any(word in v_type for word in ["קטנוע", "בליץ", "Scooter", "Delivery", "קורקינט"]):
        mode = "motorcycle"
    else:
        mode = "driving"
        
    return f"https://www.google.com/maps/dir/?api=1&destination={encoded_dest}&travelmode={mode}"
# --- 3. נתוני רכבים ---
VEHICLES = {
    "E-Bike (אופניים)": {"voltage": 36, "capacity": 15, "cons": [1.2, 1.5, 2.0], "default_bars": 3},
    "Electric Scooter (קורקינט)": {"voltage": 48, "capacity": 15, "cons": [1.5, 1.8, 2.5], "default_bars": 5},
    "Delivery Scooter (בליץ / קטנוע)": {"voltage": 72, "capacity": 40, "cons": [3.5, 4.5, 6.0], "default_bars": 10},
    "Car (רכב חשמלי)": {"voltage": 400, "capacity": 150, "cons": [13, 17, 23], "default_bars": 10},
    "Electric Van (מסחרית חשמלית)": {"voltage": 400, "capacity": 200, "cons": [25, 32, 45], "default_bars": 10}
}

st.set_page_config(page_title="EV Master Pro", layout="wide")

# --- 4. חיבור ל-GPS ---
location = get_geolocation()
curr_coords = (location['coords']['latitude'], location['coords']['longitude']) if location else None

# --- 5. Sidebar: הגדרות ---
# בתוך ה-Sidebar (תפריט הצד)
with st.sidebar:
    st.header("⚙️ הגדרות נסיעה")
    # כאן אנחנו מגדירים את בחירת הרכב עם Key ברור
    v_name = st.selectbox("בחר כלי רכב:", list(VEHICLES.keys()), key='my_vehicle')
    v_data = VEHICLES[v_name]

if st.sidebar.button("🔄 איפוס יום חדש"):
    st.session_state.total_km_today = 0.0
    st.rerun()

battery_mode = st.sidebar.radio("תצוגת סוללה", ["אחוזים (%)", "פסים (Bars)"])
max_bars = st.sidebar.selectbox("כמה פסים יש בכלי?", [3, 5, 10], index=[3, 5, 10].index(v_data['default_bars']))

if battery_mode == "פסים (Bars)":
    p_start = (st.sidebar.slider("פסים בתחילת יום", 0, max_bars, max_bars) / max_bars) * 100
else:
    p_start = st.sidebar.slider("אחוז סוללה בתחילת יום (%)", 0, 100, 100)

rider_style = st.sidebar.select_slider("סגנון רכיבה", ["Eco", "Normal", "Aggressive"], "Normal")
style_idx = {"Eco": 0, "Normal": 1, "Aggressive": 2}[rider_style]
cargo = st.sidebar.slider("משקל מטען (%)", 0, 100, 0)
alert_limit = st.sidebar.slider("סף התראת טעינה (%)", 10, 30, 20)

# --- 6. חישובי מצב נוכחי ---
total_kwh = (v_data['voltage'] * v_data['capacity']) / 1000
avg_cons_kwh_per_km = v_data['cons'][style_idx] / 100 
load_f = 1 + (cargo / 100) * 0.35
used_kwh = (st.session_state.total_km_today * avg_cons_kwh_per_km) * load_f
p_now = max(0.0, round(p_start - (used_kwh / total_kwh * 100), 1))

remaining_kwh = total_kwh * (p_now / 100)
km_left = round(remaining_kwh / (avg_cons_kwh_per_km * load_f), 1) if avg_cons_kwh_per_km > 0 else 0

# --- 7. ממשק ראשי ---
st.title("⚡ ניהול משלוחים וטווח")

# התראת סוללה נמוכה
if p_now <= alert_limit:
    st.error(f"🚨 סוללה נמוכה! נותרו {p_now}%. מומלץ לחפש עמדת טעינה.")

# מדדים ראשיים
c1, c2, c3 = st.columns(3)
with c1:
    st.metric("נסעתי היום", f"{round(st.session_state.total_km_today, 1)} ק\"מ")
with c2:
    st.metric("נותרו בסוללה (משוער)", f"{km_left} ק\"מ")
with c3:
    st.metric("סוללה נוכחית", f"{p_now}%")

# הצגת הפסים
active_bars = int((p_now / 100) * max_bars)
bar_cols = st.columns(max_bars)
for i in range(max_bars):
    color = "#2ecc71" if p_now > alert_limit else "#e74c3c"
    with bar_cols[i]:
        st.markdown(f"<div style='height:25px; background-color:{color if i < active_bars else '#ecf0f1'}; border-radius:5px;'></div>", unsafe_allow_html=True)

st.divider()

with st.form("nav_form"):
    dest = st.text_input("🎯 יעד למשלוח הבא")
    calc_btn = st.form_submit_button("🔍 חשב מסלול")

if calc_btn and dest:
    if not curr_coords:
        st.error("המתן לחיבור GPS...")
    else:
        dist_air, _ = get_distance_km(curr_coords, dest)
        if dist_air > 0:
            routes = [{"name": "המהיר", "f": 1.35}, {"name": "הקצר", "f": 1.15}, {"name": "מאוזן", "f": 1.25}]
            res_cols = st.columns(3)
            for i, r in enumerate(routes):
                d_real = round(dist_air * r['f'], 2)
                used_next = (d_real * avg_cons_kwh_per_km) * load_f
                p_after = max(0.0, round(p_now - (used_next / total_kwh * 100), 1))
                
                with res_cols[i]:
                    st.subheader(f"מסלול {r['name']}")
                    st.write(f"📏 {d_real} ק\"מ")
                    st.write(f"🔋 סוללה בסיום: {p_after}%")
                    st.link_button("🚩 ניווט", get_nav_link(dest), use_container_width=True)
                    if st.button(f"✅ סיימתי נסיעה ({r['name']})", key=f"finish_{i}", use_container_width=True):
                        st.session_state.total_km_today += d_real
                        st.rerun()
        else:
            st.error("כתובת לא נמצאה")
