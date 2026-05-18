"""
CTA 'L' Network Resilience & Cascading Failure Simulator
Python 3 + NetworkX + Pandas + PyGame + Asyncio (Pygbag-compatible)
"""

import asyncio
import math
import random
import sys
import os
from collections import defaultdict, deque
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx
import pygame

# ─── Optional Pandas import ───────────────────────────────────────────────────
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════
WIN_W, WIN_H = 1100, 850
MAP_W, MAP_H = 800, 800
MAP_OFFSET_X, MAP_OFFSET_Y = 20, 25

MIN_LAT, MAX_LAT = 41.644, 42.023
MIN_LON, MAX_LON = -87.940, -87.524

FPS = 60
OVERLOAD_THRESHOLD = 1.5     # 150% capacity triggers cascade
TICK_INTERVAL = 0.9          # seconds between cascade ticks
NODE_BASE_RADIUS = 6
NODE_MAX_RADIUS = 18
CAPACITY_BASE = 1000         # arbitrary passenger units

# CTA official line colors (hex → RGB)
LINE_COLORS: Dict[str, Tuple[int,int,int]] = {
    "Red":    (199,  31,  55),
    "Blue":   ( 0,  93, 170),
    "Brown":  ( 98,  54,  27),
    "Green":  ( 0, 158,  73),
    "Orange": (249, 126,  10),
    "Pink":   (226, 126, 166),
    "Purple": (82,   35, 152),
    "Yellow": (249, 227,   0),
}

PANEL_X = MAP_W + MAP_OFFSET_X + 15
PANEL_W = WIN_W - PANEL_X - 10
BG_COLOR       = (15,  15,  20)
TEXT_COLOR     = (220, 220, 220)
HEADER_COLOR   = (255, 200,  50)
WARN_COLOR     = (255,  80,  50)
GOOD_COLOR     = ( 80, 220, 120)
DEAD_COLOR     = ( 60,  60,  60)
SELECT_COLOR   = (255, 255,   0)
OVERLOAD_COLOR = (255, 140,   0)
CASCADE_GLOW   = (255,  50,  50)
GRID_COLOR     = ( 30,  30,  38)

