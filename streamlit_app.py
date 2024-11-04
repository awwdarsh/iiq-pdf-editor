import streamlit as st
import fitz  # PyMuPDF for parsing PDFs
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
import io
from PIL import Image

# Utility to extract specific text from PDF
def extract_text_by_page(pdf_document):
    extracted_data = {}
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        text = page.get_text("text")
        
        if page_num == 0:
            # Page 1: Extract Name and check for Profile Image
            extracted_data['name'] = extract_field(text, 'Name:')
            images = page.get_images()
            extracted_data['has_profile_image'] = len(images) > 0
        elif page_num == 1:
            # Page 2: Extract Job, Colleges, Email, Location, Social Profiles
            extracted_data['job'] = extract_field(text, 'Job:')
            extracted_data['colleges'] = extract_field(text, 'Colleges:')
            extracted_data['email'] = extract_field(text, 'Email:')
            extracted_data['location'] = extract_field(text, 'Location:')
            # Extract social profiles found
            social_profiles = {}
            for line in text.split('\n'):
                if any(platform in line for platform in ['Instagram:', 'Facebook:', 'LinkedIn:', 'Twitter:']):
                    platform, link = line.split(':', 1)
                    social_profiles[platform.strip()] = link.strip()
            extracted_data['social_profiles'] = social_profiles
            # Extract platforms with no matches found
            extracted_data['no_match'] = extract_field(text, 'No Matches Found:')
        elif page_num == 2:
            # Page 3: Extract Risk Summary
            extracted_data['platforms_evaluated'] = extract_field(text, 'Platforms Evaluated:')
            extracted_data['total_flagged_posts'] = extract_field(text, 'Total Flagged Posts:')
            extracted_data['risk_level'] = extract_field(text, 'Risk Level:')
            extracted_data['flagged_summary'] = extract_field(text, 'Summary of Findings:')
        else:
            # Pages 4+: Extract flagged posts URLs
            if 'flagged_posts' not in extracted_data:
                extracted_data['flagged_posts'] = []
            # Assuming URLs are on lines starting with 'Post URL:'
            for line in text.split('\n'):
                if 'Post URL:' in line:
                    url = line.replace('Post URL:', '').strip()
                    extracted_data['flagged_posts'].append({'url': url, 'include': True})
    return extracted_data

def extract_field(text, field_name):
    lines = text.split('\n')
    for idx, line in enumerate(lines):
        if field_name in line:
            # Handle multi-line fields
            value_lines = []
            value = line.replace(field_name, '').strip()
            if value:
                value_lines.append(value)
            # Check subsequent lines for additional data
            for next_line in lines[idx+1:]:
                if ':' in next_line:  # Assuming next field starts
                    break
                else:
                    value_lines.append(next_line.strip())
            return '\n'.join(value_lines).strip()
    return ''

# Function to create an overlay PDF with updated text
def create_overlay_pdf(data, profile_image=None):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Page 1: Profile Section
    c.setFont("Helvetica", 12)
    c.drawString(100, height - 100, f"Name: {data['name']}")
    if profile_image:
        img = Image.open(profile_image)
        img_width, img_height = img.size
        aspect = img_height / float(img_width)
        img_width = 100
        img_height = img_width * aspect
        img_reader = ImageReader(profile_image)
        c.drawImage(img_reader, 100, height - 200, width=img_width, height=img_height)
    
    c.showPage()

    # Page 2: Social Details
    c.setFont("Helvetica", 12)
    c.drawString(100, height - 100, f"Job: {data['job']}")
    c.drawString(100, height - 120, f"Colleges: {data['colleges']}")
    c.drawString(100, height - 140, f"Email: {data['email']}")
    c.drawString(100, height - 160, f"Location: {data['location']}")
    
    y_pos = height - 180
    for platform, link in data["social_profiles"].items():
        c.drawString(100, y_pos, f"{platform}: {link}")
        y_pos -= 20
    c.drawString(100, y_pos, f"No Matches Found: {data['no_match']}")
    
    c.showPage()

    # Page 3: Risk Summary
    c.setFont("Helvetica", 12)
    c.drawString(100, height - 100, f"Platforms Evaluated: {data['platforms_evaluated']}")
    c.drawString(100, height - 120, f"Total Flagged Posts: {data['total_flagged_posts']}")
    c.drawString(100, height - 140, f"Risk Level: {data['risk_level']}")
    c.drawString(100, height - 160, f"Summary of Findings: {data['flagged_summary']}")

    c.showPage()

    # Pages 4+: Flagged Posts
    for post in data["flagged_posts"]:
        if post['include']:
            c.drawString(100, height - 100, f"Post URL: {post['url']}")
            c.showPage()

    c.save()
    buffer.seek(0)
    return buffer

