"""
auto_populate_market_map.py
===========================
DROP THIS FILE next to your state_colour_frame.py

HOW TO USE:
    python auto_populate_market_map.py --file "8_6_26.XLSX"

    Or to process ALL xlsx files in a folder:
    python auto_populate_market_map.py --folder "/path/to/daily_files"

WHAT IT DOES:
    1. Reads your daily dispatch Excel (SAP extract)
    2. Maps Ship-to-City → District (matches your Streamlit app districts)
    3. Aggregates Net Weight (MT) by District × Brand
    4. Outputs:  market_map_data.py  → drop-in replacement for get_state_data()
                 market_map_data.xlsx → for manual review
                 market_map_log.txt  → unmapped cities (for you to fix)

BRAND MAPPING (dispatch → app):
    COLOUR_FRAME  → Colour_Frame  (JSW own brand)
    UNICOAT       → Colour_Frame  (JSW own brand - Thinner product)
    INDRADHANUSH  → Others
    COLOURON_PLUS → Others
    PRAGATI PLUS  → Others
    ENDURA_PLUS   → Others
    ALUCOLOR      → Others
    (AM/NS, APL Apollo, PROMPT, HI TECH, RCS stay 0 — fill from market intel)
"""

import pandas as pd
import numpy as np
import argparse
import os
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
# 1. BRAND MAPPING  (dispatch file brand → your app brand column)
# ─────────────────────────────────────────────────────────────────────────────
BRAND_MAP = {
    "COLOUR_FRAME":  "Colour_Frame",
    "UNICOAT":       "Colour_Frame",   # JSW thinner range, same brand bucket
    "INDRADHANUSH":  "Others",
    "COLOURON_PLUS": "Others",
    "PRAGATI PLUS":  "Others",
    "ENDURA_PLUS":   "Others",
    "ALUCOLOR":      "Others",
}

APP_BRANDS = ["Colour_Frame", "AM/NS", "APL Apollo", "PROMPT", "HI TECH", "RCS", "Others"]

