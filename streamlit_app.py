import streamlit as st
import pdfplumber
import re
from io import BytesIO
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

def extract_pdf_data(pdf_file):
    """Extract data from the uploaded PDF file."""
    with pdfplumber.open(pdf_file) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"

    # Parse the text to extract relevant information
    data = {
        "name": re.search(r"^(.*?)\n", text).group(1).strip(),
        "personal_details": {
            "jobs": re.search(r"Jobs:\s*(.*?)\n", text).group(1) if re.search(r"Jobs:\s*(.*?)\n", text) else "",
            "colleges": re.search(r"Colleges:\s*(.*?)\n", text).group(1) if re.search(r"Colleges:\s*(.*?)\n", text) else "",
            "emails": re.search(r"Emails:\s*(.*?)\n", text).group(1) if re.search(r"Emails:\s*(.*?)\n", text) else "",
            "locations": re.search(r"Locations:\s*(.*?)\n", text).group(1) if re.search(r"Locations:\s*(.*?)\n", text) else ""
        },
        "social_profiles": [],
        "no_matches_platforms": [],
        "metrics": {},
        "flagged_posts": []
    }

    # Additional parsing as before, with error handling

    return data

def get_text_positions(pdf_file):
    text_positions = []
    with pdfplumber.open(pdf_file) as pdf:
        for page_number, page in enumerate(pdf.pages):
            for word in page.extract_words():
                text_positions.append({
                    'page_number': page_number,
                    'text': word['text'],
                    'x0': word['x0'],
                    'top': word['top'],
                    'size': 12,  # Assuming default size, adjust if needed
                    'fontname': 'Helvetica'  # Assuming default font, adjust if needed
                })
    return text_positions

def find_text_positions(text_positions, search_text):
    positions = []
    for item in text_positions:
        if item['text'] == search_text:
            positions.append(item)
    return positions

def create_overlay(data, positions):
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=letter)

    for item in positions:
        x = item['x0']
        y = letter[1] - item['top']
        size = item['size']
        fontname = item['fontname']

        c.setFont(fontname, size)
        c.setFillColorRGB(1, 1, 1)
        c.rect(x, y - size, 200, size + 5, fill=1, stroke=0)  # Adjust rectangle dimensions
        c.setFillColorRGB(0, 0, 0)
        c.drawString(x, y, data)

    c.save()
    packet.seek(0)
    return packet

def merge_pdfs(original_pdf_stream, overlay_pdf_stream):
    original_pdf = PdfReader(original_pdf_stream)
    overlay_pdf = PdfReader(overlay_pdf_stream)

    writer = PdfWriter()

    for page_num in range(len(original_pdf.pages)):
        original_page = original_pdf.pages[page_num]

        if page_num < len(overlay_pdf.pages):
            overlay_page = overlay_pdf.pages[page_num]
            original_page.merge_page(overlay_page)

        writer.add_page(original_page)

    output_stream = BytesIO()
    writer.write(output_stream)
    output_stream.seek(0)
    return output_stream

def generate_pdf(data, original_pdf_stream):
    # Step 1: Extract text positions
    text_positions = get_text_positions(original_pdf_stream)

    # Step 2: Find positions to update
    name_positions = find_text_positions(text_positions, 'Original Name')

    # Step 3: Create overlay PDF with new content
    overlay_stream = create_overlay(data['name'], name_positions)

    # Step 4: Merge overlay with original PDF
    updated_pdf_stream = merge_pdfs(original_pdf_stream, overlay_stream)

    return updated_pdf_stream

def main():
    st.set_page_config(page_title="PDF Report Editor", layout="wide")
    st.title("PDF Report Editor")

    if "data" not in st.session_state:
        st.session_state.data = None

    uploaded_file = st.file_uploader("Upload PDF Report", type="pdf")

    if uploaded_file:
        if st.session_state.data is None:
            st.session_state.data = extract_pdf_data(uploaded_file)

        st.subheader("Basic Information")
        st.session_state.data["name"] = st.text_input("Name", st.session_state.data["name"])

        if st.button("Generate Updated PDF"):
            pdf_buffer = generate_pdf(st.session_state.data, uploaded_file)
            st.download_button(
                label="Download Updated PDF",
                data=pdf_buffer,
                file_name="updated_report.pdf",
                mime="application/pdf"
            )

if __name__ == "__main__":
    main()
