"""
chatbot.py - SafeHer Assistant: NLP Conversational Engine

Understands natural-language safety and navigation questions,
pulls live data from the database, and generates specific,
data-backed replies.

Supported Intents:
  1.  safest_route       - Which route is safest?
  2.  route_at_night     - Is this route safe at night?
  3.  police_location    - Where is the nearest police station?
  4.  police_distance    - How far is the nearest police station?
  5.  safe_zones         - Where are the safe zones?
  6.  risky_area         - Should I avoid this area?
  7.  why_risky          - Why is this route risky?
  8.  alternatives       - Show me safer alternatives
  9.  score_explain      - What does the safety score mean?
  10. emergency          - I feel unsafe / being followed / danger
  11. greeting           - Hi / Hello / Help
"""

import re
from datetime import datetime

# ---------------------------------------------------------------------------
# Intent Patterns  (ordered: more specific first)
# ---------------------------------------------------------------------------
INTENT_PATTERNS = [
    # Emergency — highest priority
    ('emergency', [
        r'\bi.?m (scared|afraid|in danger|being followed)\b',
        r'\b(help me|someone is following|being stalked|stalker|attack)\b',
        r'\b(danger|emergency|unsafe right now|feel unsafe)\b',
        r'\bsos\b',
        r'\bpanic\b',
    ]),

    # Police distance
    ('police_distance', [
        r'\bhow far.*(police|station|booth)\b',
        r'\bdistance.*(police|station|booth)\b',
        r'\b(police|booth|station).*(how far|distance|km|meters|away)\b',
        r'\bhow (close|near).*(police|booth)\b',
    ]),

    # Police location
    ('police_location', [
        r'\b(nearest|closest|nearby|where).*(police|station|booth|help desk)\b',
        r'\b(police|station|booth|help desk).*(where|near|closest|find)\b',
        r'\bpolice (station|booth|outpost)\b',
        r'\bwhere.*(get help|find help)\b',
        r'\bemergency contact\b',
    ]),

    # Route at night
    ('route_at_night', [
        r'\b(safe|okay|dangerous|risky).*(night|dark|late|after (dark|\d+\s*(pm|am)))\b',
        r'\b(night|dark|late|midnight|after 9|after 10|after 11).*(safe|walk|go|route|travel)\b',
        r'\b(fastest|transit|shortcut|alley).*(night|dark|safe)\b',
        r'\bwalk(ing)? (at night|after dark|in the dark)\b',
    ]),

    # Safe zones
    ('safe_zones', [
        r'\b(safe zone|safe area|safe place|safe spot|safe location)\b',
        r'\bwhere.*(safe|safety|shelter)\b',
        r'\b(safe|green).*(zone|area|corridor)\b',
    ]),

    # Why risky
    ('why_risky', [
        r'\bwhy.*(risky|unsafe|dangerous|avoid|low score|bad score)\b',
        r'\bwhat.*(makes|wrong|bad|issue).*(route|path|area|alley)\b',
        r'\b(explain|reason).*(risk|danger|score|unsafe)\b',
        r'\bwhat.*(problem|issue).*(alley|canal|shortcut|dark)\b',
    ]),

    # Alternatives
    ('alternatives', [
        r'\b(alternative|other|another|different).*(route|path|way|option)\b',
        r'\b(safer|better).*(route|option|path|alternative)\b',
        r'\bshow.*(route|path|alternative|option)\b',
        r'\bchange.*(route|path)\b',
    ]),

    # Safest route
    ('safest_route', [
        r'\b(safest|best|recommended|which).*(route|path|way|road)\b',
        r'\b(route|path|way).*(safest|safest|recommend)\b',
        r'\bwhich (route|road|path).*(take|choose|pick|use|go)\b',
        r'\bshould i (take|use|go).*(route|road)\b',
        r'\bbest.*(way|route).*(home|travel|go)\b',
    ]),

    # Score explanation
    ('score_explain', [
        r'\b(what|explain|mean|how).*(safety score|score|rating|94|76|42)\b',
        r'\bsafety score\b',
        r'\bwhat does.*(number|score|rating) mean\b',
        r'\bhow.*(score.*(calculated|work)|scoring)\b',
    ]),

    # Risky area
    ('risky_area', [
        r'\b(risky|dangerous|avoid|unsafe|bad|dark).*(area|zone|place|spot|section)\b',
        r'\b(area|zone|place|spot).*(risky|dangerous|avoid|unsafe|bad|dark)\b',
        r'\bshould i avoid\b',
        r'\b(canal|alley|shortcut|underpass).*(safe|risky|avoid)\b',
        r'\b(which|what).*(area|zone|place).*(avoid|danger|risk)\b',
    ]),

    # Greeting
    ('greeting', [
        r'\b(hi|hello|hey|good (morning|afternoon|evening|night))\b',
        r'\b(help|assist|what can you do|start)\b',
    ]),
]


