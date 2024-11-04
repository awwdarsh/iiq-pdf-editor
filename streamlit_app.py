import re
import streamlit as st
import pdfplumber
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PIL import Image
import tempfile
from io import BytesIO

def extract_pdf_data(pdf_file):
    """Extract data from the uploaded PDF file."""
    with pdfplumber.open(pdf_file) as pdf:
        text = "\n".join(page.extract_text() for page in pdf.pages)

    # Parse data using updated regex patterns
    data = {
        "name": re.search(r"^(.*?)\n", text).group(1).strip() if re.search(r"^(.*?)\n", text) else "",
        "personal_details": {
            "jobs": re.search(r"Jobs:\s*(.*?)\n", text).group(1) if re.search(r"Jobs:\s*(.*?)\n", text) else "",
            "colleges": re.search(r"Colleges:\s*(.*?)\n", text).group(1) if re.search(r"Colleges:\s*(.*?)\n", text) else "",
            "emails": re.search(r"Emails:\s*(.*?)\n", text).group(1) if re.search(r"Emails:\s*(.*?)\n", text) else "",
            "locations": re.search(r"Locations:\s*(.*?)\n", text).group(1) if re.search(r"Locations:\s*(.*?)\n", text) else ""
        },
        "social_profiles": [],
        "no_matches_platforms": [],
        "metrics": {
            "platforms_evaluated": 0,
            "flagged_posts": 0,
            "flagged_categories": 0
        },
        "flagged_posts": []
    }

    # Extract metrics
    data["metrics"]["platforms_evaluated"] = int(re.search(r"(\d+)\s*Social platforms evaluated", text).group(1) or 0)
    data["metrics"]["flagged_posts"] = int(re.search(r"(\d+)\s*Total flagged posts", text).group(1) or 0)
    data["metrics"]["flagged_categories"] = len(re.findall(r"potential issues found:", text))

    # Extract social profiles (both usernames and URLs)
    profiles_section = re.search(r"Social media profiles found:\s*(.*?)\n\n", text, re.DOTALL)
    if profiles_section:
        profiles_text = profiles_section.group(1)
        for line in profiles_text.split("\n"):
            if line.startswith("@") or line.startswith("https://"):
                data["social_profiles"].append({"platform": "Unknown", "username": line.strip(), "url": line.strip()})

    # Extract flagged posts with improved date parsing
    flagged_posts = re.findall(r"(.*?)\nPosted on\s*•\s*(\w+ \d{2}, \d{4} \d{2}:\d{2} [AP]M)", text, re.DOTALL)
    for post in flagged_posts:
        data["flagged_posts"].append({
            "content": post[0].strip(),
            "date": post[1].strip(),
            "url": "",
            "include": True,
            "platform": "LinkedIn"
        })

    return data

def get_text_positions(pdf_file):
    """Extract text positions from PDF for precise overlay positioning."""
    text_positions = []
    with pdfplumber.open(pdf_file) as pdf:
        for page_number, page in enumerate(pdf.pages):
            words = page.extract_words()
            for word in words:
                text_positions.append({
                    'page_number': page_number,
                    'text': word['text'],
                    'x0': word['x0'],
                    'top': word['top'],
                    'size': word.get('size', 12),
                    'fontname': word.get('fontname', 'Helvetica')
                })
    return text_positions

def find_text_positions(text_positions, search_text):
    """Find the positions of a specific text in the PDF."""
    positions = []
    for item in text_positions:
        if item['text'] == search_text:
            positions.append(item)
    return positions

def create_overlay(field_updates, positions_dict, page_size, profile_image=None):
    """Create overlay PDF with updated data and profile image if available."""
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=page_size)

    # Update text fields
    for field_name, data in field_updates.items():
        positions = positions_dict.get(field_name, [])
        for item in positions:
            x = item['x0']
            y = page_size[1] - item['top']
            size = item['size']
            fontname = item['fontname']

            c.setFont(fontname, size)
            c.setFillColorRGB(1, 1, 1)
            c.rect(x, y - size, 200, size + 5, fill=1, stroke=0)
            c.setFillColorRGB(0, 0, 0)
            c.drawString(x, y, data)

    # Add profile image if provided
    if profile_image:
        img_positions = positions_dict.get("profile_image", [])
        for item in img_positions:
            x = item["x0"]
            y = page_size[1] - item["top"] - 100
            c.drawImage(profile_image, x, y, width=100, height=100)

    c.save()
    packet.seek(0)
    return packet

def merge_pdfs(original_pdf_stream, overlay_pdf_stream):
    """Merge the original PDF with the overlay PDF."""
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

