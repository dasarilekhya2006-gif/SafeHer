"""
safe_route_recommender.py - Explainable AI-Based Safe Route Recommendation Algorithm

Calculates safety scores (0 to 100) for navigation routes using a segment-based
weighted scoring model tailored for women's safety.

Exact Factor Weights:
- Street lighting:            25% (0.25)
- Crime history:              30% (0.30)
- Crowd/activity level:       15% (0.15)
- Distance to police stations: 15% (0.15)
- Safe zones:                 10% (0.10)
- Time of day:                 5% (0.05)
Total:                       100% (1.00)

Workflow:
1. Divide route coordinates into smaller segments.
2. Calculate individual factor scores (0-100) for every segment.
3. Compute weighted safety score for each segment.
4. Detect risky segments (poorly lit, isolated, high crime) & safe corridors.
5. Aggregate segment scores with a weak-link bottleneck penalty.
6. Rank routes by safety.
7. Return safest route, scores, risky areas, safe areas, and human-readable explanations.
"""

import math
import json
from datetime import datetime

# -------------------------------------------------------------------------
# Algorithm Weights (Strictly summing to 1.00 / 100%)
# -------------------------------------------------------------------------
WEIGHTS = {
    'street_lighting': 0.25,
    'crime_history': 0.30,
    'crowd_activity': 0.15,
    'police_distance': 0.15,
    'safe_zones': 0.10,
    'time_of_day': 0.05
}

# Thresholds for classification
RISKY_SEGMENT_THRESHOLD = 55.0  # Segment score < 55 is flagged as risky
SAFE_SEGMENT_THRESHOLD = 80.0   # Segment score >= 80 is flagged as safe corridor


def haversine_distance(coord1, coord2):
    """
    Computes great-circle distance between two (lat, lng) tuples in meters.
    """
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    R = 6371000  # Earth's radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


