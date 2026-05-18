"""
CTA 'L' network graph construction.

No pygame dependency. Safe to import in headless batch environments.
GTFS loading attempted first; falls back to hardcoded topology automatically.
"""

from __future__ import annotations

from typing import Optional
import networkx as nx

try:
    import pandas as pd
    _HAS_PANDAS = True
except ImportError:
    _HAS_PANDAS = False

# ── Station data: (id, name, lat, lon, lines) ─────────────────────────────────
_STATIONS: list[tuple] = [
    # Red Line
    ("howard",            "Howard",                42.0192, -87.6727, ["Red", "Purple", "Yellow"]),
    ("jarvis",            "Jarvis",                42.0153, -87.6694, ["Red"]),
    ("morse",             "Morse",                 42.0083, -87.6658, ["Red"]),
    ("loyola",            "Loyola",                42.0013, -87.6614, ["Red"]),
    ("granville",         "Granville",             41.9939, -87.6594, ["Red"]),
    ("thorndale",         "Thorndale",             41.9899, -87.6593, ["Red"]),
    ("bryn_mawr",         "Bryn Mawr",             41.9835, -87.6594, ["Red"]),
    ("berwyn",            "Berwyn",                41.9778, -87.6590, ["Red"]),
    ("argyle",            "Argyle",                41.9736, -87.6588, ["Red"]),
    ("lawrence",          "Lawrence",              41.9690, -87.6585, ["Red"]),
    ("wilson",            "Wilson",                41.9646, -87.6578, ["Red", "Purple"]),
    ("sheridan",          "Sheridan",              41.9533, -87.6545, ["Red"]),
    ("addison_red",       "Addison (Red)",         41.9474, -87.6539, ["Red"]),
    ("belmont_red",       "Belmont",               41.9400, -87.6526, ["Red", "Brown", "Purple"]),
    ("fullerton",         "Fullerton",             41.9252, -87.6527, ["Red", "Brown", "Purple"]),
    ("north_clybourn",    "North/Clybourn",        41.9109, -87.6479, ["Red"]),
    ("clark_division",    "Clark/Division",        41.9044, -87.6313, ["Red"]),
    ("chicago_red",       "Chicago (Red)",         41.8965, -87.6310, ["Red"]),
    ("grand_red",         "Grand (Red)",           41.8916, -87.6312, ["Red"]),
    ("lake_red",          "Lake (Red)",            41.8848, -87.6277, ["Red"]),
    ("monroe_red",        "Monroe (Red)",          41.8807, -87.6276, ["Red"]),
    ("jackson_red",       "Jackson (Red)",         41.8782, -87.6277, ["Red"]),
    ("harrison",          "Harrison",              41.8741, -87.6274, ["Red"]),
    ("roosevelt_red",     "Roosevelt",             41.8674, -87.6271, ["Red", "Orange", "Green"]),
    ("cermak_chinatown",  "Cermak-Chinatown",      41.8530, -87.6305, ["Red"]),
    ("sox_35th",          "Sox-35th",              41.8310, -87.6306, ["Red"]),
    ("47th_red",          "47th (Red)",            41.8095, -87.6307, ["Red"]),
    ("garfield_red",      "Garfield (Red)",        41.7955, -87.6308, ["Red"]),
    ("63rd_red",          "63rd (Red)",            41.7800, -87.6308, ["Red"]),
    ("69th",              "69th",                  41.7685, -87.6254, ["Red"]),
    ("79th",              "79th",                  41.7502, -87.6252, ["Red"]),
    ("87th",              "87th",                  41.7363, -87.6252, ["Red"]),
    ("95th_dan_ryan",     "95th/Dan Ryan",         41.7224, -87.6246, ["Red"]),
    # Blue Line – O'Hare branch
    ("ohare",             "O'Hare",                41.9761, -87.9073, ["Blue"]),
    ("rosemont",          "Rosemont",              41.9836, -87.8586, ["Blue"]),
    ("cumberland",        "Cumberland",            41.9836, -87.8450, ["Blue"]),
    ("harlem_blue",       "Harlem (Blue)",         41.9836, -87.8067, ["Blue"]),
    ("jefferson_park",    "Jefferson Park",        41.9707, -87.7612, ["Blue"]),
    ("montrose_blue",     "Montrose (Blue)",       41.9614, -87.7438, ["Blue"]),
    ("irving_park_blue",  "Irving Park (Blue)",    41.9525, -87.7314, ["Blue"]),
    ("addison_blue",      "Addison (Blue)",        41.9474, -87.7177, ["Blue"]),
    ("belmont_blue",      "Belmont (Blue)",        41.9387, -87.7127, ["Blue"]),
    ("logan_square",      "Logan Square",          41.9296, -87.7075, ["Blue"]),
    ("california",        "California",            41.9216, -87.6980, ["Blue"]),
    ("western_blue",      "Western (Blue)",        41.9161, -87.6871, ["Blue"]),
    ("damen_blue",        "Damen (Blue)",          41.9094, -87.6774, ["Blue"]),
    ("division",          "Division (Blue)",       41.9031, -87.6679, ["Blue"]),
    ("chicago_blue",      "Chicago (Blue)",        41.8963, -87.6575, ["Blue"]),
    ("grand_blue",        "Grand (Blue)",          41.8912, -87.6479, ["Blue"]),
    ("clark_lake",        "Clark/Lake",            41.8858, -87.6312, ["Blue", "Brown", "Green", "Orange", "Pink", "Purple"]),
    ("washington_blue",   "Washington (Blue)",     41.8832, -87.6291, ["Blue", "Orange"]),
    ("monroe_blue",       "Monroe (Blue)",         41.8807, -87.6291, ["Blue", "Orange"]),
    ("jackson_blue",      "Jackson (Blue)",        41.8781, -87.6291, ["Blue", "Orange"]),
    ("lasalle_blue",      "LaSalle (Blue)",        41.8755, -87.6308, ["Blue"]),
    ("clinton_blue",      "Clinton (Blue)",        41.8750, -87.6404, ["Blue"]),
    ("uic_halsted",       "UIC-Halsted",           41.8754, -87.6497, ["Blue"]),
    ("racine",            "Racine",                41.8754, -87.6591, ["Blue"]),
    ("illinois_med",      "Illinois Medical",      41.8755, -87.6739, ["Blue"]),
    ("western_forest",    "Western (Forest Pk)",   41.8754, -87.6880, ["Blue"]),
    ("kedzie_blue",       "Kedzie (Blue)",         41.8754, -87.7054, ["Blue"]),
    ("pulaski_blue",      "Pulaski (Blue)",        41.8754, -87.7254, ["Blue"]),
    ("cicero_blue",       "Cicero (Blue)",         41.8754, -87.7454, ["Blue"]),
    ("austin_blue",       "Austin (Blue)",         41.8754, -87.7757, ["Blue"]),
    ("oak_park_blue",     "Oak Park (Blue)",       41.8754, -87.7935, ["Blue"]),
    ("harlem_forest",     "Harlem/Forest Park",    41.8754, -87.8095, ["Blue"]),
    ("forest_park",       "Forest Park",           41.8752, -87.8178, ["Blue"]),
    # Brown Line
    ("kimball",           "Kimball",               41.9679, -87.7136, ["Brown"]),
    ("kedzie_brown",      "Kedzie (Brown)",        41.9658, -87.7083, ["Brown"]),
    ("francisco",         "Francisco",             41.9661, -87.7015, ["Brown"]),
    ("rockwell",          "Rockwell",              41.9662, -87.6940, ["Brown"]),
    ("western_brown",     "Western (Brown)",       41.9663, -87.6881, ["Brown"]),
    ("damen_brown",       "Damen (Brown)",         41.9663, -87.6782, ["Brown"]),
    ("montrose_brown",    "Montrose (Brown)",      41.9614, -87.6745, ["Brown"]),
    ("irving_park_brown", "Irving Park (Brown)",   41.9525, -87.6745, ["Brown"]),
    ("addison_brown",     "Addison (Brown)",       41.9474, -87.6745, ["Brown"]),
    ("paulina",           "Paulina",               41.9434, -87.6706, ["Brown"]),
    ("southport",         "Southport",             41.9436, -87.6638, ["Brown"]),
    ("wellington",        "Wellington",            41.9361, -87.6538, ["Brown", "Purple"]),
    ("diversey",          "Diversey",              41.9324, -87.6537, ["Brown", "Purple"]),
    ("armitage",          "Armitage",              41.9184, -87.6526, ["Brown", "Purple"]),
    ("sedgwick",          "Sedgwick",              41.9107, -87.6387, ["Brown", "Purple"]),
    ("chicago_brown",     "Chicago (Brown/Purple)",41.8965, -87.6317, ["Brown", "Purple"]),
    ("merchandise_mart",  "Merchandise Mart",      41.8886, -87.6336, ["Brown", "Purple"]),
    ("quincy",            "Quincy",                41.8788, -87.6338, ["Brown", "Orange", "Purple", "Pink"]),
    ("harold_wash",       "Harold Washington Lib", 41.8761, -87.6291, ["Brown", "Orange", "Purple", "Pink"]),
    ("adams_wabash",      "Adams/Wabash",          41.8796, -87.6262, ["Brown", "Green", "Orange", "Pink", "Purple"]),
    ("madison_wabash",    "Madison/Wabash",        41.8821, -87.6261, ["Brown", "Green", "Orange", "Pink", "Purple"]),
    ("randolph_wabash",   "Randolph/Wabash",       41.8847, -87.6261, ["Brown", "Green", "Orange", "Pink", "Purple"]),
    # Green Line
    ("harlem_green",      "Harlem/Lake (Green)",   41.8870, -87.8041, ["Green"]),
    ("oak_park_green",    "Oak Park (Green)",      41.8870, -87.7934, ["Green"]),
    ("ridgeland",         "Ridgeland",             41.8871, -87.7835, ["Green"]),
    ("austin_green",      "Austin (Green)",        41.8870, -87.7757, ["Green"]),
    ("central_green",     "Central (Green)",       41.8870, -87.7654, ["Green"]),
    ("laramie",           "Laramie",               41.8870, -87.7553, ["Green"]),
    ("cicero_green",      "Cicero (Green)",        41.8870, -87.7454, ["Green"]),
    ("pulaski_green",     "Pulaski (Green)",       41.8870, -87.7254, ["Green"]),
    ("conservatory",      "Conservatory",          41.8869, -87.7165, ["Green"]),
    ("kedzie_green",      "Kedzie (Green)",        41.8869, -87.7054, ["Green"]),
    ("ashland_green",     "Ashland (Green)",       41.8870, -87.6648, ["Green"]),
    ("morgan",            "Morgan",                41.8870, -87.6519, ["Green", "Pink"]),
    ("clinton_green",     "Clinton (Green/Pink)",  41.8859, -87.6416, ["Green", "Pink"]),
    ("lake_loop",         "Lake",                  41.8848, -87.6277, ["Green", "Brown"]),
    ("halsted_green",     "Halsted (Green)",       41.8357, -87.6484, ["Green"]),
    ("35th_bronzeville",  "35th/Bronzeville",      41.8311, -87.6287, ["Green"]),
    ("43rd",              "43rd",                  41.8165, -87.6184, ["Green"]),
    ("47th_green",        "47th (Green)",          41.8096, -87.6184, ["Green"]),
    ("51st",              "51st",                  41.8013, -87.6185, ["Green"]),
    ("garfield_green",    "Garfield (Green)",      41.7955, -87.6185, ["Green"]),
    ("king_drive",        "King Drive",            41.7802, -87.6155, ["Green"]),
    ("cottage_grove",     "Cottage Grove",         41.7802, -87.6058, ["Green"]),
    ("east_63rd",         "East 63rd",             41.7802, -87.5906, ["Green"]),
    # Orange Line
    ("midway",            "Midway",                41.7866, -87.7373, ["Orange"]),
    ("pulaski_orange",    "Pulaski (Orange)",      41.7999, -87.7254, ["Orange"]),
    ("kedzie_orange",     "Kedzie (Orange)",       41.8048, -87.7054, ["Orange"]),
    ("western_orange",    "Western (Orange)",      41.8050, -87.6879, ["Orange"]),
    ("35th_archer",       "35th/Archer",           41.8297, -87.6807, ["Orange"]),
    ("ashland_orange",    "Ashland (Orange)",      41.8394, -87.6647, ["Orange"]),
    ("halsted_orange",    "Halsted (Orange)",      41.8447, -87.6479, ["Orange"]),
    # Pink Line
    ("54th_cermak",       "54th/Cermak",           41.8523, -87.7584, ["Pink"]),
    ("cermak_pink",       "Cermak/Kildare",        41.8524, -87.7384, ["Pink"]),
    ("kostner",           "Kostner",               41.8524, -87.7284, ["Pink"]),
    ("pulaski_pink",      "Pulaski (Pink)",        41.8524, -87.7254, ["Pink"]),
    ("central_pink",      "Central Park (Pink)",   41.8524, -87.7154, ["Pink"]),
    ("kedzie_pink",       "Kedzie (Pink)",         41.8524, -87.7054, ["Pink"]),
    ("california_pink",   "California (Pink)",     41.8524, -87.6983, ["Pink"]),
    ("western_pink",      "Western (Pink)",        41.8524, -87.6879, ["Pink"]),
    ("damen_pink",        "Damen (Pink)",          41.8524, -87.6774, ["Pink"]),
    ("18th",              "18th",                  41.8575, -87.6679, ["Pink"]),
    ("polk",              "Polk",                  41.8712, -87.6479, ["Pink"]),
    ("ashland_pink",      "Ashland (Pink)",        41.8750, -87.6649, ["Pink"]),
    # Purple Line
    ("linden",            "Linden",                42.0733, -87.6935, ["Purple"]),
    ("central_purple",    "Central (Purple)",      42.0638, -87.6862, ["Purple"]),
    ("noyes",             "Noyes",                 42.0582, -87.6835, ["Purple"]),
    ("foster",            "Foster (Purple)",       42.0530, -87.6834, ["Purple"]),
    ("davis",             "Davis",                 42.0467, -87.6833, ["Purple"]),
    ("dempster",          "Dempster",              42.0416, -87.6834, ["Purple"]),
    ("main",              "Main",                  42.0329, -87.6797, ["Purple"]),
    ("south_blvd",        "South Blvd",            42.0260, -87.6780, ["Purple"]),
    # Yellow Line
    ("dempster_skokie",   "Dempster-Skokie",       42.0381, -87.7510, ["Yellow"]),
    ("oakton_skokie",     "Oakton-Skokie",         42.0253, -87.7484, ["Yellow"]),
]

