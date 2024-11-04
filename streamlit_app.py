import streamlit as st
import fitz  # PyMuPDF for parsing PDFs
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.platypus import Image as ReportLabImage
from PIL import Image
import io

# Utility to extract specific text from PDF
def extract_text_by_page(pdf_document):
    text = {}
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        text[page_num] = page.get_text("text")
    return text

# Function to update the PDF using ReportLab
def create_updated_pdf(buffer, data, profile_image=None):
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # Page 1: Profile Section
    c.drawString(100, height - 100, f"Name: {data['name']}")
    if profile_image:
        img = Image.open(profile_image)
        img_buffer = io.BytesIO()
        img.save(img_buffer, format="PNG")
        img_buffer.seek(0)
        report_img = ReportLabImage(img_buffer, width=100, height=100)
        report_img.drawOn(c, 100, height - 200)

    # Page 2: Social Details
    c.showPage()
    c.drawString(100, height - 100, f"Job: {data['job']}")
    c.drawString(100, height - 120, f"Colleges: {data['colleges']}")
    c.drawString(100, height - 140, f"Email: {data['email']}")
    c.drawString(100, height - 160, f"Location: {data['location']}")
    
    # Social Profiles
    y_pos = height - 180
    for platform, link in data["social_profiles"].items():
        c.drawString(100, y_pos, f"{platform}: {link}")
        y_pos -= 20
    c.drawString(100, y_pos, f"No Matches Found: {data['no_match']}")

    # Page 3: Risk Summary
    c.showPage()
    c.drawString(100, height - 100, f"Platforms Evaluated: {data['platforms_evaluated']}")
    c.drawString(100, height - 120, f"Total Flagged Posts: {data['total_flagged_posts']}")
    c.drawString(100, height - 140, f"Risk Level: {data['risk_level']}")
    c.drawString(100, height - 160, f"Summary of Findings: {data['flagged_summary']}")

    # Pages 4+: Flagged Posts
    c.showPage()
    for post in data["flagged_posts"]:
        if post['include']:
            c.drawString(100, height - 100, f"Post URL: {post['url']}")
            height -= 20

    c.save()

# Streamlit App
st.title("PDF Report Editor")
uploaded_file = st.file_uploader("Upload PDF Report", type="pdf")

if uploaded_file:
    pdf_document = fitz.open(stream=uploaded_file.read(), filetype="pdf")
    
    # Extract text for specific sections
    pdf_text = extract_text_by_page(pdf_document)

    # Form for user input on editable fields
    data = {}
    # Page 1: Profile
    st.header("Page 1: Profile")
    profile_image = st.file_uploader("Upload Profile Image (if needed)", type=["jpg", "png"])
    data['name'] = st.text_input("Name", "Juddy Maiyo")  # Set initial value based on parsed content

    # Page 2: Social Details
    st.header("Page 2: Details")
    data['job'] = st.text_input("Job", "PLATCORP HOLDINGS LTD")
    data['colleges'] = st.text_area("Colleges", "University of Nairobi")
    data['email'] = st.text_input("Email", "maiyojudy@gmail.com")
    data['location'] = st.text_input("Location", "Nairobi, Nairobi, Kenya")
    
    # Social media profiles
    st.subheader("Social Media Profiles Found")
    data["social_profiles"] = {
        "Instagram": st.text_input("Instagram Profile", "https://www.instagram.com/maiyo.judy/"),
        "Facebook": st.text_input("Facebook Profile", "https://www.facebook.com/jmaiyo"),
        "LinkedIn": st.text_input("LinkedIn Profile", "https://www.linkedin.com/in/judy-maiyo-01399358/"),
        "Twitter": st.text_input("Twitter Profile", "https://twitter.com/JudyMaiyo"),
    }
    
    st.subheader("Social Media Platforms with No Matches Found")
    data["no_match"] = st.text_input("Platforms without matches", "TikTok")
    
    # Page 3: Risk Summary
    st.header("Page 3: Risk Summary")
    data['platforms_evaluated'] = st.number_input("Number of Platforms Evaluated", value=4, min_value=0)
    data['total_flagged_posts'] = st.number_input("Total Flagged Posts", value=1, min_value=0)
    data['risk_level'] = st.selectbox("Profile Risk Level", ["Low", "Medium", "High"], index=2)
    data['flagged_summary'] = st.text_area("Summary of Findings", "1 posts were flagged under 1 different categories.")

    # Pages 4+ Flagged Posts
    st.header("Flagged Posts")
    data["flagged_posts"] = []
    for page_num in range(4, pdf_document.page_count - 1):  # Assuming last page has no flagged posts
        page = pdf_document[page_num]
        # Extract post URL and default checkbox status based on parsed content
        post_url = "https://www.example.com"  # Replace with actual extraction code
        include_post = st.checkbox(f"Include Post: {post_url}", value=True)
        data["flagged_posts"].append({"url": post_url, "include": include_post})

    # Generate Updated PDF
    if st.button("Generate Updated PDF"):
        buffer = io.BytesIO()
        create_updated_pdf(buffer, data, profile_image)
        buffer.seek(0)

        st.success("PDF updated successfully!")
        st.download_button("Download Updated PDF", buffer, file_name="Updated_Report.pdf", mime="application/pdf")
