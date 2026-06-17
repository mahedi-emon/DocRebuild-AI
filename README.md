# DocRebuild AI

DocRebuild AI is a production-grade local application designed to reconstruct scanned PDFs, image-based textbooks, NCTB books, and mixed-language documents into highly accurate, editable DOCX files while preserving complex layouts, images, tables, equations, and reading order.

It operates entirely on local hardware, using a multi-model OCR ensemble, deep-learning layout analysis, semantic document understanding, and automated quality assurance pipelines.

---

## Key Features
* **Scanned-to-DOCX Reconstruction**: Not just simple OCR text dumping—rebuilds complete Word documents with custom formatting, headings, alignment, fonts, and inline styles.
* **Bangla, English & Math Support**: Highly optimized for Bangla OCR, mathematical formulas (converts formulas to native Word equations via LaTeX), and mixed-language textbook parsing.
* **100% Local & Privacy-Friendly**: Designed to run entirely on your local laptop (CPU/GPU) without sending any data to external APIs.
* **No Celery/Redis Dependencies**: Rewritten to run directly in-process using Python background threads, making it incredibly easy to start up and run without setting up background task brokers.
* **Optimized Resource Footprint**: Toggles heavy machine learning models on and off via `.env` configuration to run comfortably on laptops with standard CPU/RAM footprints.

---

## Pipeline Flow

1. **PDF Ingestion**: Renders PDF pages to high-resolution images (300 DPI) using PyMuPDF. For image inputs (PNG, JPG), handles them directly.
2. **Layout Analysis**: Detects structural blocks (paragraphs, titles, tables, equations, images) using DocLayout-YOLO with graceful fallback to full-page paragraphs.
3. **OCR Ensemble**: Runs EasyOCR, DocTR, and PaddleOCR and fuses word candidates using weighted majority voting.
4. **Document Understanding**: Extracts semantic markdown hierarchy with Docling & Marker.
5. **Vision Validation**: Cross-checks low-confidence regions using Florence-2.
6. **Table Extraction**: Extracts table cell grids using Microsoft Table Transformer (DETR).
7. **Math Recognition**: Converts equation crops into native LaTeX math using Pix2Tex (LaTeX OCR) which are rendered as native Word equations.
8. **Bangla Validation**: Spell-checks Bengali vocabulary using custom Trie dictionaries.
9. **DOCX Reconstruction**: Assembles OpenXML document sections, applying fonts, spacing, alignment, and inline math.
10. **Quality Assurance**: Compares generated DOCX structure against original layouts to compute accuracy.
11. **Visual Verification**: SSIM-based visual comparison verification.

---

## Project Structure

* `/backend`: FastAPI backend server, OCR wrappers, database schemas, and docx reconstruction logic.
* `/frontend`: React + TypeScript SPA client interface styled with a custom dark-themed glassmorphism CSS system.
* `docker-compose.yml` & `Dockerfile.*`: Containerization templates for full Docker stack deployment.

---

## Local Installation & Setup

### Prerequisites
- Python 3.11+ (Python 3.12+ recommended)
- Node.js 18+ & npm
- Git

---

### Step-by-Step Native Run

#### 1. Setup Backend
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a Python virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```
3. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` in the root workspace directory and adjust model parameters as needed. Note that by default heavy models like Surya, TrOCR, and Florence2 are disabled to fit low-resource laptops.

#### 2. Start the Backend Server
From the `backend` directory:
```bash
python -m app.main
```
The server will start at `http://localhost:8000`. You can access the Interactive Swagger documentation at `http://localhost:8000/docs`.

---

#### 3. Setup & Start the Frontend
1. Open a new terminal and navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install npm packages:
   ```bash
   npm install
   ```
3. Run the Vite client:
   ```bash
   npm run dev
   ```
The client dashboard will start at `http://localhost:5173`. You can upload scanned PDFs or images and watch the 12 pipeline stages process in real-time.

---

## Docker Deployment (Optional)

Alternatively, launch the entire containerized stack using:
```bash
docker-compose up --build
```
This runs the client on port `3000` and the API gateway on port `8000`.