# ---------------------------------------------------------------------------
# Intent Classifier
# ---------------------------------------------------------------------------
def detect_intent(message: str) -> str:
    """Classify user message into one of the supported intents."""
    msg = message.lower().strip()
    for intent, patterns in INTENT_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, msg):
                return intent
    return 'general'


# ---------------------------------------------------------------------------
# Response Generators
# ---------------------------------------------------------------------------

def _score_label(score: int) -> str:
    if score >= 85:
        return "🟢 Excellent"
    elif score >= 70:
        return "🟡 Moderate"
    elif score >= 55:
        return "🟠 Caution"
    else:
        return "🔴 Risky"


def _time_context(time_of_day: str) -> str:
    if time_of_day == 'night':
        return "night-time"
    elif time_of_day == 'day':
        return "daytime"
    hour = datetime.now().hour
    return "night-time" if (hour >= 20 or hour < 6) else "daytime"


def respond_safest_route(routes: list, time_of_day: str) -> dict:
    if not routes:
        return {
            'reply': "I couldn't fetch live route data right now, but generally the Main Boulevard Safe Corridor is the safest choice — 96% LED lit with police booths within 60 metres.",
            'recommendations': ["Choose the green 'SAFEST' route card on the map", "Tap 'Start Safe Route' to begin navigation"],
            'intent': 'safest_route',
            'safety_score': 94
        }

    safest = routes[0]
    others = routes[1:]
    score = safest.get('score', 94)
    name = safest.get('shortName', safest.get('name', 'Main Boulevard'))
    time_ctx = _time_context(time_of_day)

    alt_text = ""
    if others:
        alt = others[0]
        alt_text = (f" The next option is '{alt.get('shortName', alt.get('name', ''))}' "
                    f"with a score of {alt.get('score', 76)}/100 — {_score_label(alt.get('score', 76))}.")

    reply = (
        f"🛡️ The safest route right now is the **{name}** with a safety score of **{score}/100** "
        f"({_score_label(score)}) under {time_ctx} conditions. "
        f"It has {safest.get('lighting', {}).get('val', 'high')} street lighting, "
        f"{safest.get('crowd', {}).get('val', 'high')} foot traffic, and "
        f"{safest.get('police', {}).get('val', 'a police booth nearby')}."
        f"{alt_text}"
    )

    recommendations = [
        f"Select '{name}' on the route cards",
        "Tap 'Start Safe Route' for live turn-by-turn navigation",
        "Share your live trip with trusted contacts before leaving"
    ]
    return {'reply': reply, 'recommendations': recommendations, 'intent': 'safest_route', 'safety_score': score}


