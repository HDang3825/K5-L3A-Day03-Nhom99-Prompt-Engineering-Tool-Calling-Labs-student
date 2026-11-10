# Day 03 Lab v2 Report — Research Agent

> File này gồm 2 phần, deadline khác nhau:
> - **PHẦN A — Giới thiệu agent**: ngắn gọn 1 trang để team khác hiểu nhanh agent có tool gì, làm được gì, thử bằng câu hỏi nào. **Xong trước 16:30** để làm tài liệu phụ trợ khi demo. Có thể làm thành poster HTML/SVG (`artifacts/poster.html` / `poster.svg`) để show cho team cùng zone.
> - **PHẦN B — Chi tiết / Bằng chứng**: bảng đầy đủ (v0–v3, failure, eval, chat) dựa trên log thật. **Có thể hoàn thiện sau buổi debate để nộp bài.**

## Team

- Team: Nhom99
- Members:
- Provider/model:

---

# PHẦN A — Giới thiệu agent

## A1. Agent này làm được gì

> Agent này là một trợ lý nghiên cứu toàn diện: chuyên tra cứu tin tức web, mạng xã hội, tài liệu nội bộ và học thuật, đọc nội dung URL, sau đó tổng hợp thành bản tin định dạng chuẩn. Hệ thống vận hành an toàn bằng cách chủ động hỏi người dùng khi thiếu dữ kiện và luôn yêu cầu xác nhận trước khi gửi bản tin lên Telegram.

Ví dụ: "Research agent: tìm tin theo từ khóa / theo tài khoản, đọc URL, tổng hợp thành digest, và gửi lên Telegram khi được xác nhận."

**Link dùng thử (deploy):**

> Dán link public để team khác mở thử ngay. Cách deploy nhanh bằng Cloudflare Tunnel xem README. Nếu deploy Vercel/Streamlit Cloud thì dán link đó.
>
> URL: 

## A2. Tool agent có

> Liệt kê các tool agent đang dùng (gồm tool mới nhóm tự thêm). Mỗi tool 1 dòng: tên + làm được gì.

| Tên tool | Làm được gì | Tool mới nhóm thêm? |
|---|---|---|
| clarify | hỏi lại người dùng khi thiếu thông tin | không |
| timeline |lấy bài đăng gần đây của một tài khoản|không  |
| social_search |tìm bài đăng theo từ khóa| không |
| lookup |tìm trên web| không |
| fetch |đọc nội dung một URL| không |
|format|trình bày các item đã có thành markdown digest| không |
|dedupe|Lọc bỏ các kết quả bị trùng lặp URL trước khi đưa vào format.|có|

## A3. Câu hỏi mẫu để thử

> 3–5 câu hỏi/yêu cầu mẫu để team khác tự thử agent ngay.

1.
2.
3.

---

# PHẦN B — Chi tiết / Bằng chứng

## B1. Version Evidence

Fill from `artifacts/version_log.csv` and `runs/*.json`.

| Version | Changed Artifact | Hypothesis | Metric Before | Metric After | Run File |
|:---:|:---|:---|:---:|:---:|:---|
| v0 | baseline | Initial baseline eval on raw starter kit | N/A | 0.70 | `runs/v0_B_base_openrouter_20261110T101611818393.json` |
| v1 | `artifacts/system_prompt.md` | Removing guessing prompts and requiring clarify for missing info will eliminate missing_info failures | 0.70 | 0.75 | `runs/v1_B_base_openrouter_20261110T105244505939.json` |
| v2 | `artifacts/tools.yaml` | Adding parameter conventions in tools.yaml eliminates wrong_arg_value errors | 0.75 | 0.90 | `runs/v2_B_base_openrouter_20261110T111137230831.json` |
| v3 | `artifacts/system_prompt.md` | Adding yes_no confirmation rule, parallel tool calling, and explicit numeric limits extraction fixes R12, R13, and argument omission | 0.90 | 0.95 | `runs/v3_B_base_openrouter_20261110T121304873083.json` |
| v4 | `artifacts/tools.yaml` | Refining parameter description and multi-turn constraints in tools.yaml achieves full argument accuracy | 0.95 | 1.00 | `runs/v4_B_base_openrouter_20261110T121900213141.json` |

