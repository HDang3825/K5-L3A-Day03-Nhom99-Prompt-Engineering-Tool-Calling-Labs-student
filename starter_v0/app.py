from __future__ import annotations

import os
import socket
import uuid
from datetime import datetime
from typing import Any

import streamlit as st

from chat import ROOT, json_text, now_iso, run_model_tool_loop, trim_history, write_transcript
from env_loader import load_lab_env
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import artifact_version_dict, build_artifact_version


PROVIDERS = {
    "OpenRouter": ("openrouter", "OPENROUTER_API_KEY"),
    "OpenAI": ("openai", "OPENAI_API_KEY"),
    "Anthropic": ("anthropic", "ANTHROPIC_API_KEY"),
    "Gemini": ("gemini", "GEMINI_API_KEY"),
    "Ollama · local model": ("ollama", None),
}
ARTIFACTS_DIR = ROOT / "artifacts"
TRANSCRIPTS_DIR = ROOT / "transcripts"
TOOL_CREDENTIALS = (
    ("Tavily · web search", "TAVILY_API_KEY"),
    ("Firecrawl · page fetch", "FIRECRAWL_API_KEY"),
    ("RapidAPI · social search", "RAPIDAPI_KEY"),
    ("Telegram · send action", "TELEGRAM_BOT_TOKEN"),
)
SUGGESTED_PROMPTS = (
    ("Tìm tin AI mới", "Tìm 3 tin AI nổi bật trong tuần này và tóm tắt bằng tiếng Việt."),
    ("Tìm paper về RAG", "Tìm 3 bài báo arXiv mới về retrieval augmented generation."),
    ("Tra cứu policy", "Tóm tắt chính sách dữ liệu cá nhân nội bộ và nêu nguồn."),
)


def ollama_available() -> bool:
    try:
        with socket.create_connection(("127.0.0.1", 11434), timeout=0.4):
            return True
    except OSError:
        return False


def provider_ready(provider_label: str) -> bool:
    _, key_name = PROVIDERS[provider_label]
    if key_name is None:
        return ollama_available()
    return bool(os.getenv(key_name, "").strip())


def new_transcript(provider_name: str, model: str, version: str) -> dict[str, Any]:
    prompt_path = ARTIFACTS_DIR / "system_prompt.md"
    tools_path = ARTIFACTS_DIR / "tools.yaml"
    artifact_version = build_artifact_version(version, prompt_path, tools_path)
    return {
        "transcript_id": f"{version}_{provider_name}_{datetime.now().strftime('%Y%m%dT%H%M%S')}_{uuid.uuid4().hex[:8]}",
        **artifact_version_dict(artifact_version),
        "provider": provider_name,
        "model": model,
        "system_prompt": str(prompt_path),
        "tools": str(tools_path),
        "history_window": 5,
        "max_tool_rounds": 4,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "turns": [],
    }


load_lab_env(ROOT)
st.set_page_config(page_title="Research Agent", page_icon="⌘", layout="wide")
st.markdown(
    """
    <style>
      :root { color-scheme: dark; }
      .stApp { background:#1b1b1b; color:#ececec; }
      [data-testid="stHeader"] { background:rgba(27,27,27,.96); }
      [data-testid="stSidebar"] { background:#141414; border-right:1px solid #292929; }
      [data-testid="stSidebar"] > div:first-child { padding-top:1rem; }
      .block-container { max-width:900px; padding-top:1.15rem; padding-bottom:2rem; }
      h1,h2,h3 { color:#f0f0f0; letter-spacing:-.025em; }
      p, label, .stCaption { color:#b4b4b4; }
      .brand { display:flex; gap:.65rem; align-items:center; color:#f1f1f1; font-size:1.02rem; font-weight:680; margin:.2rem 0 1.25rem; }
      .brand-icon { display:inline-flex; align-items:center; justify-content:center; width:1.85rem; height:1.85rem; border-radius:9px; background:#262626; color:#f4f4f4; font-size:1.05rem; }
      .side-label { color:#858585; font-size:.73rem; font-weight:720; letter-spacing:.09em; text-transform:uppercase; margin:1.35rem 0 .45rem; }
      .topline { display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #303030; padding:.15rem 0 .8rem; margin-bottom:1.2rem; color:#b8b8b8; font-size:.84rem; }
      .workspace-title { color:#e8e8e8; font-weight:650; }
      .welcome { text-align:center; padding:9vh 0 2rem; }
      .welcome h1 { font-size:2rem; font-weight:620; margin-bottom:.45rem; }
      .welcome p { color:#a5a5a5; margin:0; font-size:.96rem; }
      .stButton > button { border-radius:10px; border:1px solid #383838; background:#242424; color:#e7e7e7; font-weight:520; min-height:2.5rem; }
      .stButton > button:hover { border-color:#656565; background:#2d2d2d; color:#fff; }
      [data-testid="stChatMessage"] { padding:.45rem .4rem; border:0; background:transparent; }
      [data-testid="stChatInput"] { border:1px solid #424242; border-radius:18px; background:#252525; }
      [data-testid="stChatInput"] textarea { color:#ededed; }
      [data-testid="stExpander"] { border:1px solid #373737; border-radius:10px; background:#202020; }
      div[data-baseweb="select"] > div, div[data-baseweb="input"] > div { background:#202020; border-color:#414141; }
      [data-testid="stDialog"] { background:#1f1f1f; }
      [data-testid="stDialog"] [data-testid="stVerticalBlock"] { gap:.75rem; }
      .muted { color:#858585; font-size:.78rem; }
      .stAlert { border-radius:10px; }
    </style>
    """,
    unsafe_allow_html=True,
)