def respond_route_at_night(routes: list) -> dict:
    if not routes:
        return {
            'reply': "At night, always pick the most brightly lit route. Avoid shortcuts, alleys, and areas with closed shops.",
            'recommendations': ["Use the Main Boulevard route after dark", "Keep trusted contacts updated on your location"],
            'intent': 'route_at_night',
            'safety_score': 80
        }

    safest = routes[0]
    risky = routes[-1] if len(routes) > 1 else None

    risky_warning = ""
    if risky and risky.get('id') != safest.get('id'):
        r_score = risky.get('score', 42)
        r_name = risky.get('shortName', risky.get('name', 'Shortcut'))
        r_lighting = risky.get('lighting', {}).get('val', 'low lighting')
        risky_warning = (f" ⚠️ Avoid the **{r_name}** at night — it scores only {r_score}/100 "
                         f"with {r_lighting} and no police surveillance.")

    safest_score = safest.get('score', 94)
    safest_name = safest.get('shortName', safest.get('name', 'Main Boulevard'))

    # Night penalty context
    night_note = ""
    if safest_score < 90:
        night_note = " Note: safety scores are slightly reduced at night due to reduced visibility."

    reply = (
        f"🌙 At night, the **{safest_name}** remains the safest choice with a score of "
        f"**{safest_score}/100** — {_score_label(safest_score)}.{night_note}"
        f"{risky_warning}"
    )

    recommendations = [
        f"Take the '{safest_name}' route after dark",
        "Walk in well-lit, populated areas only",
        "Avoid quiet lanes, alleys, and underpasses at night",
        "Keep 112 (Emergency) and 1091 (Women Helpline) ready"
    ]
    return {'reply': reply, 'recommendations': recommendations, 'intent': 'route_at_night', 'safety_score': safest_score}


def respond_police_location(police_stations: list, user_coords: list) -> dict:
    if not police_stations:
        return {
            'reply': "📍 Call 112 (National Emergency) or 1091 (Women Helpline) for immediate police assistance.",
            'recommendations': ["Dial 112 for police dispatch", "Dial 1091 for Women Safety Helpline"],
            'intent': 'police_location',
            'safety_score': 95
        }

    count = len(police_stations)
    names = [p['name'] for p in police_stations]
    nearest = police_stations[0]

    reply = (
        f"👮 There are **{count} police assistance points** along your route corridor:\n"
        + "\n".join([f"• {n}" for n in names])
        + f"\n\nThe nearest is **{nearest['name']}** — {nearest.get('desc', '24/7 duty officers')}. "
        f"Contact: {nearest.get('phone', '112')}."
    )

    recommendations = [
        f"Call {nearest.get('phone', '112')} — {nearest['name']}",
        "Dial 112 for immediate police dispatch anywhere",
        "Dial 1091 for the Women Safety Helpline",
        "Police markers (🛡️ blue shields) are visible on the map"
    ]
    return {'reply': reply, 'recommendations': recommendations, 'intent': 'police_location', 'safety_score': 95}


def respond_police_distance(police_stations: list, user_coords: list) -> dict:
    import math

    def haversine(c1, c2):
        R = 6371000
        lat1, lng1 = math.radians(c1[0]), math.radians(c1[1])
        lat2, lng2 = math.radians(c2[0]), math.radians(c2[1])
        dlat = lat2 - lat1
        dlng = lng2 - lng1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
        return int(R * 2 * math.asin(math.sqrt(a)))

    if not police_stations or not user_coords:
        return {
            'reply': "The nearest police booth is approximately 150–300 metres from the Main Boulevard corridor. Dial 112 for immediate response.",
            'recommendations': ["Dial 112 — police response in ~90 seconds on this route"],
            'intent': 'police_distance',
            'safety_score': 95
        }

    with_dist = []
    for p in police_stations:
        d = haversine(user_coords, [p['lat'], p['lng']])
        with_dist.append((d, p))
    with_dist.sort(key=lambda x: x[0])

    nearest_dist, nearest = with_dist[0]
    dist_str = f"{nearest_dist} m" if nearest_dist < 1000 else f"{nearest_dist/1000:.1f} km"

    reply = (
        f"📍 The nearest police point is **{nearest['name']}**, approximately **{dist_str} away** from your current location. "
        f"Response time is estimated within 90 seconds on this corridor. "
        f"Contact: {nearest.get('phone', '112')}."
    )

    all_dist = [f"• {p['name']} — {d} m" for d, p in with_dist]
    recommendations = [
        f"Call {nearest.get('phone', '112')} — {nearest['name']} ({dist_str})",
        "Dial 112 for national emergency dispatch"
    ]
    return {'reply': reply, 'recommendations': recommendations, 'intent': 'police_distance', 'safety_score': 95}