# ═══════════════════════════════════════════════════════════════════════════════
# HARDCODED CTA FALLBACK DATA
# Each station: (id, name, lat, lon, lines)
# ═══════════════════════════════════════════════════════════════════════════════
STATIONS_DATA = [
    # ── Red Line ──────────────────────────────────────────────────────────────
    ("howard",       "Howard",              42.0192, -87.6727, ["Red","Purple","Yellow"]),
    ("jarvis",       "Jarvis",              42.0153, -87.6694, ["Red"]),
    ("morse",        "Morse",               42.0083, -87.6658, ["Red"]),
    ("loyola",       "Loyola",              42.0013, -87.6614, ["Red"]),
    ("granville",    "Granville",           41.9939, -87.6594, ["Red"]),
    ("thorndale",    "Thorndale",           41.9899, -87.6593, ["Red"]),
    ("bryn_mawr",    "Bryn Mawr",           41.9835, -87.6594, ["Red"]),
    ("berwyn",       "Berwyn",              41.9778, -87.6590, ["Red"]),
    ("argyle",       "Argyle",              41.9736, -87.6588, ["Red"]),
    ("lawrence",     "Lawrence",            41.9690, -87.6585, ["Red"]),
    ("wilson",       "Wilson",              41.9646, -87.6578, ["Red","Purple"]),
    ("sheridan",     "Sheridan",            41.9533, -87.6545, ["Red"]),
    ("addison_red",  "Addison (Red)",       41.9474, -87.6539, ["Red"]),
    ("belmont_red",  "Belmont",             41.9400, -87.6526, ["Red","Brown","Purple"]),
    ("fullerton",    "Fullerton",           41.9252, -87.6527, ["Red","Brown","Purple"]),
    ("north_clybourn","North/Clybourn",     41.9109, -87.6479, ["Red"]),
    ("clark_division","Clark/Division",     41.9044, -87.6313, ["Red"]),
    ("chicago_red",  "Chicago (Red)",       41.8965, -87.6310, ["Red"]),
    ("grand_red",    "Grand (Red)",         41.8916, -87.6312, ["Red"]),
    ("lake_red",     "Lake (Red)",          41.8848, -87.6277, ["Red"]),
    ("monroe_red",   "Monroe (Red)",        41.8807, -87.6276, ["Red"]),
    ("jackson_red",  "Jackson (Red)",       41.8782, -87.6277, ["Red"]),
    ("harrison",     "Harrison",            41.8741, -87.6274, ["Red"]),
    ("roosevelt_red","Roosevelt",           41.8674, -87.6271, ["Red","Orange","Green"]),
    ("cermak_chinatown","Cermak-Chinatown", 41.8530, -87.6305, ["Red"]),
    ("sox_35th",     "Sox-35th",            41.8310, -87.6306, ["Red"]),
    ("47th_red",     "47th (Red)",          41.8095, -87.6307, ["Red"]),
    ("garfield_red", "Garfield (Red)",      41.7955, -87.6308, ["Red"]),
    ("63rd_red",     "63rd (Red)",          41.7800, -87.6308, ["Red"]),
    ("69th",         "69th",                41.7685, -87.6254, ["Red"]),
    ("79th",         "79th",                41.7502, -87.6252, ["Red"]),
    ("87th",         "87th",                41.7363, -87.6252, ["Red"]),
    ("95th_dan_ryan","95th/Dan Ryan",       41.7224, -87.6246, ["Red"]),

    # ── Blue Line (O'Hare branch) ─────────────────────────────────────────────
    ("ohare",        "O'Hare",              41.9761, -87.9073, ["Blue"]),
    ("rosemont",     "Rosemont",            41.9836, -87.8586, ["Blue"]),
    ("o_hare_blue",  "O'Hare/River Rd",     41.9836, -87.8450, ["Blue"]),   # Cumberland
    ("harlem_blue",  "Harlem (Blue)",       41.9836, -87.8067, ["Blue"]),
    ("jefferson_park","Jefferson Park",     41.9707, -87.7612, ["Blue"]),
    ("montrose_blue","Montrose (Blue)",     41.9614, -87.7438, ["Blue"]),
    ("irving_park_blue","Irving Park (Blue)",41.9525,-87.7314, ["Blue"]),
    ("addison_blue", "Addison (Blue)",      41.9474, -87.7177, ["Blue"]),
    ("belmont_blue", "Belmont (Blue)",      41.9387, -87.7127, ["Blue"]),
    ("logan_square", "Logan Square",        41.9296, -87.7075, ["Blue"]),
    ("california",   "California",          41.9216, -87.6980, ["Blue"]),
    ("western_blue", "Western (Blue)",      41.9161, -87.6871, ["Blue"]),
    ("damen_blue",   "Damen (Blue)",        41.9094, -87.6774, ["Blue"]),
    ("division",     "Division (Blue)",     41.9031, -87.6679, ["Blue"]),
    ("chicago_blue", "Chicago (Blue)",      41.8963, -87.6575, ["Blue"]),
    ("grand_blue",   "Grand (Blue)",        41.8912, -87.6479, ["Blue"]),
    ("clark_lake",   "Clark/Lake",          41.8858, -87.6312, ["Blue","Brown","Green","Orange","Pink","Purple"]),
    ("washington_blue","Washington (Blue)", 41.8832, -87.6291, ["Blue","Orange"]),
    ("monroe_blue",  "Monroe (Blue)",       41.8807, -87.6291, ["Blue","Orange"]),
    ("jackson_blue", "Jackson (Blue)",      41.8781, -87.6291, ["Blue","Orange"]),
    ("lasalle_blue", "LaSalle (Blue)",      41.8755, -87.6308, ["Blue"]),
    ("clinton_blue", "Clinton (Blue)",      41.8750, -87.6404, ["Blue"]),
    ("uic_halsted",  "UIC-Halsted",         41.8754, -87.6497, ["Blue"]),
    ("racine",       "Racine",              41.8754, -87.6591, ["Blue"]),
    ("illinois_med", "Illinois Medical",    41.8755, -87.6739, ["Blue"]),
    ("western_forest","Western (Forest Pk)",41.8754,-87.6880,  ["Blue"]),
    ("kedzie_blue",  "Kedzie (Blue)",       41.8754, -87.7054, ["Blue"]),
    ("pulaski_blue", "Pulaski (Blue)",      41.8754, -87.7254, ["Blue"]),
    ("cicero_blue",  "Cicero (Blue)",       41.8754, -87.7454, ["Blue"]),
    ("austin_blue",  "Austin (Blue)",       41.8754, -87.7757, ["Blue"]),
    ("oak_park_blue","Oak Park (Blue)",     41.8754, -87.7935, ["Blue"]),
    ("harlem_forest","Harlem/Forest Park",  41.8754, -87.8095, ["Blue"]),
    ("forest_park",  "Forest Park",         41.8752, -87.8178, ["Blue"]),

    # ── Brown Line ────────────────────────────────────────────────────────────
    ("kimball",      "Kimball",             41.9679, -87.7136, ["Brown"]),
    ("kedzie_brown", "Kedzie (Brown)",      41.9658, -87.7083, ["Brown"]),
    ("francisco",    "Francisco",           41.9661, -87.7015, ["Brown"]),
    ("rockwell",     "Rockwell",            41.9662, -87.6940, ["Brown"]),
    ("western_brown","Western (Brown)",     41.9663, -87.6881, ["Brown"]),
    ("damen_brown",  "Damen (Brown)",       41.9663, -87.6782, ["Brown"]),
    ("montrose_brown","Montrose (Brown)",   41.9614, -87.6745, ["Brown"]),
    ("irving_park_brown","Irving Park (Brn)",41.9525,-87.6745, ["Brown"]),
    ("addison_brown","Addison (Brown)",     41.9474, -87.6745, ["Brown"]),
    ("paulina",      "Paulina",             41.9434, -87.6706, ["Brown"]),
    ("southport",    "Southport",           41.9436, -87.6638, ["Brown"]),
    ("wellington",   "Wellington",          41.9361, -87.6538, ["Brown","Purple"]),
    ("diversey",     "Diversey",            41.9324, -87.6537, ["Brown","Purple"]),
    ("armitage",     "Armitage",            41.9184, -87.6526, ["Brown","Purple"]),
    ("sedgwick",     "Sedgwick",            41.9107, -87.6387, ["Brown","Purple"]),
    ("chicago_brown","Chicago (Brown)",     41.8965, -87.6317, ["Brown","Purple"]),
    ("merchandise_mart","Merchandise Mart", 41.8886, -87.6336, ["Brown","Purple"]),
    ("quincy",       "Quincy",              41.8788, -87.6338, ["Brown","Orange","Purple","Pink"]),
    ("harold_wash",  "Harold Washington Lib",41.8761,-87.6291, ["Brown","Orange","Purple","Pink"]),
    ("adams_wabash", "Adams/Wabash",        41.8796, -87.6262, ["Brown","Green","Orange","Pink","Purple"]),
    ("madison_wabash","Madison/Wabash",     41.8821, -87.6261, ["Brown","Green","Orange","Pink","Purple"]),
    ("randolph_wabash","Randolph/Wabash",   41.8847, -87.6261, ["Brown","Green","Orange","Pink","Purple"]),

    # ── Green Line ────────────────────────────────────────────────────────────
    ("harlem_green", "Harlem/Lake (Green)", 41.8870, -87.8041, ["Green"]),
    ("oak_park_green","Oak Park (Green)",   41.8870, -87.7934, ["Green"]),
    ("ridgeland",    "Ridgeland",           41.8871, -87.7835, ["Green"]),
    ("austin_green", "Austin (Green)",      41.8870, -87.7757, ["Green"]),
    ("central_green","Central (Green)",     41.8870, -87.7654, ["Green"]),
    ("laramie",      "Laramie",             41.8870, -87.7553, ["Green"]),
    ("cicero_green", "Cicero (Green)",      41.8870, -87.7454, ["Green"]),
    ("pulaski_green","Pulaski (Green)",     41.8870, -87.7254, ["Green"]),
    ("conservatory", "Conservatory",        41.8869, -87.7165, ["Green"]),
    ("kedzie_green", "Kedzie (Green)",      41.8869, -87.7054, ["Green"]),
    ("ashland_green","Ashland (Green)",     41.8870, -87.6648, ["Green"]),
    ("morgan",       "Morgan",              41.8870, -87.6519, ["Green","Pink"]),
    ("clinton_green","Clinton (Green)",     41.8859, -87.6416, ["Green","Pink"]),
    ("lake_loop",    "Lake",                41.8848, -87.6277, ["Green","Brown"]),
    ("east_63rd",    "East 63rd",           41.7802, -87.5906, ["Green"]),
    ("cottage_grove","Cottage Grove",       41.7802, -87.6058, ["Green"]),
    ("king_drive",   "King Drive",          41.7802, -87.6155, ["Green"]),
    ("43rd",         "43rd",                41.8165, -87.6184, ["Green"]),
    ("47th_green",   "47th (Green)",        41.8096, -87.6184, ["Green"]),
    ("51st",         "51st",                41.8013, -87.6185, ["Green"]),
    ("garfield_green","Garfield (Green)",   41.7955, -87.6185, ["Green"]),
    ("halsted_green","Halsted (Green)",     41.8357, -87.6484, ["Green"]),
    ("35th_bronzeville","35th/Bronzeville",  41.8311, -87.6287, ["Green"]),

    # ── Orange Line ───────────────────────────────────────────────────────────
    ("midway",       "Midway",              41.7866, -87.7373, ["Orange"]),
    ("pulaski_orange","Pulaski (Orange)",   41.7999, -87.7254, ["Orange"]),
    ("kedzie_orange","Kedzie (Orange)",     41.8048, -87.7054, ["Orange"]),
    ("western_orange","Western (Orange)",  41.8050, -87.6879, ["Orange"]),
    ("35th_archer",  "35th/Archer",         41.8297, -87.6807, ["Orange"]),
    ("ashland_orange","Ashland (Orange)",   41.8394, -87.6647, ["Orange"]),
    ("halsted_orange","Halsted (Orange)",   41.8447, -87.6479, ["Orange"]),
    ("roosevelt_orange","Roosevelt (Orange)",41.8674,-87.6271, ["Orange","Green","Red"]),

    # ── Pink Line ─────────────────────────────────────────────────────────────
    ("54th_cermak",  "54th/Cermak",         41.8523, -87.7584, ["Pink"]),
    ("cermak_pink",  "Cermak/Kildare",      41.8524, -87.7384, ["Pink"]),
    ("kostner",      "Kostner",             41.8524, -87.7284, ["Pink"]),
    ("pulaski_pink", "Pulaski (Pink)",      41.8524, -87.7254, ["Pink"]),
    ("central_pink", "Central Park (Pink)", 41.8524, -87.7154, ["Pink"]),
    ("kedzie_pink",  "Kedzie (Pink)",       41.8524, -87.7054, ["Pink"]),
    ("california_pink","California (Pink)", 41.8524, -87.6983, ["Pink"]),
    ("western_pink", "Western (Pink)",      41.8524, -87.6879, ["Pink"]),
    ("damen_pink",   "Damen (Pink)",        41.8524, -87.6774, ["Pink"]),
    ("18th",         "18th",                41.8575, -87.6679, ["Pink"]),
    ("polk",         "Polk",                41.8712, -87.6479, ["Pink"]),
    ("ashland_pink", "Ashland (Pink)",      41.8750, -87.6649, ["Pink"]),

    # ── Purple Line ───────────────────────────────────────────────────────────
    ("linden",       "Linden",              42.0733, -87.6935, ["Purple"]),
    ("central_purple","Central (Purple)",   42.0638, -87.6862, ["Purple"]),
    ("noyes",        "Noyes",               42.0582, -87.6835, ["Purple"]),
    ("foster",       "Foster (Purple)",     42.0530, -87.6834, ["Purple"]),
    ("davis",        "Davis",               42.0467, -87.6833, ["Purple"]),
    ("dempster",     "Dempster",            42.0416, -87.6834, ["Purple"]),
    ("main",         "Main",                42.0329, -87.6797, ["Purple"]),
    ("south_blvd",   "South Blvd",          42.0260, -87.6780, ["Purple"]),

    # ── Yellow Line ───────────────────────────────────────────────────────────
    ("dempster_skokie","Dempster-Skokie",   42.0381, -87.7510, ["Yellow"]),
    ("oakton_skokie","Oakton-Skokie",       42.0253, -87.7484, ["Yellow"]),
]