# ── Edge data: (node_a, node_b, line, weight) ─────────────────────────────────
_EDGES: list[tuple] = [
    # Red Line
    ("howard",         "jarvis",          "Red",    1),
    ("jarvis",         "morse",           "Red",    1),
    ("morse",          "loyola",          "Red",    1),
    ("loyola",         "granville",       "Red",    1),
    ("granville",      "thorndale",       "Red",    1),
    ("thorndale",      "bryn_mawr",       "Red",    1),
    ("bryn_mawr",      "berwyn",          "Red",    1),
    ("berwyn",         "argyle",          "Red",    1),
    ("argyle",         "lawrence",        "Red",    1),
    ("lawrence",       "wilson",          "Red",    1),
    ("wilson",         "sheridan",        "Red",    1),
    ("sheridan",       "addison_red",     "Red",    1),
    ("addison_red",    "belmont_red",     "Red",    1),
    ("belmont_red",    "fullerton",       "Red",    1),
    ("fullerton",      "north_clybourn",  "Red",    1),
    ("north_clybourn", "clark_division",  "Red",    1),
    ("clark_division", "chicago_red",     "Red",    1),
    ("chicago_red",    "grand_red",       "Red",    1),
    ("grand_red",      "lake_red",        "Red",    1),
    ("lake_red",       "monroe_red",      "Red",    1),
    ("monroe_red",     "jackson_red",     "Red",    1),
    ("jackson_red",    "harrison",        "Red",    1),
    ("harrison",       "roosevelt_red",   "Red",    1),
    ("roosevelt_red",  "cermak_chinatown","Red",    1),
    ("cermak_chinatown","sox_35th",       "Red",    1),
    ("sox_35th",       "47th_red",        "Red",    1),
    ("47th_red",       "garfield_red",    "Red",    1),
    ("garfield_red",   "63rd_red",        "Red",    1),
    ("63rd_red",       "69th",            "Red",    1),
    ("69th",           "79th",            "Red",    1),
    ("79th",           "87th",            "Red",    1),
    ("87th",           "95th_dan_ryan",   "Red",    1),
    # Blue Line – O'Hare branch
    ("ohare",          "rosemont",        "Blue",   1),
    ("rosemont",       "cumberland",      "Blue",   1),
    ("cumberland",     "harlem_blue",     "Blue",   1),
    ("harlem_blue",    "jefferson_park",  "Blue",   1),
    ("jefferson_park", "montrose_blue",   "Blue",   1),
    ("montrose_blue",  "irving_park_blue","Blue",   1),
    ("irving_park_blue","addison_blue",   "Blue",   1),
    ("addison_blue",   "belmont_blue",    "Blue",   1),
    ("belmont_blue",   "logan_square",    "Blue",   1),
    ("logan_square",   "california",      "Blue",   1),
    ("california",     "western_blue",    "Blue",   1),
    ("western_blue",   "damen_blue",      "Blue",   1),
    ("damen_blue",     "division",        "Blue",   1),
    ("division",       "chicago_blue",    "Blue",   1),
    ("chicago_blue",   "grand_blue",      "Blue",   1),
    ("grand_blue",     "clark_lake",      "Blue",   1),
    ("clark_lake",     "washington_blue", "Blue",   1),
    ("washington_blue","monroe_blue",     "Blue",   1),
    ("monroe_blue",    "jackson_blue",    "Blue",   1),
    ("jackson_blue",   "lasalle_blue",    "Blue",   1),
    ("lasalle_blue",   "clinton_blue",    "Blue",   1),
    ("clinton_blue",   "uic_halsted",     "Blue",   1),
    ("uic_halsted",    "racine",          "Blue",   1),
    ("racine",         "illinois_med",    "Blue",   1),
    ("illinois_med",   "western_forest",  "Blue",   1),
    ("western_forest", "kedzie_blue",     "Blue",   1),
    ("kedzie_blue",    "pulaski_blue",    "Blue",   1),
    ("pulaski_blue",   "cicero_blue",     "Blue",   1),
    ("cicero_blue",    "austin_blue",     "Blue",   1),
    ("austin_blue",    "oak_park_blue",   "Blue",   1),
    ("oak_park_blue",  "harlem_forest",   "Blue",   1),
    ("harlem_forest",  "forest_park",     "Blue",   1),
    # Brown Line
    ("kimball",        "kedzie_brown",    "Brown",  1),
    ("kedzie_brown",   "francisco",       "Brown",  1),
    ("francisco",      "rockwell",        "Brown",  1),
    ("rockwell",       "western_brown",   "Brown",  1),
    ("western_brown",  "damen_brown",     "Brown",  1),
    ("damen_brown",    "montrose_brown",  "Brown",  1),
    ("montrose_brown", "irving_park_brown","Brown", 1),
    ("irving_park_brown","addison_brown", "Brown",  1),
    ("addison_brown",  "paulina",         "Brown",  1),
    ("paulina",        "southport",       "Brown",  1),
    ("southport",      "belmont_red",     "Brown",  1),
    ("belmont_red",    "wellington",      "Brown",  1),
    ("wellington",     "diversey",        "Brown",  1),
    ("diversey",       "fullerton",       "Brown",  1),
    ("fullerton",      "armitage",        "Brown",  1),
    ("armitage",       "sedgwick",        "Brown",  1),
    ("sedgwick",       "chicago_brown",   "Brown",  1),
    ("chicago_brown",  "merchandise_mart","Brown",  1),
    ("merchandise_mart","clark_lake",     "Brown",  1),
    ("clark_lake",     "randolph_wabash", "Brown",  1),
    ("randolph_wabash","madison_wabash",  "Brown",  1),
    ("madison_wabash", "adams_wabash",    "Brown",  1),
    ("adams_wabash",   "harold_wash",     "Brown",  1),
    ("harold_wash",    "quincy",          "Brown",  1),
    ("quincy",         "washington_blue", "Brown",  1),
    # Green Line – west branch
    ("harlem_green",   "oak_park_green",  "Green",  1),
    ("oak_park_green", "ridgeland",       "Green",  1),
    ("ridgeland",      "austin_green",    "Green",  1),
    ("austin_green",   "central_green",   "Green",  1),
    ("central_green",  "laramie",         "Green",  1),
    ("laramie",        "cicero_green",    "Green",  1),
    ("cicero_green",   "pulaski_green",   "Green",  1),
    ("pulaski_green",  "conservatory",    "Green",  1),
    ("conservatory",   "kedzie_green",    "Green",  1),
    ("kedzie_green",   "ashland_green",   "Green",  1),
    ("ashland_green",  "morgan",          "Green",  1),
    ("morgan",         "clinton_green",   "Green",  1),
    ("clinton_green",  "clark_lake",      "Green",  1),
    ("clark_lake",     "lake_loop",       "Green",  1),
    ("lake_loop",      "randolph_wabash", "Green",  1),
    ("randolph_wabash","adams_wabash",    "Green",  1),
    ("adams_wabash",   "roosevelt_red",   "Green",  1),
    ("roosevelt_red",  "35th_bronzeville","Green",  1),
    ("35th_bronzeville","43rd",           "Green",  1),
    ("43rd",           "47th_green",      "Green",  1),
    ("47th_green",     "51st",            "Green",  1),
    ("51st",           "garfield_green",  "Green",  1),
    ("garfield_green", "king_drive",      "Green",  1),
    ("king_drive",     "cottage_grove",   "Green",  1),
    ("cottage_grove",  "east_63rd",       "Green",  1),
    ("morgan",         "halsted_green",   "Green",  1),
    ("halsted_green",  "35th_bronzeville","Green",  1),
    # Orange Line
    ("midway",         "pulaski_orange",  "Orange", 1),
    ("pulaski_orange", "kedzie_orange",   "Orange", 1),
    ("kedzie_orange",  "western_orange",  "Orange", 1),
    ("western_orange", "35th_archer",     "Orange", 1),
    ("35th_archer",    "ashland_orange",  "Orange", 1),
    ("ashland_orange", "halsted_orange",  "Orange", 1),
    ("halsted_orange", "roosevelt_red",   "Orange", 1),
    ("roosevelt_red",  "harold_wash",     "Orange", 1),
    ("harold_wash",    "quincy",          "Orange", 1),
    ("quincy",         "washington_blue", "Orange", 1),
    ("washington_blue","clark_lake",      "Orange", 1),
    # Pink Line
    ("54th_cermak",    "cermak_pink",     "Pink",   1),
    ("cermak_pink",    "kostner",         "Pink",   1),
    ("kostner",        "pulaski_pink",    "Pink",   1),
    ("pulaski_pink",   "central_pink",    "Pink",   1),
    ("central_pink",   "kedzie_pink",     "Pink",   1),
    ("kedzie_pink",    "california_pink", "Pink",   1),
    ("california_pink","western_pink",    "Pink",   1),
    ("western_pink",   "damen_pink",      "Pink",   1),
    ("damen_pink",     "18th",            "Pink",   1),
    ("18th",           "polk",            "Pink",   1),
    ("polk",           "ashland_pink",    "Pink",   1),
    ("ashland_pink",   "morgan",          "Pink",   1),
    ("morgan",         "clinton_green",   "Pink",   1),
    ("clinton_green",  "clark_lake",      "Pink",   1),
    ("clark_lake",     "randolph_wabash", "Pink",   1),
    ("randolph_wabash","adams_wabash",    "Pink",   1),
    ("adams_wabash",   "quincy",          "Pink",   1),
    ("quincy",         "harold_wash",     "Pink",   1),
    ("harold_wash",    "washington_blue", "Pink",   1),
    # Purple Line
    ("linden",         "central_purple",  "Purple", 1),
    ("central_purple", "noyes",           "Purple", 1),
    ("noyes",          "foster",          "Purple", 1),
    ("foster",         "davis",           "Purple", 1),
    ("davis",          "dempster",        "Purple", 1),
    ("dempster",       "main",            "Purple", 1),
    ("main",           "south_blvd",      "Purple", 1),
    ("south_blvd",     "howard",          "Purple", 1),
    ("howard",         "wilson",          "Purple", 1),
    ("wilson",         "belmont_red",     "Purple", 1),
    ("belmont_red",    "wellington",      "Purple", 1),
    ("wellington",     "diversey",        "Purple", 1),
    ("diversey",       "fullerton",       "Purple", 1),
    ("fullerton",      "armitage",        "Purple", 1),
    ("armitage",       "sedgwick",        "Purple", 1),
    ("sedgwick",       "chicago_brown",   "Purple", 1),
    ("chicago_brown",  "merchandise_mart","Purple", 1),
    ("merchandise_mart","clark_lake",     "Purple", 1),
    ("clark_lake",     "randolph_wabash", "Purple", 1),
    ("randolph_wabash","madison_wabash",  "Purple", 1),
    ("madison_wabash", "adams_wabash",    "Purple", 1),
    ("adams_wabash",   "quincy",          "Purple", 1),
    ("quincy",         "harold_wash",     "Purple", 1),
    ("harold_wash",    "washington_blue", "Purple", 1),
    # Yellow Line
    ("howard",         "dempster_skokie", "Yellow", 2),
    ("dempster_skokie","oakton_skokie",   "Yellow", 1),
]