## B2. Failure Analysis

Use actual failures from `results[*].result.failures`.

| Case ID | Failure Type | Actual Tool Calls | What Failed | Fix |
|:---|:---|:---|:---|:---|
| R10_missing_handle | missing_info | `timeline(screenname="SamAltman")` | Agent tự suy đoán bừa tài khoản SamAltman khi đề bài không cho handle do prompt ban đầu xúi đoán. | Loại bỏ chỉ dẫn xúi đoán mò trong `system_prompt.md`, thêm luật bắt buộc gọi `clarify` khi thiếu tên tài khoản / URL. |
| R03_web_news_routing | wrong_arg_value | `lookup(query="AI news", topic="news")` | Query bị thừa chữ "news" ("AI news") dù đã có `topic="news"` và `timeframe="day"`. | Viết lại mô tả tham số `query` trong `tools.yaml`, quy ước cấm chèn các từ "news", "tin tức", "today" vào query khi đã chọn topic/timeframe. |
| R12_confirm_before_send | wrong_boundary | `clarify(response_type="text")` | Khi người dùng yêu cầu gửi/đăng bài, agent hỏi xin nội dung (dạng text) thay vì hỏi xin xác nhận Có/Không. | Thêm quy tắc Destructive Action trong `system_prompt.md`, bắt buộc gọi `clarify` với `response_type="yes_no"` khi cần user xác nhận gửi tin. |
| R13_parallel_web_and_tweets | wrong_tool | Chỉ gọi mỗi `lookup` | Người dùng yêu cầu tra cứu cả tin tức web lẫn mạng xã hội nhưng agent chỉ gọi 1 tool, bỏ sót `social_search`. | Bổ sung quy tắc Parallel Tool Calling trong `system_prompt.md`, hướng dẫn gọi đồng thời cả `lookup` và `social_search` trong cùng một lượt. |
| M03_correction_handle | wrong_arg_value | `timeline(screenname="karpathy")` (thiếu `limit`) | Model bị trôi ngữ cảnh (context drift) qua 3 lượt thoại, ỷ lại vào `default: 5` nên bỏ quên cập nhật `limit=3` ở lượt cuối. | Bổ sung quy tắc Numeric Limits trong prompt và nhấn mạnh ràng buộc bắt buộc truyền `limit` trong `tools.yaml` khi người dùng chỉ định số lượng. |

## B3. Team Eval Cases

List the 10 cases added to `data/eval_group.json` (5 single turn + 5 multi turn).

| Case ID | What It Tests | Expected Tool/Behavior | Result |
|---|---|---|---|
|  |  |  |  |

## B4. Live Chat Evidence

Use `transcripts/*.transcript.json`.

| Turn | User Request | Tool Calls | Version Evidence | Outcome |
|---|---|---|---|---|
|  |  |  |  |  |

## B5. Bonus Evidence

Only fill if your team did bonus.

| Bonus | Evidence File | What Worked | Risk / Guardrail |
|---|---|---|---|
| send (Telegram) |  |  |  |
| arXiv/company policy |  |  |  |
| UI |  |  |  |
| Tool unit tests (`tests/`) | `pytest` output |  |  |

Tool unit tests: số test đã viết, số bug tìm được trong tool có sẵn (nếu có), và một ví dụ lỗi mà unit test bắt được nhưng eval không bắt được.

## B6. Reflection

