import streamlit as st
import pdfplumber
import re
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from PIL import Image
import requests

def extract_pdf_data(pdf_file):
    """Extract data from the uploaded PDF file."""
    with pdfplumber.open(pdf_file) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"

    # Print the extracted text for debugging
    # Uncomment the next line to see the text in the console
    # print(text)

    # Parse the text to extract relevant information
    data = {
        "name": re.search(r"^(.*?)\n", text).group(1).strip(),
        "personal_details": {
            "jobs": re.search(r"Jobs:\s*(.*?)\n", text).group(1),
            "colleges": re.search(r"Colleges:\s*(.*?)\n", text).group(1),
            "emails": re.search(r"Emails:\s*(.*?)\n", text).group(1),
            "locations": re.search(r"Locations:\s*(.*?)\n", text).group(1)
        },
        "social_profiles": [],
        "no_matches_platforms": [],
        "metrics": {},
        "flagged_posts": []
    }

    # Extract metrics with error handling
    platforms_evaluated_match = re.search(r"(\d+)\s*Social platforms evaluated", text)
    if platforms_evaluated_match:
        data["metrics"]["platforms_evaluated"] = int(platforms_evaluated_match.group(1))
    else:
        data["metrics"]["platforms_evaluated"] = 0  # or handle as you see fit

    flagged_posts_match = re.search(r"(\d+)\s*Total flagged posts", text)
    if flagged_posts_match:
        data["metrics"]["flagged_posts"] = int(flagged_posts_match.group(1))
    else:
        data["metrics"]["flagged_posts"] = 0

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

def generate_pdf(data):
    """Generate a new PDF with the updated data."""
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    
    # Page 1
    y = 750  # Starting y position
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, data["name"])
    
    if "profile_image" in st.session_state and st.session_state.profile_image is not None:
        img = Image.open(st.session_state.profile_image)
        img = img.resize((100, 100))  # Resize image to reasonable dimensions
        img_path = "temp_profile.png"
        img.save(img_path)
        c.drawImage(img_path, 50, y - 120, width=100, height=100)
    
    # Page 2 - Personal Details
    c.showPage()
    y = 750
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Personal Details")
    
    y -= 30
    c.setFont("Helvetica", 12)
    for key, value in data["personal_details"].items():
        c.drawString(50, y, f"{key.capitalize()}: {value}")
        y -= 20
    
    # Social Profiles
    y -= 20
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Social Media Profiles")
    
    y -= 20
    c.setFont("Helvetica", 12)
    for profile in data["social_profiles"]:
        c.drawString(50, y, f"{profile['platform']}: {profile['username']}")
        y -= 20
    
    # No Matches Platforms
    y -= 20
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Platforms with No Matches")
    
    y -= 20
    c.setFont("Helvetica", 12)
    for platform in data["no_matches_platforms"]:
        c.drawString(50, y, platform)
        y -= 20
    
    # Page 3 - Metrics
    c.showPage()
    y = 750
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, y, "Metrics")
    
    y -= 30
    c.setFont("Helvetica", 12)
    for key, value in data["metrics"].items():
        c.drawString(50, y, f"{key.replace('_', ' ').capitalize()}: {value}")
        y -= 20
    
    # Flagged Posts
    for post in data["flagged_posts"]:
        if post["include"]:
            c.showPage()
            y = 750
            c.setFont("Helvetica-Bold", 14)
            c.drawString(50, y, f"Flagged Post - {post['platform']}")
            
            y -= 30
            c.setFont("Helvetica", 12)
            # Split long content into multiple lines
            words = post["content"].split()
            lines = []
            current_line = []
            
            for word in words:
                current_line.append(word)
                if len(" ".join(current_line)) > 60:  # Adjust based on your needs
                    lines.append(" ".join(current_line[:-1]))
                    current_line = [word]
            if current_line:
                lines.append(" ".join(current_line))
            
            for line in lines:
                c.drawString(50, y, line)
                y -= 20
            
            y -= 20
            c.drawString(50, y, f"Posted on: {post['date']}")
            if post["url"]:
                y -= 20
                c.drawString(50, y, f"URL: {post['url']}")
    
    c.save()
    buffer.seek(0)
    return buffer

def main():
    st.set_page_config(page_title="PDF Report Editor", layout="wide")
    st.title("PDF Report Editor")
    
    # Initialize session state
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
            pdf_buffer = generate_pdf(st.session_state.data)
            st.download_button(
                label="Download Updated PDF",
                data=pdf_buffer,
                file_name="updated_report.pdf",
                mime="application/pdf"
            )

if __name__ == "__main__":
    main()
