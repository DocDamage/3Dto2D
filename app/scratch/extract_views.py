import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = ROOT / "web" / "index.html"
COMPONENTS_DIR = ROOT / "web" / "components"

def extract_views():
    COMPONENTS_DIR.mkdir(parents=True, exist_ok=True)
    html_content = INDEX_PATH.read_text(encoding="utf-8")
    
    # We want to find all <section class="view" ...> tags and extract them.
    # We can parse the HTML by tracking section open/close tags using stack matching.
    
    view_starts = []
    # Find positions of all <section class="view" id="view-..."> or <section class="view active" id="view-...">
    pattern = re.compile(r'<section\s+[^>]*class=["\'][^"\']*view[^"\']*["\'][^>]*>')
    for match in pattern.finditer(html_content):
        view_starts.append(match.start())
        
    print(f"Found {len(view_starts)} views in index.html.")
    
    # We will extract each view from end to start to avoid shifting indices.
    view_starts.sort(reverse=True)
    
    modified_html = html_content
    
    for start_pos in view_starts:
        # Find the matching </section> tag using a stack
        stack = 1
        pos = start_pos
        
        # Read the start tag to find ID
        tag_match = re.match(r'<section\s+([^>]*)>', html_content[start_pos:])
        if not tag_match:
            continue
            
        attributes = tag_match.group(1)
        id_match = re.search(r'id=["\']([^"\']+)["\']', attributes)
        if not id_match:
            continue
            
        view_id = id_match.group(1)
        print(f"Extracting view: {view_id}")
        
        # Skip the opening tag length to start stack counting
        pos = start_pos + len(tag_match.group(0))
        
        while stack > 0 and pos < len(html_content):
            # Check for next tag
            if html_content[pos] == '<':
                if html_content[pos:pos+9].lower() == '</section':
                    stack -= 1
                    if stack == 0:
                        # Found the end of the section!
                        end_tag_match = re.match(r'</section\s*>', html_content[pos:], re.IGNORECASE)
                        if end_tag_match:
                            pos += len(end_tag_match.group(0))
                        break
                elif html_content[pos:pos+8].lower() == '<section':
                    stack += 1
            pos += 1
            
        # The full block containing opening tag and closing tag is html_content[start_pos:pos]
        view_block = html_content[start_pos:pos]
        
        # Save the view block as a component
        component_name = view_id.replace("view-", "")
        component_path = COMPONENTS_DIR / f"{component_name}.html"
        component_path.write_text(view_block, encoding="utf-8")
        print(f"Saved {component_name}.html to components/")
        
        # Replace the full block in modified_html with a placeholder
        # e.g., <section class="view" id="view-dashboard"></section>
        # Keep active class on view-guide for the initial shell
        active_str = " active" if "active" in tag_match.group(0) else ""
        placeholder = f'<section class="view{active_str}" id="{view_id}"></section>'
        
        modified_html = modified_html[:start_pos] + placeholder + modified_html[pos:]
        
    # Write back the cleaned index.html
    INDEX_PATH.write_text(modified_html, encoding="utf-8")
    print("Successfully componentized index.html!")

if __name__ == "__main__":
    extract_views()