# ─────────────────────────────────────────────────────────────────────────────
# 2. CITY → DISTRICT MAPPING
#    Key  = Ship to City (upper) from dispatch file
#    Value = District name exactly as used in your get_state_data()
# ─────────────────────────────────────────────────────────────────────────────
CITY_TO_DISTRICT = {
    # ── HARYANA ──────────────────────────────────────────────────────────────
    "FARIDABAD":    "FARIDABAD",
    "GURUGRAM":     "GURUGRAM",
    "GURGAON":      "GURUGRAM",
    "HISAR":        "HISAR",
    "SIRSA":        "SIRSA",
    "PALWAL":       "PALWAL",
    "REWARI":       "REWARI",
    "AMBALA":       "AMBALA",
    "PANIPAT":      "PANIPAT",
    "KARNAL":       "KARNAL",
    "ROHTAK":       "ROHTAK",
    "SONIPAT":      "SONIPAT",
    "KURUKSHETRA":  "KURUKSHETRA",
    "YAMUNANAGAR":  "YAMUNANAGAR",
    "BHIWANI":      "BHIWANI",
    "JIND":         "JIND",
    "FATEHABAD":    "FATEHABAD",
    "PANCHKULA":    "PANCHKULA",

    # ── PUNJAB ───────────────────────────────────────────────────────────────
    "LUDHIANA":     "LUDHIANA",
    "AMRITSAR":     "AMRITSAR",
    "JALANDHAR":    "JALANDHAR",
    "PATIALA":      "PATIALA",
    "BATHINDA":     "BATHINDA",
    "PATHANKOT":    "PATHANKOT",
    "GURDASPUR":    "GURDASPUR",
    "MOGA":         "MOGA",
    "BARNALA":      "BARNALA",
    "SANGRUR":      "SANGRUR",
    "FARIDKOT":     "FARIDKOT",
    "FIROZPUR":     "FIROZPUR",
    "FAZILKA":      "FAZILKA",

    # ── DELHI ────────────────────────────────────────────────────────────────
    "DELHI":        "SOUTH",
    "NEW DELHI":    "NEW DELHI",

    # ── UTTAR PRADESH ────────────────────────────────────────────────────────
    "GHAZIABAD":    "GHAZIABAD",
    "VARANASI":     "VARANASI",
    "AGRA":         "AGRA",
    "LUCKNOW":      "LUCKNOW",
    "KANPUR":       "KANPUR NAGAR",
    "MEERUT":       "MEERUT",
    "NOIDA":        "GAUTAM BUDDHA NAGAR",
    "ALIGARH":      "ALIGARH",
    "BAREILLY":     "BAREILLY",
    "MATHURA":      "MATHURA",
    "GORAKHPUR":    "GORAKHPUR",
    "PRAYAGRAJ":    "PRAYAGRAJ",
    "ALLAHABAD":    "PRAYAGRAJ",
    "MORADABAD":    "MORADABAD",
    "SAHARANPUR":   "SAHARANPUR",
    "MUZAFFARNAGAR": "MUZAFFARNAGAR",

    # ── RAJASTHAN ────────────────────────────────────────────────────────────
    "JAIPUR":       "JAIPUR",
    "JODHPUR":      "JODHPUR",
    "UDAIPUR":      "UDAIPUR",
    "KOTA":         "KOTA",
    "ALWAR":        "ALWAR",
    "AJMER":        "AJMER",
    "BIKANER":      "BIKANER",
    "SIKAR":        "SIKAR",

    # ── GUJARAT ──────────────────────────────────────────────────────────────
    "AHMEDABAD":    "AHMADABAD",
    "AHMADABAD":    "AHMADABAD",
    "MEHSANA":      "MAHESANA",
    "MAHESANA":     "MAHESANA",
    "NADIAD":       "KHEDA",
    "SURAT":        "SURAT",
    "VADODARA":     "VADODARA",
    "RAJKOT":       "RAJKOT",
    "GANDHINAGAR":  "GANDHINAGAR",
    "ANAND":        "ANAND",
    "BHAVNAGAR":    "BHAVNAGAR",
    "JUNAGADH":     "JUNAGADH",
    "MORBI":        "MORBI",
    "KUTCH":        "KACHCHH",
    "KACHCHH":      "KACHCHH",

    # ── MADHYA PRADESH ───────────────────────────────────────────────────────
    "INDORE":       "INDORE",
    "BHOPAL":       "BHOPAL",
    "JABALPUR":     "JABALPUR",
    "GWALIOR":      "GWALIOR",
    "REWA":         "REWA",
    "UJJAIN":       "UJJAIN",

    # ── MAHARASHTRA ──────────────────────────────────────────────────────────
    "MUMBAI":       "MUMBAI",
    "NAVI MUMBAI":  "THANE",
    "THANE":        "THANE",
    "TALOJA":       "RAIGARH",
    "PUNE":         "PUNE",
    "NAGPUR":       "NAGPUR",
    "NASHIK":       "NASHIK",
    "AURANGABAD":   "AURANGABAD",
    "AHMEDNAGAR":   "AHMEDNAGAR",
    "KOLHAPUR":     "KOLHAPUR",
    "SOLAPUR":      "SOLAPUR",
    "SANGLI":       "SANGLI",
    "SATARA":       "SATARA",
    "LATUR":        "LATUR",
    "JALGAON":      "JALGAON",
    "WALUJ MIDC":   "AURANGABAD",
    "SHIRUR PUNE":  "PUNE",
    "TOAP":         "RAIGARH",

    # ── CHHATTISGARH ─────────────────────────────────────────────────────────
    "RAIPUR":       "RAIPUR",
    "BILASPUR":     "BILASPUR",
    "DURG":         "DURG",

    # ── KARNATAKA ────────────────────────────────────────────────────────────
    "BANGALORE":    "BANGALORE URBAN",
    "BENGALURU":    "BANGALORE URBAN",
    "MANGALORE":    "DAKSHINA KANNADA",
    "BELLARY":      "BELLARY",
    "HUBLI":        "DHARWAD",
    "MYSORE":       "MYSURU",

    # ── KERALA ───────────────────────────────────────────────────────────────
    "KOCHI":        "ERNAKULAM",
    "COCHIN":       "ERNAKULAM",
    "CALICUT":      "KOZHIKODE",
    "KOZHIKODE":    "KOZHIKODE",
    "KOLLAM":       "KOLLAM",
    "THRISSUR":     "THRISSUR",
    "PALAKKAD":     "PALAKKAD",
    "MALLAPPALLY":  "PATHANAMTHITTA",
    "KANAYANNUR":   "ERNAKULAM",
    "THIRUVANANTHAPURAM": "THIRUVANANTHAPURAM",

    # ── ANDHRA PRADESH ───────────────────────────────────────────────────────
    "GUNTUR":       "GUNTUR",
    "VISHAKHAPATNAM": "VISAKHAPATNAM",
    "VIZAG":        "VISAKHAPATNAM",
    "VIJAYAWADA":   "KRISHNA",
    "ANANTAPUR":    "ANANTAPUR",
    "TIRUPATI":     "CHITTOOR",

    # ── TELANGANA ────────────────────────────────────────────────────────────
    "HYDERABAD":    "HYDERABAD",
    "SECUNDERABAD": "HYDERABAD",
    "WARANGAL":     "WARANGAL",

    # ── TAMIL NADU ───────────────────────────────────────────────────────────
    "TIRUVALLUR":   "TIRUVALLUR",
    "TIRUVALLUIR":  "TIRUVALLUR",
    "CHENNAI":      "CHENNAI",
    "COIMBATORE":   "COIMBATORE",
    "MADURAI":      "MADURAI",

    # ── WEST BENGAL ──────────────────────────────────────────────────────────
    "KOLKATA":      "KOLKATA",
    "HOWRAH":       "HOWRAH",

    # ── BIHAR ────────────────────────────────────────────────────────────────
    "MUZAFFARPUR":  "MUZAFFARPUR",
    "PATNA":        "PATNA",
    "GAYA":         "GAYA",

    # ── ASSAM ────────────────────────────────────────────────────────────────
    "GUWAHATI":     "KAMRUP METROPOLITAN",

    # ── GOA ──────────────────────────────────────────────────────────────────
    "GOA":          "NORTH GOA",
    "PANAJI":       "NORTH GOA",
    "MARGAO":       "SOUTH GOA",
}

