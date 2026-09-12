# Hệ Thống AI Research Agent Đa Tác Nhân

Hệ thống web tự động hóa toàn bộ quy trình nghiên cứu học thuật: từ một chủ đề đầu vào, hệ thống lập kế hoạch, tìm kiếm web, đánh giá độ tin cậy nguồn, tổng hợp nội dung có trích dẫn bằng RAG và tạo báo cáo hoàn chỉnh theo thời gian thực.

---

## Tiến Độ Thực Hiện

| Giai đoạn | Nội dung | Deadline | Trạng thái |
|:---------:|----------|----------|:----------:|
| **CP1** | Đăng ký đề tài | 04/09/2026 | ✅ Hoàn thành |
| **CP2** | Phân tích yêu cầu & thiết kế tổng quan | 12/09/2026 | ✅ Hoàn thành |
| **CP3** | Thiết kế chi tiết & xây dựng pipeline | 19/09/2026 | 🔄 Đang làm |
| **CP4** | Triển khai & tích hợp hệ thống | 26/09/2026 | ⏳ Chưa làm |
| **CP5** | Kiểm thử & đánh giá | 03/10/2026 | ⏳ Chưa làm |
| **CP6** | Báo cáo & demo sản phẩm | 10/10/2026 | ⏳ Chưa làm |

---

## Kiến Trúc Pipeline

```
Người dùng nhập chủ đề
        │
        ▼
┌──────────────┐
│   PLANNER    │  Phân tích chủ đề → tạo 3-5 câu hỏi nghiên cứu
│    AGENT     │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│   SEARCH &   │  Tìm kiếm qua Tavily API → thu thập nội dung 15 nguồn
│  SCRAPER     │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ CREDIBILITY  │  Chấm điểm 4 tiêu chí → lọc nguồn đáng tin cậy (≥ 5.0/10)
│  EVALUATOR   │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  SYNTHESIS   │  ChromaDB indexing + semantic retrieval + tổng hợp có trích dẫn
│  AGENT (RAG) │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│    REPORT    │  Tạo báo cáo học thuật hoàn chỉnh (Markdown + DOCX)
│    WRITER    │
└──────────────┘
        │
        ▼
  Streaming SSE → Giao diện Next.js hiển thị thời gian thực
```

---

## Công Nghệ Sử Dụng

| Tầng | Công nghệ |
|------|-----------|
| Điều phối pipeline | LangGraph (StateGraph + ResearchState TypedDict) |
| Mô hình ngôn ngữ | NVIDIA NIM API — llama-3.3-70b-instruct, llama-3.2-11b-vision-instruct |
| Tìm kiếm web | Tavily Search API |
| Vector store | ChromaDB (SQLite backend) + ONNX DefaultEmbeddingFunction |
| Backend | FastAPI + Server-Sent Events (SSE) |
| Frontend | Next.js 14 + TypeScript + Tailwind CSS |
| Tạo file báo cáo | python-docx |

---

## Chạy Thử Cục Bộ

### Yêu cầu

- Python 3.10+
- Node.js 18+
- API key: `NVIDIA_API_KEY`, `TAVILY_API_KEY`

### Backend

```bash
cd backend
pip install -r requirements.txt
python start.py
# Chạy tại http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Chạy tại http://localhost:3000
```

---

## Cấu Trúc Dự Án

```
Agent/
├── backend/
│   ├── app/
│   │   ├── agents/
│   │   │   ├── planner.py          # Lập kế hoạch nghiên cứu
│   │   │   ├── searcher.py         # Tìm kiếm và thu thập nguồn
│   │   │   ├── credibility.py      # Đánh giá độ tin cậy nguồn
│   │   │   ├── synthesizer.py      # Tổng hợp RAG có trích dẫn
│   │   │   └── report_writer.py    # Viết báo cáo hoàn chỉnh
│   │   ├── core/
│   │   │   ├── config.py           # Cấu hình LLM và API
│   │   │   ├── state.py            # ResearchState TypedDict
│   │   │   └── pipeline.py         # LangGraph orchestration
│   │   ├── services/
│   │   │   └── vectorstore.py      # ChromaDB wrapper
│   │   ├── api/routes.py           # FastAPI endpoints + SSE
│   │   └── main.py
│   ├── requirements.txt
│   ├── start.py
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/page.tsx
│   │   └── components/
│   ├── package.json
│   └── Dockerfile
├── docker-compose.yml
└── README.md
```

---

## API

| Endpoint | Method | Mô tả |
|----------|--------|-------|
| `/api/v1/research/stream` | POST | SSE stream tiến trình pipeline |
| `/api/v1/health` | GET | Kiểm tra trạng thái server |

---

## Thông Tin Nhóm

| STT | MSSV | Họ và tên |
|-----|------|-----------|
| 1 | 523100007 | Chu Văn Bình |
| 2 | 523100042 | Nguyễn Khánh Ninh |
| 3 | 523100190 | Nguyễn Đình Vinh |
| 4 | 523100032 | Đoàn Chí Khang |

**Trường:** Đại học Phương Đông — Khoa Công nghệ Số & Truyền thông — Ngành CNTT
