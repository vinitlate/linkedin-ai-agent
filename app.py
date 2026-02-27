import streamlit as st
from agent_core import run_agent, load_memory, add_feedback, update_profile_settings, list_available_chat_models, run_weekly_trend_to_post

st.set_page_config(page_title="LinkedIn Agent", layout="wide")

st.title("LinkedIn Content Agent")
st.caption("Goal → Plan → Draft → Save → Learn")

# Always load memory fresh so changes appear immediately after saving
memory = load_memory()

with st.sidebar:
    st.header("Profile & Settings")

    edit_mode = st.toggle("Edit profile", value=False)

    # Defaults from memory
    default_name = memory["profile"]["name"]
    default_niche = memory["profile"]["niche"]
    default_audience = memory["profile"]["audience"]
    default_tone_rules = "\n".join(memory["profile"]["tone_rules"])

    default_post_length = memory["best_practices"].get("post_length", "120-220 words")
    default_structure = "\n".join(memory["best_practices"].get("structure", []))

    if not edit_mode:
        st.write(f"**Name:** {default_name}")
        st.write(f"**Niche:** {default_niche}")
        st.write(f"**Audience:** {default_audience}")
        st.write("**Tone rules:**")
        for r in memory["profile"]["tone_rules"]:
            st.write(f"- {r}")

        st.divider()
        st.write(f"**Post length:** {default_post_length}")
        st.write("**Structure:**")
        for s in memory["best_practices"].get("structure", []):
            st.write(f"- {s}")

    else:
        name = st.text_input("Name", value=default_name)
        niche = st.text_input("Niche", value=default_niche)
        audience = st.text_input("Audience", value=default_audience)

        tone_rules_text = st.text_area(
            "Tone rules (one per line)",
            value=default_tone_rules,
            height=140,
            help="Example: sound practical, not hype-y",
        )

        st.subheader("Post template")
        post_length = st.text_input("Target post length", value=default_post_length)

        structure_text = st.text_area(
            "Structure (one per line)",
            value=default_structure,
            height=140,
            help="Example:\nhook\nproblem\ninsight\nexample\ntakeaway\nquestion",
        )

        if st.button("Save settings", type="primary", use_container_width=True):
            try:
                updated_profile = {
                    "name": name,
                    "niche": niche,
                    "audience": audience,
                    "tone_rules": [line for line in tone_rules_text.splitlines()],
                }
                updated_best = {
                    "post_length": post_length,
                    "structure": [line for line in structure_text.splitlines()],
                }
                update_profile_settings(updated_profile, updated_best)
                st.success("Saved ✅ Reloading…")
                st.rerun()
            except Exception as e:
                st.error(str(e))

    st.divider()
    st.header("Generation")
    try:
        models = list_available_chat_models()
        if not models:
            st.warning("No chat-capable models found.")
            models = ["gpt-5.2"]
    except Exception as e:
        st.error(f"Failed to fetch models: {e}")
        models = ["gpt-5.2"]

    model = st.selectbox("Model", models, index=0)
    do_compress = st.checkbox("Auto-shorten to ~180 words", value=True)

topic = st.text_input("Topic", placeholder="e.g., Idempotency, Kafka vs Kinesis, AI agents vs chatbots")

col1, col2 = st.columns([1, 1])

if "result" not in st.session_state:
    st.session_state.result = None

