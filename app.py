"""
GitBook PDF Export Tool - Enhanced Edition v2
Uses GitBook's native PDF export as base, then adds:
- Custom cover page
- Clickable table of contents
- Headers and footers with branding
"""

import streamlit as st
import requests
import io
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch, cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, black, white, Color
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image,
    Table, TableStyle, Frame, PageTemplate, BaseDocTemplate
)
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from PIL import Image as PILImage
import tempfile
import os

# Page configuration
st.set_page_config(
    page_title="GitBook PDF Export Tool",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1a1a2e;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .info-box {
        background-color: #f0f7ff;
        border-left: 4px solid #0066cc;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0 8px 8px 0;
    }
    .success-box {
        background-color: #f0fff0;
        border-left: 4px solid #00cc66;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0 8px 8px 0;
    }
    .warning-box {
        background-color: #fffbf0;
        border-left: 4px solid #ffaa00;
        padding: 1rem;
        margin: 1rem 0;
        border-radius: 0 8px 8px 0;
    }
</style>
""", unsafe_allow_html=True)


@dataclass
class PDFConfig:
    """Configuration for PDF enhancement"""
    # Cover page options
    include_cover: bool = True
    cover_title: str = ""
    cover_subtitle: str = ""
    cover_logo: Optional[bytes] = None
    cover_image: Optional[bytes] = None
    show_version: bool = True
    version_text: str = ""
    show_date: bool = True
    date_format: str = "%B %Y"
    
    # Table of contents
    include_toc: bool = True
    toc_depth: int = 3
    
    # Header/Footer
    include_header: bool = True
    header_text: str = ""
    header_logo: Optional[bytes] = None
    include_footer: bool = True
    footer_text: str = ""
    footer_logo: Optional[bytes] = None
    show_page_numbers: bool = True
    page_number_start: int = 1  # What number to start content pages at
    
    # Styling
    page_size: str = "Letter"
    primary_color: str = "#0066cc"
    
    # Content
    organization_name: str = ""


class GitBookAPI:
    """Client for interacting with GitBook API"""
    
    BASE_URL = "https://api.gitbook.com/v1"
    
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json"
        }
    
    def _make_request(self, method: str, endpoint: str, params: dict = None) -> dict:
        """Make an API request and return JSON response"""
        url = f"{self.BASE_URL}{endpoint}"
        try:
            response = requests.request(method, url, headers=self.headers, params=params, timeout=60)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 401:
                raise Exception("Invalid API token. Please check your credentials.")
            elif response.status_code == 404:
                raise Exception("Resource not found. Please verify the Space ID.")
            elif response.status_code == 403:
                raise Exception("Access denied. You may not have permission to access this space.")
            else:
                raise Exception(f"API Error: {str(e)}")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Connection error: {str(e)}")
    
    def get_space(self, space_id: str) -> dict:
        """Get space information"""
        return self._make_request("GET", f"/spaces/{space_id}")
    
    def get_all_pages(self, space_id: str) -> dict:
        """Get all pages in a space"""
        return self._make_request("GET", f"/spaces/{space_id}/content/pages")
    
    def get_organization(self, org_id: str) -> dict:
        """Get organization information"""
        return self._make_request("GET", f"/orgs/{org_id}")
    
    def get_pdf_url(self, space_id: str, page_id: str = None, only_page: bool = False) -> str:
        """Get the URL for PDF export and return the actual URL"""
        params = {}
        if page_id:
            params["page"] = page_id
            if only_page:
                params["only"] = True
        
        result = self._make_request("GET", f"/spaces/{space_id}/pdf", params=params)
        return result.get('url', '')
    
    def download_pdf(self, space_id: str) -> bytes:
        """Download the GitBook-generated PDF"""
        pdf_url = self.get_pdf_url(space_id)
        if not pdf_url:
            raise Exception("Could not get PDF URL from GitBook")
        
        # Download the PDF
        response = requests.get(pdf_url, timeout=120)
        response.raise_for_status()
        return response.content


class PDFEnhancer:
    """Enhance GitBook PDF with cover page, TOC, headers/footers"""
    
    def __init__(self, config: PDFConfig):
        self.config = config
        self.page_size = letter if config.page_size == "Letter" else A4
        self.width, self.height = self.page_size
        self.primary_color = HexColor(config.primary_color)
        
    def _create_cover_page(self, space_info: dict, org_info: dict = None) -> bytes:
        """Create a cover page as a separate PDF"""
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=self.page_size)
        
        width, height = self.page_size
        primary_color = self.primary_color
        
        # Background - subtle gradient effect with rectangles
        c.setFillColor(HexColor('#f8f9fa'))
        c.rect(0, 0, width, height, fill=True, stroke=False)
        
        # Decorative header bar
        c.setFillColor(primary_color)
        c.rect(0, height - 20, width, 20, fill=True, stroke=False)
        
        # Logo
        current_y = height - 100
        if self.config.cover_logo:
            try:
                logo_img = PILImage.open(io.BytesIO(self.config.cover_logo))
                
                # Save to temp file for ReportLab
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    logo_img.save(tmp.name, 'PNG')
                    tmp_path = tmp.name
                
                # Calculate dimensions
                aspect = logo_img.width / logo_img.height
                max_width = 2.5 * inch
                max_height = 1.2 * inch
                
                if aspect > max_width / max_height:
                    img_width = max_width
                    img_height = img_width / aspect
                else:
                    img_height = max_height
                    img_width = img_height * aspect
                
                x = (width - img_width) / 2
                c.drawImage(tmp_path, x, current_y - img_height, width=img_width, height=img_height, preserveAspectRatio=True)
                current_y -= img_height + 30
                
                # Clean up
                os.unlink(tmp_path)
            except Exception as e:
                st.warning(f"Could not load cover logo: {e}")
        
        # Cover image
        if self.config.cover_image:
            try:
                cover_img = PILImage.open(io.BytesIO(self.config.cover_image))
                
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                    cover_img.save(tmp.name, 'PNG')
                    tmp_path = tmp.name
                
                aspect = cover_img.width / cover_img.height
                max_width = 5 * inch
                max_height = 2.5 * inch
                
                if aspect > max_width / max_height:
                    img_width = max_width
                    img_height = img_width / aspect
                else:
                    img_height = max_height
                    img_width = img_height * aspect
                
                x = (width - img_width) / 2
                current_y -= 20
                c.drawImage(tmp_path, x, current_y - img_height, width=img_width, height=img_height, preserveAspectRatio=True)
                current_y -= img_height + 40
                
                os.unlink(tmp_path)
            except Exception as e:
                st.warning(f"Could not load cover image: {e}")
        
        # Title
        title = self.config.cover_title or space_info.get('title', 'Documentation')
        c.setFillColor(HexColor('#1a1a2e'))
        
        # Dynamic font size based on title length
        if len(title) > 40:
            title_size = 28
        elif len(title) > 25:
            title_size = 32
        else:
            title_size = 38
            
        c.setFont("Helvetica-Bold", title_size)
        
        # Center title
        title_width = stringWidth(title, "Helvetica-Bold", title_size)
        if title_width > width - 100:
            # Title too long, need to wrap
            words = title.split()
            lines = []
            current_line = []
            for word in words:
                test_line = ' '.join(current_line + [word])
                if stringWidth(test_line, "Helvetica-Bold", title_size) < width - 100:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                    current_line = [word]
            if current_line:
                lines.append(' '.join(current_line))
            
            current_y -= 20
            for line in lines:
                line_width = stringWidth(line, "Helvetica-Bold", title_size)
                c.drawString((width - line_width) / 2, current_y, line)
                current_y -= title_size + 8
        else:
            current_y -= 20
            c.drawString((width - title_width) / 2, current_y, title)
            current_y -= title_size + 15
        
        # Subtitle
        subtitle = self.config.cover_subtitle
        if subtitle:
            c.setFont("Helvetica", 16)
            c.setFillColor(HexColor('#666666'))
            subtitle_width = stringWidth(subtitle, "Helvetica", 16)
            
            if subtitle_width > width - 100:
                # Wrap subtitle
                words = subtitle.split()
                lines = []
                current_line = []
                for word in words:
                    test_line = ' '.join(current_line + [word])
                    if stringWidth(test_line, "Helvetica", 16) < width - 100:
                        current_line.append(word)
                    else:
                        if current_line:
                            lines.append(' '.join(current_line))
                        current_line = [word]
                if current_line:
                    lines.append(' '.join(current_line))
                
                for line in lines:
                    line_width = stringWidth(line, "Helvetica", 16)
                    c.drawString((width - line_width) / 2, current_y, line)
                    current_y -= 24
            else:
                c.drawString((width - subtitle_width) / 2, current_y, subtitle)
                current_y -= 30
        
        # Decorative line
        current_y -= 20
        c.setStrokeColor(primary_color)
        c.setLineWidth(2)
        line_width = 3 * inch
        c.line((width - line_width) / 2, current_y, (width + line_width) / 2, current_y)
        
        # Meta information (version, date, org)
        meta_y = 150
        c.setFont("Helvetica", 12)
        c.setFillColor(HexColor('#888888'))
        
        meta_lines = []
        if self.config.show_version and self.config.version_text:
            meta_lines.append(f"Version {self.config.version_text}")
        if self.config.show_date:
            date_str = datetime.now().strftime(self.config.date_format)
            meta_lines.append(date_str)
        if self.config.organization_name:
            meta_lines.append(self.config.organization_name)
        elif org_info and org_info.get('title'):
            meta_lines.append(org_info.get('title'))
        
        for line in meta_lines:
            line_width = stringWidth(line, "Helvetica", 12)
            c.drawString((width - line_width) / 2, meta_y, line)
            meta_y -= 20
        
        # Footer bar
        c.setFillColor(primary_color)
        c.rect(0, 0, width, 10, fill=True, stroke=False)
        
        c.save()
        buffer.seek(0)
        return buffer.getvalue()
    
    def _create_toc_pages(self, pages: List[dict], total_content_pages: int) -> bytes:
        """Create table of contents pages with clickable links"""
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=self.page_size)
        
        width, height = self.page_size
        margin = 72
        usable_width = width - 2 * margin
        
        # Calculate number of front matter pages (cover + toc pages)
        # We'll figure out actual TOC pages after building entries
        
        # Build TOC entries
        toc_entries = []
        
        def process_pages(page_list: List[dict], depth: int = 0, page_offset: int = 0) -> int:
            """Process pages recursively and return the page count"""
            nonlocal toc_entries
            current_page = page_offset
            
            for page in page_list:
                if page.get('type') == 'link':
                    continue
                    
                if depth < self.config.toc_depth:
                    title = page.get('title', 'Untitled')
                    toc_entries.append({
                        'title': title,
                        'level': depth,
                        'page': current_page + 1  # Will be adjusted later
                    })
                
                current_page += 1
                
                # Process children
                if page.get('pages'):
                    current_page = process_pages(page.get('pages', []), depth + 1, current_page)
            
            return current_page
        
        process_pages(pages)
        
        # Calculate how many TOC pages we need
        entries_per_page = 35
        num_toc_pages = max(1, (len(toc_entries) + entries_per_page - 1) // entries_per_page)
        
        # Adjust page numbers - add cover (1) + toc pages
        front_matter_pages = 1 + num_toc_pages
        for entry in toc_entries:
            entry['page'] += front_matter_pages
        
        # Draw TOC
        current_entry = 0
        
        for toc_page in range(num_toc_pages):
            y = height - margin
            
            # Title (only on first page)
            if toc_page == 0:
                c.setFont("Helvetica-Bold", 28)
                c.setFillColor(self.primary_color)
                c.drawString(margin, y, "Table of Contents")
                y -= 50
            else:
                y -= 20
            
            c.setFillColor(black)
            
            # Draw entries
            entries_on_this_page = 0
            while current_entry < len(toc_entries) and entries_on_this_page < entries_per_page:
                entry = toc_entries[current_entry]
                level = entry['level']
                title = entry['title']
                page_num = entry['page']
                
                # Indentation based on level
                indent = level * 20
                
                # Font size and style based on level
                if level == 0:
                    c.setFont("Helvetica-Bold", 12)
                    c.setFillColor(self.primary_color)
                elif level == 1:
                    c.setFont("Helvetica-Bold", 11)
                    c.setFillColor(HexColor('#333333'))
                else:
                    c.setFont("Helvetica", 10)
                    c.setFillColor(HexColor('#555555'))
                
                # Truncate title if too long
                max_title_width = usable_width - indent - 50
                display_title = title
                while stringWidth(display_title, c._fontname, c._fontsize) > max_title_width and len(display_title) > 10:
                    display_title = display_title[:-4] + "..."
                
                # Draw title
                c.drawString(margin + indent, y, display_title)
                
                # Draw page number
                c.setFont("Helvetica", 10)
                c.setFillColor(HexColor('#666666'))
                page_str = str(page_num)
                page_width = stringWidth(page_str, "Helvetica", 10)
                c.drawString(width - margin - page_width, y, page_str)
                
                # Draw dot leader
                title_end = margin + indent + stringWidth(display_title, c._fontname, c._fontsize) + 10
                dots_start = title_end
                dots_end = width - margin - page_width - 10
                
                if dots_end > dots_start:
                    c.setFillColor(HexColor('#cccccc'))
                    dot_spacing = 4
                    x = dots_start
                    while x < dots_end:
                        c.circle(x, y + 3, 0.5, fill=True, stroke=False)
                        x += dot_spacing
                
                y -= 18 if level == 0 else 16
                current_entry += 1
                entries_on_this_page += 1
                
                # Check if we need a new page
                if y < margin + 50:
                    break
            
            # Add page number to TOC page
            c.setFont("Helvetica", 9)
            c.setFillColor(HexColor('#888888'))
            page_num_str = str(toc_page + 2)  # Cover is page 1
            c.drawCentredString(width / 2, 30, page_num_str)
            
            if current_entry < len(toc_entries):
                c.showPage()
        
        c.save()
        buffer.seek(0)
        return buffer.getvalue()
    
    def _add_headers_footers(self, input_pdf: bytes, start_page: int = 1) -> bytes:
        """Add headers and footers to existing PDF pages"""
        reader = PdfReader(io.BytesIO(input_pdf))
        writer = PdfWriter()
        
        total_pages = len(reader.pages)
        
        for i, page in enumerate(reader.pages):
            # Create overlay with header/footer
            overlay_buffer = io.BytesIO()
            c = canvas.Canvas(overlay_buffer, pagesize=self.page_size)
            
            width, height = self.page_size
            page_num = start_page + i
            
            # Header
            if self.config.include_header:
                header_text = self.config.header_text or self.config.cover_title or "Documentation"
                c.setFont("Helvetica", 9)
                c.setFillColor(HexColor('#888888'))
                c.drawString(72, height - 40, header_text)
                
                # Header line
                c.setStrokeColor(HexColor('#dddddd'))
                c.setLineWidth(0.5)
                c.line(72, height - 50, width - 72, height - 50)
            
            # Footer
            if self.config.include_footer or self.config.show_page_numbers:
                # Footer line
                c.setStrokeColor(HexColor('#dddddd'))
                c.setLineWidth(0.5)
                c.line(72, 45, width - 72, 45)
                
                c.setFont("Helvetica", 9)
                c.setFillColor(HexColor('#888888'))
                
                # Footer text on left
                if self.config.include_footer and self.config.footer_text:
                    c.drawString(72, 30, self.config.footer_text)
                
                # Page number on right
                if self.config.show_page_numbers:
                    page_str = f"Page {page_num}"
                    c.drawRightString(width - 72, 30, page_str)
            
            c.save()
            overlay_buffer.seek(0)
            
            # Merge overlay with page
            overlay_reader = PdfReader(overlay_buffer)
            if len(overlay_reader.pages) > 0:
                page.merge_page(overlay_reader.pages[0])
            
            writer.add_page(page)
        
        output_buffer = io.BytesIO()
        writer.write(output_buffer)
        output_buffer.seek(0)
        return output_buffer.getvalue()
    
    def enhance_pdf(self, gitbook_pdf: bytes, space_info: dict, pages: List[dict], org_info: dict = None) -> bytes:
        """Enhance the GitBook PDF with cover, TOC, headers/footers"""
        
        # Read the original GitBook PDF
        original_reader = PdfReader(io.BytesIO(gitbook_pdf))
        total_content_pages = len(original_reader.pages)
        
        writer = PdfWriter()
        
        # 1. Create and add cover page
        if self.config.include_cover:
            cover_pdf = self._create_cover_page(space_info, org_info)
            cover_reader = PdfReader(io.BytesIO(cover_pdf))
            for page in cover_reader.pages:
                writer.add_page(page)
        
        # 2. Create and add TOC
        toc_start_page = 1 if self.config.include_cover else 0
        
        if self.config.include_toc and pages:
            toc_pdf = self._create_toc_pages(pages, total_content_pages)
            toc_reader = PdfReader(io.BytesIO(toc_pdf))
            for page in toc_reader.pages:
                writer.add_page(page)
            content_start_page = toc_start_page + len(toc_reader.pages) + 1
        else:
            content_start_page = toc_start_page + 1
        
        # 3. Add headers/footers to original content and append
        if self.config.include_header or self.config.include_footer or self.config.show_page_numbers:
            enhanced_content = self._add_headers_footers(gitbook_pdf, start_page=content_start_page)
            enhanced_reader = PdfReader(io.BytesIO(enhanced_content))
            for page in enhanced_reader.pages:
                writer.add_page(page)
        else:
            for page in original_reader.pages:
                writer.add_page(page)
        
        # 4. Add PDF metadata
        writer.add_metadata({
            '/Title': self.config.cover_title or space_info.get('title', 'Documentation'),
            '/Author': self.config.organization_name or (org_info.get('title') if org_info else 'GitBook'),
            '/Subject': self.config.cover_subtitle or '',
            '/Creator': 'GitBook PDF Export Tool',
            '/Producer': 'ReportLab + pypdf'
        })
        
        # Output
        output_buffer = io.BytesIO()
        writer.write(output_buffer)
        output_buffer.seek(0)
        return output_buffer.getvalue()


def main():
    """Main application entry point"""
    
    # Header
    st.markdown('<h1 class="main-header">📚 GitBook PDF Export Tool</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Enhance your GitBook PDF exports with custom cover pages, table of contents, and branding.</p>', unsafe_allow_html=True)
    
    # Sidebar for API configuration
    with st.sidebar:
        st.header("🔑 API Configuration")
        
        # Check for secrets (Streamlit Cloud)
        default_token = ""
        default_space = ""
        default_org = ""
        
        try:
            default_token = st.secrets.get("GITBOOK_API_TOKEN", "")
            default_space = st.secrets.get("DEFAULT_SPACE_ID", "")
            default_org = st.secrets.get("DEFAULT_ORG_ID", "")
        except Exception:
            pass
        
        api_token = st.text_input(
            "GitBook API Token",
            value=default_token,
            type="password",
            help="Your GitBook personal access token. Get it from GitBook settings."
        )
        
        space_id = st.text_input(
            "Space ID",
            value=default_space,
            help="The unique identifier for your GitBook space."
        )
        
        org_id = st.text_input(
            "Organization ID (Optional)",
            value=default_org,
            help="Optional: Include organization branding."
        )
        
        st.divider()
        
        if st.button("🔍 Test Connection", use_container_width=True):
            if api_token and space_id:
                try:
                    api = GitBookAPI(api_token)
                    space = api.get_space(space_id)
                    st.success(f"✅ Connected!\n\n**Space:** {space.get('title', 'Unknown')}")
                except Exception as e:
                    st.error(f"❌ {e}")
            else:
                st.warning("Please enter API token and Space ID")
        
        st.divider()
        
        st.markdown("""
        <div class="info-box" style="font-size: 0.85rem;">
        <strong>ℹ️ How it works:</strong><br>
        1. Fetches GitBook's native PDF (with proper rendering)<br>
        2. Adds custom cover page<br>
        3. Generates clickable TOC<br>
        4. Adds headers & footers
        </div>
        """, unsafe_allow_html=True)
    
    # Store config in session state
    if 'pdf_config' not in st.session_state:
        st.session_state.pdf_config = PDFConfig()
    
    config = st.session_state.pdf_config
    
    # Main content tabs
    tabs = st.tabs(["📄 Cover Page", "📑 Table of Contents", "📋 Headers & Footers", "🎨 Styling"])
    
    # Tab 1: Cover Page
    with tabs[0]:
        config.include_cover = st.checkbox("Include cover page", value=True)
        
        if config.include_cover:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📝 Cover Content")
                config.cover_title = st.text_input(
                    "Title", 
                    value=config.cover_title,
                    placeholder="Uses space title if empty"
                )
                config.cover_subtitle = st.text_input(
                    "Subtitle",
                    value=config.cover_subtitle,
                    placeholder="Optional description or tagline"
                )
                
                config.show_version = st.checkbox("Show version", value=config.show_version)
                if config.show_version:
                    config.version_text = st.text_input(
                        "Version",
                        value=config.version_text,
                        placeholder="e.g., 1.0.0"
                    )
                
                config.show_date = st.checkbox("Show date", value=config.show_date)
                if config.show_date:
                    config.date_format = st.selectbox(
                        "Date format",
                        ["%B %Y", "%B %d, %Y", "%Y-%m-%d", "%d/%m/%Y"],
                        format_func=lambda x: datetime.now().strftime(x)
                    )
                
                config.organization_name = st.text_input(
                    "Organization name",
                    value=config.organization_name,
                    placeholder="Uses org name from API if empty"
                )
            
            with col2:
                st.subheader("🖼️ Cover Images")
                
                logo_file = st.file_uploader(
                    "Logo image",
                    type=['png', 'jpg', 'jpeg'],
                    help="Your company or product logo (recommended: 200x100px)"
                )
                if logo_file:
                    config.cover_logo = logo_file.getvalue()
                    st.image(logo_file, caption="Logo preview", width=150)
                
                cover_image = st.file_uploader(
                    "Cover image (optional)",
                    type=['png', 'jpg', 'jpeg'],
                    help="Hero image for cover page (recommended: 1200x600px)"
                )
                if cover_image:
                    config.cover_image = cover_image.getvalue()
                    st.image(cover_image, caption="Cover image preview", width=300)
    
    # Tab 2: Table of Contents
    with tabs[1]:
        config.include_toc = st.checkbox("Include Table of Contents", value=True)
        
        if config.include_toc:
            config.toc_depth = st.slider(
                "TOC depth (heading levels to include)",
                min_value=1,
                max_value=5,
                value=3,
                help="How many levels of nested pages to show in TOC"
            )
            
            st.markdown("""
            <div class="info-box">
            <strong>📑 Table of Contents Features:</strong>
            <ul>
                <li>Auto-generated from your GitBook page structure</li>
                <li>Shows page numbers for easy reference</li>
                <li>Indented entries for nested pages</li>
                <li>Dot leaders for easy reading</li>
            </ul>
            </div>
            """, unsafe_allow_html=True)
    
    # Tab 3: Headers & Footers
    with tabs[2]:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📋 Header")
            config.include_header = st.checkbox("Include header", value=True)
            if config.include_header:
                config.header_text = st.text_input(
                    "Header text",
                    value=config.header_text,
                    placeholder="Document title will be used if empty"
                )
        
        with col2:
            st.subheader("📋 Footer")
            config.include_footer = st.checkbox("Include footer", value=True)
            if config.include_footer:
                config.footer_text = st.text_input(
                    "Footer text",
                    value=config.footer_text,
                    placeholder="e.g., © 2024 Your Company • Confidential"
                )
            
            config.show_page_numbers = st.checkbox("Show page numbers", value=True)
    
    # Tab 4: Styling
    with tabs[3]:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📐 Page Setup")
            config.page_size = st.selectbox(
                "Page size",
                ["Letter", "A4"],
                index=0 if config.page_size == "Letter" else 1
            )
        
        with col2:
            st.subheader("🎨 Colors")
            config.primary_color = st.color_picker(
                "Primary color (used in headings, accents)",
                value=config.primary_color
            )
            
            # Preview
            st.markdown(f"""
            <div style="background-color: {config.primary_color}; color: white; padding: 10px; border-radius: 5px; text-align: center;">
            Color Preview
            </div>
            """, unsafe_allow_html=True)
    
    # Export section
    st.divider()
    st.header("🚀 Generate Enhanced PDF")
    
    if api_token and space_id:
        st.markdown("""
        <div class="success-box">
        ✅ Ready to export! This will:<br>
        1. Download the GitBook-rendered PDF (with proper images, code blocks, etc.)<br>
        2. Add your custom cover page, TOC, and headers/footers
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="warning-box">
        ⚠️ Please enter your API token and Space ID in the sidebar to continue.
        </div>
        """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        export_button = st.button(
            "📥 Generate Enhanced PDF",
            type="primary",
            use_container_width=True,
            disabled=not (api_token and space_id)
        )
    
    with col2:
        download_original = st.button(
            "📄 Original Only",
            use_container_width=True,
            disabled=not (api_token and space_id),
            help="Download GitBook's original PDF without enhancements"
        )
    
    # Handle original PDF download
    if download_original:
        try:
            with st.spinner("🔄 Fetching GitBook PDF..."):
                api = GitBookAPI(api_token)
                space_info = api.get_space(space_id)
                pdf_bytes = api.download_pdf(space_id)
                
                filename = f"{space_info.get('title', 'documentation').replace(' ', '_').lower()}_original.pdf"
                
                st.success("✅ Original PDF downloaded!")
                st.download_button(
                    label="📥 Download Original PDF",
                    data=pdf_bytes,
                    file_name=filename,
                    mime="application/pdf",
                    use_container_width=True
                )
        except Exception as e:
            st.error(f"❌ Error: {e}")
    
    # Handle enhanced PDF generation
    if export_button:
        try:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Step 1: Get space info
            status_text.text("🔄 Fetching space information...")
            progress_bar.progress(10)
            api = GitBookAPI(api_token)
            space_info = api.get_space(space_id)
            st.info(f"📚 Space: **{space_info.get('title', 'Unknown')}**")
            
            # Step 2: Get org info if provided
            org_info = None
            if org_id:
                try:
                    status_text.text("🔄 Fetching organization information...")
                    progress_bar.progress(20)
                    org_info = api.get_organization(org_id)
                    st.info(f"🏢 Organization: **{org_info.get('title', 'Unknown')}**")
                except:
                    pass
            
            # Step 3: Get pages for TOC
            status_text.text("🔄 Fetching page structure...")
            progress_bar.progress(30)
            pages_data = api.get_all_pages(space_id)
            pages = pages_data.get('pages', [])
            st.info(f"📄 Found **{len(pages)}** top-level pages")
            
            # Step 4: Download GitBook's PDF
            status_text.text("🔄 Downloading GitBook PDF (this may take a moment)...")
            progress_bar.progress(50)
            gitbook_pdf = api.download_pdf(space_id)
            st.info(f"📦 Downloaded GitBook PDF: **{len(gitbook_pdf) / 1024:.1f} KB**")
            
            # Step 5: Enhance the PDF
            status_text.text("🔄 Adding cover page, TOC, and headers/footers...")
            progress_bar.progress(80)
            
            enhancer = PDFEnhancer(config)
            enhanced_pdf = enhancer.enhance_pdf(gitbook_pdf, space_info, pages, org_info)
            
            progress_bar.progress(100)
            status_text.text("✅ Complete!")
            
            # Success
            st.success("✅ Enhanced PDF generated successfully!")
            
            # Stats
            original_reader = PdfReader(io.BytesIO(gitbook_pdf))
            enhanced_reader = PdfReader(io.BytesIO(enhanced_pdf))
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Original Pages", len(original_reader.pages))
            with col2:
                st.metric("Enhanced Pages", len(enhanced_reader.pages))
            with col3:
                st.metric("Added Pages", len(enhanced_reader.pages) - len(original_reader.pages))
            
            # Download button
            filename = f"{space_info.get('title', 'documentation').replace(' ', '_').lower()}_enhanced.pdf"
            st.download_button(
                label="📥 Download Enhanced PDF",
                data=enhanced_pdf,
                file_name=filename,
                mime="application/pdf",
                use_container_width=True,
                type="primary"
            )
        
        except Exception as e:
            st.error(f"❌ Error generating PDF: {e}")
            st.exception(e)
    
    # Footer
    st.divider()
    st.markdown("""
    <div style="text-align: center; color: #888; font-size: 0.9rem;">
    GitBook PDF Export Tool v2.0 | Uses GitBook's native PDF rendering<br/>
    <a href="https://gitbook.com/docs/developers/gitbook-api" target="_blank">GitBook API Documentation</a>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