- **Which fixes belonged in `system_prompt.md`?**
  - Các quy tắc định hướng hành vi cấp cao (high-level behavior policy):
    1. *Chính sách xử lý thiếu thông tin:* Cấm tự ý suy đoán, bắt buộc phải gọi tool `clarify` khi thiếu các tham số quan trọng như account handle hoặc URL.
    2. *Ranh giới an toàn (Guardrails / Destructive actions):* Cấm tự ý thực thi hành động gửi tin/đăng bài (`send`) khi chưa có sự xác nhận từ người dùng; bắt buộc dùng `clarify(response_type="yes_no")` để hỏi xin xác nhận Có/Không.
    3. *Quy tắc gọi song song (Parallel Tool Calling):* Hướng dẫn agent gọi đồng thời nhiều tool phù hợp (`lookup` và `social_search`) khi câu hỏi yêu cầu dữ liệu từ nhiều nguồn khác nhau.

- **Which fixes belonged in `tools.yaml`?**
  - Các quy ước tham số kỹ thuật cụ thể (Argument Conventions & Schemas):
    1. *Định dạng định danh:* Quy ước `screenname` phải viết liền chữ thường, không chứa khoảng trắng hay ký tự `@`.
    2. *Lọc từ khóa lõi:* Quy ước `query` trong `lookup` chỉ chứa thực thể tìm kiếm cốt lõi, cấm ghép các từ thừa như "news", "tin tức", "today" khi đã có `topic="news"` và `timeframe`.
    3. *Ràng buộc kiểu dữ liệu:* Giải thích rõ ràng mục đích của `response_type` (`yes_no` vs `text`), và nhấn mạnh việc bắt buộc trích xuất giá trị `limit` từ yêu cầu người dùng thay vì ỷ lại vào giá trị `default`.

- **Which failure needed manual review instead of automatic grading?**
  - Case `R12_confirm_before_send`: Khi chạy tự động, eval kiểm tra đối số `response_type: "yes_no"`. Thực tế model đã có ý thức an toàn dừng lại hỏi người dùng qua `clarify`, nhưng do truyền `response_type="text"` (hỏi xin nội dung bản tin) nên hệ thống tự động chấm FAIL dạng `wrong_boundary`. Nếu không đọc kỹ log `runs/*.json` bằng tay, nhóm sẽ ngộ nhận rằng model vẫn tự ý gọi `send` trái phép, trong khi bản chất model chỉ bị lệch kiểu tham số hỏi lại.

- **What would you improve next?**
  - Bổ sung các ví dụ Few-shot trong System Prompt để nâng cao năng lực theo dõi và tích lũy trạng thái ngữ cảnh qua nhiều lượt đối thoại phức tạp (Multi-turn Context Accumulation).
  - Tích hợp lớp tiền xử lý (pre-validation layer) trực tiếp trong mã nguồn của các tool để tự động chuẩn hóa đối số từ model (như tự động strip `@` khỏi username, tự động drop các từ khóa trùng lặp), giúp hệ thống có khả năng phòng thủ và chịu lỗi (fault-tolerant) cao hơn trước các biến thiên ngẫu nhiên của LLM.

## B7. Small Local Model Challenge (bonus)

Only fill if your team did the local model challenge.

| Version | Model (provider) | Prompt/Tools | case_accuracy | tool_routing | argument | multiturn | Run File |
|---|---|---|---|---|---|---|---|
| v3 | (cloud) | v3 |  |  |  |  |  |
| v3-... | (ollama) | v3 |  |  |  |  |  |
| v3-... | (ollama) | v3 |  |  |  |  |  |
| v4-local |  |  |  |  |  |  |  |
| v5-local |  |  |  |  |  |  |  |

Lỗi đặc thù của model nhỏ (đếm từ run JSON):

| Failure Pattern | Count | Example Case | Fix Tried | Helped? |
|---|---|---|---|---|
| wrong / hallucinated tool |  |  |  |  |
| invalid JSON args (`_invalid_json_arguments`) |  |  |  |  |
| no tool call / answered directly |  |  |  |  |
| missed `clarify` |  |  |  |  |
| repeated / unnecessary calls |  |  |  |  |

- Cái gì giúp model nhỏ gọi tool đúng hơn nhất? Bằng chứng?
- Bản prompt tối ưu cho local chạy trên model cloud thì sao?
- Khi nào nhóm sẽ chọn model local thay vì cloud cho agent này?
