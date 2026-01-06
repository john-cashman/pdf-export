"""
GitBook PDF Export Tool - Enhanced Edition
A Streamlit app for exporting GitBook content to professionally formatted PDFs
with cover pages, table of contents, headers/footers, and branding options.
"""

import streamlit as st
import requests
import io
import base64
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, black, white
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image,
    Table, TableStyle, ListFlowable, ListItem, KeepTogether,
    Preformatted, HRFlowable, CondPageBreak
)
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage
import markdown
from bs4 import BeautifulSoup
import re
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
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 1rem 2rem;
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
    """Configuration for PDF generation"""
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
    
    # Styling
    page_size: str = "Letter"
    primary_color: str = "#0066cc"
    font_family: str = "Helvetica"
    base_font_size: int = 11
    
    # Content options
    include_hidden_pages: bool = False
    include_page_descriptions: bool = True
    code_syntax_highlighting: bool = True


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
            response = requests.request(method, url, headers=self.headers, params=params)
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
    
    def get_space_content(self, space_id: str) -> dict:
        """Get current revision content of a space"""
        return self._make_request("GET", f"/spaces/{space_id}/content")
    
    def get_all_pages(self, space_id: str) -> dict:
        """Get all pages in a space"""
        return self._make_request("GET", f"/spaces/{space_id}/content/pages")
    
    def get_page_by_id(self, space_id: str, page_id: str, format: str = "markdown") -> dict:
        """Get a specific page with content in markdown format"""
        return self._make_request(
            "GET", 
            f"/spaces/{space_id}/content/page/{page_id}",
            params={"format": format, "dereferenced": "reusable-contents"}
        )
    
    def get_page_document(self, space_id: str, page_id: str) -> dict:
        """Get the document structure of a page"""
        return self._make_request("GET", f"/spaces/{space_id}/content/page/{page_id}")
    
    def get_files(self, space_id: str) -> dict:
        """Get all files in a space"""
        return self._make_request("GET", f"/spaces/{space_id}/content/files")
    
    def get_organization(self, org_id: str) -> dict:
        """Get organization information"""
        return self._make_request("GET", f"/orgs/{org_id}")
    
    def get_pdf_url(self, space_id: str, page_id: str = None, only_page: bool = False) -> dict:
        """Get the URL for PDF export (GitBook's built-in PDF)"""
        params = {}
        if page_id:
            params["page"] = page_id
            if only_page:
                params["only"] = True
        return self._make_request("GET", f"/spaces/{space_id}/pdf", params=params)