# Edges: (station_id_a, station_id_b, line, weight)
EDGES_DATA = [
    # Red Line – north branch
    ("howard","jarvis","Red",1),("jarvis","morse","Red",1),("morse","loyola","Red",1),
    ("loyola","granville","Red",1),("granville","thorndale","Red",1),
    ("thorndale","bryn_mawr","Red",1),("bryn_mawr","berwyn","Red",1),
    ("berwyn","argyle","Red",1),("argyle","lawrence","Red",1),
    ("lawrence","wilson","Red",1),("wilson","sheridan","Red",1),
    ("sheridan","addison_red","Red",1),("addison_red","belmont_red","Red",1),
    ("belmont_red","fullerton","Red",1),("fullerton","north_clybourn","Red",1),
    ("north_clybourn","clark_division","Red",1),("clark_division","chicago_red","Red",1),
    ("chicago_red","grand_red","Red",1),("grand_red","lake_red","Red",1),
    ("lake_red","monroe_red","Red",1),("monroe_red","jackson_red","Red",1),
    ("jackson_red","harrison","Red",1),("harrison","roosevelt_red","Red",1),
    ("roosevelt_red","cermak_chinatown","Red",1),("cermak_chinatown","sox_35th","Red",1),
    ("sox_35th","47th_red","Red",1),("47th_red","garfield_red","Red",1),
    ("garfield_red","63rd_red","Red",1),("63rd_red","69th","Red",1),
    ("69th","79th","Red",1),("79th","87th","Red",1),("87th","95th_dan_ryan","Red",1),

    # Blue Line – O'Hare branch
    ("ohare","rosemont","Blue",1),("rosemont","o_hare_blue","Blue",1),
    ("o_hare_blue","harlem_blue","Blue",1),("harlem_blue","jefferson_park","Blue",1),
    ("jefferson_park","montrose_blue","Blue",1),("montrose_blue","irving_park_blue","Blue",1),
    ("irving_park_blue","addison_blue","Blue",1),("addison_blue","belmont_blue","Blue",1),
    ("belmont_blue","logan_square","Blue",1),("logan_square","california","Blue",1),
    ("california","western_blue","Blue",1),("western_blue","damen_blue","Blue",1),
    ("damen_blue","division","Blue",1),("division","chicago_blue","Blue",1),
    ("chicago_blue","grand_blue","Blue",1),("grand_blue","clark_lake","Blue",1),
    ("clark_lake","washington_blue","Blue",1),("washington_blue","monroe_blue","Blue",1),
    ("monroe_blue","jackson_blue","Blue",1),("jackson_blue","lasalle_blue","Blue",1),
    ("lasalle_blue","clinton_blue","Blue",1),("clinton_blue","uic_halsted","Blue",1),
    ("uic_halsted","racine","Blue",1),("racine","illinois_med","Blue",1),
    ("illinois_med","western_forest","Blue",1),("western_forest","kedzie_blue","Blue",1),
    ("kedzie_blue","pulaski_blue","Blue",1),("pulaski_blue","cicero_blue","Blue",1),
    ("cicero_blue","austin_blue","Blue",1),("austin_blue","oak_park_blue","Blue",1),
    ("oak_park_blue","harlem_forest","Blue",1),("harlem_forest","forest_park","Blue",1),

    # Brown Line
    ("kimball","kedzie_brown","Brown",1),("kedzie_brown","francisco","Brown",1),
    ("francisco","rockwell","Brown",1),("rockwell","western_brown","Brown",1),
    ("western_brown","damen_brown","Brown",1),("damen_brown","montrose_brown","Brown",1),
    ("montrose_brown","irving_park_brown","Brown",1),
    ("irving_park_brown","addison_brown","Brown",1),
    ("addison_brown","paulina","Brown",1),("paulina","southport","Brown",1),
    ("southport","belmont_red","Brown",1),  # transfer at Belmont
    ("belmont_red","wellington","Brown",1),("wellington","diversey","Brown",1),
    ("diversey","fullerton","Brown",1),  # transfer at Fullerton
    ("fullerton","armitage","Brown",1),("armitage","sedgwick","Brown",1),
    ("sedgwick","chicago_brown","Brown",1),("chicago_brown","merchandise_mart","Brown",1),
    ("merchandise_mart","clark_lake","Brown",1),
    # Loop segment Brown
    ("clark_lake","randolph_wabash","Brown",1),
    ("randolph_wabash","madison_wabash","Brown",1),
    ("madison_wabash","adams_wabash","Brown",1),
    ("adams_wabash","harold_wash","Brown",1),
    ("harold_wash","quincy","Brown",1),
    ("quincy","washington_blue","Brown",1),

    # Green Line – west branch
    ("harlem_green","oak_park_green","Green",1),("oak_park_green","ridgeland","Green",1),
    ("ridgeland","austin_green","Green",1),("austin_green","central_green","Green",1),
    ("central_green","laramie","Green",1),("laramie","cicero_green","Green",1),
    ("cicero_green","pulaski_green","Green",1),("pulaski_green","conservatory","Green",1),
    ("conservatory","kedzie_green","Green",1),("kedzie_green","ashland_green","Green",1),
    ("ashland_green","morgan","Green",1),("morgan","clinton_green","Green",1),
    ("clinton_green","clark_lake","Green",1),
    # Loop segment Green
    ("clark_lake","lake_loop","Green",1),
    ("lake_loop","randolph_wabash","Green",1),
    ("randolph_wabash","adams_wabash","Green",1),
    ("adams_wabash","roosevelt_red","Green",1),
    ("roosevelt_red","35th_bronzeville","Green",1),
    ("35th_bronzeville","43rd","Green",1),("43rd","47th_green","Green",1),
    ("47th_green","51st","Green",1),("51st","garfield_green","Green",1),
    ("garfield_green","king_drive","Green",1),("king_drive","cottage_grove","Green",1),
    ("cottage_grove","east_63rd","Green",1),
    # Halsted branch
    ("morgan","halsted_green","Green",1),("halsted_green","35th_bronzeville","Green",1),

    # Orange Line
    ("midway","pulaski_orange","Orange",1),("pulaski_orange","kedzie_orange","Orange",1),
    ("kedzie_orange","western_orange","Orange",1),("western_orange","35th_archer","Orange",1),
    ("35th_archer","ashland_orange","Orange",1),("ashland_orange","halsted_orange","Orange",1),
    ("halsted_orange","roosevelt_red","Orange",1),
    # Loop Orange
    ("roosevelt_red","harold_wash","Orange",1),
    ("harold_wash","quincy","Orange",1),("quincy","washington_blue","Orange",1),
    ("washington_blue","clark_lake","Orange",1),

    # Pink Line
    ("54th_cermak","cermak_pink","Pink",1),("cermak_pink","kostner","Pink",1),
    ("kostner","pulaski_pink","Pink",1),("pulaski_pink","central_pink","Pink",1),
    ("central_pink","kedzie_pink","Pink",1),("kedzie_pink","california_pink","Pink",1),
    ("california_pink","western_pink","Pink",1),("western_pink","damen_pink","Pink",1),
    ("damen_pink","18th","Pink",1),("18th","polk","Pink",1),
    ("polk","ashland_pink","Pink",1),("ashland_pink","morgan","Pink",1),
    ("morgan","clinton_green","Pink",1),
    ("clinton_green","clark_lake","Pink",1),
    # Loop Pink
    ("clark_lake","randolph_wabash","Pink",1),
    ("randolph_wabash","adams_wabash","Pink",1),
    ("adams_wabash","quincy","Pink",1),("quincy","harold_wash","Pink",1),
    ("harold_wash","washington_blue","Pink",1),

    # Purple Line (express shares tracks with Red/Brown north of Howard)
    ("linden","central_purple","Purple",1),("central_purple","noyes","Purple",1),
    ("noyes","foster","Purple",1),("foster","davis","Purple",1),
    ("davis","dempster","Purple",1),("dempster","main","Purple",1),
    ("main","south_blvd","Purple",1),("south_blvd","howard","Purple",1),
    ("howard","wilson","Purple",1),("wilson","belmont_red","Purple",1),
    ("belmont_red","wellington","Purple",1),("wellington","diversey","Purple",1),
    ("diversey","fullerton","Purple",1),("fullerton","armitage","Purple",1),
    ("armitage","sedgwick","Purple",1),("sedgwick","chicago_brown","Purple",1),
    ("chicago_brown","merchandise_mart","Purple",1),
    ("merchandise_mart","clark_lake","Purple",1),
    ("clark_lake","randolph_wabash","Purple",1),
    ("randolph_wabash","madison_wabash","Purple",1),
    ("madison_wabash","adams_wabash","Purple",1),
    ("adams_wabash","quincy","Purple",1),("quincy","harold_wash","Purple",1),
    ("harold_wash","washington_blue","Purple",1),

    # Yellow (Skokie Swift)
    ("howard","dempster_skokie","Yellow",2),
    ("dempster_skokie","oakton_skokie","Yellow",1),
]


