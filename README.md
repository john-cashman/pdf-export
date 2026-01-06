# GitBook PDF Export Tool - Enhanced Edition

A powerful Streamlit application for exporting GitBook documentation to professionally formatted PDFs with extensive customization options.

## Features

### 🎨 Cover Page Options
- **Custom branding**: Upload your company logo
- **Hero images**: Add cover artwork
- **Title & subtitle**: Override space title or use GitBook defaults
- **Version display**: Show document version
- **Date formatting**: Multiple date format options (Month Year, full date, ISO, etc.)
- **Organization attribution**: Automatically include org name

### 📑 Table of Contents
- **Configurable depth**: 1-5 levels deep
- **Clickable links**: Navigate to any section (in supported PDF readers)
- **Automatic generation**: Built from your GitBook page structure

### 📄 Headers & Footers
- **Custom header text**: Document title or custom text
- **Logo support**: Add logos to header/footer
- **Page numbers**: Automatic page numbering
- **Custom footer text**: Copyright, company info, etc.

### 🎨 Styling
- **Page sizes**: Letter or A4
- **Custom colors**: Pick your primary brand color
- **Font options**: Helvetica, Times-Roman, Courier
- **Adjustable font sizes**: Base font size slider

### 📊 Content Options
- **Page descriptions**: Include/exclude page descriptions
- **Hidden pages**: Optionally include hidden content
- **Code syntax highlighting**: Formatted code blocks
- **Table formatting**: Styled tables with headers
- **Image placeholders**: References for embedded images

## Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Quick Start

1. **Clone or download this repository**:
```bash
git clone <repository-url>
cd gitbook_pdf_export
```

2. **Create a virtual environment** (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

4. **Run the application**:
```bash
streamlit run app.py
```

5. **Open your browser** to `http://localhost:8501`

## Configuration

### Getting Your GitBook API Token

1. Log into your GitBook account
2. Go to **Settings** → **Personal access tokens**
3. Click **Create token**
4. Copy the token (it won't be shown again!)

### Finding Your Space ID

The Space ID is in your GitBook URL:
```
https://app.gitbook.com/o/{ORG_ID}/s/{SPACE_ID}/
                                    ^^^^^^^^^^^
```

Or find it via:
1. Open your space in GitBook
2. Click the **⋮** menu → **Settings**
3. Scroll to find the Space ID

### Finding Your Organization ID (Optional)

The Organization ID is in your GitBook URL:
```
https://app.gitbook.com/o/{ORG_ID}/s/{SPACE_ID}/
                          ^^^^^^^^
```

## API Endpoints Used

This tool uses the following GitBook API endpoints:

| Endpoint | Purpose |
|----------|---------|
| `GET /v1/spaces/{spaceId}` | Get space information |
| `GET /v1/spaces/{spaceId}/content/pages` | List all pages |
| `GET /v1/spaces/{spaceId}/content/page/{pageId}` | Get page content (markdown) |
| `GET /v1/spaces/{spaceId}/pdf` | Get GitBook's native PDF URL |
| `GET /v1/orgs/{organizationId}` | Get organization info |

## Usage Guide

### Basic Export

1. Enter your **API Token** in the sidebar
2. Enter your **Space ID**
3. (Optional) Enter **Organization ID** for branding
4. Click **Test Connection** to verify
5. Click **Generate PDF**

### Customizing Your PDF

#### Cover Page Tab
- **Title**: Custom title (leave blank to use GitBook title)
- **Subtitle**: Description or tagline
- **Logo**: Upload PNG/JPG (recommended: 200x100px)
- **Cover Image**: Hero image (recommended: 1200x600px)
- **Version**: e.g., "v2.1.0"
- **Date**: Choose format from dropdown

#### Export Options Tab
- **TOC**: Enable/disable, set depth (1-5 levels)
- **Content**: Include descriptions, hidden pages
- **Headers/Footers**: Text and page numbers

#### Styling Tab
- **Page Size**: Letter (US) or A4 (International)
- **Colors**: Pick your brand color
- **Fonts**: Choose base font family
- **Size**: Adjust base font size

### Using GitBook's Native PDF

For Premium/Ultimate GitBook plans, you can also use GitBook's built-in PDF:

1. Check **"Use GitBook's built-in PDF"** in the sidebar
2. Click **"Get GitBook PDF"**
3. Follow the link to download

## Comparison with Existing Tools

### vs. gitbook-pdf-export (FreeBSD-Ask)

| Feature | This Tool | gitbook-pdf-export |
|---------|-----------|-------------------|
| UI | Streamlit web interface | Command line |
| Cover Page | ✅ Full customization | ❌ None |
| Table of Contents | ✅ Configurable depth | ❌ Basic |
| Headers/Footers | ✅ Custom text + logos | ❌ Limited |
| Branding | ✅ Logos, colors, fonts | ❌ None |
| API Integration | ✅ Direct GitBook API | ❌ Local markdown files |
| Installation | pip install | Manual setup |
| Platform | Cross-platform | FreeBSD/Windows focused |

### vs. gitbook2pdf

| Feature | This Tool | gitbook2pdf |
|---------|-----------|-------------|
| Input Source | GitBook API | Public GitBook URLs |
| Authentication | API token (private spaces) | None (public only) |
| Cover Page | ✅ Full customization | ❌ None |
| TOC | ✅ Multi-level | ✅ Basic |
| Branding | ✅ Full | ❌ CSS only |

## Troubleshooting

### "Invalid API token" Error
- Ensure your token hasn't expired
- Check for extra spaces when pasting
- Verify token permissions

### "Resource not found" Error
- Verify the Space ID is correct
- Check you have access to the space
- Ensure the space exists and isn't deleted

### "Access denied" Error
- Your API token may not have permission to this space
- Ask the space admin to grant access

### PDF Generation Fails
- Very large spaces may timeout
- Try exporting specific sections
- Check for unusual characters in content

### Images Not Appearing
- Images are currently shown as placeholders
- Full image embedding requires additional API calls
- Consider using GitBook's native PDF for full image support

## Development

### Project Structure
```
gitbook_pdf_export/
├── app.py              # Main Streamlit application
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

### Running in Development Mode
```bash
streamlit run app.py --server.runOnSave true
```

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Roadmap / Future Improvements

- [ ] **Image embedding**: Fetch and embed GitBook images
- [ ] **Async processing**: Handle large spaces better
- [ ] **Custom templates**: User-uploadable PDF templates
- [ ] **Batch export**: Export multiple spaces at once
- [ ] **Scheduled exports**: Automated periodic exports
- [ ] **EPUB support**: Alternative format export
- [ ] **Multi-language**: Support for translated spaces
- [ ] **Custom fonts**: Upload custom TTF fonts
- [ ] **Watermarks**: Add custom watermarks
- [ ] **Page selection**: Export specific pages only

## License

MIT License - see LICENSE file for details.

## Credits

- Built with [Streamlit](https://streamlit.io/)
- PDF generation by [ReportLab](https://www.reportlab.com/)
- Markdown parsing by [python-markdown](https://python-markdown.github.io/)
- Inspired by [gitbook-pdf-export](https://github.com/FreeBSD-Ask/gitbook-pdf-export)

## Support

For issues and feature requests, please open a GitHub issue.

---

Made with ❤️ for the GitBook community