class PDFBuilder:
    """Build professional PDFs from GitBook content"""
    
    def __init__(self, config: PDFConfig):
        self.config = config
        self.page_size = letter if config.page_size == "Letter" else A4
        self.styles = self._create_styles()
        self.toc_entries = []
        self.current_page_num = 1
        
    def _create_styles(self) -> dict:
        """Create custom paragraph styles"""
        styles = getSampleStyleSheet()
        primary_color = HexColor(self.config.primary_color)
        
        # Title styles
        styles.add(ParagraphStyle(
            name='CoverTitle',
            parent=styles['Title'],
            fontSize=36,
            leading=44,
            alignment=TA_CENTER,
            textColor=primary_color,
            spaceAfter=20,
            fontName='Helvetica-Bold'
        ))
        
        styles.add(ParagraphStyle(
            name='CoverSubtitle',
            parent=styles['Normal'],
            fontSize=18,
            leading=24,
            alignment=TA_CENTER,
            textColor=HexColor('#666666'),
            spaceAfter=40,
            fontName='Helvetica'
        ))
        
        styles.add(ParagraphStyle(
            name='CoverMeta',
            parent=styles['Normal'],
            fontSize=12,
            leading=16,
            alignment=TA_CENTER,
            textColor=HexColor('#888888'),
            fontName='Helvetica'
        ))
        
        # TOC styles
        styles.add(ParagraphStyle(
            name='TOCHeading',
            parent=styles['Heading1'],
            fontSize=24,
            leading=30,
            textColor=primary_color,
            spaceAfter=30,
            fontName='Helvetica-Bold'
        ))
        
        for level in range(1, 4):
            styles.add(ParagraphStyle(
                name=f'TOCEntry{level}',
                parent=styles['Normal'],
                fontSize=12 - (level - 1),
                leading=18 - (level - 1) * 2,
                leftIndent=(level - 1) * 20,
                textColor=primary_color if level == 1 else black,
                fontName='Helvetica-Bold' if level == 1 else 'Helvetica',
                spaceAfter=6
            ))
        
        # Content heading styles
        heading_sizes = [24, 20, 16, 14, 12, 11]
        for i, size in enumerate(heading_sizes, 1):
            styles.add(ParagraphStyle(
                name=f'CustomHeading{i}',
                parent=styles['Normal'],
                fontSize=size,
                leading=size + 6,
                textColor=primary_color if i <= 2 else black,
                fontName='Helvetica-Bold',
                spaceBefore=16 if i <= 2 else 12,
                spaceAfter=8,
                keepWithNext=True
            ))
        
        # Body styles
        styles.add(ParagraphStyle(
            name='CustomBody',
            parent=styles['Normal'],
            fontSize=self.config.base_font_size,
            leading=self.config.base_font_size + 5,
            alignment=TA_JUSTIFY,
            spaceAfter=8,
            fontName='Helvetica'
        ))
        
        styles.add(ParagraphStyle(
            name='CodeBlock',
            parent=styles['Normal'],
            fontSize=9,
            leading=12,
            fontName='Courier',
            backColor=HexColor('#f5f5f5'),
            borderColor=HexColor('#e0e0e0'),
            borderWidth=1,
            borderPadding=8,
            spaceAfter=12,
            leftIndent=10,
            rightIndent=10
        ))
        
        styles.add(ParagraphStyle(
            name='InlineCode',
            parent=styles['Normal'],
            fontSize=10,
            fontName='Courier',
            backColor=HexColor('#f0f0f0'),
        ))
        
        styles.add(ParagraphStyle(
            name='BlockQuote',
            parent=styles['Normal'],
            fontSize=self.config.base_font_size,
            leading=self.config.base_font_size + 4,
            leftIndent=20,
            borderColor=primary_color,
            borderWidth=3,
            borderPadding=10,
            textColor=HexColor('#555555'),
            fontName='Helvetica-Oblique',
            spaceAfter=12
        ))
        
        styles.add(ParagraphStyle(
            name='Hint',
            parent=styles['Normal'],
            fontSize=self.config.base_font_size,
            leading=self.config.base_font_size + 4,
            leftIndent=15,
            backColor=HexColor('#e7f3ff'),
            borderColor=HexColor('#0066cc'),
            borderPadding=10,
            spaceAfter=12
        ))
        
        return styles
    
    def _create_cover_page(self, space_info: dict, org_info: dict = None) -> List:
        """Create a cover page"""
        elements = []
        
        # Add spacing at top
        elements.append(Spacer(1, 2 * inch))
        
        # Logo
        if self.config.cover_logo:
            try:
                logo_img = PILImage.open(io.BytesIO(self.config.cover_logo))
                aspect = logo_img.width / logo_img.height
                max_width = 3 * inch
                max_height = 1.5 * inch
                
                if aspect > 1:
                    img_width = min(logo_img.width, max_width)
                    img_height = img_width / aspect
                else:
                    img_height = min(logo_img.height, max_height)
                    img_width = img_height * aspect
                
                img = Image(io.BytesIO(self.config.cover_logo), width=img_width, height=img_height)
                img.hAlign = 'CENTER'
                elements.append(img)
                elements.append(Spacer(1, 0.5 * inch))
            except Exception as e:
                st.warning(f"Could not load cover logo: {e}")
        
        # Cover image
        if self.config.cover_image:
            try:
                cover_img = PILImage.open(io.BytesIO(self.config.cover_image))
                aspect = cover_img.width / cover_img.height
                max_width = 5 * inch
                max_height = 3 * inch
                
                if aspect > max_width / max_height:
                    img_width = max_width
                    img_height = img_width / aspect
                else:
                    img_height = max_height
                    img_width = img_height * aspect
                
                img = Image(io.BytesIO(self.config.cover_image), width=img_width, height=img_height)
                img.hAlign = 'CENTER'
                elements.append(img)
                elements.append(Spacer(1, 0.5 * inch))
            except Exception as e:
                st.warning(f"Could not load cover image: {e}")
        
        # Title
        title = self.config.cover_title or space_info.get('title', 'Documentation')
        elements.append(Paragraph(title, self.styles['CoverTitle']))
        
        # Subtitle
        if self.config.cover_subtitle:
            elements.append(Paragraph(self.config.cover_subtitle, self.styles['CoverSubtitle']))
        elif space_info.get('description'):
            elements.append(Paragraph(space_info.get('description', ''), self.styles['CoverSubtitle']))
        
        elements.append(Spacer(1, 1 * inch))
        
        # Version and Date
        meta_parts = []
        if self.config.show_version and self.config.version_text:
            meta_parts.append(f"Version: {self.config.version_text}")
        if self.config.show_date:
            date_str = datetime.now().strftime(self.config.date_format)
            meta_parts.append(date_str)
        
        if org_info and org_info.get('title'):
            meta_parts.append(f"Published by {org_info.get('title')}")
        
        if meta_parts:
            elements.append(Paragraph("<br/>".join(meta_parts), self.styles['CoverMeta']))
        
        elements.append(PageBreak())
        return elements
    
    def _create_toc(self, pages: List[dict], depth: int = 0) -> List:
        """Create table of contents"""
        elements = []
        
        if depth == 0:
            elements.append(Paragraph("Table of Contents", self.styles['TOCHeading']))
        
        for page in pages:
            if page.get('type') == 'link':
                continue
            
            if depth < self.config.toc_depth:
                level = min(depth + 1, 3)
                title = page.get('title', 'Untitled')
                
                # Store for bookmark linking
                page_id = page.get('id', '')
                self.toc_entries.append({
                    'title': title,
                    'id': page_id,
                    'level': level
                })
                
                entry_style = self.styles[f'TOCEntry{level}']
                elements.append(Paragraph(title, entry_style))
                
                # Process child pages
                if page.get('pages'):
                    child_elements = self._create_toc(page.get('pages', []), depth + 1)
                    elements.extend(child_elements)
        
        if depth == 0:
            elements.append(PageBreak())
        
        return elements
    
    def _markdown_to_elements(self, markdown_text: str) -> List:
        """Convert markdown content to ReportLab elements"""
        elements = []
        
        if not markdown_text:
            return elements
        
        # Convert markdown to HTML
        html = markdown.markdown(
            markdown_text,
            extensions=['tables', 'fenced_code', 'codehilite', 'toc']
        )
        
        # Parse HTML
        soup = BeautifulSoup(html, 'html.parser')
        
        for element in soup.children:
            if hasattr(element, 'name'):
                elements.extend(self._process_html_element(element))
        
        return elements
    
    def _process_html_element(self, element) -> List:
        """Process a single HTML element into ReportLab flowables"""
        flowables = []
        
        if element.name is None:
            # Text node
            text = str(element).strip()
            if text:
                flowables.append(Paragraph(text, self.styles['CustomBody']))
            return flowables
        
        tag = element.name.lower()
        
        # Headings
        if tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            level = int(tag[1])
            style = self.styles.get(f'CustomHeading{level}', self.styles['CustomHeading1'])
            text = element.get_text().strip()
            flowables.append(Paragraph(text, style))
        
        # Paragraphs
        elif tag == 'p':
            text = self._process_inline_elements(element)
            if text.strip():
                flowables.append(Paragraph(text, self.styles['CustomBody']))
        
        # Code blocks
        elif tag == 'pre':
            code_element = element.find('code')
            if code_element:
                code_text = code_element.get_text()
            else:
                code_text = element.get_text()
            
            # Clean up code text
            code_text = code_text.strip()
            code_text = code_text.replace('<', '&lt;').replace('>', '&gt;')
            code_text = code_text.replace('\n', '<br/>')
            
            flowables.append(Preformatted(code_text, self.styles['CodeBlock']))
        
        # Blockquotes
        elif tag == 'blockquote':
            text = self._process_inline_elements(element)
            flowables.append(Paragraph(text, self.styles['BlockQuote']))
        
        # Unordered lists
        elif tag == 'ul':
            items = []
            for li in element.find_all('li', recursive=False):
                item_text = self._process_inline_elements(li)
                items.append(ListItem(Paragraph(item_text, self.styles['CustomBody'])))
            
            if items:
                flowables.append(ListFlowable(items, bulletType='bullet', leftIndent=20))
        
        # Ordered lists
        elif tag == 'ol':
            items = []
            for i, li in enumerate(element.find_all('li', recursive=False), 1):
                item_text = self._process_inline_elements(li)
                items.append(ListItem(Paragraph(item_text, self.styles['CustomBody'])))
            
            if items:
                flowables.append(ListFlowable(items, bulletType='1', leftIndent=20))
        
        # Tables
        elif tag == 'table':
            table_data = []
            
            # Get headers
            headers = element.find_all('th')
            if headers:
                header_row = [self._process_inline_elements(th) for th in headers]
                table_data.append(header_row)
            
            # Get rows
            for row in element.find_all('tr'):
                cells = row.find_all(['td', 'th'])
                if cells and not (len(cells) == len(headers) and all(c.name == 'th' for c in cells)):
                    row_data = [self._process_inline_elements(cell) for cell in cells]
                    table_data.append(row_data)
            
            if table_data:
                # Create table with styling
                table = Table(table_data)
                style = TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), HexColor(self.config.primary_color)),
                    ('TEXTCOLOR', (0, 0), (-1, 0), white),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 10),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), HexColor('#f9f9f9')),
                    ('GRID', (0, 0), (-1, -1), 1, HexColor('#dddddd')),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ('TOPPADDING', (0, 1), (-1, -1), 6),
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                ])
                table.setStyle(style)
                flowables.append(table)
                flowables.append(Spacer(1, 12))
        
        # Horizontal rules
        elif tag == 'hr':
            flowables.append(HRFlowable(
                width="100%",
                thickness=1,
                color=HexColor('#dddddd'),
                spaceBefore=12,
                spaceAfter=12
            ))
        
        # Images
        elif tag == 'img':
            src = element.get('src', '')
            alt = element.get('alt', '')
            # Note: Would need to fetch images from URLs in a full implementation
            flowables.append(Paragraph(f"[Image: {alt or src}]", self.styles['CustomBody']))
        
        # Divs and other containers
        elif tag in ['div', 'section', 'article']:
            for child in element.children:
                if hasattr(child, 'name') or str(child).strip():
                    flowables.extend(self._process_html_element(child))
        
        return flowables
    
    def _process_inline_elements(self, element) -> str:
        """Process inline elements and return formatted text"""
        if element is None:
            return ""
        
        if isinstance(element, str):
            return element
        
        parts = []
        for child in element.children:
            if isinstance(child, str):
                parts.append(child)
            elif hasattr(child, 'name'):
                tag = child.name.lower()
                text = self._process_inline_elements(child)
                
                if tag in ['strong', 'b']:
                    parts.append(f"<b>{text}</b>")
                elif tag in ['em', 'i']:
                    parts.append(f"<i>{text}</i>")
                elif tag == 'code':
                    parts.append(f"<font face='Courier' size='9' backColor='#f0f0f0'>{text}</font>")
                elif tag == 'a':
                    href = child.get('href', '')
                    parts.append(f"<a href='{href}' color='blue'><u>{text}</u></a>")
                elif tag == 'br':
                    parts.append("<br/>")
                else:
                    parts.append(text)
        
        return ''.join(parts)
    
    def _process_pages(self, api: GitBookAPI, space_id: str, pages: List[dict], depth: int = 0) -> List:
        """Process all pages and convert to PDF elements"""
        elements = []
        
        for page in pages:
            page_type = page.get('type', 'document')
            
            # Skip links and groups that are just containers
            if page_type == 'link':
                continue
            
            # Skip hidden pages if configured
            if page.get('hidden') and not self.config.include_hidden_pages:
                continue
            
            # Add page title
            title = page.get('title', 'Untitled')
            heading_level = min(depth + 1, 6)
            style = self.styles.get(f'CustomHeading{heading_level}', self.styles['CustomHeading1'])
            
            # Add conditional page break for top-level pages
            if depth == 0:
                elements.append(CondPageBreak(3 * inch))
            
            elements.append(Paragraph(title, style))
            
            # Add description if available and configured
            if self.config.include_page_descriptions and page.get('description'):
                desc_style = ParagraphStyle(
                    'PageDescription',
                    parent=self.styles['CustomBody'],
                    textColor=HexColor('#666666'),
                    fontName='Helvetica-Oblique',
                    spaceAfter=16
                )
                elements.append(Paragraph(page.get('description'), desc_style))
            
            # Get page content if it's a document
            if page_type == 'document' and page.get('id'):
                try:
                    page_detail = api.get_page_by_id(space_id, page['id'], format='markdown')
                    markdown_content = page_detail.get('markdown', '')
                    
                    if markdown_content:
                        content_elements = self._markdown_to_elements(markdown_content)
                        elements.extend(content_elements)
                except Exception as e:
                    st.warning(f"Could not fetch content for page '{title}': {e}")
            
            elements.append(Spacer(1, 12))
            
            # Process child pages recursively
            if page.get('pages'):
                child_elements = self._process_pages(api, space_id, page['pages'], depth + 1)
                elements.extend(child_elements)
        
        return elements
    
    def build_pdf(self, api: GitBookAPI, space_id: str, space_info: dict, 
                  pages: List[dict], org_info: dict = None) -> bytes:
        """Build the complete PDF document"""
        buffer = io.BytesIO()
        
        # Create document with custom page template
        doc = SimpleDocTemplate(
            buffer,
            pagesize=self.page_size,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72,
            title=self.config.cover_title or space_info.get('title', 'Documentation'),
            author=org_info.get('title') if org_info else 'GitBook'
        )
        
        # Build story (list of flowables)
        story = []
        
        # Cover page
        if self.config.include_cover:
            cover_elements = self._create_cover_page(space_info, org_info)
            story.extend(cover_elements)
        
        # Table of contents
        if self.config.include_toc:
            toc_elements = self._create_toc(pages)
            story.extend(toc_elements)
        
        # Content pages
        content_elements = self._process_pages(api, space_id, pages)
        story.extend(content_elements)
        
        # Build PDF with custom header/footer
        def add_header_footer(canvas_obj, doc):
            canvas_obj.saveState()
            
            # Header
            if self.config.include_header:
                header_text = self.config.header_text or space_info.get('title', '')
                canvas_obj.setFont('Helvetica', 9)
                canvas_obj.setFillColor(HexColor('#888888'))
                canvas_obj.drawString(72, self.page_size[1] - 50, header_text)
                canvas_obj.line(72, self.page_size[1] - 55, self.page_size[0] - 72, self.page_size[1] - 55)
            
            # Footer
            if self.config.include_footer or self.config.show_page_numbers:
                canvas_obj.setFont('Helvetica', 9)
                canvas_obj.setFillColor(HexColor('#888888'))
                
                # Footer line
                canvas_obj.line(72, 50, self.page_size[0] - 72, 50)
                
                # Footer text
                if self.config.include_footer and self.config.footer_text:
                    canvas_obj.drawString(72, 35, self.config.footer_text)
                
                # Page number
                if self.config.show_page_numbers:
                    page_num = f"Page {doc.page}"
                    canvas_obj.drawRightString(self.page_size[0] - 72, 35, page_num)
            
            canvas_obj.restoreState()
        
        # Build the document
        doc.build(story, onFirstPage=add_header_footer, onLaterPages=add_header_footer)
        
        buffer.seek(0)
        return buffer.getvalue()