# ═══════════════════════════════════════════════════════════════════════════════
# COORDINATE TRANSFORM
# ═══════════════════════════════════════════════════════════════════════════════
def latlon_to_screen(lat: float, lon: float) -> Tuple[int, int]:
    """Map real-world lat/lon to screen pixel coordinates (Y-inverted)."""
    nx_ = (lon - MIN_LON) / (MAX_LON - MIN_LON)
    # Invert Y: higher lat → lower pixel y
    ny_ = 1.0 - (lat - MIN_LAT) / (MAX_LAT - MIN_LAT)
    sx = int(MAP_OFFSET_X + nx_ * MAP_W)
    sy = int(MAP_OFFSET_Y + ny_ * MAP_H)
    return sx, sy


# ═══════════════════════════════════════════════════════════════════════════════
# NETWORK BUILDER
# ═══════════════════════════════════════════════════════════════════════════════
def try_load_gtfs() -> Optional[nx.Graph]:
    """Attempt to parse local GTFS stops.txt and stop_times.txt."""
    if not HAS_PANDAS:
        return None
    try:
        stops = pd.read_csv("stops.txt")
        stop_times = pd.read_csv("stop_times.txt")
        # Filter rail (stop_id starts with known patterns)
        rail_stops = stops[stops["stop_id"].astype(str).str.startswith(("3", "4"))]
        if len(rail_stops) < 10:
            return None
        # Build minimal graph
        G = nx.Graph()
        for _, row in rail_stops.iterrows():
            G.add_node(str(row["stop_id"]), name=str(row["stop_name"]),
                       lat=float(row["stop_lat"]), lon=float(row["stop_lon"]),
                       lines=[], pos=latlon_to_screen(float(row["stop_lat"]), float(row["stop_lon"])))
        return G if len(G.nodes) >= 10 else None
    except Exception:
        return None