def generate_pdf(data, original_pdf_stream, profile_image_path=None):
    """Generate the updated PDF with overlay data and profile image."""
    text_positions = get_text_positions(original_pdf_stream)

    fields_to_update = {
        'Name:': data['name'],
        'Jobs:': data['personal_details']['jobs'],
        'Colleges:': data['personal_details']['colleges'],
        'Emails:': data['personal_details']['emails'],
        'Locations:': data['personal_details']['locations'],
        'Platforms Evaluated:': str(data['metrics']['platforms_evaluated']),
        'Flagged Posts:': str(data['metrics']['flagged_posts']),
        'Flagged Categories:': str(data['metrics']['flagged_categories']),
    }

    positions_dict = {field: find_text_positions(text_positions, field) for field in fields_to_update.keys()}
    positions_dict['profile_image'] = find_text_positions(text_positions, 'Profile Image')

    page_size = letter
    overlay_stream = create_overlay(fields_to_update, positions_dict, page_size, profile_image=profile_image_path)

    updated_pdf_stream = merge_pdfs(original_pdf_stream, overlay_stream)

    return updated_pdf_stream

def main():
    st.set_page_config(page_title="PDF Report Editor", layout="wide")
    st.title("PDF Report Editor")

    if "data" not in st.session_state:
        st.session_state.data = None
    if "profile_image" not in st.session_state:
        st.session_state.profile_image = None

    uploaded_file = st.file_uploader("Upload PDF Report", type="pdf")

    if uploaded_file:
        if st.session_state.data is None:
            st.session_state.data = extract_pdf_data(uploaded_file)

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Basic Information")
            st.session_state.data["name"] = st.text_input("Name", st.session_state.data["name"])
            st.session_state.profile_image = st.file_uploader("Profile Image", type=["png", "jpg", "jpeg"])

            st.subheader("Personal Details")
            for key in st.session_state.data["personal_details"]:
                st.session_state.data["personal_details"][key] = st.text_input(
                    key.capitalize(),
                    st.session_state.data["personal_details"][key]
                )

        with col2:
            st.subheader("Social Media Profiles")
            for i, profile in enumerate(st.session_state.data["social_profiles"]):
                cols = st.columns(3)
                with cols[0]:
                    profile["platform"] = st.text_input(f"Platform {i+1}", profile["platform"])
                with cols[1]:
                    profile["username"] = st.text_input(f"Username {i+1}", profile["username"])
                with cols[2]:
                    profile["url"] = st.text_input(f"URL {i+1}", profile["url"])

            if st.button("Add Social Profile"):
                st.session_state.data["social_profiles"].append({
                    "platform": "",
                    "username": "",
                    "url": ""
                })

        st.subheader("Platforms with No Matches")
        no_matches = st.text_area(
            "Enter platforms (one per line)",
            "\n".join(st.session_state.data["no_matches_platforms"])
        )
        st.session_state.data["no_matches_platforms"] = [
            platform.strip() for platform in no_matches.split("\n") if platform.strip()
        ]

        st.subheader("Metrics")
        cols = st.columns(3)
        with cols[0]:
            st.session_state.data["metrics"]["platforms_evaluated"] = st.number_input(
                "Platforms Evaluated",
                min_value=0,
                value=st.session_state.data["metrics"].get("platforms_evaluated", 0)
            )
        with cols[1]:
            st.session_state.data["metrics"]["flagged_posts"] = st.number_input(
                "Flagged Posts",
                min_value=0,
                value=st.session_state.data["metrics"].get("flagged_posts", 0)
            )
        with cols[2]:
            st.session_state.data["metrics"]["flagged_categories"] = st.number_input(
                "Flagged Categories",
                min_value=0,
                value=st.session_state.data["metrics"].get("flagged_categories", 0)
            )

        st.subheader("Flagged Posts")
        for i, post in enumerate(st.session_state.data["flagged_posts"]):
            with st.expander(f"Post {i+1}"):
                post["include"] = st.checkbox("Include in report", post["include"], key=f"include_{i}")
                post["platform"] = st.text_input("Platform", post["platform"], key=f"platform_{i}")
                post["content"] = st.text_area("Content", post["content"], key=f"content_{i}")
                post["date"] = st.text_input("Date", post["date"], key=f"date_{i}")
                post["url"] = st.text_input("URL", post["url"], key=f"url_{i}")

        if st.button("Generate Updated PDF"):
            # Save profile image temporarily if provided
            profile_image_path = None
            if st.session_state.profile_image is not None:
                img = Image.open(st.session_state.profile_image)
                img = img.resize((100, 100))  # Resize image as needed
                temp_image = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
                img.save(temp_image.name)
                profile_image_path = temp_image.name

            pdf_buffer = generate_pdf(st.session_state.data, uploaded_file, profile_image_path=profile_image_path)
            st.download_button(
                label="Download Updated PDF",
                data=pdf_buffer,
                file_name="updated_report.pdf",
                mime="application/pdf"
            )

            # Clean up temporary image file
            if profile_image_path:
                temp_image.close()

if __name__ == "__main__":
    main()