try:
    declarations = load_tool_declarations(ARTIFACTS_DIR / "tools.yaml")
except Exception as exc:
    st.error(f"Không đọc được danh sách tool: {type(exc).__name__}: {exc}")
    st.stop()

st.session_state.setdefault("config_provider", "OpenRouter")
st.session_state.setdefault("config_version", "v0")
initial_provider_name = PROVIDERS[st.session_state.config_provider][0]
initial_provider = make_provider(initial_provider_name)
initial_model = getattr(initial_provider, "default_model", "")
if st.session_state.get("config_model_provider") != initial_provider_name:
    st.session_state.config_model_provider = initial_provider_name
    st.session_state.config_model = initial_model


@st.dialog("Cấu hình agent", width="large")
def show_config() -> None:
    provider_label = st.selectbox("Model provider", list(PROVIDERS), key="config_provider")
    provider_name, key_name = PROVIDERS[provider_label]
    provider = make_provider(provider_name)
    default_model = getattr(provider, "default_model", "")
    if st.session_state.get("config_model_provider") != provider_name:
        st.session_state.config_model_provider = provider_name
        st.session_state.config_model = default_model
    model = st.text_input("Model", key="config_model", help="Có thể giữ model mặc định của provider.").strip() or default_model
    st.text_input("Phiên bản prompt/tools", key="config_version", help="Ví dụ: v0, v1, v2.")

    tab_connection, tab_tools, tab_declarations = st.tabs(["Kết nối", "Dịch vụ", "Tool agent"])
    with tab_connection:
        configured = provider_ready(provider_label)
        if configured:
            st.success("Thông tin xác thực đã có. Chạy kiểm tra để xác nhận provider phản hồi.")
        elif key_name:
            st.warning(f"Chưa có `{key_name}` trong file `.env`.")
            st.caption("Thêm key vào `.env`, rồi tải lại ứng dụng. Giá trị key không hiển thị ở đây.")
        else:
            st.warning("Ollama chưa hoạt động tại localhost:11434.")

        connection_key = (provider_name, model)
        if st.session_state.get("connection_config") != connection_key:
            st.session_state.connection_config = connection_key
            st.session_state.connection_result = None
        if st.button("Thử kết nối model", key="test_provider", disabled=not configured):
            try:
                with st.spinner("Đang kiểm tra provider..."):
                    check = provider.complete(
                        [
                            {"role": "system", "content": "Connection check. Reply with exactly CONNECTED."},
                            {"role": "user", "content": "Confirm the connection."},
                        ],
                        tools=[],
                        model=model,
                        temperature=0.0,
                    )
                st.session_state.connection_result = "ok" if check.text else "empty"
            except Exception as exc:
                st.session_state.connection_result = f"error:{type(exc).__name__}"

        result = st.session_state.get("connection_result")
        if result == "ok":
            st.success("Model đã phản hồi.")
        elif result == "empty":
            st.warning("Provider trả về phản hồi rỗng.")
        elif isinstance(result, str) and result.startswith("error:"):
            st.error(f"Kết nối lỗi: {result.removeprefix('error:')}")
        st.caption("Key được đọc từ `starter_v0/.env` và không hiển thị trong giao diện.")

    with tab_tools:
        st.caption("Tình trạng các dịch vụ ngoài được kiểm tra tại thời điểm mở cấu hình.")
        for label, env_name in TOOL_CREDENTIALS:
            configured = bool(os.getenv(env_name, "").strip())
            st.write(f"{'🟢' if configured else '⚪'} **{label}** · {'Đã cấu hình' if configured else 'Chưa cấu hình'}")
        st.caption("Policy, format, clarify và arXiv không cần API key dịch vụ riêng.")

    with tab_declarations:
        st.caption(f"Agent hiện có {len(declarations)} tool từ `artifacts/tools.yaml`.")
        for declaration in declarations:
            function = declaration.get("function", declaration)
            with st.expander(str(function.get("name", "tool"))):
                st.write(function.get("description", "Chưa có mô tả."))