def build_graph() -> nx.Graph:
    """Build the simulation graph from fallback data (or GTFS if available)."""
    gtfs = try_load_gtfs()
    if gtfs and len(gtfs.nodes) >= 10:
        return gtfs

    G = nx.Graph()
    for sid, name, lat, lon, lines in STATIONS_DATA:
        pos = latlon_to_screen(lat, lon)
        G.add_node(sid,
                   name=name,
                   lat=lat, lon=lon,
                   lines=lines,
                   pos=pos,
                   capacity=CAPACITY_BASE * (1 + 0.5 * len(lines)),
                   load=0.0,
                   active=True,
                   overloaded=False)

    for a, b, line, w in EDGES_DATA:
        if a in G.nodes and b in G.nodes:
            if G.has_edge(a, b):
                G[a][b]["lines"].add(line)
            else:
                G.add_edge(a, b, weight=w, lines={line})
    return G


# ═══════════════════════════════════════════════════════════════════════════════
# SIMULATION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════
class CascadeSimulator:
    def __init__(self, G: nx.Graph):
        self.original_G = G
        self.G = G.copy()
        self._store_initial_state()
        self.pending_cascade: deque = deque()
        self.cascade_queue: Set[str] = set()
        self.efficiency_history: List[float] = []
        self.last_tick = 0.0
        self.mode = "random"   # "random" | "targeted"
        self.recalc_metrics()

    def _store_initial_state(self):
        for n, d in self.original_G.nodes(data=True):
            d_copy = dict(d)
            self.original_G.nodes[n].update(d_copy)

    def active_subgraph(self) -> nx.Graph:
        active = [n for n, d in self.G.nodes(data=True) if d.get("active", True)]
        return self.G.subgraph(active).copy()

    def recalc_metrics(self):
        sg = self.active_subgraph()
        n = sg.number_of_nodes()
        if n < 2:
            self.centrality = {}
            self.efficiency = 0.0
            self.components = list(nx.connected_components(sg)) if n else []
            return

        # Betweenness centrality (normalized)
        try:
            self.centrality = nx.betweenness_centrality(sg, normalized=True, weight="weight")
        except Exception:
            self.centrality = {v: 0.0 for v in sg.nodes}

        # Global efficiency
        self.efficiency = nx.global_efficiency(sg)
        self.components = [c for c in nx.connected_components(sg)]
        self.efficiency_history.append(self.efficiency)
        if len(self.efficiency_history) > 200:
            self.efficiency_history.pop(0)

    def deactivate_node(self, node_id: str):
        if node_id not in self.G.nodes:
            return
        if not self.G.nodes[node_id].get("active", True):
            return
        self.G.nodes[node_id]["active"] = False
        self.G.nodes[node_id]["overloaded"] = False
        self._redistribute_load(node_id)
        self.recalc_metrics()

    def _redistribute_load(self, failed_node: str):
        """Dijkstra-based rerouting; marks neighbours overloaded if >150% capacity."""
        sg = self.active_subgraph()
        neighbors = list(self.original_G.neighbors(failed_node))
        for nb in neighbors:
            if not self.G.nodes.get(nb, {}).get("active", False):
                continue
            # Extra load this node absorbs
            extra = self.G.nodes[failed_node]["capacity"] * 0.4
            self.G.nodes[nb]["load"] = self.G.nodes[nb].get("load", 0) + extra
            cap = self.G.nodes[nb]["capacity"]
            if self.G.nodes[nb]["load"] > cap * OVERLOAD_THRESHOLD:
                if nb not in self.cascade_queue:
                    self.cascade_queue.add(nb)
                    self.pending_cascade.append(nb)
                    self.G.nodes[nb]["overloaded"] = True

    def tick_cascade(self) -> List[str]:
        """Process next batch of queued cascade failures. Returns list of newly failed nodes."""
        failed_this_tick = []
        if self.pending_cascade:
            node = self.pending_cascade.popleft()
            self.cascade_queue.discard(node)
            if self.G.nodes.get(node, {}).get("active", False):
                self.deactivate_node(node)
                failed_this_tick.append(node)
        return failed_this_tick

    def reset(self):
        for n, d in self.original_G.nodes(data=True):
            self.G.nodes[n]["active"] = True
            self.G.nodes[n]["load"] = 0.0
            self.G.nodes[n]["overloaded"] = False
        self.pending_cascade.clear()
        self.cascade_queue.clear()
        self.efficiency_history.clear()
        self.recalc_metrics()

    def random_attack(self):
        active = [n for n, d in self.G.nodes(data=True) if d.get("active", True)]
        if active:
            self.deactivate_node(random.choice(active))

    def targeted_attack(self):
        """Deactivate highest-betweenness active node."""
        active = {n for n, d in self.G.nodes(data=True) if d.get("active", True)}
        if not active:
            return
        target = max(active, key=lambda n: self.centrality.get(n, 0))
        self.deactivate_node(target)

    @property
    def active_count(self) -> int:
        return sum(1 for _, d in self.G.nodes(data=True) if d.get("active", True))

    @property
    def component_count(self) -> int:
        return len(self.components)

    @property
    def cascade_pending(self) -> int:
        return len(self.pending_cascade)


