import streamlit as st
import pdfplumber
import re
from io import BytesIO
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PIL import Image
import tempfile

def extract_pdf_data(pdf_file):
    """Extract data from the uploaded PDF file."""
    with pdfplumber.open(pdf_file) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"

    # Parse the text to extract relevant information
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

    # Extract metrics with error handling
    platforms_evaluated_match = re.search(r"(\d+)\s*Social platforms evaluated", text)
    if platforms_evaluated_match:
        data["metrics"]["platforms_evaluated"] = int(platforms_evaluated_match.group(1))

    flagged_posts_match = re.search(r"(\d+)\s*Total flagged posts", text)
    if flagged_posts_match:
        data["metrics"]["flagged_posts"] = int(flagged_posts_match.group(1))

    data["metrics"]["flagged_categories"] = len(re.findall(r"potential issues found:", text))

    # Extract social profiles
    profiles_text_match = re.search(r"Social media profiles found:\s*(.*?)\n\n", text, re.DOTALL)
    if profiles_text_match:
        profiles_text = profiles_text_match.group(1)
        data["social_profiles"] = [{"platform": "Unknown", "username": username.strip(), "url": ""}
                                   for username in profiles_text.split("\n") if username.strip()]

    # Extract platforms with no matches
    no_matches_match = re.search(r"Social media platforms with no matches found:\s*(.*?)\n\n", text, re.DOTALL)
    if no_matches_match:
        data["no_matches_platforms"] = [platform.strip() for platform in no_matches_match.group(1).split("\n") if platform.strip()]

    # Extract flagged posts
    posts = re.findall(r"(.*?)\nPosted on\s*•\s*(.*?)\n.*?View original post", text, re.DOTALL)
    data["flagged_posts"] = [{
        "content": post[0].strip(),
        "date": post[1],
        "url": "",
        "include": True,
        "platform": "Unknown"  # You might want to extract this from the context
    } for post in posts]

    return data

def get_text_positions(pdf_file):
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
                    'size': word.get('size', 12),  # Default size if not available
                    'fontname': word.get('fontname', 'Helvetica')  # Default font if not available
                })
    return text_positions

def find_text_positions(text_positions, search_text):
    positions = []
    for item in text_positions:
        if item['text'] == search_text:
            positions.append(item)
    return positions

def create_overlay(field_updates, positions_dict, page_size, profile_image=None):
    packet = BytesIO()
    c = canvas.Canvas(packet, pagesize=page_size)

    # Draw updated fields
    for field_name, data in field_updates.items():
        positions = positions_dict.get(field_name, [])
        for item in positions:
            x = item['x0']
            y = page_size[1] - item['top']  # Adjust y-coordinate
            size = item['size']
            fontname = item['fontname']

            c.setFont(fontname, size)
            # Draw white rectangle to cover old text
            c.setFillColorRGB(1, 1, 1)
            c.rect(x, y - size, 200, size + 5, fill=1, stroke=0)  # Adjust rectangle dimensions
            c.setFillColorRGB(0, 0, 0)
            c.drawString(x, y, data)

    # Draw profile image if available
    if profile_image:
        image_positions = positions_dict.get('profile_image', [])
        for item in image_positions:
            x = item['x0']
            y = page_size[1] - item['top'] - 100  # Adjust as needed
            c.drawImage(profile_image, x, y, width=100, height=100)

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

def generate_pdf(data, original_pdf_stream, profile_image_path=None):
    # Step 1: Extract text positions
    text_positions = get_text_positions(original_pdf_stream)

    # Step 2: Find positions to update
    fields_to_update = {
        'name': data['name'],
        'jobs': data['personal_details']['jobs'],
        'colleges': data['personal_details']['colleges'],
        'emails': data['personal_details']['emails'],
        'locations': data['personal_details']['locations'],
        # Add more fields as needed
    }

    positions_dict = {}
    for field_name in fields_to_update.keys():
        positions_dict[field_name] = find_text_positions(text_positions, field_name.capitalize() + ":")

    # For profile image, we need to decide on a placeholder text or coordinate
    # Assuming there is a placeholder text 'Profile Image' in the PDF
    positions_dict['profile_image'] = find_text_positions(text_positions, 'Profile Image')

    # Step 3: Create overlay PDF with new content
    page_size = letter  # Adjust if your PDF uses a different page size
    overlay_stream = create_overlay(fields_to_update, positions_dict, page_size, profile_image=profile_image_path)

    # Step 4: Merge overlay with original PDF
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

        # Create two columns
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
                value=st.session_state.data["metrics"]["platforms_evaluated"]
            )
        with cols[1]:
            st.session_state.data["metrics"]["flagged_posts"] = st.number_input(
                "Flagged Posts",
                min_value=0,
                value=st.session_state.data["metrics"]["flagged_posts"]
            )
        with cols[2]:
            st.session_state.data["metrics"]["flagged_categories"] = st.number_input(
                "Flagged Categories",
                min_value=0,
                value=st.session_state.data["metrics"]["flagged_categories"]
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
