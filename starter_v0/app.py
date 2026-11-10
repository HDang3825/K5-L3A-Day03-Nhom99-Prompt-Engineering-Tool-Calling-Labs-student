from __future__ import annotations

import json
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
RUNS_DIR = ROOT / "runs"
TOOL_CREDENTIALS = (
    ("Tavily · web search", "TAVILY_API_KEY"),
    ("Firecrawl · page fetch", "FIRECRAWL_API_KEY"),
    ("RapidAPI · social search", "RAPIDAPI_KEY"),
    ("Telegram · send action", "TELEGRAM_BOT_TOKEN"),
)
STREAMLIT_SECRET_KEYS = (
    "OPENROUTER_API_KEY",
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "TAVILY_API_KEY",
    "FIRECRAWL_API_KEY",
    "RAPIDAPI_KEY",
    "RAPIDAPI_TWITTER_HOST",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "ARXIV_USER_AGENT",
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


def load_streamlit_secrets() -> None:
    """Expose Community Cloud secrets to tools that read environment variables."""
    try:
        secrets = st.secrets
        for key in STREAMLIT_SECRET_KEYS:
            value = secrets.get(key)
            if isinstance(value, str) and value.strip():
                os.environ.setdefault(key, value.strip())
    except FileNotFoundError:
        # Local runs may not have a .streamlit/secrets.toml file.
        pass


def read_run_summaries() -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for path in sorted(RUNS_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            version = data.get("version") or path.stem.split("_", 1)[0]
            summary = data.get("summary", {})
            summaries.append({
                "version": str(version),
                "file": path.name,
                "case_accuracy": summary.get("case_accuracy"),
                "tool_routing_accuracy": summary.get("tool_routing_accuracy"),
                "argument_accuracy": summary.get("argument_accuracy"),
                "multiturn_accuracy": summary.get("multiturn_accuracy"),
                "passed_cases": summary.get("passed_cases"),
                "total_cases": summary.get("total_cases"),
            })
        except (OSError, json.JSONDecodeError, TypeError):
            continue
    return summaries


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
load_streamlit_secrets()
st.set_page_config(page_title="Research Agent", page_icon="⌘", layout="wide")
st.markdown(
    """
    <style>
      .stApp { background:var(--background-color); color:var(--text-color); }
      [data-testid="stHeader"] { background:var(--background-color); }
      [data-testid="stSidebar"] { background:var(--secondary-background-color); border-right:1px solid var(--secondary-background-color); }
      [data-testid="stSidebar"] > div:first-child { padding-top:1rem; }
      .block-container { max-width:900px; padding-top:1.15rem; padding-bottom:2rem; }
      h1,h2,h3 { color:var(--text-color); letter-spacing:-.025em; }
      p, label, .stCaption { color:var(--text-color); opacity:.78; }
      .brand { display:flex; gap:.65rem; align-items:center; color:var(--text-color); font-size:1.02rem; font-weight:680; margin:.2rem 0 1.25rem; }
      .brand-icon { display:inline-flex; align-items:center; justify-content:center; width:1.85rem; height:1.85rem; border-radius:9px; background:var(--background-color); border:1px solid var(--secondary-background-color); color:var(--text-color); font-size:1.05rem; }
      .side-label { color:var(--text-color); opacity:.62; font-size:.73rem; font-weight:720; letter-spacing:.09em; text-transform:uppercase; margin:1.35rem 0 .45rem; }
      .topline { display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid var(--secondary-background-color); padding:.15rem 0 .8rem; margin-bottom:1.2rem; color:var(--text-color); opacity:.82; font-size:.84rem; }
      .workspace-title { color:var(--text-color); font-weight:650; opacity:1; }
      .welcome { text-align:center; padding:9vh 0 2rem; }
      .welcome h1 { color:var(--text-color); font-size:2rem; font-weight:620; margin-bottom:.45rem; }
      .welcome p { color:var(--text-color); opacity:.7; margin:0; font-size:.96rem; }
      .stButton > button { border-radius:10px; border:1px solid var(--secondary-background-color); background:var(--secondary-background-color); color:var(--text-color); font-weight:520; min-height:2.5rem; }
      .stButton > button:hover { border-color:var(--primary-color); background:var(--secondary-background-color); color:var(--text-color); }
      [data-testid="stChatMessage"] { padding:.45rem .4rem; border:0; background:transparent; }
      [data-testid="stChatInput"] { border:1px solid var(--secondary-background-color); border-radius:18px; background:var(--secondary-background-color); }
      [data-testid="stChatInput"] textarea { color:var(--text-color); }
      [data-testid="stExpander"] { border:1px solid var(--secondary-background-color); border-radius:10px; background:var(--secondary-background-color); }
      div[data-baseweb="select"] > div, div[data-baseweb="input"] > div { background:var(--secondary-background-color); border-color:var(--secondary-background-color); }
      [data-testid="stDialog"] { background:var(--background-color); color:var(--text-color); }
      [data-testid="stDialog"] [data-testid="stVerticalBlock"] { gap:.75rem; }
      .muted { color:var(--text-color); opacity:.62; font-size:.78rem; }
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
st.session_state.setdefault("agent_processing", False)
st.session_state.setdefault("active_prompt", None)
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

    run_summaries = read_run_summaries()
    selected_version = st.session_state.config_version.strip() or "v0"
    matching_runs = [run for run in run_summaries if run["version"] == selected_version]
    if not matching_runs:
        available_versions = sorted({run["version"] for run in run_summaries})
        available_text = ", ".join(available_versions) if available_versions else "chưa có version nào"
        st.error(
            f"Không tìm thấy run cho version `{selected_version}` trong `runs/`. "
            f"Các version hiện có: {available_text}."
        )

    tab_connection, tab_tools, tab_declarations, tab_runs = st.tabs(["Kết nối", "Dịch vụ", "Tool agent", "Runs"])
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

    with tab_runs:
        if matching_runs:
            st.success(f"Đã tìm thấy {len(matching_runs)} run cho {selected_version}.")
        st.caption("Danh sách này được đọc trực tiếp từ `starter_v0/runs/*.json`.")
        if run_summaries:
            for run in run_summaries:
                accuracy = run["case_accuracy"]
                accuracy_text = f"{accuracy:.0%}" if isinstance(accuracy, (int, float)) else "—"
                with st.expander(f"{run['version']} · {accuracy_text} · {run['file']}"):
                    metric_labels = (
                        ("Độ chính xác tổng", "case_accuracy", True),
                        ("Chọn tool", "tool_routing_accuracy", True),
                        ("Đối số tool", "argument_accuracy", True),
                        ("Đa lượt", "multiturn_accuracy", True),
                        ("Số case đạt", "passed_cases", False),
                        ("Tổng số case", "total_cases", False),
                    )
                    for label, key, is_percentage in metric_labels:
                        value = run[key]
                        if isinstance(value, (int, float)) and is_percentage:
                            value = f"{value:.0%}"
                        elif value is None:
                            value = "—"
                        st.markdown(f"**{label}:** {value}")
        else:
            st.caption("Thư mục `runs/` chưa có file JSON nào.")


def start_new_chat() -> None:
    for key in ("history", "transcript", "session_config", "active_prompt"):
        st.session_state.pop(key, None)
    st.session_state.agent_processing = False


with st.sidebar:
    st.markdown('<div class="brand"><span class="brand-icon">⌘</span><span>Research Agent</span></div>', unsafe_allow_html=True)
    busy = st.session_state.agent_processing
    if st.button("＋  Cuộc trò chuyện mới", use_container_width=True, key="new_chat", disabled=busy):
        start_new_chat()
        st.rerun()
    st.markdown('<div class="side-label">Cuộc trò chuyện</div>', unsafe_allow_html=True)
    st.button("◉  Phiên hiện tại", use_container_width=True, disabled=True, key="current_chat")
    st.markdown('<div style="height:48vh"></div>', unsafe_allow_html=True)
    if st.button("⚙  Cấu hình", use_container_width=True, key="open_config", disabled=busy):
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
            if st.button(title, key=f"sample_{index}", use_container_width=True, disabled=st.session_state.agent_processing):
                st.session_state.active_prompt = sample
                st.session_state.agent_processing = True
                st.rerun()

for message in st.session_state.history:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

busy = st.session_state.agent_processing
submitted = st.chat_input(
    "Agent đang trả lời, chờ xong để hỏi tiếp…" if busy else "Nhắn Research Agent…",
    disabled=busy,
    submit_mode="disable",
)
if submitted and not busy:
    st.session_state.active_prompt = submitted
    st.session_state.agent_processing = True
    st.rerun()

prompt = st.session_state.active_prompt if st.session_state.agent_processing else None
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
    try:
        write_transcript(transcript_path, st.session_state.transcript)
    except Exception as exc:
        st.error(f"Không lưu được transcript: {type(exc).__name__}: {exc}")
    st.session_state.active_prompt = None
    st.session_state.agent_processing = False
    st.rerun()