# ═══════════════════════════════════════════════════════════════════════════════
# RENDERER
# ═══════════════════════════════════════════════════════════════════════════════
class Renderer:
    def __init__(self, screen: pygame.Surface, sim: CascadeSimulator):
        self.screen = screen
        self.sim = sim
        self.font_sm = pygame.font.SysFont("monospace", 12)
        self.font_md = pygame.font.SysFont("monospace", 15)
        self.font_lg = pygame.font.SysFont("monospace", 22, bold=True)
        self.font_xl = pygame.font.SysFont("monospace", 28, bold=True)
        self.selected_node: Optional[str] = None
        self.pulse_t = 0.0
        self.flash_nodes: Dict[str, float] = {}   # node → time remaining
        self.disaster_box: Optional[Tuple[int,int,int,int]] = None
        self.disaster_alpha = 0.0

    def update(self, dt: float):
        self.pulse_t += dt * 2.5
        for n in list(self.flash_nodes):
            self.flash_nodes[n] -= dt
            if self.flash_nodes[n] <= 0:
                del self.flash_nodes[n]
        if self.disaster_alpha > 0:
            self.disaster_alpha = max(0, self.disaster_alpha - dt * 0.8)

    def trigger_flash(self, node_id: str, duration: float = 1.2):
        self.flash_nodes[node_id] = duration

    def trigger_disaster_box(self, x, y, w, h):
        self.disaster_box = (x, y, w, h)
        self.disaster_alpha = 1.0

    def node_radius(self, node_id: str) -> int:
        c = self.sim.centrality.get(node_id, 0)
        r = NODE_BASE_RADIUS + int((NODE_MAX_RADIUS - NODE_BASE_RADIUS) * c)
        return max(NODE_BASE_RADIUS, r)

    def draw_background(self):
        self.screen.fill(BG_COLOR)
        # Map border
        pygame.draw.rect(self.screen, (40, 40, 55),
                         (MAP_OFFSET_X - 2, MAP_OFFSET_Y - 2, MAP_W + 4, MAP_H + 4), 2)
        # Subtle grid
        grid_step = 80
        for gx in range(MAP_OFFSET_X, MAP_OFFSET_X + MAP_W, grid_step):
            pygame.draw.line(self.screen, GRID_COLOR, (gx, MAP_OFFSET_Y), (gx, MAP_OFFSET_Y + MAP_H))
        for gy in range(MAP_OFFSET_Y, MAP_OFFSET_Y + MAP_H, grid_step):
            pygame.draw.line(self.screen, GRID_COLOR, (MAP_OFFSET_X, gy), (MAP_OFFSET_X + MAP_W, gy))

    def draw_edges(self):
        G = self.sim.G
        drawn = set()
        for u, v, edata in G.edges(data=True):
            key = (min(u,v), max(u,v))
            if key in drawn:
                continue
            drawn.add(key)
            u_active = G.nodes[u].get("active", True)
            v_active = G.nodes[v].get("active", True)
            pu = G.nodes[u]["pos"]
            pv = G.nodes[v]["pos"]
            lines = edata.get("lines", set())
            if not lines:
                lines = {"Blue"}
            line_list = sorted(lines)
            n_lines = len(line_list)
            # Offset multi-line edges
            for i, line_name in enumerate(line_list):
                color = LINE_COLORS.get(line_name, (150,150,150))
                if not (u_active and v_active):
                    color = tuple(max(0, c - 120) for c in color)
                offset = (i - (n_lines - 1) / 2) * 2
                ox = int(-offset * math.sin(math.atan2(pv[1]-pu[1], pv[0]-pu[0])))
                oy = int( offset * math.cos(math.atan2(pv[1]-pu[1], pv[0]-pu[0])))
                width = 2 if (u_active and v_active) else 1
                pygame.draw.aaline(self.screen, color,
                                   (pu[0]+ox, pu[1]+oy),
                                   (pv[0]+ox, pv[1]+oy))
                if width == 2:
                    pygame.draw.line(self.screen, color,
                                     (pu[0]+ox, pu[1]+oy),
                                     (pv[0]+ox, pv[1]+oy), 1)

    def draw_nodes(self):
        G = self.sim.G
        pulse = (math.sin(self.pulse_t) + 1) / 2  # 0..1

        for node_id, data in G.nodes(data=True):
            pos = data["pos"]
            active = data.get("active", True)
            overloaded = data.get("overloaded", False)
            r = self.node_radius(node_id)
            lines = data.get("lines", ["Blue"])
            primary_line = lines[0] if lines else "Blue"
            base_color = LINE_COLORS.get(primary_line, (150,150,150))

            if not active:
                color = DEAD_COLOR
                r = max(4, r - 3)
            elif overloaded:
                # Pulsing orange/red glow
                mix = pulse
                color = tuple(int(OVERLOAD_COLOR[i] * mix + CASCADE_GLOW[i] * (1-mix)) for i in range(3))
                r += int(pulse * 5)
            else:
                color = base_color

            # Flash effect
            if node_id in self.flash_nodes:
                t = self.flash_nodes[node_id]
                flash_mix = min(1.0, t)
                color = tuple(int(color[i] * (1 - flash_mix) + SELECT_COLOR[i] * flash_mix) for i in range(3))
                r = int(r + flash_mix * 8)

            # Selection ring
            if node_id == self.selected_node:
                pygame.draw.circle(self.screen, SELECT_COLOR, pos, r + 5, 2)

            # Drop shadow
            shadow_pos = (pos[0] + 2, pos[1] + 2)
            pygame.draw.circle(self.screen, (0, 0, 0), shadow_pos, r)

            # Main node
            pygame.draw.circle(self.screen, color, pos, r)

            # Bright highlight
            if active:
                hi_color = tuple(min(255, c + 80) for c in color)
                pygame.draw.circle(self.screen, hi_color, pos, max(2, r - 3), 1)

            # Transfer station marker
            if len(lines) >= 3 and active:
                pygame.draw.circle(self.screen, TEXT_COLOR, pos, r + 3, 1)

            # Station name (only for important nodes)
            show_label = (len(lines) >= 2 or r >= NODE_BASE_RADIUS + 3) and active
            if show_label:
                label = data.get("name", node_id)
                if len(label) > 18:
                    label = label[:16] + ".."
                surf = self.font_sm.render(label, True, TEXT_COLOR)
                self.screen.blit(surf, (pos[0] + r + 3, pos[1] - 7))

    def draw_disaster_box(self):
        if self.disaster_box and self.disaster_alpha > 0:
            x, y, w, h = self.disaster_box
            alpha = int(self.disaster_alpha * 180)
            overlay = pygame.Surface((w, h), pygame.SRCALPHA)
            overlay.fill((255, 50, 50, alpha))
            self.screen.blit(overlay, (x, y))
            pygame.draw.rect(self.screen, WARN_COLOR, (x, y, w, h),
                             max(1, int(self.disaster_alpha * 3)))

    def draw_hud(self, fps: float):
        G = self.sim.G
        total = len(G.nodes)
        active = self.sim.active_count
        dead = total - active
        eff = self.sim.efficiency
        comps = self.sim.component_count
        cascade = self.sim.cascade_pending
        mode = self.sim.mode

        px = PANEL_X
        y = MAP_OFFSET_Y + 5

        def label(txt, color=TEXT_COLOR, font=None):
            nonlocal y
            f = font or self.font_md
            s = f.render(txt, True, color)
            self.screen.blit(s, (px, y))
            y += s.get_height() + 4

        def hbar(val, maxval, color, h=10):
            nonlocal y
            bw = PANEL_W - 10
            pygame.draw.rect(self.screen, (50,50,60), (px, y, bw, h))
            fill = int(bw * max(0, min(1, val / maxval))) if maxval else 0
            pygame.draw.rect(self.screen, color, (px, y, fill, h))
            y += h + 6

        # Title
        label("CTA 'L' RESILIENCE SIM", HEADER_COLOR, self.font_xl)
        y += 6

        # Mode
        mode_color = WARN_COLOR if mode == "targeted" else GOOD_COLOR
        label(f"MODE: {'TARGETED ATTACK' if mode=='targeted' else 'RANDOM DISASTER'}", mode_color)
        y += 4

        # Stats
        label("─" * 26)
        label(f"Active Stations : {active:>4} / {total}", GOOD_COLOR if active > total * 0.6 else WARN_COLOR)
        hbar(active, total, GOOD_COLOR)

        label(f"Failed Stations : {dead:>4}", WARN_COLOR if dead > 0 else TEXT_COLOR)
        hbar(dead, total, WARN_COLOR)

        label(f"Network Fragments: {comps:>3}", SELECT_COLOR if comps > 1 else TEXT_COLOR)
        hbar(comps, max(10, total // 5), (180, 100, 255))

        eff_color = GOOD_COLOR if eff > 0.6 else (WARN_COLOR if eff > 0.3 else CASCADE_GLOW)
        label(f"Global Efficiency: {eff*100:5.1f}%", eff_color)
        hbar(eff, 1.0, eff_color)

        casc_color = CASCADE_GLOW if cascade > 0 else TEXT_COLOR
        label(f"Cascade Dominoes : {cascade:>3}", casc_color)
        y += 4

        # Efficiency history sparkline
        label("─" * 26)
        label("Efficiency History:", TEXT_COLOR, self.font_sm)
        hist = self.sim.efficiency_history[-PANEL_W + 20:]
        if len(hist) > 1:
            spark_h = 40
            spark_rect = pygame.Rect(px, y, PANEL_W - 10, spark_h)
            pygame.draw.rect(self.screen, (30,30,40), spark_rect)
            for i, e in enumerate(hist):
                sx = spark_rect.x + int(i * spark_rect.w / len(hist))
                sy = spark_rect.bottom - int(e * spark_h)
                col = GOOD_COLOR if e > 0.6 else (WARN_COLOR if e > 0.3 else CASCADE_GLOW)
                pygame.draw.line(self.screen, col, (sx, spark_rect.bottom), (sx, sy), 2)
            pygame.draw.rect(self.screen, (80,80,90), spark_rect, 1)
        y += 50

        # Selected node info
        if self.selected_node and self.selected_node in G.nodes:
            nd = G.nodes[self.selected_node]
            label("─" * 26)
            label("Selected Node:", HEADER_COLOR, self.font_sm)
            label(nd.get("name","?"), TEXT_COLOR)
            label(f"Lines: {', '.join(nd.get('lines',[]))}", TEXT_COLOR, self.font_sm)
            label(f"Centrality: {self.sim.centrality.get(self.selected_node,0):.4f}", TEXT_COLOR, self.font_sm)
            stat = "ACTIVE" if nd.get("active") else "FAILED"
            label(f"Status: {stat}", GOOD_COLOR if nd.get("active") else WARN_COLOR, self.font_sm)
        y += 8

        # Controls
        label("─" * 26)
        label("CONTROLS", HEADER_COLOR, self.font_sm)
        label("L-Click  Remove station", TEXT_COLOR, self.font_sm)
        label("R  Reset network", TEXT_COLOR, self.font_sm)
        label("M  Toggle attack mode", TEXT_COLOR, self.font_sm)
        label("D  Disaster (random box)", TEXT_COLOR, self.font_sm)
        label("T  Targeted attack", TEXT_COLOR, self.font_sm)
        label("A  Auto-cascade step", TEXT_COLOR, self.font_sm)

        # FPS
        fps_color = GOOD_COLOR if fps >= 50 else (WARN_COLOR if fps >= 30 else WARN_COLOR)
        fps_surf = self.font_sm.render(f"FPS: {fps:.0f}", True, fps_color)
        self.screen.blit(fps_surf, (PANEL_X, WIN_H - 20))

    def get_node_at(self, mx: int, my: int) -> Optional[str]:
        """Return node_id if (mx, my) is within its click radius."""
        best = None
        best_d = float("inf")
        for node_id, data in self.sim.G.nodes(data=True):
            px, py = data["pos"]
            d = math.hypot(mx - px, my - py)
            r = self.node_radius(node_id) + 4
            if d <= r and d < best_d:
                best_d = d
                best = node_id
        return best

    def draw_all(self, fps: float):
        self.draw_background()
        self.draw_disaster_box()
        self.draw_edges()
        self.draw_nodes()
        self.draw_hud(fps)


# ═══════════════════════════════════════════════════════════════════════════════
# DISASTER BOX ATTACK
# ═══════════════════════════════════════════════════════════════════════════════
def apply_disaster_box(sim: CascadeSimulator, renderer: Renderer):
    """Remove a random rectangular region of nodes."""
    bw = random.randint(80, 200)
    bh = random.randint(80, 200)
    bx = random.randint(MAP_OFFSET_X, MAP_OFFSET_X + MAP_W - bw)
    by = random.randint(MAP_OFFSET_Y, MAP_OFFSET_Y + MAP_H - bh)
    renderer.trigger_disaster_box(bx, by, bw, bh)
    removed = 0
    for nid, data in sim.G.nodes(data=True):
        if data.get("active", True):
            px, py = data["pos"]
            if bx <= px <= bx + bw and by <= py <= by + bh:
                sim.deactivate_node(nid)
                renderer.trigger_flash(nid, 1.5)
                removed += 1
    return removed


# ═══════════════════════════════════════════════════════════════════════════════
# ASYNC MAIN (Pygbag-compatible)
# ═══════════════════════════════════════════════════════════════════════════════
async def main():
    pygame.init()
    screen = pygame.display.set_mode((WIN_W, WIN_H))
    pygame.display.set_caption("CTA 'L' Resilience Simulator")
    clock = pygame.time.Clock()

    G = build_graph()
    sim = CascadeSimulator(G)
    renderer = Renderer(screen, sim)

    running = True
    last_cascade_time = 0.0
    dt = 0.0

    while running:
        dt = clock.tick(FPS) / 1000.0
        now = pygame.time.get_ticks() / 1000.0

        # ── Events ──────────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    sim.reset()
                    renderer.selected_node = None
                    renderer.flash_nodes.clear()

                elif event.key == pygame.K_m:
                    sim.mode = "targeted" if sim.mode == "random" else "random"

                elif event.key == pygame.K_d:
                    apply_disaster_box(sim, renderer)

                elif event.key == pygame.K_t:
                    sim.targeted_attack()

                elif event.key == pygame.K_a:
                    # Manual cascade step
                    failed = sim.tick_cascade()
                    for nid in failed:
                        renderer.trigger_flash(nid, 1.0)

                elif event.key == pygame.K_ESCAPE:
                    running = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    mx, my = event.pos
                    hit = renderer.get_node_at(mx, my)
                    if hit:
                        renderer.selected_node = hit
                        if sim.G.nodes[hit].get("active", True):
                            sim.deactivate_node(hit)
                            renderer.trigger_flash(hit, 1.2)
                        else:
                            # Re-enable? No — permanently failed
                            pass
                    else:
                        renderer.selected_node = None

        # ── Cascade tick ────────────────────────────────────────────────────
        if sim.cascade_pending > 0 and (now - last_cascade_time) >= TICK_INTERVAL:
            failed = sim.tick_cascade()
            for nid in failed:
                renderer.trigger_flash(nid, 1.0)
            last_cascade_time = now

        # ── Render ──────────────────────────────────────────────────────────
        renderer.update(dt)
        fps = clock.get_fps()
        renderer.draw_all(fps)
        pygame.display.flip()

        # Required for Pygbag / WebAssembly
        await asyncio.sleep(0)

    pygame.quit()


if __name__ == "__main__":
    asyncio.run(main())
