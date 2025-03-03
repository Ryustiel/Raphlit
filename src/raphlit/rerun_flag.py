
from typing import (
    Optional,
    Literal,
)
import streamlit as st

def rerun_if_flag(scope: Optional[Literal["app", "fragment"]] = None):
    if "rerun_flag" in st.session_state:
        del st.session_state["rerun_flag"]
        st.rerun(scope=scope) if scope else st.rerun()

def set_rerun_flag():
    st.session_state["rerun_flag"] = True
    