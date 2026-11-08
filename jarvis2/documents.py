"""Read explicitly selected local documents; never execute their contents."""
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET
def read(path):
    path=Path(path)
    if not path.is_file() or path.stat().st_size>2*1024*1024:raise ValueError('Choose a document up to 2 MB.')
    ext=path.suffix.lower()
    if ext in ('.txt','.md','.csv'):
        text=path.read_text(encoding='utf-8-sig',errors='replace')
    elif ext=='.docx':
        with zipfile.ZipFile(path) as archive:
            info=archive.getinfo('word/document.xml')
            if info.file_size>8*1024*1024:raise ValueError('The document text is too large.')
            root=ET.fromstring(archive.read(info))
        text='\n'.join(''.join(node.itertext()) for node in root.iter() if node.tag.endswith('}p'))
    elif ext=='.pdf':
        try:from pypdf import PdfReader
        except ImportError:raise ValueError('PDF reading is unavailable; choose a text or Word document.')
        pdf=PdfReader(path)
        if pdf.is_encrypted:raise ValueError('Encrypted documents are not read.')
        text='\n'.join(page.extract_text() or '' for page in list(pdf.pages)[:5])
    else:raise ValueError('Choose a text, Markdown, CSV, Word or PDF document.')
    return {'name':path.name,'text':text[:12000],'truncated':len(text)>12000 or (ext=='.pdf' and len(pdf.pages)>5)}
