import streamlit as st
import requests

API_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="Internal HR Policy Assistant", page_icon="📋", layout="centered")

if "admin_token" not in st.session_state:
    st.session_state.admin_token = ""
if "messages" not in st.session_state:
    st.session_state.messages = []
if "rated_indices" not in st.session_state:
    st.session_state.rated_indices = {}

def send_feedback(idx: int, question: str, answer: str, citations: list, rating: str):
    try:
        res = requests.post(
            f"{API_URL}/feedback",
            json={
                "question": question,
                "answer": answer,
                "citations": citations,
                "rating": rating,
            },
            timeout=10,
        )
        if res.status_code == 200:
            st.session_state.rated_indices[idx] = rating
    except Exception:
        st.toast("Could not save feedback.")

# --- Sidebar: Role Switcher & Active Policies ---
with st.sidebar:
    st.header("Navigation & Role")
    role = st.radio("Select View:", ["Employee (Ask HR)", "Admin (Manage Policies)"])
    st.divider()

    st.subheader("Active Policies")
    try:
        docs_res = requests.get(f"{API_URL}/documents", timeout=5)
        if docs_res.status_code == 200:
            docs = docs_res.json().get("documents", [])
            if docs:
                for d in docs:
                    st.markdown(f"- 📄 **{d}**")
            else:
                st.info("No policies indexed yet.")
    except Exception:
        st.warning("Backend offline. Start FastAPI first.")

# ==========================================
# VIEW 1: ADMIN PAGE (Token-Protected)
# ==========================================
if role == "Admin (Manage Policies)":
    st.title("🔐 Admin: Policy Management")
    st.caption("Upload new HR policies or replace existing versions (.md, .txt, .pdf).")

    token_input = st.text_input(
        "Enter Admin Token",
        type="password",
        value=st.session_state.admin_token,
        placeholder="e.g., hr-admin-2026",
    )
    st.session_state.admin_token = token_input

    if not token_input:
        st.info("Please enter the Admin Token (configured in `.env`) to unlock policy uploads & feedback logs.")
    else:
        uploaded_file = st.file_uploader("Choose a policy document", type=["md", "txt", "pdf"])
        if uploaded_file is not None:
            if st.button("Upload & Index Policy", type="primary"):
                with st.spinner("Chunking and indexing..."):
                    try:
                        files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                        headers = {"X-Admin-Token": token_input}
                        res = requests.post(f"{API_URL}/upload", files=files, headers=headers, timeout=30)
                        if res.status_code == 200:
                            data = res.json()
                            st.success(f"Indexed **{data['document']}** ({data['chunks_indexed']} sections)")
                            st.rerun()
                        elif res.status_code == 401:
                            st.error("Invalid Admin Token. Access denied.")
                        else:
                            st.error(res.json().get("detail", "Upload failed."))
                    except Exception as e:
                        st.error(f"Backend error: {e}")

        st.divider()
        st.subheader("📊 Employee Answer Feedback Log")
        try:
            fb_res = requests.get(
                f"{API_URL}/feedback",
                headers={"X-Admin-Token": token_input},
                timeout=10,
            )
            if fb_res.status_code == 200:
                entries = fb_res.json().get("feedback", [])
                if not entries:
                    st.caption("No feedback recorded yet.")
                else:
                    up_count = sum(1 for e in entries if e["rating"] == "up")
                    down_count = sum(1 for e in entries if e["rating"] == "down")
                    st.write(f"**Total Ratings:** {len(entries)} (👍 {up_count} | 👎 {down_count})")
                    for item in reversed(entries[-10:]):
                        icon = "👍" if item["rating"] == "up" else "👎"
                        st.markdown(f"- {icon} **Q:** {item['question']} → *{item['answer']}*")
            elif fb_res.status_code == 401:
                st.error("Invalid Admin Token for viewing feedback.")
        except Exception:
            st.warning("Could not load feedback logs.")

# ==========================================
# VIEW 2: EMPLOYEE PAGE (Public Q&A + Thumbs Up/Down)
# ==========================================
else:
    st.title("📋 Internal HR Policy Assistant")
    st.caption("Ask questions strictly grounded in uploaded company HR policies.")

    for idx, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("citations"):
                st.markdown("**Citations:**")
                for c in msg["citations"]:
                    st.markdown(f"> 📌 `{c['document']}` — *{c['section']}*")

            if msg["role"] == "assistant":
                rated = st.session_state.rated_indices.get(idx)
                if rated:
                    st.caption(f"Feedback recorded: {'👍 Helpful' if rated == 'up' else '👎 Flagged for HR review'}")
                else:
                    col1, col2, _ = st.columns([1, 1, 6])
                    with col1:
                        if st.button("👍", key=f"up_{idx}", help="Helpful answer"):
                            send_feedback(idx, msg.get("question", ""), msg["content"], msg.get("citations", []), "up")
                            st.rerun()
                    with col2:
                        if st.button("👎", key=f"down_{idx}", help="Incorrect or unhelpful"):
                            send_feedback(idx, msg.get("question", ""), msg["content"], msg.get("citations", []), "down")
                            st.rerun()

    question = st.chat_input("Ask an HR policy question (e.g., Does Standard cover dental implants?)")

    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Searching policies..."):
                try:
                    res = requests.post(f"{API_URL}/ask", json={"question": question}, timeout=30)
                    if res.status_code == 200:
                        data = res.json()
                        st.session_state.messages.append({
                            "role": "assistant",
                            "question": question,
                            "content": data["answer"],
                            "citations": data.get("citations", []),
                        })
                        st.rerun()
                    else:
                        st.error(res.json().get("detail", "Request failed."))
                except Exception as e:
                    st.error(f"Could not reach API: {e}")