# Function to merge the overlay with the original PDF
def create_updated_pdf(original_pdf_stream, data, profile_image=None):
    # Create overlay PDF
    overlay_pdf = create_overlay_pdf(data, profile_image)

    # Read the original and overlay PDFs
    original_pdf_stream.seek(0)
    reader = PdfReader(original_pdf_stream)
    overlay_reader = PdfReader(overlay_pdf)
    writer = PdfWriter()

    overlay_pages = overlay_reader.pages
    overlay_page_count = len(overlay_pages)

    # Merge the overlay pages with the original pages
    for page_num in range(len(reader.pages)):
        page = reader.pages[page_num]
        if page_num < overlay_page_count:
            overlay_page = overlay_pages[page_num]
            page.merge_page(overlay_page)
        writer.add_page(page)

    # Save the updated PDF to a buffer
    output_buffer = io.BytesIO()
    writer.write(output_buffer)
    output_buffer.seek(0)
    return output_buffer

# Streamlit App
def main():
    st.title("PDF Report Editor")
    uploaded_file = st.file_uploader("Upload PDF Report", type="pdf")

    if uploaded_file:
        # Read the uploaded PDF file
        pdf_data = uploaded_file.read()
        pdf_document = fitz.open(stream=pdf_data, filetype="pdf")

        # Extract text for specific sections
        extracted_data = extract_text_by_page(pdf_document)

        # Form for user input on editable fields
        data = {}
        # Page 1: Profile
        st.header("Page 1: Profile")
        if not extracted_data.get('has_profile_image'):
            profile_image = st.file_uploader("Upload Profile Image (if needed)", type=["jpg", "png"])
        else:
            st.info("Profile image already present in the PDF.")
            profile_image = None  # Keep existing image
        data['name'] = st.text_input("Name", extracted_data.get('name', ''))

        # Page 2: Social Details
        st.header("Page 2: Details")
        data['job'] = st.text_input("Job", extracted_data.get('job', ''))
        data['colleges'] = st.text_area("Colleges", extracted_data.get('colleges', ''))
        data['email'] = st.text_input("Email", extracted_data.get('email', ''))
        data['location'] = st.text_input("Location", extracted_data.get('location', ''))

        # Social media profiles
        st.subheader("Social Media Profiles Found")
        social_profiles = extracted_data.get('social_profiles', {})
        platforms = ['Instagram', 'Facebook', 'LinkedIn', 'Twitter']
        data["social_profiles"] = {}
        for platform in platforms:
            data["social_profiles"][platform] = st.text_input(
                f"{platform} Profile",
                social_profiles.get(platform, '')
            )

        st.subheader("Social Media Platforms with No Matches Found")
        data["no_match"] = st.text_input("Platforms without matches", extracted_data.get('no_match', ''))

        # Page 3: Risk Summary
        st.header("Page 3: Risk Summary")
        platforms_evaluated = extracted_data.get('platforms_evaluated', '0')
        total_flagged_posts = extracted_data.get('total_flagged_posts', '0')
        data['platforms_evaluated'] = st.number_input(
            "Number of Platforms Evaluated",
            value=int(platforms_evaluated) if platforms_evaluated.isdigit() else 0,
            min_value=0
        )
        data['total_flagged_posts'] = st.number_input(
            "Total Flagged Posts",
            value=int(total_flagged_posts) if total_flagged_posts.isdigit() else 0,
            min_value=0
        )
        risk_levels = ["Low", "Medium", "High"]
        risk_level = extracted_data.get('risk_level', 'Low')
        if risk_level not in risk_levels:
            risk_level = 'Low'
        data['risk_level'] = st.selectbox(
            "Profile Risk Level",
            risk_levels,
            index=risk_levels.index(risk_level)
        )
        data['flagged_summary'] = st.text_area("Summary of Findings", extracted_data.get('flagged_summary', ''))

        # Pages 4+ Flagged Posts
        st.header("Flagged Posts")
        data["flagged_posts"] = []
        flagged_posts = extracted_data.get('flagged_posts', [])
        for idx, post in enumerate(flagged_posts):
            include_post = st.checkbox(f"Include Post: {post['url']}", value=post['include'], key=idx)
            data["flagged_posts"].append({"url": post['url'], "include": include_post})

        # Generate Updated PDF
        if st.button("Generate Updated PDF"):
            # Re-open the uploaded file to get a fresh stream
            uploaded_file.seek(0)
            buffer = create_updated_pdf(uploaded_file, data, profile_image)
            st.success("PDF updated successfully!")
            st.download_button("Download Updated PDF", buffer, file_name="Updated_Report.pdf", mime="application/pdf")

if __name__ == "__main__":
    main()