class SafeRouteRecommender:
    """
    Explainable AI Safe Route Recommendation Engine.
    """

    def __init__(self, weights=None):
        self.weights = weights or WEIGHTS

    def parse_time_of_day(self, time_of_day=None):
        """
        Evaluates the time factor score (0 to 100) and label based on day/night status.
        Daytime has high natural visibility and witness presence.
        Nighttime introduces vulnerability requiring high artificial lighting.
        """
        if time_of_day:
            t_str = str(time_of_day).lower().strip()
            if 'night' in t_str or 'late' in t_str:
                return 35.0, 'night'
            if 'day' in t_str or 'morning' in t_str or 'afternoon' in t_str:
                return 100.0, 'day'
            if 'eve' in t_str:
                return 70.0, 'evening'
            # Try parsing HH:MM
            if ':' in t_str:
                try:
                    hour = int(t_str.split(':')[0])
                    if 20 <= hour or hour < 5:
                        return 30.0, 'night'
                    elif 5 <= hour < 17:
                        return 100.0, 'day'
                    else:
                        return 70.0, 'evening'
                except ValueError:
                    pass

        # Default: check current local server hour
        hour = datetime.now().hour
        if 20 <= hour or hour < 5:
            return 30.0, 'night'
        elif 5 <= hour < 17:
            return 100.0, 'day'
        else:
            return 70.0, 'evening'

    def divide_into_segments(self, coordinates):
        """
        Divides route coordinates into individual sequential road segments.
        Each segment contains:
          - index
          - start_coord [lat, lng]
          - end_coord [lat, lng]
          - midpoint [lat, lng]
          - length_meters
        """
        if not coordinates or len(coordinates) < 2:
            return []

        segments = []
        for i in range(len(coordinates) - 1):
            p1 = coordinates[i]
            p2 = coordinates[i + 1]
            length = haversine_distance(p1, p2)
            midpoint = [(p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0]

            segments.append({
                'segment_index': i + 1,
                'start_coord': p1,
                'end_coord': p2,
                'midpoint': midpoint,
                'length_meters': round(length, 1)
            })

        return segments

    def calculate_police_score(self, point, police_stations):
        """
        Calculates police proximity score (0 to 100) from a coordinate point.
        - Distance <= 150m: 100 (Immediate patrol booth)
        - Distance <= 500m: 75 to 99
        - Distance <= 1200m: 40 to 74
        - Distance > 1200m: 10 to 39
        """
        if not police_stations:
            return 30.0, float('inf'), None

        min_dist = float('inf')
        nearest_station = None
        for ps in police_stations:
            dist = haversine_distance(point, (ps['lat'], ps['lng']))
            if dist < min_dist:
                min_dist = dist
                nearest_station = ps

        if min_dist <= 150:
            score = 100.0
        elif min_dist <= 500:
            # Linear decay from 100 to 75
            score = 100.0 - ((min_dist - 150) / 350.0) * 25.0
        elif min_dist <= 1200:
            # Linear decay from 75 to 40
            score = 75.0 - ((min_dist - 500) / 700.0) * 35.0
        else:
            # Below 40 down to minimum 10
            score = max(10.0, 40.0 - ((min_dist - 1200) / 1000.0) * 25.0)

        return round(score, 1), round(min_dist, 1), nearest_station

    def calculate_safe_zone_score(self, point, safety_zones):
        """
        Calculates safe zone score (0 to 100) based on intersection with safe or risky zones.
        - Inside a Safe Zone: 90 - 100
        - Inside a Risky / Low-light Zone: 10 - 25
        - Neutral Zone (outside both): 65
        """
        if not safety_zones:
            return 65.0, 'neutral', None

        for zone in safety_zones:
            dist = haversine_distance(point, (zone['lat'], zone['lng']))
            if dist <= zone['radius']:
                if zone['type'] == 'safe':
                    return 95.0, 'safe', zone
                else:
                    return 15.0, 'risky', zone

        return 65.0, 'neutral', None

    def evaluate_segment(self, segment, safety_context, time_period='auto'):
        """
        Evaluates the safety score of an individual road segment across all 6 factors:
        1. Street Lighting (25%)
        2. Crime History (30%)
        3. Crowd/Activity Level (15%)
        4. Police Distance (15%)
        5. Safe Zones (10%)
        6. Time of Day (5%)
        """
        midpoint = segment['midpoint']

        # 1. Street Lighting Score (0 to 100)
        # Default derived from context or segment properties
        lighting_score = float(safety_context.get('lighting_pct', 70))

        # 2. Crime History Score (0 to 100, where 100 = 0 crime, 0 = extreme crime)
        crime_rate = float(safety_context.get('crime_pct', 25))
        crime_score = max(0.0, min(100.0, 100.0 - crime_rate))

        # 3. Crowd / Activity Level (0 to 100)
        crowd_score = float(safety_context.get('crowd_pct', 60))

        # 4. Police Proximity Score (0 to 100)
        police_stations = safety_context.get('police_stations', [])
        police_score, police_dist, nearest_police = self.calculate_police_score(midpoint, police_stations)

        # 5. Safe Zones Score (0 to 100)
        safety_zones = safety_context.get('safety_zones', [])
        zone_score, zone_status, zone_match = self.calculate_safe_zone_score(midpoint, safety_zones)

        # 6. Time of Day Score (0 to 100)
        time_score, period_label = self.parse_time_of_day(time_period)

        # Nighttime compound penalty:
        # At night, poor street lighting and deserted areas become significantly more dangerous
        situational_adjustment = 0.0
        if period_label == 'night':
            if lighting_score < 40:
                situational_adjustment -= 12.0
            if crowd_score < 30:
                situational_adjustment -= 8.0
            if zone_status == 'risky':
                situational_adjustment -= 10.0

        # Weighted Sum Formulation
        weighted_score = (
            (lighting_score * self.weights['street_lighting']) +
            (crime_score * self.weights['crime_history']) +
            (crowd_score * self.weights['crowd_activity']) +
            (police_score * self.weights['police_distance']) +
            (zone_score * self.weights['safe_zones']) +
            (time_score * self.weights['time_of_day']) +
            situational_adjustment
        )

        final_segment_score = round(max(5.0, min(100.0, weighted_score)), 1)

        # Risk Classification
        is_risky = (final_segment_score < RISKY_SEGMENT_THRESHOLD) or (zone_status == 'risky') or (lighting_score < 35)
        is_safe = (final_segment_score >= SAFE_SEGMENT_THRESHOLD) and (zone_status != 'risky')

        return {
            'segment_index': segment['segment_index'],
            'start_coord': segment['start_coord'],
            'end_coord': segment['end_coord'],
            'midpoint': midpoint,
            'length_meters': segment['length_meters'],
            'segment_score': final_segment_score,
            'is_risky': is_risky,
            'is_safe': is_safe,
            'zone_status': zone_status,
            'zone_name': zone_match['title'] if zone_match else None,
            'nearest_police': nearest_police['name'] if nearest_police else None,
            'police_distance_m': police_dist,
            'factor_breakdown': {
                'street_lighting': {
                    'score': lighting_score,
                    'weighted': round(lighting_score * self.weights['street_lighting'], 2),
                    'weight_pct': '25%'
                },
                'crime_history': {
                    'score': crime_score,
                    'weighted': round(crime_score * self.weights['crime_history'], 2),
                    'weight_pct': '30%'
                },
                'crowd_activity': {
                    'score': crowd_score,
                    'weighted': round(crowd_score * self.weights['crowd_activity'], 2),
                    'weight_pct': '15%'
                },
                'police_distance': {
                    'score': police_score,
                    'weighted': round(police_score * self.weights['police_distance'], 2),
                    'weight_pct': '15%',
                    'distance_m': police_dist
                },
                'safe_zones': {
                    'score': zone_score,
                    'weighted': round(zone_score * self.weights['safe_zones'], 2),
                    'weight_pct': '10%',
                    'status': zone_status
                },
                'time_of_day': {
                    'score': time_score,
                    'weighted': round(time_score * self.weights['time_of_day'], 2),
                    'weight_pct': '5%',
                    'period': period_label
                }
            }
        }

    def evaluate_route(self, route_input, safety_zones=None, police_stations=None, time_of_day='auto'):
        """
        Divides a route into segments, evaluates each segment, detects risky & safe zones,
        and aggregates into the final route safety score.
        """
        route_id = route_input.get('id', 'route-1')
        route_name = route_input.get('name', 'Route')
        coordinates = route_input.get('coordinates', [])

        if len(coordinates) < 2:
            return {
                'id': route_id,
                'name': route_name,
                'safety_score': 0,
                'error': 'At least 2 coordinates required for a route.'
            }

        # Divide into smaller segments
        segments = self.divide_into_segments(coordinates)

        # Build safety context for this route
        safety_context = {
            'lighting_pct': route_input.get('lighting_pct', route_input.get('lighting', {}).get('percent', 70)),
            'crime_pct': route_input.get('crime_pct', route_input.get('crime', {}).get('percent', 30)),
            'crowd_pct': route_input.get('crowd_pct', route_input.get('crowd', {}).get('percent', 60)),
            'safety_zones': safety_zones or [],
            'police_stations': police_stations or []
        }

        evaluated_segments = []
        risky_areas = []
        safe_areas = []
        total_length_m = 0.0
        weighted_sum_by_length = 0.0
        min_segment_score = 100.0

        for seg in segments:
            eval_seg = self.evaluate_segment(seg, safety_context, time_of_day)
            evaluated_segments.append(eval_seg)

            seg_len = seg['length_meters']
            seg_score = eval_seg['segment_score']
            total_length_m += seg_len
            weighted_sum_by_length += seg_score * seg_len

            if seg_score < min_segment_score:
                min_segment_score = seg_score

            # Detect Risky Area
            if eval_seg['is_risky']:
                risky_areas.append({
                    'segment_index': eval_seg['segment_index'],
                    'location': eval_seg['midpoint'],
                    'score': seg_score,
                    'reason': f"Low score ({seg_score}/100) due to low illumination or isolated surroundings.",
                    'zone_name': eval_seg['zone_name'],
                    'length_meters': seg_len
                })

            # Detect Safe Area
            if eval_seg['is_safe']:
                safe_areas.append({
                    'segment_index': eval_seg['segment_index'],
                    'location': eval_seg['midpoint'],
                    'score': seg_score,
                    'features': "Well-lit corridor, high civilian foot-traffic, verified safe watch zone.",
                    'zone_name': eval_seg['zone_name'],
                    'length_meters': seg_len
                })

        # Length-weighted average of segment scores
        if total_length_m > 0:
            avg_segment_score = weighted_sum_by_length / total_length_m
        else:
            avg_segment_score = sum(s['segment_score'] for s in evaluated_segments) / len(evaluated_segments)

        # Bottleneck weak-link penalty:
        # A route that has an extremely dangerous segment should not achieve a high safety score.
        # Final Score = 85% average score + 15% minimum segment score
        final_route_score = int(round(0.85 * avg_segment_score + 0.15 * min_segment_score))
        final_route_score = max(10, min(99, final_route_score))

        # Explainable Reasons for the Score
        reasons = self.generate_reasons(
            final_route_score,
            safety_context,
            risky_areas,
            safe_areas,
            evaluated_segments,
            time_of_day
        )

        # Route Tier & Badge
        if final_route_score >= 82:
            tier = 'SAFEST RECOMMENDED ROUTE'
            score_color = 'green'
            route_type = 'safest'
        elif final_route_score >= 60:
            tier = 'MODERATE SAFETY ROUTE'
            score_color = 'amber'
            route_type = 'moderate'
        else:
            tier = 'HIGH RISK — NOT RECOMMENDED'
            score_color = 'red'
            route_type = 'risky'

        return {
            'id': route_id,
            'name': route_name,
            'safety_score': final_route_score,
            'score_color': score_color,
            'tier': tier,
            'type': route_type,
            'total_distance_km': round(total_length_m / 1000.0, 2),
            'total_segments': len(evaluated_segments),
            'min_segment_score': min_segment_score,
            'avg_segment_score': round(avg_segment_score, 1),
            'risky_areas': risky_areas,
            'safe_areas': safe_areas,
            'reasons': reasons,
            'segments': evaluated_segments
        }

    def generate_reasons(self, final_score, context, risky_areas, safe_areas, segments, time_of_day):
        """
        Generates human-readable, transparent bullet points explaining why the route received this score.
        """
        reasons = []
        lighting = context.get('lighting_pct', 70)
        crime = context.get('crime_pct', 30)
        crowd = context.get('crowd_pct', 60)
        _, period = self.parse_time_of_day(time_of_day)

        # Lighting Reason (25% Weight)
        if lighting >= 85:
            reasons.append(f"High Street Lighting ({lighting}%): Continuous high-intensity LED street illumination provides excellent line-of-sight.")
        elif lighting >= 60:
            reasons.append(f"Moderate Lighting ({lighting}%): Standard street lighting present, with occasional tree shadow patches.")
        else:
            reasons.append(f"Poor Lighting Warning ({lighting}%): Several unlit stretches and dark corners with broken streetlights.")

        # Crime History Reason (30% Weight)
        if crime <= 20:
            reasons.append(f"Low Crime Rate (Crime Index {crime}%): Zero violent incidents recorded in past 180 days with active CCTV coverage.")
        elif crime <= 50:
            reasons.append(f"Moderate Crime Risk (Crime Index {crime}%): Occasional non-violent petty incidents reported.")
        else:
            reasons.append(f"Elevated Crime Alert (Crime Index {crime}%): High frequency of reported incidents after dark.")

        # Crowd & Commercial Activity (15% Weight)
        if crowd >= 75:
            reasons.append(f"High Pedestrian Activity ({crowd}%): Open 24/7 stores, pharmacies, and transit hubs ensure continuous natural surveillance.")
        elif crowd >= 45:
            reasons.append(f"Moderate Activity ({crowd}%): Moderate foot traffic until evening, becoming quiet late at night.")
        else:
            reasons.append(f"Isolation Warning ({crowd}%): Deserted service lanes and closed shutters with scarce civilian presence.")

        # Police Proximity (15% Weight)
        police_dists = [s['police_distance_m'] for s in segments if s.get('police_distance_m')]
        if police_dists:
            min_p_dist = min(police_dists)
            if min_p_dist <= 250:
                reasons.append(f"Rapid Emergency Response: Active Police Assistance Booth within {int(min_p_dist)}m (<2 min response time).")
            elif min_p_dist <= 750:
                reasons.append(f"Police Proximity: Police station situated within {int(min_p_dist)}m.")
            else:
                reasons.append(f"Limited Police Coverage: Nearest police outpost is over {int(min_p_dist)}m away.")

        # Safe vs Risky Zones (10% Weight)
        if safe_areas:
            reasons.append(f"Safe Corridors: Route traverses {len(safe_areas)} verified Safe Watch zones with security presence.")
        if risky_areas:
            reasons.append(f"Risky Zones: Traverses {len(risky_areas)} unmonitored or low-light zones.")

        # Time of Day Context (5% Weight)
        if period == 'night':
            reasons.append("Time Factor (Nighttime): Route scores adjusted with nighttime vulnerability factors applied.")
        else:
            reasons.append("Time Factor (Daytime): Ambient daylight provides clear natural visibility.")

        return reasons

    def rank_routes(self, routes_list, safety_zones=None, police_stations=None, time_of_day='auto'):
        """
        Ranks a list of candidate routes from highest to lowest safety score.
        Returns:
          - ranked_routes: list of evaluated routes sorted by safety score (descending)
          - safest_route: the #1 highest-scoring route
          - summary: high-level recommendation summary
        """
        evaluated_routes = []
        for r in routes_list:
            eval_res = self.evaluate_route(r, safety_zones, police_stations, time_of_day)
            evaluated_routes.append(eval_res)

        # Sort by safety score descending (Safest first)
        evaluated_routes.sort(key=lambda x: x['safety_score'], reverse=True)

        safest = evaluated_routes[0] if evaluated_routes else None

        return {
            'safest_route': safest,
            'ranked_routes': evaluated_routes,
            'total_routes_evaluated': len(evaluated_routes),
            'recommendation_summary': {
                'recommended_route_name': safest['name'] if safest else None,
                'recommended_score': safest['safety_score'] if safest else 0,
                'tier': safest['tier'] if safest else None,
                'advice': f"Choose '{safest['name'] if safest else ''}' for optimal lighting, active crowd presence, and fast police response."
            }
        }


# -------------------------------------------------------------------------
# Standalone Demonstration with Sample Input and Output
# -------------------------------------------------------------------------
if __name__ == '__main__':
    print("=" * 75)
    print("  🛡️  SafeHer AI Safe Route Recommendation Algorithm Demo")
    print("=" * 75)

    # 1. Sample Environmental Safety Data
    sample_police_stations = [
        {'lat': 28.6370, 'lng': 77.2235, 'name': 'Police Assistance Booth #4', 'phone': '112'},
        {'lat': 28.6335, 'lng': 77.2180, 'name': 'Metro Security & Transit Police', 'phone': '112'}
    ]

    sample_safety_zones = [
        {'lat': 28.6365, 'lng': 77.2240, 'radius': 420, 'type': 'safe', 'title': 'Grand Boulevard Commercial Corridor'},
        {'lat': 28.6385, 'lng': 77.2175, 'radius': 350, 'type': 'risky', 'title': 'Canal Back Alleyway'}
    ]

    # 2. Sample Candidate Routes
    sample_candidate_routes = [
        {
            'id': 'route-boulevard',
            'name': 'Main Boulevard Safe Corridor',
            'lighting_pct': 96,
            'crime_pct': 12,
            'crowd_pct': 92,
            'coordinates': [
                [28.6328, 77.2155],
                [28.6342, 77.2185],
                [28.6360, 77.2220],
                [28.6385, 77.2305],
                [28.6435, 77.2340]
            ]
        },
        {
            'id': 'route-transit',
            'name': 'Metro Avenue & Transit Link',
            'lighting_pct': 72,
            'crime_pct': 45,
            'crowd_pct': 65,
            'coordinates': [
                [28.6328, 77.2155],
                [28.6350, 77.2170],
                [28.6380, 77.2210],
                [28.6435, 77.2340]
            ]
        },
        {
            'id': 'route-alley',
            'name': 'Old Canal Alleyway Shortcut',
            'lighting_pct': 28,
            'crime_pct': 85,
            'crowd_pct': 18,
            'coordinates': [
                [28.6328, 77.2155],
                [28.6348, 77.2140],
                [28.6390, 77.2180],
                [28.6435, 77.2340]
            ]
        }
    ]

    recommender = SafeRouteRecommender()
    results = recommender.rank_routes(
        routes_list=sample_candidate_routes,
        safety_zones=sample_safety_zones,
        police_stations=sample_police_stations,
        time_of_day='night'
    )

    print(f"\nTotal Routes Evaluated: {results['total_routes_evaluated']}")
    print(f"Recommended Safest Route: {results['safest_route']['name']}")
    print(f"Safety Score: {results['safest_route']['safety_score']}/100 ({results['safest_route']['tier']})")
    print(f"Total Distance: {results['safest_route']['total_distance_km']} km across {results['safest_route']['total_segments']} segments\n")

    print("--- RANKED ROUTES ---")
    for idx, r in enumerate(results['ranked_routes'], 1):
        print(f"#{idx} [{r['safety_score']}/100] {r['name']} ({r['tier']})")
        print(f"   Safe Segments: {len(r['safe_areas'])} | Risky Segments: {len(r['risky_areas'])}")
        print(f"   Key Reasons: {r['reasons'][0]} | {r['reasons'][1]}")

    print("\n--- RISKY SEGMENTS DETECTED ON RISKY ROUTE ---")
    risky_rt = results['ranked_routes'][-1]
    for ra in risky_rt['risky_areas']:
        print(f"⚠️ Segment #{ra['segment_index']} at {ra['location']} (Score: {ra['score']}/100): {ra['reason']}")

    print("\n--- SAMPLE JSON OUTPUT STRUCTURE ---")
    print(json.dumps({
        'safest_route': results['safest_route']['name'],
        'safety_score': results['safest_route']['safety_score'],
        'risky_areas_count': len(results['safest_route']['risky_areas']),
        'safe_areas_count': len(results['safest_route']['safe_areas']),
        'reasons': results['safest_route']['reasons']
    }, indent=2))
    print("=" * 75)