# ─────────────────────────────────────────────────────────────────────────────
# 3. STATE MAPPING  (Ship to state → your app state name)
# ─────────────────────────────────────────────────────────────────────────────
STATE_MAP = {
    "Haryana":          "Haryana",
    "Punjab":           "Punjab",
    "Delhi":            "Delhi",
    "Uttar Pradesh":    "Uttar Pradesh",
    "Rajasthan":        "Rajasthan",
    "Gujarat":          "Gujarat",
    "Madhya Pradesh":   "Madhya Pradesh",
    "Maharashtra":      "Maharashtra",
    "Chhattisgarh":     "Chhattisgarh",
    "Karnataka":        "Karnataka",
    "Kerala":           "Kerala",
    "Andhra Pradesh":   "Andhra Pradesh",
    "Telangana":        "Telangana",
    "Tamil Nadu":       "Tamil Nadu",
    "West Bengal":      "West Bengal",
    "Bihar":            "Bihar",
    "Assam":            "Assam",
    "Goa":              "Goa",
    "Jammu and Kashmir": "Jammu and Kashmir",
    "Himachal Pradesh": "Himachal Pradesh",
    "Uttarakhand":      "Uttarakhand",
}


# ─────────────────────────────────────────────────────────────────────────────
# 4. CORE PROCESSING
# ─────────────────────────────────────────────────────────────────────────────
def process_dispatch_file(filepath: str) -> pd.DataFrame:
    """Read dispatch Excel and return cleaned DataFrame."""
    print(f"  Reading: {os.path.basename(filepath)}")
    df = pd.read_excel(filepath)

    required = ["Ship to state", "Ship to City", "Brand", "Net Weight"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in {filepath}: {missing}")

    df["Ship to City_upper"] = df["Ship to City"].str.strip().str.upper()
    df["App_Brand"] = df["Brand"].map(BRAND_MAP).fillna("Others")
    df["App_State"] = df["Ship to state"].map(STATE_MAP)
    df["App_District"] = df["Ship to City_upper"].map(CITY_TO_DISTRICT)

    return df


def aggregate_volumes(df: pd.DataFrame) -> dict:
    """
    Returns dict:
      { state_name: { district_name: { brand: mt_volume } } }
    """
    result = {}
    for _, row in df.iterrows():
        state = row["App_State"]
        district = row["App_District"]
        brand = row["App_Brand"]
        wt = row["Net Weight"]

        if pd.isna(state) or pd.isna(district) or pd.isna(wt):
            continue

        result.setdefault(state, {})
        result[state].setdefault(district, {b: 0.0 for b in APP_BRANDS})
        result[state][district][brand] = round(
            result[state][district].get(brand, 0.0) + wt, 3
        )

    return result


def find_unmapped(df: pd.DataFrame) -> pd.DataFrame:
    """Return rows where city or state couldn't be mapped."""
    unmapped = df[df["App_District"].isna() | df["App_State"].isna()].copy()
    return (
        unmapped.groupby(["Ship to state", "Ship to City", "Brand"])["Net Weight"]
        .sum()
        .reset_index()
        .sort_values("Net Weight", ascending=False)
    )


# ─────────────────────────────────────────────────────────────────────────────
# 5. GENERATE OUTPUT FILES
# ─────────────────────────────────────────────────────────────────────────────
def generate_python_module(volumes: dict, output_path: str, file_date: str):
    """
    Writes market_map_data.py — a drop-in module your Streamlit app imports.
    Replace the manual data dicts in get_state_data() with:

        from market_map_data import get_state_data
    """
    lines = [
        '"""',
        f'market_map_data.py — AUTO-GENERATED on {datetime.now().strftime("%Y-%m-%d %H:%M")}',
        f'Source file date: {file_date}',
        f'DO NOT EDIT MANUALLY — regenerate by running auto_populate_market_map.py',
        '"""',
        "import pandas as pd",
        "",
        "",
        "def get_state_data(state_name: str) -> pd.DataFrame:",
        '    """Return district-level brand volume DataFrame for the given state."""',
        "    data_store = {",
    ]

    for state, districts in sorted(volumes.items()):
        lines.append(f'        "{state}": {{')
        lines.append(f'            "District": {sorted(districts.keys())},')
        for brand in APP_BRANDS:
            col_safe = brand.replace("/", "_").replace(" ", "_")
            values = [round(districts[d].get(brand, 0.0), 1) for d in sorted(districts.keys())]
            lines.append(f'            "{brand}": {values},')
        lines.append("        },")

    lines += [
        "    }",
        "",
        "    if state_name not in data_store:",
        '        raise ValueError(f"No dispatch data found for state: {state_name}")',
        "",
        "    return pd.DataFrame(data_store[state_name])",
        "",
        "",
        "AVAILABLE_STATES = [",
    ]
    for s in sorted(volumes.keys()):
        lines.append(f'    "{s}",')
    lines.append("]")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))
    print(f"  ✅ Python module written: {output_path}")