def start_new_chat() -> None:
    for key in ("history", "transcript", "session_config"):
        st.session_state.pop(key, None)


with st.sidebar:
    st.markdown('<div class="brand"><span class="brand-icon">⌘</span><span>Research Agent</span></div>', unsafe_allow_html=True)
    if st.button("＋  Cuộc trò chuyện mới", use_container_width=True, key="new_chat"):
        start_new_chat()
        st.rerun()
    st.markdown('<div class="side-label">Cuộc trò chuyện</div>', unsafe_allow_html=True)
    st.button("◉  Phiên hiện tại", use_container_width=True, disabled=True, key="current_chat")
    st.markdown('<div style="height:48vh"></div>', unsafe_allow_html=True)
    if st.button("⚙  Cấu hình", use_container_width=True, key="open_config"):
        show_config()

provider_label = st.session_state.config_provider
provider_name, _ = PROVIDERS[provider_label]
provider = make_provider(provider_name)
default_model = getattr(provider, "default_model", "")
model = st.session_state.config_model.strip() or default_model
version = st.session_state.config_version.strip() or "v0"
session_config = (provider_name, model, version)
if st.session_state.get("session_config") != session_config:
    st.session_state.history = []
    st.session_state.transcript = new_transcript(provider_name, model, version)
    st.session_state.session_config = session_config

st.markdown(
    f'<div class="topline"><span class="workspace-title">Research Agent</span><span>{version}</span></div>',
    unsafe_allow_html=True,
)

if not st.session_state.history:
    st.markdown(
        '<div class="welcome"><h1>Bạn muốn nghiên cứu điều gì?</h1><p>Đặt câu hỏi để agent chọn tool, thu thập thông tin và lưu lại bằng chứng.</p></div>',
        unsafe_allow_html=True,
    )
    sample_cols = st.columns(3)
    for index, (title, sample) in enumerate(SUGGESTED_PROMPTS):
        with sample_cols[index]:
            if st.button(title, key=f"sample_{index}", use_container_width=True):
                st.session_state.pending_prompt = sample
                st.rerun()

for message in st.session_state.history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

submitted = st.chat_input("Nhắn Research Agent…")
prompt = submitted or st.session_state.pop("pending_prompt", None)
if prompt:
    st.session_state.history.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    turn_record: dict[str, Any] = {
        "turn_index": len(st.session_state.transcript["turns"]) + 1,
        "started_at": now_iso(),
        "user": prompt,
        "status": "started",
        "assistant_text": None,
        "rounds": [],
        "tool_events": [],
    }
    with st.chat_message("assistant"):
        try:
            system_prompt = (ARTIFACTS_DIR / "system_prompt.md").read_text(encoding="utf-8")
            messages = [
                {"role": "system", "content": system_prompt},
                *trim_history(st.session_state.history[:-1], 5),
                {"role": "user", "content": prompt},
            ]
            with st.spinner("Agent đang xử lý..."):
                result = run_model_tool_loop(
                    provider=provider,
                    messages=messages,
                    tools=to_openai_tools(declarations),
                    model=model,
                    max_tool_rounds=4,
                )
            turn_record.update(result)
            answer = result.get("assistant_text") or "Agent không trả về nội dung văn bản."
            st.markdown(answer)
            if result.get("tool_events"):
                with st.expander(f"Bằng chứng tool · {len(result['tool_events'])} lượt gọi"):
                    for event in result["tool_events"]:
                        st.markdown(f"**{event.get('tool', 'tool')}**")
                        st.json(event)
            st.session_state.history.append({"role": "assistant", "content": answer})
        except Exception as exc:
            error_text = f"{type(exc).__name__}: {exc}"
            turn_record.update({"status": "provider_error", "error": error_text})
            st.error(error_text)
            st.session_state.history.append({"role": "assistant", "content": f"Lỗi kết nối: {error_text}"})

    turn_record["ended_at"] = now_iso()
    st.session_state.transcript["turns"].append(turn_record)
    transcript_path = TRANSCRIPTS_DIR / f"{st.session_state.transcript['transcript_id']}.transcript.json"
    write_transcript(transcript_path, st.session_state.transcript)
    st.rerun()