def main():
    """Main application entry point"""
    
    # Header
    st.markdown('<h1 class="main-header">📚 GitBook PDF Export Tool</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Export your GitBook documentation to professionally formatted PDFs with custom branding, table of contents, and more.</p>', unsafe_allow_html=True)
    
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
            pass  # Secrets not configured
        
        api_token = st.text_input(
            "GitBook API Token",
            value=default_token,
            type="password",
            help="Your GitBook personal access token. Get it from GitBook settings."
        )
        
        space_id = st.text_input(
            "Space ID",
            value=default_space,
            help="The unique identifier for your GitBook space. Found in the space URL."
        )
        
        org_id = st.text_input(
            "Organization ID (Optional)",
            value=default_org,
            help="Optional: Include organization branding. Found in org URL."
        )
        
        st.divider()
        
        st.header("📄 Quick Actions")
        
        use_gitbook_pdf = st.checkbox(
            "Use GitBook's built-in PDF",
            value=False,
            help="Use GitBook's native PDF export instead of custom generation. Available for Premium/Ultimate plans."
        )
        
        if st.button("🔍 Test Connection", use_container_width=True):
            if api_token and space_id:
                try:
                    api = GitBookAPI(api_token)
                    space = api.get_space(space_id)
                    st.success(f"✅ Connected! Space: {space.get('title', 'Unknown')}")
                except Exception as e:
                    st.error(f"❌ Connection failed: {e}")
            else:
                st.warning("Please enter API token and Space ID")
    
    # Main content tabs
    tabs = st.tabs(["📋 Export Options", "🎨 Styling", "📄 Cover Page", "🔧 Advanced"])
    
    # Store config in session state
    if 'pdf_config' not in st.session_state:
        st.session_state.pdf_config = PDFConfig()
    
    config = st.session_state.pdf_config
    
    # Tab 1: Export Options
    with tabs[0]:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📑 Table of Contents")
            config.include_toc = st.checkbox("Include Table of Contents", value=True)
            if config.include_toc:
                config.toc_depth = st.slider("TOC Depth", min_value=1, max_value=5, value=3)
            
            st.subheader("📊 Content Options")
            config.include_page_descriptions = st.checkbox("Include page descriptions", value=True)
            config.include_hidden_pages = st.checkbox("Include hidden pages", value=False)
            config.code_syntax_highlighting = st.checkbox("Syntax highlighting for code", value=True)
        
        with col2:
            st.subheader("📄 Header & Footer")
            config.include_header = st.checkbox("Include header", value=True)
            if config.include_header:
                config.header_text = st.text_input("Header text", placeholder="Document title will be used if empty")
            
            config.include_footer = st.checkbox("Include footer", value=True)
            if config.include_footer:
                config.footer_text = st.text_input("Footer text", placeholder="e.g., © 2024 Your Company")
            
            config.show_page_numbers = st.checkbox("Show page numbers", value=True)
    
    # Tab 2: Styling
    with tabs[1]:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📐 Page Setup")
            config.page_size = st.selectbox("Page size", ["Letter", "A4"])
            config.base_font_size = st.slider("Base font size", min_value=9, max_value=14, value=11)
        
        with col2:
            st.subheader("🎨 Colors & Fonts")
            config.primary_color = st.color_picker("Primary color", value="#0066cc")
            config.font_family = st.selectbox("Font family", ["Helvetica", "Times-Roman", "Courier"])
    
    # Tab 3: Cover Page
    with tabs[2]:
        config.include_cover = st.checkbox("Include cover page", value=True)
        
        if config.include_cover:
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📝 Cover Content")
                config.cover_title = st.text_input("Title", placeholder="Uses space title if empty")
                config.cover_subtitle = st.text_input("Subtitle", placeholder="Uses space description if empty")
                
                config.show_version = st.checkbox("Show version", value=True)
                if config.show_version:
                    config.version_text = st.text_input("Version", placeholder="e.g., 1.0.0")
                
                config.show_date = st.checkbox("Show date", value=True)
                if config.show_date:
                    config.date_format = st.selectbox(
                        "Date format",
                        ["%B %Y", "%B %d, %Y", "%Y-%m-%d", "%d/%m/%Y"],
                        format_func=lambda x: datetime.now().strftime(x)
                    )
            
            with col2:
                st.subheader("🖼️ Cover Images")
                
                logo_file = st.file_uploader(
                    "Logo image",
                    type=['png', 'jpg', 'jpeg', 'svg'],
                    help="Your company or product logo"
                )
                if logo_file:
                    config.cover_logo = logo_file.getvalue()
                    st.image(logo_file, caption="Logo preview", width=150)
                
                cover_image = st.file_uploader(
                    "Cover image",
                    type=['png', 'jpg', 'jpeg'],
                    help="Main cover artwork or hero image"
                )
                if cover_image:
                    config.cover_image = cover_image.getvalue()
                    st.image(cover_image, caption="Cover image preview", width=300)
    
    # Tab 4: Advanced
    with tabs[3]:
        st.subheader("🔧 Advanced Options")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Header Logo**")
            header_logo_file = st.file_uploader(
                "Upload header logo",
                type=['png', 'jpg', 'jpeg'],
                key="header_logo"
            )
            if header_logo_file:
                config.header_logo = header_logo_file.getvalue()
        
        with col2:
            st.markdown("**Footer Logo**")
            footer_logo_file = st.file_uploader(
                "Upload footer logo",
                type=['png', 'jpg', 'jpeg'],
                key="footer_logo"
            )
            if footer_logo_file:
                config.footer_logo = footer_logo_file.getvalue()
        
        st.divider()
        
        st.markdown("""
        <div class="info-box">
        <strong>💡 Tips:</strong>
        <ul>
            <li>Use PNG format for logos with transparency</li>
            <li>Recommended logo size: 200x100 pixels</li>
            <li>Cover images work best at 1200x600 pixels</li>
        </ul>
        </div>
        """, unsafe_allow_html=True)
    
    # Export section
    st.divider()
    st.header("🚀 Generate PDF")
    
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        if api_token and space_id:
            st.markdown("""
            <div class="success-box">
            ✅ Ready to export! Click the button below to generate your PDF.
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="warning-box">
            ⚠️ Please enter your API token and Space ID in the sidebar to continue.
            </div>
            """, unsafe_allow_html=True)
    
    with col2:
        export_button = st.button(
            "📥 Generate PDF",
            type="primary",
            use_container_width=True,
            disabled=not (api_token and space_id)
        )
    
    with col3:
        if use_gitbook_pdf and api_token and space_id:
            if st.button("📥 Get GitBook PDF", use_container_width=True):
                try:
                    api = GitBookAPI(api_token)
                    result = api.get_pdf_url(space_id)
                    pdf_url = result.get('url')
                    if pdf_url:
                        st.markdown(f"[Download PDF]({pdf_url})")
                    else:
                        st.error("Could not get PDF URL")
                except Exception as e:
                    st.error(f"Error: {e}")
    
    # Generate PDF
    if export_button:
        try:
            with st.spinner("🔄 Fetching content from GitBook..."):
                api = GitBookAPI(api_token)
                
                # Get space info
                space_info = api.get_space(space_id)
                st.info(f"📚 Space: {space_info.get('title', 'Unknown')}")
                
                # Get organization info if provided
                org_info = None
                if org_id:
                    try:
                        org_info = api.get_organization(org_id)
                        st.info(f"🏢 Organization: {org_info.get('title', 'Unknown')}")
                    except:
                        pass
                
                # Get pages
                pages_data = api.get_all_pages(space_id)
                pages = pages_data.get('pages', [])
                st.info(f"📄 Found {len(pages)} top-level pages")
            
            with st.spinner("🔄 Generating PDF..."):
                # Build PDF
                builder = PDFBuilder(config)
                pdf_bytes = builder.build_pdf(api, space_id, space_info, pages, org_info)
                
                # Success message
                st.success("✅ PDF generated successfully!")
                
                # Download button
                filename = f"{space_info.get('title', 'documentation').replace(' ', '_').lower()}.pdf"
                st.download_button(
                    label="📥 Download PDF",
                    data=pdf_bytes,
                    file_name=filename,
                    mime="application/pdf",
                    use_container_width=True
                )
                
                # Show preview info
                st.info(f"📊 PDF size: {len(pdf_bytes) / 1024:.1f} KB")
        
        except Exception as e:
            st.error(f"❌ Error generating PDF: {e}")
            st.exception(e)
    
    # Footer
    st.divider()
    st.markdown("""
    <div style="text-align: center; color: #888; font-size: 0.9rem;">
    GitBook PDF Export Tool v2.0 | Built with Streamlit & ReportLab<br/>
    <a href="https://gitbook.com/docs/developers/gitbook-api" target="_blank">GitBook API Documentation</a>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
