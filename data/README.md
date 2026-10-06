# Syllabus Knowledge Base Data

This directory stores textbook chapters and syllabus reference materials used by the **Adaptive Study Tutor** RAG pipeline.

## Sample NCERT Chapters Included
The system is pre-bundled with curriculum-accurate chapter texts based on official NCERT textbooks:
1. **Force and Laws of Motion** (`ncert_class9_ch9_force_and_laws_of_motion.txt`):
   - NCERT Class 9 Science, Chapter 9.
   - Covers: Balanced and Unbalanced Forces, Newton's First Law of Motion, Inertia and Mass, Second Law ($F = ma$), Momentum, Newton's Third Law (Action-Reaction pairs, recoil of gun, swimming, rocket propulsion), and Conservation of Momentum.
2. **Life Processes - Photosynthesis** (`ncert_class10_ch6_life_processes_photosynthesis.txt`):
   - NCERT Class 10 Science, Chapter 6.
   - Covers: Autotrophic Nutrition, Site of Photosynthesis (Chloroplasts, Chlorophyll), Stomata and Guard Cell function, Overall Photosynthesis Equation ($6\text{CO}_2 + 12\text{H}_2\text{O} \to \text{C}_6\text{H}_{12}\text{O}_6 + 6\text{O}_2 + 6\text{H}_2\text{O}$), and Events during Photosynthesis (Absorption, Conversion, Splitting of Water, Reduction of $\text{CO}_2$).

## How to Ingest Official NCERT PDF Files
You can also download original PDFs directly from the official NCERT portal:
1. Visit: [https://ncert.nic.in/textbook.php](https://ncert.nic.in/textbook.php)
2. Select Class (e.g., Class IX or Class X), Subject (Science), and Book Title (*Science*).
3. Download Chapter 9 (`iesc109.pdf`) or Chapter 6 (`jesc106.pdf`).
4. Drop any `.pdf` files into `data/syllabus/`.
5. Run the ingestion command:
   ```bash
   python -m rag.ingest
   ```
   Or simply run `setup.bat`.

The ingestion script automatically parses both `.pdf` (via `pypdf`) and `.txt` files, extracts page numbers and chapters, chunks text into 800-1000 character windows with 150-character overlap, generates dense embeddings, and stores them in `data/vector_store/`.