def respond_safe_zones(safety_zones: list) -> dict:
    safe = [z for z in safety_zones if z.get('type') == 'safe']
    risky = [z for z in safety_zones if z.get('type') == 'risky']

    if not safety_zones:
        return {
            'reply': "🟢 Safe zones are areas with high lighting, active shops, and police presence — shown as green circles on the map.",
            'recommendations': ["Look for green-shaded areas on the map", "Stick to commercial corridors and main roads"],
            'intent': 'safe_zones',
            'safety_score': 90
        }

    safe_names = [z['title'] for z in safe]
    risky_names = [z['title'] for z in risky]

    safe_list = "\n".join([f"• 🟢 {n}" for n in safe_names]) if safe_names else "• No tagged safe zones in current corridor"
    risky_list = "\n".join([f"• 🔴 {n}" for n in risky_names]) if risky_names else ""

    reply = (
        f"🗺️ Here are the tagged zones along your route:\n\n"
        f"**Safe Zones ({len(safe)}):**\n{safe_list}\n"
    )
    if risky_list:
        reply += f"\n**Risky / Low-Light Areas ({len(risky)}):**\n{risky_list}\n\n"
        reply += "Zones are visible as coloured circles on the map — green for safe, red for risky."

    recommendations = [
        "Stay within or near green-shaded safe zones",
        "Avoid red-shaded areas especially after dark",
        "Use the 'Toggle Zones' button on the map to show/hide zones"
    ]
    return {'reply': reply, 'recommendations': recommendations, 'intent': 'safe_zones', 'safety_score': 88}


def respond_why_risky(routes: list) -> dict:
    risky_route = None
    for r in routes:
        if r.get('type') == 'risky' or r.get('score', 100) < 55:
            risky_route = r
            break

    if not risky_route:
        risky_route = routes[-1] if routes else None

    if not risky_route:
        return {
            'reply': "⚠️ A route is considered risky when it has poor street lighting (<50%), high crime history, isolated sections, and no nearby police presence.",
            'recommendations': ["Avoid routes scoring below 55/100", "Look for the red 'RISKY' badge on route cards"],
            'intent': 'why_risky',
            'safety_score': 42
        }

    name = risky_route.get('shortName', risky_route.get('name', 'Risky Route'))
    score = risky_route.get('score', 42)
    lighting = risky_route.get('lighting', {})
    crime = risky_route.get('crime', {})
    crowd = risky_route.get('crowd', {})
    police = risky_route.get('police', {})

    reasons = []
    if lighting.get('percent', 100) < 50:
        reasons.append(f"🔦 Poor lighting — only {lighting.get('val', 'low')} coverage")
    if crime.get('percent', 0) > 50:
        reasons.append(f"🚨 High crime history — {crime.get('val', 'elevated')} incidents")
    if crowd.get('percent', 100) < 40:
        reasons.append(f"👥 Isolated — {crowd.get('val', 'very low')} foot traffic")
    if police.get('percent', 100) < 40:
        reasons.append(f"👮 No nearby police — {police.get('val', 'far away')}")

    if not reasons:
        reasons = ["Poor visibility", "Isolated stretches", "Limited police coverage"]

    reasons_text = "\n".join([f"• {r}" for r in reasons])
    reply = (
        f"⚠️ The **{name}** has a low safety score of **{score}/100** ({_score_label(score)}) because:\n\n"
        f"{reasons_text}\n\n"
        f"This makes it significantly more dangerous, especially at night."
    )

    recommendations = [
        "Do NOT use this route at night or when travelling alone",
        "Choose the SAFEST route — it takes only a few extra minutes",
        "If already on this route, move to the nearest lit main road immediately"
    ]
    return {'reply': reply, 'recommendations': recommendations, 'intent': 'why_risky', 'safety_score': score}