def generate_excel_report(df: pd.DataFrame, volumes: dict, output_path: str):
    """Write a multi-sheet Excel for human review."""
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:

        # Sheet 1: Raw mapped rows
        cols = ["Ship to state", "Ship to City", "Name 1", "Brand",
                "App_State", "App_District", "App_Brand", "Net Weight"]
        df[cols].sort_values(["App_State", "App_District", "App_Brand"]).to_excel(
            writer, sheet_name="Mapped Rows", index=False
        )

        # Sheet 2: State-District-Brand pivot
        rows = []
        for state, districts in sorted(volumes.items()):
            for district, brands in sorted(districts.items()):
                row = {"State": state, "District": district}
                row.update(brands)
                row["Total"] = sum(brands.values())
                rows.append(row)
        pivot_df = pd.DataFrame(rows)
        pivot_df.to_excel(writer, sheet_name="District Summary", index=False)

        # Sheet 3: State totals
        state_rows = []
        for state, districts in sorted(volumes.items()):
            row = {"State": state}
            for brand in APP_BRANDS:
                row[brand] = sum(d.get(brand, 0) for d in districts.values())
            row["Total"] = sum(row[b] for b in APP_BRANDS)
            state_rows.append(row)
        pd.DataFrame(state_rows).to_excel(writer, sheet_name="State Totals", index=False)

    print(f"  ✅ Excel report written: {output_path}")