def build_graph(gtfs_dir: Optional[str] = None) -> nx.Graph:
    """Return the CTA L network graph.

    Attempts GTFS ingestion from gtfs_dir if supplied and pandas is available.
    Falls back to the hardcoded topology unconditionally.
    """
    if gtfs_dir and _HAS_PANDAS:
        g = _try_load_gtfs(gtfs_dir)
        if g is not None:
            return g
    return _build_hardcoded()


def _build_hardcoded() -> nx.Graph:
    G = nx.Graph()
    for sid, name, lat, lon, lines in _STATIONS:
        G.add_node(sid, name=name, lat=float(lat), lon=float(lon), lines=list(lines))

    for a, b, line, w in _EDGES:
        if a not in G or b not in G:
            continue
        if G.has_edge(a, b):
            G[a][b]["lines"].add(line)
        else:
            G.add_edge(a, b, weight=w, lines={line})
    return G


def _try_load_gtfs(gtfs_dir: str) -> Optional[nx.Graph]:
    import os
    stops_path = os.path.join(gtfs_dir, "stops.txt")
    times_path = os.path.join(gtfs_dir, "stop_times.txt")
    if not (os.path.exists(stops_path) and os.path.exists(times_path)):
        return None
    try:
        stops = pd.read_csv(stops_path)
        # CTA rail stop_ids start with numeric codes in the 3xxxx-4xxxx range
        rail = stops[stops["stop_id"].astype(str).str.match(r"^[34]\d{4}$")]
        if len(rail) < 10:
            return None
        G = nx.Graph()
        for _, row in rail.iterrows():
            G.add_node(
                str(row["stop_id"]),
                name=str(row["stop_name"]),
                lat=float(row["stop_lat"]),
                lon=float(row["stop_lon"]),
                lines=[],
            )
        # Minimal edge construction: consecutive stops in same trip
        times = pd.read_csv(times_path, usecols=["trip_id", "stop_id", "stop_sequence"])
        times = times[times["stop_id"].astype(str).str.match(r"^[34]\d{4}$")]
        times = times.sort_values(["trip_id", "stop_sequence"])
        for trip_id, group in times.groupby("trip_id"):
            ids = [str(x) for x in group["stop_id"].tolist()]
            for i in range(len(ids) - 1):
                a, b = ids[i], ids[i + 1]
                if a in G and b in G and not G.has_edge(a, b):
                    G.add_edge(a, b, weight=1, lines=set())
        return G if len(G.edges) >= 50 else None
    except Exception:
        return None
