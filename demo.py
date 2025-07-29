import streamlit as st
import pandas as pd
from pulp import *
from streamlit_extras.stylable_container import stylable_container

# Hide "Press Enter to apply" instructions for number_input
st.markdown("""
<style>
[data-testid="InputInstructions"] {
    display: none;
}
</style>
""", unsafe_allow_html=True)

# Load data
df = pd.read_excel("Price_3.xlsx")

# --- Utility Functions ---
def get_price_column(market, location):
    return {
        ('Thai', 'OPD'): 'OPD_Thai_Price',
        ('Thai', 'IPD'): 'IPD_Thai_Price',
        ('International', 'OPD'): 'OPD_Inter_Price',
        ('International', 'IPD'): 'IPD_Inter_Price'
    }.get((market, location), None)

def optimize_for_drug(vial_options, original_only_filter=False, dose=None):
    if original_only_filter:
        vial_options = vial_options[vial_options['OriginalBrand'] == True]
    if vial_options.empty:
        return None

    vial_options = vial_options.to_dict(orient='records')
    prob = LpProblem("MinCost", LpMinimize)
    x = [LpVariable(f"x{i}", lowBound=0, cat='Integer') for i in range(len(vial_options))]

    prob += lpSum([x[i] * vial_options[i]['Selected_Price'] for i in range(len(vial_options))])
    prob += lpSum([x[i] * vial_options[i]['Strength'] for i in range(len(vial_options))]) >= dose
    prob.solve()

    if LpStatus[prob.status] == 'Optimal':
        result = {'combo': [], 'cost': 0, 'dose': 0, 'codes': []}
        for i, var in enumerate(x):
            qty = int(var.varValue)
            if qty > 0:
                opt = vial_options[i]
                result['combo'].append(f"{qty} x {opt['Strength']} mg @ ฿{opt['Selected_Price']} [Code: {opt.get('Drug_Code', 'N/A')}]")
                result['cost'] += qty * opt['Selected_Price']
                result['dose'] += qty * opt['Strength']
                result['codes'].append(opt.get('Drug_Code', 'N/A'))
        return result
    return None

# --- Session State ---
if "drug_list" not in st.session_state:
    st.session_state.drug_list = []

if "edit_index" not in st.session_state:
    st.session_state.edit_index = None

# --- UI: Header ---
st.title("Drug Optimization")
st.caption("Enter patient details and drug information")

st.set_page_config(layout="centered")


# --- UI: Patient Info ---
st.markdown("### 👤 Patient Information")
market = st.radio("Nationality", ["Thai", "International"], horizontal=True)
location = st.radio("Department", ["IPD", "OPD"], horizontal=True)

# --- UI: Add Drug Box (Always Visible) ---
st.markdown("### ➕ Add Drug")
add_col1, add_col2, add_col3 = st.columns([0.5, 0.3, 0.2], vertical_alignment="bottom", gap="small")

new_drug = add_col1.selectbox("Drug Name", df["Drug"].unique(), key="add_drug", index=None, placeholder="Select a drug")
new_dose = add_col2.number_input("Quantity", min_value=0.1, step=0.1, key="add_dose", value=None, placeholder="Insert number", format="%.2f")

if add_col3.button("➕ Add to List", type="primary"):
    st.session_state.drug_list.append({"drug": new_drug, "dose": new_dose})
    st.rerun()

# --- UI: Drug List ---
if st.session_state.drug_list:
    st.markdown("### 📋 Drug List")

    for idx, item in enumerate(st.session_state.drug_list):
        if st.session_state.edit_index == idx:
            # --- Inline Editing Row (wrapped in form) ---
            with st.form(key=f"edit_form_{idx}"):
                edit_col1, edit_col2, edit_col3, edit_col4 = st.columns([3, 2, 1, 1], gap="small", vertical_alignment="bottom")

                drug_options = df["Drug"].unique().tolist()
                edited_drug = edit_col1.selectbox(
                    "Edit Drug Name", drug_options,
                    index=drug_options.index(item["drug"]),
                    key=f"edit_drug_{idx}"
                )
                edited_dose = edit_col2.number_input(
                    "Edit Quantity", min_value=0.1, step=0.1, value=item["dose"], format="%.2f",
                    key=f"edit_dose_{idx}"
                )

                save = edit_col3.form_submit_button("💾 Save")
                cancel = edit_col4.form_submit_button("↩️ Back")

                if save:
                    st.session_state.drug_list[idx] = {"drug": edited_drug, "dose": edited_dose}
                    st.session_state.edit_index = None
                    st.rerun()
                elif cancel:
                    st.session_state.edit_index = None
                    st.rerun()

        else:
            # --- Normal display row with buttons inside the box using single markdown ---
            st.markdown(f"""
                <div style='background-color:#F0F2F6;padding:10px 15px;border-radius:10px;display:flex;justify-content:space-between;align-items:center;min-height:60px;'>
                    <div style='flex-grow:1;text-align:left;'>
                        <p style='margin:0;line-height:1.4;'>
                            💊 <b>{item['drug']}</b><br>
                            Quantity: {item['dose']:.2f}
                        </p>
                    </div>
                </div>
            """, unsafe_allow_html=True)

            st.markdown("""<div><br></div>""", unsafe_allow_html=True)

            # Buttons below for functionality
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("✏️ Edit", key=f"edit_btn_{idx}", type="secondary", use_container_width=True):
                    st.session_state.edit_index = idx
                    st.rerun()
            with col2:
                if st.button("🗑️ Delete", key=f"delete_btn_{idx}", type="secondary", use_container_width=True):
                    st.session_state.drug_list.pop(idx)
                    st.rerun()


# --- UI: Run Calculation ---
if st.session_state.drug_list:
    st.markdown("---")
    if st.button("📊 Run Calculation"):
        st.markdown("## 🧪 Results")
        for entry in st.session_state.drug_list:
            st.subheader(f"{entry['drug']} ({entry['dose']} mg)")
            vial_options = df[df["Drug"] == entry["drug"]].copy()
            price_col = get_price_column(market, location)
            if not price_col:
                st.error("Invalid price column.")
                continue

            vial_options["Selected_Price"] = vial_options[price_col]
            vial_options = vial_options.dropna(subset=["Selected_Price"])

            plan_a = optimize_for_drug(vial_options, original_only_filter=False, dose=entry["dose"])
            plan_b = optimize_for_drug(vial_options, original_only_filter=True, dose=entry["dose"])

            st.markdown("### 💰 Plan A: Cheapest")
            if plan_a:
                st.write(f"- Total Cost: ฿{plan_a['cost']}")
                st.write(f"- Total Dose: {plan_a['dose']} mg")
                for line in plan_a["combo"]:
                    st.write(f"  - {line}")
            else:
                st.warning("No valid combination (all brands)")

            st.markdown("### 🧬 Plan B: Originator Only")
            if plan_b:
                st.write(f"- Total Cost: ฿{plan_b['cost']}")
                st.write(f"- Total Dose: {plan_b['dose']} mg")
                for line in plan_b["combo"]:
                    st.write(f"  - {line}")
            else:
                st.warning("No valid combination (original brand only)")
            st.divider()