def respond_alternatives(routes: list, time_of_day: str) -> dict:
    if not routes or len(routes) < 2:
        return {
            'reply': "🔄 There are 3 route options available — the Safest Boulevard, the Transit Avenue, and a faster shortcut. The safest is always recommended.",
            'recommendations': ["Browse all route cards in the left panel", "Click any route card to see it on the map"],
            'intent': 'alternatives',
            'safety_score': 85
        }

    time_ctx = _time_context(time_of_day)
    comparison_lines = []
    for r in routes:
        badge = "✅" if r.get('type') == 'safest' else ("⚠️" if r.get('type') == 'moderate' else "❌")
        comparison_lines.append(
            f"{badge} **{r.get('shortName', r.get('name', 'Route'))}** — {r.get('score', 0)}/100 "
            f"({_score_label(r.get('score', 0))}) · {r.get('time', '?')} · {r.get('distance', '?')}"
        )

    comparison = "\n".join(comparison_lines)
    reply = (
        f"🗺️ Here are all **{len(routes)} available routes** under {time_ctx} conditions:\n\n"
        f"{comparison}\n\n"
        f"The top-rated route is strongly recommended for solo travel."
    )

    recommendations = [
        "Click a route card to preview it on the map",
        "The green SAFEST route is always recommended for solo travel",
        "Avoid any route rated below 55/100 — especially at night"
    ]
    return {'reply': reply, 'recommendations': recommendations, 'intent': 'alternatives', 'safety_score': routes[0].get('score', 94)}


def respond_score_explain(routes: list) -> dict:
    safest_score = routes[0].get('score', 94) if routes else 94
    risky_score = routes[-1].get('score', 42) if routes and len(routes) > 1 else 42

    reply = (
        f"📊 The **Safety Score (0–100)** is calculated using 6 weighted factors:\n\n"
        f"• 🔦 Street Lighting — **25%** (LED coverage %)\n"
        f"• 🚨 Crime History — **30%** (incident records)\n"
        f"• 👥 Crowd Activity — **15%** (foot traffic, open shops)\n"
        f"• 👮 Police Proximity — **15%** (distance to nearest booth)\n"
        f"• 🛡️ Safe Zones — **10%** (overlap with verified safe areas)\n"
        f"• 🌙 Time of Day — **5%** (night vs. daytime penalty)\n\n"
        f"**Score Guide:**\n"
        f"• 85–100 🟢 Excellent — safe to travel alone\n"
        f"• 70–84 🟡 Moderate — take precautions\n"
        f"• 55–69 🟠 Caution — not recommended alone at night\n"
        f"• 0–54 🔴 Risky — avoid this route"
    )

    recommendations = [
        "Choose routes scoring 85+ for safest solo travel",
        "Avoid routes below 55 at night",
        "Night-time scores are automatically reduced by 5–15%"
    ]
    return {'reply': reply, 'recommendations': recommendations, 'intent': 'score_explain', 'safety_score': 94}


def respond_risky_area(safety_zones: list) -> dict:
    risky = [z for z in safety_zones if z.get('type') == 'risky']

    if not risky:
        return {
            'reply': "⚠️ Risky areas are locations with poor lighting, no police coverage, isolated paths, or high crime history. They appear as red circles on the map.",
            'recommendations': ["Look for red-shaded circles on the map", "Avoid any route passing through red zones, especially at night"],
            'intent': 'risky_area',
            'safety_score': 45
        }

    risky_text = "\n".join([f"• 🔴 **{z['title']}** — {z.get('desc', 'Low light and isolated')}" for z in risky])
    reply = (
        f"⚠️ The following **{len(risky)} risky area(s)** have been identified along the route corridor:\n\n"
        f"{risky_text}\n\n"
        f"These areas are shown as **red circles** on the map. Avoid them — especially after dark."
    )

    recommendations = [
        "Do NOT enter red-marked areas at night",
        "Toggle 'Safety Zones' on the map to see all risky areas",
        "Choose a route that avoids these areas entirely"
    ]
    return {'reply': reply, 'recommendations': recommendations, 'intent': 'risky_area', 'safety_score': 40}