def generate_log(unmapped: pd.DataFrame, output_path: str):
    """Write unmapped cities log so you can add them to CITY_TO_DISTRICT."""
    lines = [
        f"UNMAPPED CITIES LOG — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 60,
        "Add these to CITY_TO_DISTRICT dict in auto_populate_market_map.py",
        "",
    ]
    if unmapped.empty:
        lines.append("✅ All cities successfully mapped!")
    else:
        lines.append(f"⚠️  {len(unmapped)} city combinations could not be mapped:\n")
        for _, row in unmapped.iterrows():
            lines.append(
                f"  State: {row['Ship to state']:<20}  "
                f"City: {row['Ship to City']:<25}  "
                f"Brand: {row['Brand']:<20}  "
                f"MT: {row['Net Weight']:.2f}"
            )
    with open(output_path, "w") as f:
        f.write("\n".join(lines))
    print(f"  ✅ Log written: {output_path}")
    if not unmapped.empty:
        print(f"  ⚠️  {len(unmapped)} unmapped cities — check market_map_log.txt")


# ─────────────────────────────────────────────────────────────────────────────
# 6. STREAMLIT INTEGRATION SNIPPET (printed to console)
# ─────────────────────────────────────────────────────────────────────────────
INTEGRATION_SNIPPET = """
╔══════════════════════════════════════════════════════════════════╗
║  HOW TO USE market_map_data.py IN YOUR STREAMLIT APP            ║
╠══════════════════════════════════════════════════════════════════╣
║                                                                  ║
║  1. Copy market_map_data.py to same folder as                    ║
║     state_colour_frame.py                                        ║
║                                                                  ║
║  2. At the TOP of state_colour_frame.py, replace:               ║
║                                                                  ║
║     @st.cache_data                                               ║
║     def get_state_data(state_name):                              ║
║         if state_name == "Punjab":                               ║
║             data = { ... }                                       ║
║         ...                                                      ║
║                                                                  ║
║     WITH:                                                        ║
║                                                                  ║
║     from market_map_data import get_state_data, AVAILABLE_STATES ║
║     get_state_data = st.cache_data(get_state_data)              ║
║                                                                  ║
║  3. Update sidebar dropdown:                                     ║
║     target_state = st.sidebar.selectbox(                        ║
║         "Select State", AVAILABLE_STATES)                       ║
║                                                                  ║
║  4. Run daily:                                                   ║
║     python auto_populate_market_map.py --file "8_6_26.XLSX"     ║
║                                                                  ║
╚══════════════════════════════════════════════════════════════════╝
"""


# ─────────────────────────────────────────────────────────────────────────────
# 7. MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="Auto-populate JSW market map from daily dispatch Excel"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file", help="Path to a single dispatch XLSX file")
    group.add_argument("--folder", help="Path to folder of dispatch XLSX files (processes all)")
    parser.add_argument("--out", default=".", help="Output folder (default: current dir)")
    args = parser.parse_args()

    os.makedirs(args.out, exist_ok=True)

    # Collect files
    if args.file:
        files = [args.file]
        file_date = os.path.basename(args.file).replace(".XLSX", "").replace(".xlsx", "")
    else:
        files = [
            os.path.join(args.folder, f)
            for f in os.listdir(args.folder)
            if f.lower().endswith(".xlsx")
        ]
        file_date = "multi-file"
        print(f"  Found {len(files)} files in folder")

    # Process
    all_dfs = []
    for f in files:
        try:
            all_dfs.append(process_dispatch_file(f))
        except Exception as e:
            print(f"  ❌ Skipped {f}: {e}")

    if not all_dfs:
        print("No files processed. Exiting.")
        return

    combined = pd.concat(all_dfs, ignore_index=True)
    print(f"\n  Total rows: {len(combined):,}")
    print(f"  Total MT  : {combined['Net Weight'].sum():.1f}")

    # Aggregate
    volumes = aggregate_volumes(combined)
    unmapped = find_unmapped(combined)

    print(f"\n  States mapped   : {len(volumes)}")
    print(f"  Districts mapped: {sum(len(d) for d in volumes.values())}")
    print(f"  Unmapped rows   : {len(combined[combined['App_District'].isna()])}")

    # Write outputs
    print("\n  Writing outputs...")
    generate_python_module(
        volumes,
        os.path.join(args.out, "market_map_data.py"),
        file_date
    )
    generate_excel_report(
        combined,
        volumes,
        os.path.join(args.out, "market_map_data.xlsx")
    )
    generate_log(
        unmapped,
        os.path.join(args.out, "market_map_log.txt")
    )

    print(INTEGRATION_SNIPPET)


if __name__ == "__main__":
    main()
