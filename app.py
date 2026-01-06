"""
GitBook PDF Export Tool - Enhanced Edition v3
Uses GitBook's native PDF export as base, then adds:
- Custom cover page with branding
- Table of contents
- Headers and footers with optional logo
"""

import streamlit as st
import requests
import io
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass, field
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, mm
from reportlab.lib.colors import HexColor, black
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from PIL import Image as PILImage
import tempfile
import os
import time

# Page configuration
st.set_page_config(
    page_title="GitBook PDF Export Tool",
    page_icon="📚",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1a1a2e;
        margin-bottom: 0.5rem;
    }
    .section-header {
        font-size: 1.1rem;
        font-weight: 600;
        color: #333;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
        padding-bottom: 0.3rem;
        border-bottom: 2px solid #0066cc;
    }
</style>
""", unsafe_allow_html=True)


@dataclass
class PDFConfig:
    """Configuration for PDF enhancement"""
    # Cover page
    include_cover: bool = True
    cover_title: str = ""
    cover_subtitle: str = ""
    cover_logo: Optional[bytes] = None
    show_version: bool = False
    version_text: str = ""
    show_date: bool = True
    date_format: str = "%B %Y"
    
    # Table of contents
    include_toc: bool = True
    
    # Header/Footer
    include_header: bool = True
    header_text: str = ""
    include_footer: bool = True
    footer_text: str = ""
    footer_logo: Optional[bytes] = None
    show_page_numbers: bool = True
    
    # Styling
    primary_color: str = "#0066cc"
    
    # Organization
    organization_name: str = ""
    organization_logo_url: str = ""


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
            status = response.status_code
            if status == 401:
                raise Exception("Invalid API token. Please check your credentials.")
            elif status == 404:
                raise Exception("Resource not found. Please verify the Space ID.")
            elif status == 403:
                raise Exception("Access denied. Check permissions or if PDF export requires a Premium/Ultimate plan.")
            else:
                raise Exception(f"API Error ({status}): {str(e)}")
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
    
    def get_pdf_url(self, space_id: str) -> str:
        """Get the URL for PDF export"""
        result = self._make_request("GET", f"/spaces/{space_id}/pdf")
        url = result.get('url', '')
        if not url:
            raise Exception("Could not get PDF URL. PDF export may require a Premium or Ultimate GitBook plan.")
        return url
    
    def download_pdf(self, space_id: str) -> bytes:
        """Download the GitBook-generated PDF"""
        pdf_url = self.get_pdf_url(space_id)
        
        # Download with streaming to handle large files
        response = requests.get(pdf_url, timeout=300, stream=True)
        response.raise_for_status()
        
        # Check content type
        content_type = response.headers.get('content-type', '')
        if 'html' in content_type.lower():
            raise Exception("Received HTML instead of PDF. The PDF export URL may have expired or be invalid.")
        
        # Read content
        content = response.content
        
        # Verify it's a PDF
        if not content.startswith(b'%PDF'):
            raise Exception("Downloaded content is not a valid PDF file.")
        
        return content


class PDFEnhancer:
    """Enhance GitBook PDF with cover page, TOC, headers/footers"""
    
    def __init__(self, config: PDFConfig):
        self.config = config
        self.page_size = A4
        self.width, self.height = self.page_size
        self.primary_color = HexColor(config.primary_color)
        
    def _draw_image_from_bytes(self, c, img_bytes: bytes, x: float, y: float, 
                                max_width: float, max_height: float) -> float:
        """Draw an image from bytes and return the height used"""
        try:
            img = PILImage.open(io.BytesIO(img_bytes))
            
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Save to temp file
            with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                img.save(tmp.name, 'JPEG', quality=95)
                tmp_path = tmp.name
            
            # Calculate dimensions
            aspect = img.width / img.height
            if aspect > max_width / max_height:
                img_width = max_width
                img_height = img_width / aspect
            else:
                img_height = max_height
                img_width = img_height * aspect
            
            c.drawImage(tmp_path, x, y - img_height, width=img_width, height=img_height)
            
            os.unlink(tmp_path)
            return img_height
        except Exception as e:
            st.warning(f"Could not load image: {e}")
            return 0
    
    def _create_cover_page(self, space_info: dict, org_info: dict = None) -> bytes:
        """Create a cover page"""
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=self.page_size)
        
        width, height = self.page_size
        
        # Background
        c.setFillColor(HexColor('#f8f9fa'))
        c.rect(0, 0, width, height, fill=True, stroke=False)
        
        # Top accent bar
        c.setFillColor(self.primary_color)
        c.rect(0, height - 15, width, 15, fill=True, stroke=False)
        
        current_y = height - 80
        
        # Logo
        if self.config.cover_logo:
            img_height = self._draw_image_from_bytes(
                c, self.config.cover_logo,
                (width - 2.5*inch) / 2, current_y,
                2.5*inch, 1.2*inch
            )
            if img_height > 0:
                current_y -= img_height + 40
        
        # Title
        title = self.config.cover_title or space_info.get('title', 'Documentation')
        c.setFillColor(HexColor('#1a1a2e'))
        
        title_size = 36 if len(title) <= 30 else (30 if len(title) <= 45 else 24)
        c.setFont("Helvetica-Bold", title_size)
        
        # Wrap title if needed
        max_title_width = width - 100
        title_width = stringWidth(title, "Helvetica-Bold", title_size)
        
        if title_width > max_title_width:
            words = title.split()
            lines = []
            current_line = []
            for word in words:
                test = ' '.join(current_line + [word])
                if stringWidth(test, "Helvetica-Bold", title_size) < max_title_width:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                    current_line = [word]
            if current_line:
                lines.append(' '.join(current_line))
            
            for line in lines:
                lw = stringWidth(line, "Helvetica-Bold", title_size)
                c.drawString((width - lw) / 2, current_y, line)
                current_y -= title_size + 10
        else:
            c.drawString((width - title_width) / 2, current_y, title)
            current_y -= title_size + 20
        
        # Subtitle
        if self.config.cover_subtitle:
            c.setFont("Helvetica", 14)
            c.setFillColor(HexColor('#666666'))
            sub_width = stringWidth(self.config.cover_subtitle, "Helvetica", 14)
            c.drawString((width - sub_width) / 2, current_y, self.config.cover_subtitle)
            current_y -= 30
        
        # Decorative line
        current_y -= 20
        c.setStrokeColor(self.primary_color)
        c.setLineWidth(2)
        c.line((width - 3*inch) / 2, current_y, (width + 3*inch) / 2, current_y)
        
        # Meta info at bottom
        meta_y = 120
        c.setFont("Helvetica", 11)
        c.setFillColor(HexColor('#888888'))
        
        meta_lines = []
        if self.config.show_version and self.config.version_text:
            meta_lines.append(f"Version {self.config.version_text}")
        if self.config.show_date:
            meta_lines.append(datetime.now().strftime(self.config.date_format))
        
        org_name = self.config.organization_name
        if not org_name and org_info:
            org_name = org_info.get('title', '')
        if org_name:
            meta_lines.append(org_name)
        
        for line in meta_lines:
            lw = stringWidth(line, "Helvetica", 11)
            c.drawString((width - lw) / 2, meta_y, line)
            meta_y -= 18
        
        # Bottom accent bar
        c.setFillColor(self.primary_color)
        c.rect(0, 0, width, 8, fill=True, stroke=False)
        
        c.save()
        buffer.seek(0)
        return buffer.getvalue()
    
    def _create_toc_pages(self, pages: List[dict]) -> bytes:
        """Create table of contents"""
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=self.page_size)
        
        width, height = self.page_size
        margin = 60
        
        # Build TOC entries (groups, pages, subpages)
        toc_entries = []
        
        def process_pages(page_list: List[dict], depth: int = 0):
            for page in page_list:
                if page.get('type') == 'link':
                    continue
                
                # Include up to 3 levels (group, page, subpage)
                if depth <= 2:
                    toc_entries.append({
                        'title': page.get('title', 'Untitled'),
                        'level': depth
                    })
                
                if page.get('pages'):
                    process_pages(page['pages'], depth + 1)
        
        process_pages(pages)
        
        # Calculate pages needed
        entries_per_page = 40
        num_toc_pages = max(1, (len(toc_entries) + entries_per_page - 1) // entries_per_page)
        
        # Assign page numbers (cover=1, toc pages, then content)
        front_matter = 1 + num_toc_pages
        for i, entry in enumerate(toc_entries):
            entry['page'] = front_matter + i + 1  # Simplified: each entry = 1 page
        
        # Draw TOC
        current_entry = 0
        for toc_page_num in range(num_toc_pages):
            y = height - margin
            
            if toc_page_num == 0:
                c.setFont("Helvetica-Bold", 24)
                c.setFillColor(self.primary_color)
                c.drawString(margin, y, "Table of Contents")
                y -= 45
            
            entries_drawn = 0
            while current_entry < len(toc_entries) and entries_drawn < entries_per_page:
                entry = toc_entries[current_entry]
                level = entry['level']
                title = entry['title']
                
                indent = level * 18
                
                # Style by level
                if level == 0:
                    c.setFont("Helvetica-Bold", 11)
                    c.setFillColor(self.primary_color)
                elif level == 1:
                    c.setFont("Helvetica", 10)
                    c.setFillColor(HexColor('#333333'))
                else:
                    c.setFont("Helvetica", 9)
                    c.setFillColor(HexColor('#666666'))
                
                # Truncate if needed
                max_w = width - 2*margin - indent - 40
                display_title = title
                while stringWidth(display_title, c._fontname, c._fontsize) > max_w and len(display_title) > 10:
                    display_title = display_title[:-4] + "..."
                
                c.drawString(margin + indent, y, display_title)
                
                y -= 16 if level == 0 else 14
                current_entry += 1
                entries_drawn += 1
                
                if y < margin + 40:
                    break
            
            if current_entry < len(toc_entries):
                c.showPage()
        
        c.save()
        buffer.seek(0)
        return buffer.getvalue()
    
    def _add_headers_footers(self, input_pdf: bytes, start_page: int = 1) -> bytes:
        """Add headers and footers to PDF pages"""
        reader = PdfReader(io.BytesIO(input_pdf))
        writer = PdfWriter()
        
        # Prepare footer logo if provided
        footer_logo_path = None
        if self.config.footer_logo:
            try:
                img = PILImage.open(io.BytesIO(self.config.footer_logo))
                if img.mode in ('RGBA', 'P'):
                    img = img.convert('RGB')
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp:
                    img.save(tmp.name, 'JPEG', quality=90)
                    footer_logo_path = tmp.name
            except:
                pass
        
        for i, page in enumerate(reader.pages):
            # Get page dimensions
            page_box = page.mediabox
            page_width = float(page_box.width)
            page_height = float(page_box.height)
            
            # Create overlay
            overlay_buffer = io.BytesIO()
            c = canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))
            
            page_num = start_page + i
            
            # Header
            if self.config.include_header:
                header_text = self.config.header_text or self.config.cover_title or "Documentation"
                c.setFont("Helvetica", 8)
                c.setFillColor(HexColor('#999999'))
                c.drawString(50, page_height - 30, header_text)
                c.setStrokeColor(HexColor('#e0e0e0'))
                c.setLineWidth(0.5)
                c.line(50, page_height - 38, page_width - 50, page_height - 38)
            
            # Footer
            if self.config.include_footer or self.config.show_page_numbers:
                c.setStrokeColor(HexColor('#e0e0e0'))
                c.setLineWidth(0.5)
                c.line(50, 38, page_width - 50, 38)
                
                c.setFont("Helvetica", 8)
                c.setFillColor(HexColor('#999999'))
                
                # Footer logo on left
                logo_width = 0
                if footer_logo_path:
                    try:
                        c.drawImage(footer_logo_path, 50, 18, width=50, height=16, preserveAspectRatio=True)
                        logo_width = 60
                    except:
                        pass
                
                # Footer text
                if self.config.footer_text:
                    c.drawString(50 + logo_width, 22, self.config.footer_text)
                
                # Page number on right
                if self.config.show_page_numbers:
                    c.drawRightString(page_width - 50, 22, f"Page {page_num}")
            
            c.save()
            overlay_buffer.seek(0)
            
            # Merge
            overlay_reader = PdfReader(overlay_buffer)
            if overlay_reader.pages:
                page.merge_page(overlay_reader.pages[0])
            
            writer.add_page(page)
        
        # Cleanup
        if footer_logo_path and os.path.exists(footer_logo_path):
            os.unlink(footer_logo_path)
        
        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        return output.getvalue()
    
    def enhance_pdf(self, gitbook_pdf: bytes, space_info: dict, pages: List[dict], org_info: dict = None) -> bytes:
        """Enhance the GitBook PDF"""
        
        # Verify input is valid PDF
        if not gitbook_pdf.startswith(b'%PDF'):
            raise Exception("Input is not a valid PDF file")
        
        original_reader = PdfReader(io.BytesIO(gitbook_pdf))
        writer = PdfWriter()
        
        # 1. Add cover page
        if self.config.include_cover:
            cover_pdf = self._create_cover_page(space_info, org_info)
            cover_reader = PdfReader(io.BytesIO(cover_pdf))
            for page in cover_reader.pages:
                writer.add_page(page)
        
        # 2. Add TOC
        toc_pages_count = 0
        if self.config.include_toc and pages:
            toc_pdf = self._create_toc_pages(pages)
            toc_reader = PdfReader(io.BytesIO(toc_pdf))
            toc_pages_count = len(toc_reader.pages)
            for page in toc_reader.pages:
                writer.add_page(page)
        
        # Calculate content start page
        content_start = 1
        if self.config.include_cover:
            content_start += 1
        content_start += toc_pages_count
        
        # 3. Add headers/footers to content
        if self.config.include_header or self.config.include_footer or self.config.show_page_numbers:
            enhanced_content = self._add_headers_footers(gitbook_pdf, start_page=content_start)
            enhanced_reader = PdfReader(io.BytesIO(enhanced_content))
            for page in enhanced_reader.pages:
                writer.add_page(page)
        else:
            for page in original_reader.pages:
                writer.add_page(page)
        
        # 4. Metadata
        writer.add_metadata({
            '/Title': self.config.cover_title or space_info.get('title', 'Documentation'),
            '/Author': self.config.organization_name or (org_info.get('title') if org_info else 'GitBook'),
            '/Creator': 'GitBook PDF Export Tool'
        })
        
        output = io.BytesIO()
        writer.write(output)
        output.seek(0)
        return output.getvalue()


def main():
    """Main application"""
    
    st.markdown('<h1 class="main-header">📚 GitBook PDF Export Tool</h1>', unsafe_allow_html=True)
    st.caption("Enhance your GitBook PDF exports with cover pages, table of contents, and branding.")
    
    # Initialize config
    if 'pdf_config' not in st.session_state:
        st.session_state.pdf_config = PDFConfig()
    config = st.session_state.pdf_config
    
    # Sidebar: API Configuration
    with st.sidebar:
        st.header("🔑 Configuration")
        
        # Load defaults from secrets
        default_token = ""
        default_space = ""
        default_org = ""
        try:
            default_token = st.secrets.get("GITBOOK_API_TOKEN", "")
            default_space = st.secrets.get("DEFAULT_SPACE_ID", "")
            default_org = st.secrets.get("DEFAULT_ORG_ID", "")
        except:
            pass
        
        api_token = st.text_input("API Token", value=default_token, type="password")
        space_id = st.text_input("Space ID", value=default_space)
        org_id = st.text_input("Organization ID (optional)", value=default_org)
        
        st.divider()
        
        if st.button("🔍 Test Connection", use_container_width=True):
            if api_token and space_id:
                try:
                    api = GitBookAPI(api_token)
                    space = api.get_space(space_id)
                    st.success(f"✅ Connected to: **{space.get('title')}**")
                    
                    if org_id:
                        try:
                            org = api.get_organization(org_id)
                            st.success(f"🏢 Org: **{org.get('title')}**")
                            # Store org logo URL if available
                            if org.get('urls', {}).get('logo'):
                                config.organization_logo_url = org['urls']['logo']
                        except:
                            st.warning("Could not fetch organization info")
                except Exception as e:
                    st.error(f"❌ {e}")
            else:
                st.warning("Enter API token and Space ID")
    
    # Main content - Single page layout
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.markdown('<p class="section-header">📄 Cover Page</p>', unsafe_allow_html=True)
        
        config.include_cover = st.checkbox("Include cover page", value=config.include_cover)
        
        if config.include_cover:
            config.cover_title = st.text_input("Title", value=config.cover_title, placeholder="Uses space title if empty")
            config.cover_subtitle = st.text_input("Subtitle", value=config.cover_subtitle, placeholder="Optional tagline")
            
            col_v, col_d = st.columns(2)
            with col_v:
                config.show_version = st.checkbox("Show version", value=config.show_version)
                if config.show_version:
                    config.version_text = st.text_input("Version", value=config.version_text, placeholder="e.g., 1.0")
            with col_d:
                config.show_date = st.checkbox("Show date", value=config.show_date)
            
            config.organization_name = st.text_input("Organization", value=config.organization_name, placeholder="Auto-detected if org ID provided")
            
            logo_file = st.file_uploader("Cover Logo", type=['png', 'jpg', 'jpeg'], key="cover_logo")
            if logo_file:
                config.cover_logo = logo_file.getvalue()
                st.image(logo_file, width=100)
        
        st.markdown('<p class="section-header">📑 Table of Contents</p>', unsafe_allow_html=True)
        config.include_toc = st.checkbox("Include table of contents", value=config.include_toc)
    
    with col_right:
        st.markdown('<p class="section-header">📋 Header</p>', unsafe_allow_html=True)
        
        config.include_header = st.checkbox("Include header", value=config.include_header)
        if config.include_header:
            config.header_text = st.text_input("Header text", value=config.header_text, placeholder="Uses title if empty")
        
        st.markdown('<p class="section-header">📋 Footer</p>', unsafe_allow_html=True)
        
        config.include_footer = st.checkbox("Include footer", value=config.include_footer)
        if config.include_footer:
            config.footer_text = st.text_input("Footer text", value=config.footer_text, placeholder="e.g., © 2024 Company")
            
            footer_logo_file = st.file_uploader("Footer Logo (optional)", type=['png', 'jpg', 'jpeg'], key="footer_logo")
            if footer_logo_file:
                config.footer_logo = footer_logo_file.getvalue()
                st.image(footer_logo_file, width=80)
            
            # Option to use org logo
            if config.organization_logo_url and not footer_logo_file:
                if st.checkbox("Use organization logo in footer"):
                    try:
                        resp = requests.get(config.organization_logo_url, timeout=10)
                        if resp.status_code == 200:
                            config.footer_logo = resp.content
                            st.success("✓ Using organization logo")
                    except:
                        st.warning("Could not fetch organization logo")
        
        config.show_page_numbers = st.checkbox("Show page numbers", value=config.show_page_numbers)
        
        st.markdown('<p class="section-header">🎨 Styling</p>', unsafe_allow_html=True)
        config.primary_color = st.color_picker("Primary color", value=config.primary_color)
    
    # Export Section
    st.divider()
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        export_btn = st.button(
            "📥 Generate Enhanced PDF",
            type="primary",
            use_container_width=True,
            disabled=not (api_token and space_id)
        )
    
    with col2:
        original_btn = st.button(
            "📄 Original Only",
            use_container_width=True,
            disabled=not (api_token and space_id)
        )
    
    # Handle export
    if export_btn or original_btn:
        try:
            api = GitBookAPI(api_token)
            
            with st.status("Generating PDF...", expanded=True) as status:
                st.write("Fetching space information...")
                space_info = api.get_space(space_id)
                
                org_info = None
                if org_id:
                    try:
                        st.write("Fetching organization...")
                        org_info = api.get_organization(org_id)
                    except:
                        pass
                
                st.write("Fetching page structure...")
                pages_data = api.get_all_pages(space_id)
                pages = pages_data.get('pages', [])
                
                st.write("Downloading GitBook PDF (this may take a moment)...")
                gitbook_pdf = api.download_pdf(space_id)
                st.write(f"Downloaded: {len(gitbook_pdf) / 1024:.1f} KB")
                
                if original_btn:
                    # Just return original
                    final_pdf = gitbook_pdf
                    filename = f"{space_info.get('title', 'doc').replace(' ', '_')}_original.pdf"
                else:
                    # Enhance
                    st.write("Adding cover, TOC, and headers/footers...")
                    enhancer = PDFEnhancer(config)
                    final_pdf = enhancer.enhance_pdf(gitbook_pdf, space_info, pages, org_info)
                    filename = f"{space_info.get('title', 'doc').replace(' ', '_')}_enhanced.pdf"
                
                status.update(label="✅ Complete!", state="complete")
            
            # Download button
            st.download_button(
                label="📥 Download PDF",
                data=final_pdf,
                file_name=filename,
                mime="application/pdf",
                use_container_width=True,
                type="primary"
            )
            
            # Stats
            reader = PdfReader(io.BytesIO(final_pdf))
            st.info(f"📊 Generated PDF: **{len(reader.pages)} pages** | **{len(final_pdf)/1024:.1f} KB**")
            
        except Exception as e:
            st.error(f"❌ Error: {e}")
            st.exception(e)
    
    # Footer
    st.divider()
    st.caption("GitBook PDF Export Tool v3.0 • [API Documentation](https://gitbook.com/docs/developers/gitbook-api)")


if __name__ == "__main__":
    main()