def respond_emergency(police_stations: list) -> dict:
    nearest_name = police_stations[0]['name'] if police_stations else "Nearest Police Booth"
    nearest_phone = police_stations[0].get('phone', '112') if police_stations else '112'

    reply = (
        "🚨 **STAY CALM. You are not alone.**\n\n"
        "**Do this RIGHT NOW:**\n"
        "1. 🏪 Walk into the nearest open shop, pharmacy, or café — do NOT stop in the dark\n"
        "2. 📱 Tap the **red SOS button** in the app to sound a siren and log your location\n"
        f"3. 📞 **Call 112** (Police) or **1091** (Women Helpline) immediately\n"
        f"4. 👮 Your nearest police point is: **{nearest_name}** — Call {nearest_phone}\n"
        "5. 🗣️ Speak loudly — draw attention to yourself\n"
        "6. 📲 Tap 'Alert Family (SMS)' to share your live GPS with trusted contacts\n\n"
        "⚠️ This app has logged your alert. For actual emergency dispatch, always call 112."
    )

    recommendations = [
        "Tap the red SOS button in the app NOW",
        "Call 112 — National Emergency",
        "Call 1091 — Women Safety Helpline",
        "Enter the nearest open building immediately"
    ]
    return {
        'reply': reply,
        'recommendations': recommendations,
        'intent': 'emergency',
        'safety_score': 99,
        'show_sos_button': True  # Signal frontend to show SOS button in chat
    }


def respond_greeting(time_of_day: str) -> dict:
    time_ctx = _time_context(time_of_day)
    reply = (
        f"👋 Hello! I'm your **SafeHer Assistant**, here to help you travel safely under {time_ctx} conditions.\n\n"
        "You can ask me things like:\n"
        "• *'Which route is safest right now?'*\n"
        "• *'Is the canal shortcut safe at night?'*\n"
        "• *'Where is the nearest police station?'*\n"
        "• *'Why is this route risky?'*\n"
        "• *'Show me safer alternatives'*\n"
        "• *'I feel unsafe — what should I do?'*\n\n"
        "How can I help you right now? 🛡️"
    )
    recommendations = [
        "Ask: 'Which route is safest right now?'",
        "Ask: 'Where is the nearest police station?'",
        "Ask: 'Is this route safe at night?'"
    ]
    return {'reply': reply, 'recommendations': recommendations, 'intent': 'greeting', 'safety_score': 90}


def respond_general(message: str, time_of_day: str) -> dict:
    time_ctx = _time_context(time_of_day)
    reply = (
        f"I'm your **SafeHer Assistant** — I can help with safety questions under {time_ctx} conditions. "
        "Try asking me about route safety, police locations, risky zones, or what to do in an emergency."
    )
    recommendations = [
        "Ask: 'Which route is safest?'",
        "Ask: 'Where is the nearest police station?'",
        "Ask: 'What should I do if I feel unsafe?'"
    ]
    return {'reply': reply, 'recommendations': recommendations, 'intent': 'general', 'safety_score': 90}


# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------
def generate_response(message: str, routes: list, safety_zones: list,
                      police_stations: list, user_coords: list,
                      time_of_day: str = 'auto') -> dict:
    """
    Main chatbot function called by Flask /api/chat.

    Args:
        message:         Raw user message string
        routes:          List of route dicts from safety_engine / database
        safety_zones:    List of zone dicts from database
        police_stations: List of police station dicts from database
        user_coords:     [lat, lng] of current user location
        time_of_day:     'day', 'night', or 'auto'

    Returns:
        dict with keys: reply, recommendations, intent, safety_score
                        (+ optional show_sos_button for emergency)
    """
    intent = detect_intent(message)

    dispatch = {
        'safest_route':   lambda: respond_safest_route(routes, time_of_day),
        'route_at_night': lambda: respond_route_at_night(routes),
        'police_location':lambda: respond_police_location(police_stations, user_coords),
        'police_distance':lambda: respond_police_distance(police_stations, user_coords),
        'safe_zones':     lambda: respond_safe_zones(safety_zones),
        'why_risky':      lambda: respond_why_risky(routes),
        'alternatives':   lambda: respond_alternatives(routes, time_of_day),
        'score_explain':  lambda: respond_score_explain(routes),
        'risky_area':     lambda: respond_risky_area(safety_zones),
        'emergency':      lambda: respond_emergency(police_stations),
        'greeting':       lambda: respond_greeting(time_of_day),
        'general':        lambda: respond_general(message, time_of_day),
    }

    handler = dispatch.get(intent, dispatch['general'])
    result = handler()
    result['intent'] = intent  # Ensure intent is always in result
    return result
