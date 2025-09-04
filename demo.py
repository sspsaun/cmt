import streamlit as st
import pandas as pd
from pulp import *
from streamlit_extras.stylable_container import stylable_container

# hide "Press Enter to apply" instructions for number_input
st.markdown(
    """
<style>
[data-testid="InputInstructions"] {
    display: none;
}
</style>
""",
    unsafe_allow_html=True,
)

# drug price data
df = pd.read_excel("Price_3.xlsx")

# utils
def get_price_column(market, location):
    return {
        ("Thai", "OPD"): "OPD_Thai_Price",
        ("Thai", "IPD"): "IPD_Thai_Price",
        ("International", "OPD"): "OPD_Inter_Price",
        ("International", "IPD"): "IPD_Inter_Price",
    }.get((market, location), None)

def optimize_for_drug(vial_options, original_only_filter=False, dose=None):
    if original_only_filter:
        vial_options = vial_options[vial_options["OriginalBrand"] == True]
    if vial_options.empty:
        return None

    vial_options = vial_options.to_dict(orient="records")
    prob = LpProblem("MinCost", LpMinimize)
    x = [
        LpVariable(f"x{i}", lowBound=0, cat="Integer") for i in range(len(vial_options))
    ]

    prob += lpSum(
        [x[i] * vial_options[i]["Selected_Price"] for i in range(len(vial_options))]
    )
    prob += (
        lpSum([x[i] * vial_options[i]["Strength"] for i in range(len(vial_options))])
        >= dose
    )
    prob.solve()

    if LpStatus[prob.status] == "Optimal":
        result = {"combo": [], "cost": 0, "dose": 0, "codes": []}
        for i, var in enumerate(x):
            if var.varValue is None:
                continue
            qty = int(var.varValue)
            if qty > 0:
                opt = vial_options[i]
                result["combo"].append(
                    f"{qty} x {opt['Strength']} mg @ ฿{opt['Selected_Price']} [Code: {opt.get('Drug_Code', 'N/A')}]"
                )
                result["cost"] += qty * opt["Selected_Price"]
                result["dose"] += qty * opt["Strength"]
                result["codes"].append(opt.get("Drug_Code", "N/A"))
        return result
    return None


# Session State Setup
if "drug_list" not in st.session_state:
    st.session_state.drug_list = []

if "edit_index" not in st.session_state:
    st.session_state.edit_index = None

# UI: Header
st.title("Drug Optimization")
st.caption("Enter patient details and drug information")

st.set_page_config(layout="centered")

# UI: Patient Information
st.markdown("### 👤 Patient Information")
market = st.radio("Nationality", ["Thai", "International"], horizontal=True)
location = st.radio("Department", ["OPD", "IPD"], horizontal=True)

# UI: Add Drug Box (Always Visible)
st.markdown("### ➕ Add Drug")

# Check if we need to clear inputs after adding
if "clear_inputs" in st.session_state and st.session_state.clear_inputs:
    st.session_state.add_drug = None
    st.session_state.add_dose = None
    st.session_state.clear_inputs = False

# add_col1, add_col2, add_col3 = st.columns(
#     [0.5, 0.3, 0.2], vertical_alignment="bottom", gap="small"
# )

# new_drug = add_col1.selectbox(
#     "Drug Name",
#     df["Drug"].unique(),
#     key="add_drug",
#     index=None,
#     placeholder="Select a drug",
#     format_func=lambda x: x if pd.notna(x) else "Select a drug",
# )
# new_dose = add_col2.number_input(
#     "Quantity",
#     min_value=1.0,
#     step=0.1,
#     key="add_dose",
#     placeholder="Insert number",
#     format="%.2f",
# )

# if add_col3.button("&#65291; Add to List", use_container_width=True, type="primary"):
#     # st.session_state.drug_list.append({"drug": new_drug, "dose": new_dose})
#     # st.session_state.clear_inputs = True
#     # st.rerun()
#     if new_drug and new_dose is not None:
#         st.session_state.drug_list.append({"drug": new_drug, "dose": new_dose})
#         st.session_state.clear_inputs = True
#         st.rerun()
#     else:
#         if new_drug is None or new_drug == "None":
#             st.warning("⚠️ Please select \"Drug\"")
#         if new_dose is None or new_dose <= 0:
#             st.warning("⚠️ Please insert \"Quantity\"")

with st.form(key="add_drug_form"):
    add_col1, add_col2, add_col3 = st.columns(
        [0.5, 0.3, 0.2], vertical_alignment="bottom", gap="small"
    )

    new_drug = add_col1.selectbox(
        "Drug Name",
        df["Drug"].unique(),
        key="add_drug",
        index=None,
        placeholder="Select a drug",
        format_func=lambda x: x if pd.notna(x) else "Select a drug",
    )

    new_dose = add_col2.number_input(
        "Quantity",
        min_value=1.0,
        step=0.1,
        key="add_dose",
        placeholder="Insert number",
        format="%.2f",
    )

    submit = add_col3.form_submit_button(
        "&#65291; Add to List", use_container_width=True
    )

    if submit:
        warnings = []
        if not new_drug:
            warnings.append('⚠️ Please select "Drug"')
        if new_dose is None or new_dose <= 0:
            warnings.append('⚠️ Please insert "Quantity"')

        if warnings:
            for w in warnings:
                st.warning(w)
        else:
            st.session_state.drug_list.append({"drug": new_drug, "dose": new_dose})
            st.session_state.clear_inputs = True
            st.rerun()