with col1:
    colA, colB = st.columns(2)

    if "run_params" not in st.session_state:
        st.session_state.run_params = None

    with colA:
        if st.button("Generate", type="primary", use_container_width=True, disabled=not topic.strip()):
            st.session_state.run_params = {
                "mode": "manual",
                "topic": topic.strip(),
                "model": model,
                "do_compress": do_compress,
            }
            with st.spinner("Planning + writing..."):
                st.session_state.result = run_agent(
                    st.session_state.run_params["topic"],
                    model=st.session_state.run_params["model"],
                    do_compress=st.session_state.run_params["do_compress"],
                )

    with colB:
        if st.button("Weekly trending topic", use_container_width=True):
            st.session_state.run_params = {
                "mode": "trend",
                "model": model,
                "do_compress": do_compress,
            }
            with st.spinner("Finding trending topic + writing..."):
                st.session_state.result = run_weekly_trend_to_post(
                    model=st.session_state.run_params["model"],
                    do_compress=st.session_state.run_params["do_compress"],
                )

    if st.session_state.result:
        res = st.session_state.result
        if not res["ok"]:
            st.error(res.get("error", "Unknown error"))
            if res.get("raw"):
                st.code(res["raw"])
        else:
            st.subheader("Post Draft")
            st.text_area("Copy this into LinkedIn", value=res["post"], height=320)
            st.download_button(
                "Download post as .txt",
                data=res["post"],
                file_name="linkedin_post.txt",
                use_container_width=True,
            )

            # If this run came from trend agent, show the selected trend topic + sources
            if res.get("trend"):
                t = res["trend"]
                chosen = t.get("chosen", {})
                selection = t.get("selection", {})
                frame = selection.get("teaching_frame", {})

                with st.expander("Why this topic (value-first trend agent)"):
                    st.write(f"**Chosen topic:** {chosen.get('representative_title')}")
                    st.write(f"**Cluster size:** {chosen.get('cluster_size')}")
                    st.write(f"**Sources:** {', '.join(chosen.get('sources', []))}")

                    if chosen.get("common_terms"):
                        st.write(f"**Common terms:** {', '.join(chosen.get('common_terms', [])[:10])}")

                    why_value = selection.get("why_value", [])
                    if why_value:
                        st.write("**Why this adds value:**")
                        for b in why_value:
                            st.write(f"- {b}")

                    if frame:
                        st.write("**Teaching frame:**")
                        st.write(f"- Concept: {frame.get('concept')}")
                        st.write(f"- Misconception: {frame.get('common_misconception')}")
                        st.write(f"- Example idea: {frame.get('practical_example_idea')}")
                        st.write(f"- Takeaway: {frame.get('takeaway')}")

                    links = chosen.get("links", [])
                    if links:
                        st.write("**Links:**")
                        for link in links[:6]:
                            st.write(f"- {link}")

with col2:
    if st.session_state.result and st.session_state.result.get("ok"):
        plan = st.session_state.result["plan"]

        st.subheader("Hooks")
        for h in plan["hook_options"]:
            st.write(f"- {h}")

        st.subheader("Angles")
        for a in plan["angles"]:
            st.write(f"- {a}")
        st.info(f"**Chosen angle:** {plan['best_angle']}")

        with st.expander("Outline (agent plan)"):
            for b in plan["outline"]:
                st.write(f"- {b}")

st.divider()
if st.session_state.result and st.session_state.result.get("ok"):
    meta = st.session_state.result.get("meta", {})
    st.caption(
        f"Requested: {meta.get('requested_model')} | "
        f"Used(plan): {meta.get('plan_used_model')} | "
        f"Used(write): {meta.get('write_used_model')} | "
        f"Used(compress): {meta.get('compress_used_model')}"
    )

st.header("Feedback (helps the agent learn)")

colf1, colf2, colf3 = st.columns(3)
with colf1:
    hook_rating = st.slider("Hook quality", 1, 5, 4)
with colf2:
    clarity = st.slider("Clarity for juniors", 1, 5, 4)
with colf3:
    too_long = st.selectbox("Length", ["Just right", "Too long", "Too short"], index=0)

notes = st.text_input("Notes (optional)", placeholder="e.g., more concrete example, less formal, add Urban Pulse reference")

if st.button("Save feedback", use_container_width=True):
    try:
        add_feedback(
            {
                "hook_rating": hook_rating,
                "clarity": clarity,
                "length": too_long,
                "notes": notes.strip() or None,
            }
        )
        st.success("Saved feedback to agent_memory.json ✅")
    except Exception as e:
        st.error(str(e))