# UI: Drug List
if st.session_state.drug_list:
    st.markdown("### 📋 Drug List")
    for idx, item in enumerate(st.session_state.drug_list):
        if st.session_state.edit_index == idx:
            # Inline Editing Row
            with st.form(key=f"edit_form_{idx}"):
                edit_col1, edit_col2, edit_col3, edit_col4 = st.columns(
                    [0.45, 0.25, 0.15, 0.15], gap="small", vertical_alignment="bottom"
                )
                drug_options = df["Drug"].unique().tolist()
                edited_drug = edit_col1.selectbox(
                    "Edit Drug Name",
                    drug_options,
                    index=drug_options.index(item["drug"]),
                    key=f"edit_drug_{idx}",
                    format_func=lambda x: x if pd.notna(x) else "Select a drug",
                )
                edited_dose = edit_col2.number_input(
                    "Edit Quantity",
                    min_value=0.1,
                    step=0.1,
                    value=item["dose"],
                    format="%.2f",
                    key=f"edit_dose_{idx}",
                )

                save = edit_col3.form_submit_button("Save", use_container_width=True)
                cancel = edit_col4.form_submit_button("Back", use_container_width=True)

                if save:
                    st.session_state.drug_list[idx] = {
                        "drug": edited_drug,
                        "dose": edited_dose,
                    }
                    st.session_state.edit_index = None
                    st.rerun()
                elif cancel:
                    st.session_state.edit_index = None
                    st.rerun()

        else:
            # Use stylable_container for a proper card with buttons inside
            with stylable_container(
                key=f"drug_card_{idx}",
                css_styles="""
                {
                    background-color: #F0F2F6;
                    padding: 16px;
                    border-radius: 12px;
                }
                """,
            ):
                # Card layout with text and buttons
                card_left, card_right = st.columns([4, 2], vertical_alignment="center")

                with card_left:
                    st.markdown(
                        f"<div style='margin: 0px 30px 30px 0px;'><b>💊 {item['drug']}</b><br>Quantity: {item['dose']:.2f}</div>",
                        unsafe_allow_html=True,
                    )

                    # st.write(f"💊 **{item['drug']}**")
                    # st.write(f"Quantity: {item['dose']:.2f}")

                # with card_right:
                #     btn1, btn2 = st.columns(2)
                #     with btn1:
                #         if st.button("✏️ Edit", key=f"edit_{idx}", use_container_width=True):
                #             st.session_state.edit_index = idx
                #             st.rerun()
                #     with btn2:
                #         if st.button("🗑️ Delete", key=f"delete_{idx}", use_container_width=True):
                #             st.session_state.drug_list.pop(idx)
                #             st.rerun()
                with card_right:
                    btn1, btn2 = st.columns(2)
                    with btn1:
                        if st.button("✏️ Edit", key=f"edit_{idx}", use_container_width=True):
                            st.session_state.edit_index = idx
                            st.rerun()
                        st.markdown("<div style='margin: 0px 0px 0px 0px;'></div>", unsafe_allow_html=True)
                    with btn2:
                        if st.button("🗑️ Delete", key=f"delete_{idx}", use_container_width=True):
                            st.session_state.drug_list.pop(idx)
                            st.rerun()
                        st.markdown("<div style='margin: 0px 0px 0px 0px;'></div>", unsafe_allow_html=True)

# UI: Run Calculation
if st.button(
    "📊 Run Calculation",
    disabled=not bool(st.session_state.drug_list),
    use_container_width=True,
):
    st.markdown("---")
    
    if st.session_state.drug_list:
        st.markdown("## 🧪 Results")

        # Initialize totals for both plans
        total_cost_plan_a = 0
        total_cost_plan_b = 0

        # Create two columns for the plans
        col_plan_a, col_plan_b = st.columns(2)

        with col_plan_a:
            st.markdown("### 💰 Plan A: Cheapest")

        with col_plan_b:
            st.markdown("### 🧬 Plan B: Originator Only")

        # Process each drug
        for entry in st.session_state.drug_list:
            
            vial_options = df[df["Drug"] == entry["drug"]].copy()
            price_col = get_price_column(market, location)
            if not price_col:
                st.error("Invalid price column.")
                continue

            vial_options["Selected_Price"] = vial_options[price_col]
            vial_options = vial_options.dropna(subset=["Selected_Price"])

            plan_a = optimize_for_drug(
                vial_options, original_only_filter=False, dose=entry["dose"]
            )
            plan_b = optimize_for_drug(
                vial_options, original_only_filter=True, dose=entry["dose"]
            )

            # Display Plan A
            with col_plan_a:
                st.markdown(f"**{entry['drug']} ({entry['dose']:,.2f} mg)**")
                if plan_a:
                    st.write(
                        f"Cost: ฿{plan_a['cost']:,.2f} | Dose: {plan_a['dose']:,} mg"
                    )
                    for line in plan_a["combo"]:
                        st.write(f"• {line}")
                    total_cost_plan_a += plan_a["cost"]
                else:
                    st.warning("No valid combination")
                st.markdown("---")

            # Display Plan B
            with col_plan_b:
                st.markdown(f"**{entry['drug']} ({entry['dose']:,.2f} mg)**")
                if plan_b:
                    st.write(
                        f"Cost: ฿{plan_b['cost']:,.2f} | Dose: {plan_b['dose']:,} mg"
                    )
                    for line in plan_b["combo"]:
                        st.write(f"• {line}")
                    total_cost_plan_b += plan_b["cost"]
                else:
                    st.warning("No valid combination")
                st.markdown("---")

        # Display totals
        with col_plan_a:
            st.markdown(f"### **Total Cost: ฿{total_cost_plan_a:,.2f}**")

        with col_plan_b:
            st.markdown(f"### **Total Cost: ฿{total_cost_plan_b:,.2f}**")
